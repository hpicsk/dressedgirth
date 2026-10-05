"""Every number and claim that paper/main.tex prints, checked against the result tables in results/.

Run `python -m pytest test_assertions.py`. The checks read results/ and paper/, never the corpus; the last one also
fetches the published repository. A failure names the manuscript label whose sentence it contradicts.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "code"))
import fig_rig  # noqa: E402
import make_params as mp  # noqa: E402
import read_560 as r5  # noqa: E402

PAPER = os.path.join(ROOT, "paper")
MAIN = os.path.join(PAPER, "main.tex")
SUPPLEMENT = os.path.join(PAPER, "supplement.tex")
PARAM_FILES = (os.path.join(PAPER, "params.tex"), os.path.join(PAPER, "params_manual.tex"))
NEWCOMMAND = re.compile(r"\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}")

def text(path):
    with open(path) as fh:
        return fh.read()

def macros(path):
    """{name: value} of a parameter file's \\newcommand lines."""
    return {m.group(1): m.group(2) for m in map(NEWCOMMAND.match, text(path).splitlines()) if m}

def body(path=MAIN):
    """A document without its comments."""
    return re.sub(r"(?<!\\)%.*", "", text(path))

def results():
    return mp.load("reduction.json")

def primary():
    res = results()
    return res["configurations"][res["primary"]]

def own(block, key, k=None):
    return mp.own(block, key, k)

# The parameter files and the generated tables

def test_params_regenerate():
    assert text(PARAM_FILES[0]) == mp.render(), "paper/params.tex differs from code/make_params.py's output; rerun it"

def test_tables_regenerate():
    for name, fn in mp.TABLES.items():
        assert text(os.path.join(PAPER, name)) == getattr(mp, fn)(), (
            f"paper/{name} differs from code/make_params.py's output; rerun it")

def test_figure_regenerates():
    with open(fig_rig.OUT, "rb") as fh:
        assert fh.read() == fig_rig.figure(), "paper/fig_rig.pdf differs from code/fig_rig.py's output; rerun it"

def test_every_macro_used():
    used = set(re.findall(r"\\([A-Za-z]+)", body()))
    unused = sorted(name for path in PARAM_FILES for name in macros(path) if name not in used)
    assert not unused, f"macros that main.tex never prints: {unused}"

def test_every_generated_file_is_read():
    read = set(re.findall(r"\\(?:input|includegraphics)(?:\[[^\]]*\])?\{([^}]+)\}", body() + body(SUPPLEMENT)))
    written = [os.path.splitext(name)[0] for name in mp.TABLES] + [os.path.splitext(os.path.basename(fig_rig.OUT))[0]]
    unread = [name for name in written if name not in read]
    assert not unread, f"generated files that neither main.tex nor supplement.tex reads: {unread}"

def populations():
    """{macro: population} from the parameter files' declarations; the manual file's numbers count none."""
    population, out = None, {}
    for line in text(PARAM_FILES[0]).splitlines():
        if line.startswith("% Population: "):
            population = line[len("% Population: "):]
        m = NEWCOMMAND.match(line)
        if m:
            note = re.search(r"\[population: ([^\]]+)\]", line)
            out[m.group(1)] = note.group(1) if note else population
    return {**out, **{name: "none" for name in macros(PARAM_FILES[1])}}

def test_population_crossings_are_recorded():
    pop = populations()
    recorded = [set(m.group(1).split()) for m in re.finditer(r"^% Crossing ([A-Za-z ]+):", text(PARAM_FILES[0]), re.M)]
    crossed = []
    for path in (MAIN, SUPPLEMENT):
        for sentence in re.split(r"(?<=\.)\s+(?=[A-Z\\(])", re.sub(r"\s+", " ", body(path))):
            counted = {name for name in re.findall(r"\\([A-Za-z]+)", sentence) if pop.get(name, "none") != "none"}
            if len({pop[name] for name in counted}) > 1 and not any(counted <= names for names in recorded):
                crossed.append(sorted(counted))
    assert not crossed, (
        f"sentences that print numbers of two populations with no '% Crossing' line in params.tex: {crossed}")

