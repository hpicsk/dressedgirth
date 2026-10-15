"""Every number and claim that paper/main.tex prints, checked against the result tables in results/.

Run `python -m pytest test_assertions.py`. The checks read results/ and paper/, never the corpus; the last one also
fetches the published repository. A failure names the manuscript label whose sentence it contradicts.
"""
import math
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
    used = set(re.findall(r"\\([A-Za-z]+)", body() + body(SUPPLEMENT)))
    unused = sorted(name for path in PARAM_FILES for name in macros(path) if name not in used)
    assert not unused, f"macros that neither main.tex nor supplement.tex prints: {unused}"

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
            f"sec:models claims that 'Under each scale rule, the models use only the subjects who have widths in all "
            f"six outfits', but {key} scores {block['n_subjects']} subjects against at most "
            f"{min(by_outfit.values())} with features")
    shod = {b["n_subjects"] for b in results()["configurations"].values() if b["scale_rule"] != "barefoot_always"}
    assert shod == {primary()["n_subjects"]}, (
        f"sec:models claims '{primary()['n_subjects']} subjects have widths in all six outfits under each scale rule "
        f"that adds a heel height', as tab:sensitivity prints; the two rules score {shod}")

# sec:rig

def test_pillar_order():
    rig = mp.load("rig.json")["leg_offset_by_pillar"]
    assert rig["A"] < 0, (
        f"the supplement's sec:rigangles claims 'The leg offset is negative in pillar A, which means that the subject's "
        f"right leg appears on the left of the image'; offset A {rig['A']:.3f}")
    ratio = mp.load("rig.json")["leg_offset_ratio_to_A"]
    assert all(ratio[p] > 0 for p in ("B", "H")) and all(ratio[p] < 0 for p in ("D", "E", "F")), (
        f"sec:rig places 'pillars B and H at ±45° from the front, pillars D and F at ±135°' and 'pillar E at 180°', "
        f"which the signs of the measured ratios show; ratios {ratio}")
    assert min(abs(ratio[p]) for p in r5.DIAGONAL) > max(abs(ratio[p]) for p in ("C", "G")), (
        f"sec:rig places the diagonal pillars at ±45° and ±135° and C and G at ±90°; ratios {ratio}")
    assert abs(ratio["E"] + 1) < 0.1, (
        f"sec:rig places pillar E at 180°, where cos θ is −1, and fig:rig prints its ratio; ratio E {ratio['E']:.3f}")
    c = math.cos(math.radians(45))
    expected = {"A": 1, "B": c, "H": c, "C": 0, "G": 0, "D": -c, "F": -c, "E": -1}
    nearest = {p: min(set(expected.values()), key=lambda v: abs(ratio[p] - v)) for p in expected}
    assert nearest == expected, (
        f"the supplement's sec:rigangles claims that Figure 1(a) prints 'each pillar's measured ratio, which lies "
        f"nearest the ratio for the angle at which the main text places the pillar'; ratios {ratio}")
    axis = {p for p, v in nearest.items() if abs(v) == 1}
    diagonal = {p for p, v in nearest.items() if abs(v) == c}
    assert (axis, diagonal) == (set(r5.FRONT_BACK), set(r5.DIAGONAL)), (
        f"sec:features claims that '$a$ is the mean of the half-widths that pillars A and E give from the front and "
        f"from behind, and $m$ the mean of the half-widths that the four diagonal pillars give'; the measured ratios "
        f"place {sorted(axis)} on the front-back axis and {sorted(diagonal)} on the diagonals, whereas the code averages "
        f"{r5.FRONT_BACK} and {r5.DIAGONAL}")

def test_subjects_taller_in_own_outfits():
    ratios = mp.load("rig.json")["height_px_ratio_to_suit"]
    assert all(v["median"] > 1 for v in ratios.values()), (
        f"sec:rig claims that over pairs of photographs from one camera 'a subject's height in pixels rises from the "
        f"measurement suit to an own outfit' in median in each of the five outfits; median ratios {ratios}")

def test_shoes_rise_less_than_the_heel():
    rig = mp.load("rig.json")
    gain = max(100 * (v["median"] - 1) for v in rig["height_px_ratio_to_suit"].values())
    heel = rig["heel_share_of_stature_pct"]["median"]
    assert gain < heel, (
        f"sec:rig claims 'although the shoes raised the subjects less than the recorded heel height', comparing "
        f"the rise in the height in pixels with the recorded heel height's median share of stature; largest rise "
        f"{gain:.2f}%, heel share {heel:.2f}%")

# sec:features