def test_every_macro_has_a_population():
    population, missing = None, []
    for line in text(PARAM_FILES[0]).splitlines():
        if line.startswith("% Population: "):
            population = line[len("% Population: "):]
        elif line.startswith("% ") and not line.startswith("% Population"):
            population = None
        m = NEWCOMMAND.match(line)
        if m:
            note = re.search(r"\[population: ([^\]]+)\]", line)
            if (note.group(1) if note else population) not in mp.POPULATIONS:
                missing.append(m.group(1))
    assert not missing, f"macros without a declared population: {missing}"
    assert "% Population: none" in text(PARAM_FILES[1]), "params_manual.tex declares no population"

# sec:data

def test_subjects_enter_every_model():
    for key, block in results()["configurations"].items():
        by_outfit = block["subjects_with_features_by_outfit"]
        assert block["n_subjects"] <= min(by_outfit.values()), (
            f"sec:models claims that the subjects with widths in all six outfits are those on which 'Every model "
            f"is fitted and scored', but {key} scores {block['n_subjects']} subjects against at most "
            f"{min(by_outfit.values())} with features")
    shod = {b["n_subjects"] for b in results()["configurations"].values() if b["scale_rule"] != "barefoot_always"}
    assert shod == {primary()["n_subjects"]}, (
        f"sec:models claims '{primary()['n_subjects']} subjects have widths in all six outfits under each scale rule "
        f"that adds a heel height', as tab:sensitivity prints; the two rules score {shod}")

# sec:rig

def test_pillar_order():
    rig = mp.load("rig.json")["leg_offset_by_pillar"]
    assert rig["A"] < 0, (
        f"sec:rig claims 'The leg offset is negative in pillar A, which means that the subject's right leg appears on "
        f"the left of the image'; offset A {rig['A']:.3f}")
    ratio = mp.load("rig.json")["leg_offset_ratio_to_A"]
    assert all(ratio[p] > 0 for p in ("B", "H")) and all(ratio[p] < 0 for p in ("D", "E", "F")), (
        f"sec:rig claims 'The measured ratio is positive in pillars B and H and negative in pillars D, E and F'; "
        f"ratios {ratio}")
    assert min(abs(ratio[p]) for p in r5.DIAGONAL) > max(abs(ratio[p]) for p in ("C", "G")), (
        f"sec:rig places the diagonal pillars at ±45° and ±135° and C and G at ±90°; ratios {ratio}")
    assert abs(ratio["E"] + 1) < 0.1, (
        f"sec:rig places pillar E at 180°, where cos θ is −1, and fig:rig prints its ratio; ratio E {ratio['E']:.3f}")

def test_subjects_taller_in_own_outfits():
    ratios = mp.load("rig.json")["height_px_ratio_to_suit"]
    assert all(v["median"] > 1 for v in ratios.values()), (
        f"sec:rig claims that the median of the height in pixels in each own outfit divided by the height in pixels in "
        f"the measurement suit 'exceeds 1'; median ratios {ratios}")

def test_shoes_rise_less_than_the_heel():
    rig = mp.load("rig.json")
    gain = max(100 * (v["median"] - 1) for v in rig["height_px_ratio_to_suit"].values())
    heel = rig["heel_share_of_stature_pct"]["median"]
    assert gain < heel, (
        f"sec:rig claims that 'the shoes raised the subjects less than the recorded heel height', comparing the rise "
        f"in the height in pixels with the recorded heel height's median share of stature; largest rise {gain:.2f}%, "
        f"heel share {heel:.2f}%")

# sec:features

def test_torso_polygon_in_the_side_pillars():
    share = {p: v["with_torso"] / v["images"] for p, v in mp.load("rig.json")["torso_by_pillar"].items()}
    side, other = max(share[p] for p in ("C", "G")), min(v for p, v in share.items() if p not in ("C", "G"))
    assert side < 0.05 < 0.95 < other, (
        f"sec:intro claims that 'The torso's polygon, on which widths can be measured, rarely appears in photographs "
        f"taken from the sides', and sec:features that 'the torso polygon gives widths but no depths'; the torso "
        f"shares are {share}")

def test_torso_polygon_mostly_misses_the_hip():
    hip = {g: v["hip_level_inside_torso"] / v["images"] for g, v in mp.load("rig.json")["hip_level_in_pillar_A"].items()}
    assert max(hip.values()) < 0.5, (
        f"sec:intro claims that the torso's polygon 'mostly does not reach the hip', and sec:features that the "
        f"torso polygon spans the level of the hip height in a minority of pillar A's standing photographs; the shares "
        f"whose torso polygon spans the hip level are {hip}")

def test_no_height_for_the_chest_girth():
    header = mp.load("rig.json")["tape_header"]
    assert "젖가슴둘레" in header and not any("젖꼭지" in c for c in header), (
        f"sec:features claims that the records 'give no height for the bust points through which the chest girth "
        f"passes', and sec:intro that 'the dataset gives no height at which to locate the chest'; the record's columns "
        f"are {header}")

# sec:results

def test_widths_lower_the_error_in_every_outfit():
    pg = primary()["per_outfit"]
    low = {g: pg[g]["reduction_ci95"][0] for g in r5.OUTFITS}
    assert all(v > 0 for v in low.values()), (
        f"sec:results claims 'In the measurement suit, the widths lower the MAPE' and 'The 95% confidence interval of "
        f"each own outfit's reduction lies above zero', and the abstract and sec:intro that the widths lowered the "
        f"error in each own outfit; the lower bounds are {low}")

def test_shortfall_holds_in_every_configuration():
    starts = {k: min(own(b, "shortfall_ci95", 0)) for k, b in results()["configurations"].items()}
    assert all(v > 0 for v in starts.values()), (
        f"sec:results claims 'The 95% confidence interval of each outfit's shortfall lies above zero', and that 'In "
        f"the five other variants, the 95% confidence interval of every own outfit's shortfall also lies above zero', "
        f"and the abstract that 'The suit's reduction exceeded each own outfit's under each assumption about shoe "
        f"heels'; the lowest lower bounds are {starts}")

def test_own_reduction_depends_on_the_variant():
    above = {k: sum(lo > 0 for lo in own(b, "reduction_ci95", 0)) for k, b in results()["configurations"].items()}
    girth = {k: v for k, v in above.items() if results()["configurations"][k]["features"] == "girth"}
    assert girth and all(v == 0 for v in girth.values()) and above[results()["primary"]] == len(r5.OWN_CLOTHES), (
        f"sec:results claims 'The 95% confidence interval of each own outfit's reduction lies above zero' under the "
        f"main variant, and that 'the 95% confidence interval of every own outfit's reduction includes zero under each "
        f"scale rule when the ellipse girth replaces the widths'; own outfits above zero per variant: {above}")

def test_own_clothes_remove_most_of_the_reduction():
    share = {k: min(own(b, "shortfall_pp")) / b["per_outfit"][r5.SUIT]["reduction_pp"]
             for k, b in results()["configurations"].items()}
    assert all(v > 0.5 for v in share.values()), (
        f"sec:results claims that 'the subjects' own clothes remove most of the suit's reduction' in every variant of "
        f"the analysis; the smallest shortfall as a share of the suit's reduction is {share}")

def test_reduction_bound_over_every_configuration():
    bound = float(macros(PARAM_FILES[0])["redOwnMaxAll"])
    blocks = results()["configurations"].values()
    seen = max(max(own(b, "reduction_pp") + own(b, "reduction_pp_range_seeds_1_9", 1)) for b in blocks)
    assert round(seen, 2) <= bound, (
        f"sec:conclusion claims that the widths lowered the error 'by at most {bound} percentage points in any variant "
        f"of the analysis under any fold split', which Supplementary Table S1 prints; the largest own-outfit reduction is {seen:.4f}")

def test_self_report_shortfall_in_every_draw():
    draws = results()["self_report"]["draws"]
    lows = [min(own(d, "shortfall_ci95", 0)) for d in draws]
    assert len(draws) == mp.red.N_DRAWS and min(lows) > 0, (
        f"sec:results claims that with the self-report errors added to stature and weight, 'In every draw, the 95% "
        f"confidence interval of each own outfit's shortfall lies above zero'; the lowest lower bound per draw is "
        f"{lows}")

def test_self_report_rescales_with_the_main_variant():
    sr, prim = results()["self_report"], primary()
    assert sr["n_subjects"] == prim["n_subjects"], (
        f"sec:models claims that the self-report analysis repeats 'the main variant's models', on its "
        f"{prim['n_subjects']} subjects; it scores {sr['n_subjects']}")