def test_torso_polygon_in_the_side_pillars():
    share = {p: v["with_torso"] / v["images"] for p, v in mp.load("rig.json")["torso_by_pillar"].items()}
    side, other = max(share[p] for p in ("C", "G")), min(v for p, v in share.items() if p not in ("C", "G"))
    assert side < 0.05 < 0.95 < other, (
        f"sec:features claims that the labelers drew the torso in at most a small share of pillar C's and pillar G's "
        f"standing photographs, 'so the torso polygon gives widths but no depths', and sec:intro that the torso's "
        f"polygon 'is missing from almost every photograph taken from the subject's sides'; the torso "
        f"shares are {share}")

def test_pillar_e_rarely_gives_a_half_width():
    by = mp.load("rig.json")["torso_by_pillar"]
    e, a = by["E"]["with_head_torso_foot"], by["A"]["with_head_torso_foot"]
    assert e < 0.05 * a, (
        f"sec:features claims 'Pillar E gives a half-width in only {e} of its standing "
        f"photographs that show the torso, because the others lack the head or a foot, so $a$ rests almost entirely "
        f"on pillar A'; pillar A gives {a}")

def test_torso_polygon_mostly_misses_the_hip():
    hip = {g: v["hip_level_inside_torso"] / v["images"] for g, v in mp.load("rig.json")["hip_level_in_pillar_A"].items()}
    assert max(hip.values()) < 0.5, (
        f"sec:features claims that the torso polygon spans the level of the hip height in a minority of pillar A's "
        f"standing photographs, and sec:intro that it 'In most photographs taken from the front, the torso's "
        f"polygon does not span the hip's level'; the shares whose torso polygon spans the hip level are {hip}")

def test_no_height_for_the_chest_girth():
    header = mp.load("rig.json")["tape_header"]
    assert "젖가슴둘레" in header and not any("젖꼭지" in c for c in header), (
        f"sec:features claims that the records 'give no height for the bust points through which the chest girth "
        f"passes'; the record's columns are {header}")

# sec:results

def test_suit_reduction_above_zero_and_own_reductions_include_zero():
    pg = primary()["per_outfit"]
    suit = pg[r5.SUIT]["reduction_ci95"]
    own_ci = {g: pg[g]["reduction_ci95"] for g in r5.OWN_CLOTHES}
    assert suit[0] > 0 and all(lo <= 0 <= hi for lo, hi in own_ci.values()), (
        f"sec:results claims 'The 95% confidence interval of the suit's reduction lies above zero, whereas the "
        f"interval of each own outfit's reduction in MAPE includes zero', as do the abstract, sec:intro and "
        f"sec:conclusion; the suit's interval is {suit} and the own outfits' are {own_ci}")

def test_shortfall_holds_in_every_configuration():
    starts = {k: min(own(b, "shortfall_ci95", 0)) for k, b in results()["configurations"].items()}
    assert all(v > 0 for v in starts.values()), (
        f"sec:results claims 'The 95% confidence interval of each own outfit's shortfall lies above zero', and that "
        f"'In the five other variants, the 95% confidence interval of every own outfit's shortfall also lies above "
        f"zero', and the abstract that 'The suit's reduction exceeded each own outfit's reduction, also when the "
        f"widths entered the regression as the girth of an ellipse fitted to them and under each rule that we tested "
        f"for converting the widths from pixels to centimeters'; the lowest lower bounds are {starts}")

def test_no_own_reduction_above_zero_in_any_variant():
    configs = results()["configurations"]
    above = {k: [g for g in r5.OWN_CLOTHES if b["per_outfit"][g]["reduction_ci95"][0] > 0] for k, b in configs.items()}
    assert not any(above.values()), (
        f"sec:results claims 'The interval of each own outfit's reduction in MAPE includes zero in every variant'; "
        f"own outfits whose interval lies above zero: {above}")

def test_own_clothes_remove_most_of_the_reduction():
    share = {k: min(own(b, "shortfall_pp")) / b["per_outfit"][r5.SUIT]["reduction_pp"]
             for k, b in results()["configurations"].items()}
    assert all(v > 0.5 for v in share.values()), (
        f"sec:results claims that 'the own outfits remove most of the suit's reduction' and that in the five other "
        f"variants 'every own outfit also removes most of the suit's reduction'; the smallest shortfall as a share of "
        f"the suit's reduction is {share}")

def test_self_report_shortfall_in_every_draw():
    draws = results()["self_report"]["draws"]
    lows = [min(own(d, "shortfall_ci95", 0)) for d in draws]
    reds = [min(own(d, "reduction_ci95", 0)) for d in draws]
    assert len(draws) == mp.red.N_DRAWS and min(lows) > 0 and min(reds) > 0, (
        f"the supplement's sec:selfreport claims, over {mp.red.N_DRAWS} random draws, that 'With the errors added, the "
        f"95% confidence interval of each own outfit's reduction and that of its shortfall lie above zero in every "
        f"draw', and sec:results that, with those errors, 'Each own outfit's interval then lies above zero'; the lowest lower bounds per draw are {reds} and {lows}")

def test_self_report_rescales_with_the_main_variant():
    sr, prim = results()["self_report"], primary()
    assert sr["n_subjects"] == prim["n_subjects"], (
        f"the supplement's sec:selfreport claims that the self-report analysis repeats 'the main variant's baseline "
        f"and width models', on its {prim['n_subjects']} subjects; it scores {sr['n_subjects']}")

def test_clothes_widen_both_widths():
    growth = own(primary(), "width_growth_cm_median")
    assert all(v > 0 for pair in growth for v in pair), (
        f"sec:results claims that 'The growth has a positive median over subjects for both widths in every own "
        f"outfit', the growth being the outfit's width minus the suit's width; median growths {growth}")

def test_growth_differs_between_subjects():
    iqr = [q[k][1] - q[k][0] for q in own(primary(), "width_growth_cm_iqr") for k in (0, 1)]
    assert min(iqr) > 1, (
        f"sec:results claims that the interquartile range of the growth over subjects is at least "
        f"{macros(PARAM_FILES[0])['growthIqrMin']} cm in every outfit and for both widths, 'so the part of the growth "
        f"that differs between subjects adds to the error'; the ranges are {iqr}")

WORDS = {"one": 1, "two": 2, "three": 3, "five": 5, "six": 6}

def test_counts_in_words():
    res = results()["configurations"]
    spelled = {"six outfits": len(r5.OUTFITS), "five outfits": len(r5.OWN_CLOTHES),
               "three scale rules": len(r5.SCALE_RULES), "two forms of the waist input": len(mp.red.FEATURE_SETS),
               "six variants of the analysis": len(res), "five other variants": len(res) - 1,
               "two widths": len(own(primary(), "width_growth_cm_median")[0])}
    seasons = [mp.OUTFIT_NAMES[g].rsplit(" ", 1)[0] for g in r5.OWN_CLOTHES]
    spelled.update({"two for spring or autumn": seasons.count("Spring/autumn"), "two for summer": seasons.count("Summer"),
                    "one for winter": seasons.count("Winter")})
    prose = re.sub(r"\s+", " ", body())
    wrong = {p: n for p, n in spelled.items() if p not in prose or WORDS[p.split()[0]] != n}
    assert not wrong, (
        f"sec:data, sec:features and sec:results spell out these counts, which the code fixes at {wrong}, or no "
        f"longer print them")

def test_primary_rows_in_words():
    rows = mp.sensitivity().split("\\midrule\n")[1].split("\n\\bottomrule")[0].splitlines()
    heel = [row.split(" & ")[1] for row in rows]
    primary = mp.RULE_NAMES[mp.red.PRIMARY_RULE]
    n = WORDS["two"]
    assert heel[:n] == [primary] * n and heel.count(primary) == n and (
        "the top two rows" in re.sub(r"\s+", " ", body(SUPPLEMENT))), (
        f"tab:sensitivity's caption claims that the primary rule's rows are 'the top two rows'; the table's heel column "
        f"reads {heel}")

# sec:models

def test_scikit_learn_version():
    pinned = re.search(r"^scikit-learn==(\S+)$", text(os.path.join(ROOT, "requirements.txt")), re.M).group(1)
    printed = macros(PARAM_FILES[1])["sklearnVersion"]
    assert printed == pinned, (
        f"sec:models claims 'the scikit-learn library (version {printed})', but requirements.txt pins {pinned}")

def test_numpy_version():
    pinned = re.search(r"^numpy==(\S+)$", text(os.path.join(ROOT, "requirements.txt")), re.M).group(1)
    printed = macros(PARAM_FILES[1])["numpyVersion"]
    assert printed == pinned, f"sec:models claims 'NumPy (version {printed})', but requirements.txt pins {pinned}"

# The release

RELEASE = "https://github.com/hpicsk/dressedgirth"  # the repository that the data availability statement names
# The files that name the authors, which the public tree leaves out while the journal's review is anonymized. The title
# page also holds the authors' contact details, which the journal receives apart from the code.
UNRELEASED = {"paper/title_page.tex", "LICENSE"}

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