def test_clothes_widen_both_widths():
    growth = own(primary(), "width_growth_cm_median")
    assert all(v > 0 for pair in growth for v in pair), (
        f"sec:results claims 'The subjects' own clothes widen both waist widths in every outfit'; median growths "
        f"{growth}")

def test_growth_differs_between_subjects():
    iqr = [q[k][1] - q[k][0] for q in own(primary(), "width_growth_cm_iqr") for k in (0, 1)]
    assert min(iqr) > 1, (
        f"sec:results claims that the interquartile range of the growth over subjects is at least "
        f"{macros(PARAM_FILES[0])['growthIqrMin']} cm in every outfit and for both widths, 'so the growth differs "
        f"between subjects'; the ranges are {iqr}")

def test_weight_and_widths_below_the_baseline_in_own_clothes():
    starts = own(primary(), "weight_widths_minus_baseline_ci95", 0)
    assert all(v > 0 for v in starts), (
        f"sec:intro claims that 'A regression on weight and the own outfits' two widths, which takes the diagonal "
        f"width in place of Feng et al.'s depth, predicted the girth less "
        f"accurately than the regression on stature, weight, sex and age', as do the abstract and sec:conclusion; "
        f"the interval starts are {starts}")

def test_weight_and_widths_undecided_in_the_suit():
    lo, hi = primary()["per_outfit"][r5.SUIT]["weight_widths_minus_baseline_ci95"]
    assert lo < 0 < hi, (
        f"sec:results claims that 'in the measurement suit the data do not show which of the two models is more "
        f"accurate'; the 95% interval of the weight-and-widths model's MAPE minus the baseline model's is {lo:.3f} to "
        f"{hi:.3f}")

WORDS = {"two": 2, "three": 3, "five": 5, "six": 6}

def test_counts_in_words():
    res = results()["configurations"]
    spelled = {"six outfits": len(r5.OUTFITS), "five outfits": len(r5.OWN_CLOTHES),
               "three scale rules": len(r5.SCALE_RULES), "two forms of the waist input": len(mp.red.FEATURE_SETS),
               "six variants of the analysis": len(res), "five other variants": len(res) - 1,
               "two widths": len(own(primary(), "width_growth_cm_median")[0])}
    prose = re.sub(r"\s+", " ", body())
    wrong = {p: n for p, n in spelled.items() if p not in prose or WORDS[p.split()[0]] != n}
    assert not wrong, (
        f"sec:data, sec:features and sec:results spell out these counts, which the code fixes at {wrong}, or no "
        f"longer print them")

# sec:models

def test_scikit_learn_version():
    pinned = re.search(r"^scikit-learn==(\S+)$", text(os.path.join(ROOT, "requirements.txt")), re.M).group(1)
    printed = macros(PARAM_FILES[1])["sklearnVersion"]
    assert printed == pinned, (
        f"sec:models claims 'scikit-learn (version {printed})', but requirements.txt pins {pinned}")

def test_numpy_version():
    pinned = re.search(r"^numpy==(\S+)$", text(os.path.join(ROOT, "requirements.txt")), re.M).group(1)
    printed = macros(PARAM_FILES[1])["numpyVersion"]
    assert printed == pinned, f"sec:models claims 'NumPy (version {printed})', but requirements.txt pins {pinned}"

# The release

RELEASE = "https://github.com/hpicsk/dressedgirth"  # the repository that the data availability statement names
UNRELEASED = {"paper/title_page.tex"}  # the authors' contact details, which the journal receives apart from the code

def tree(rev):
    """{path: (mode, type, object id)} of every file in a commit's tree."""
    out = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", rev], capture_output=True, text=True, check=True).stdout
    return {path: tuple(meta.split()) for meta, path in (line.split("\t", 1) for line in out.splitlines())}

def test_release_is_the_tree_of_main():
    subprocess.run(["git", "-C", ROOT, "fetch", "-q", RELEASE, "main"], check=True)
    released = tree("FETCH_HEAD")
    expected = {p: v for p, v in tree("HEAD").items() if p not in UNRELEASED}
    differ = sorted(p for p in released.keys() | expected.keys() if released.get(p) != expected.get(p))
    assert not differ, (
        f"The data availability statement says that 'The code that computes every number in this article from the "
        f"dataset's polygons and tape records is available at {RELEASE}', but its main branch differs from this tree "
        f"in {differ}")
