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
    """{macro: population} from both parameter files' declarations: a block's `% Population:` line, or a
    `[population: ...]` note on the macro's line."""
    out = {}
    for path in PARAM_FILES:
        population = None
        for line in text(path).splitlines():
            if line.startswith("% Population: "):
                population = line[len("% Population: "):]
            m = NEWCOMMAND.match(line)
            if m:
                note = re.search(r"\[population: ([^\]]+)\]", line)
                out[m.group(1)] = note.group(1) if note else population
    return out

def declared_populations():
    """The populations that make_params.py declares, and those that the manual file declares on its
    `% Population <name>:` lines."""
    manual = set(re.findall(r"^% Population ([A-Za-z-]+):", text(PARAM_FILES[1]), re.M))
    return set(mp.POPULATIONS) | manual

def test_population_crossings_are_recorded():
    pop = populations()
    recorded = [set(m.group(1).split()) for path in PARAM_FILES
                for m in re.finditer(r"^% Crossing ([A-Za-z ]+):", text(path), re.M)]
    crossed = []
    for path in (MAIN, SUPPLEMENT):
        for sentence in re.split(r"(?<=\.)\s+(?=[A-Z\\(])", re.sub(r"\s+", " ", body(path))):
            counted = {name for name in re.findall(r"\\([A-Za-z]+)", sentence) if pop.get(name, "none") != "none"}
            if len({pop[name] for name in counted}) > 1 and not any(counted <= names for names in recorded):
                crossed.append(sorted(counted))
    assert not crossed, (
        f"sentences that print numbers of two populations with no '% Crossing' line in a parameter file: {crossed}")

def test_every_macro_has_a_population():
    known, missing = declared_populations(), []
    for path in PARAM_FILES:
        population = None
        for line in text(path).splitlines():
            if line.startswith("% Population: "):
                population = line[len("% Population: "):]
            elif line.startswith("% ") and not line.startswith("% Population"):
                population = None
            m = NEWCOMMAND.match(line)
            if m:
                note = re.search(r"\[population: ([^\]]+)\]", line)
                if (note.group(1) if note else population) not in known:
                    missing.append(m.group(1))
    assert not missing, f"macros without a declared population: {missing}"

# sec:data

def test_subjects_enter_every_model():
    for key, block in results()["configurations"].items():
        by_outfit = block["subjects_with_features_by_outfit"]
        assert block["n_subjects"] <= min(by_outfit.values()), (
            f"sec:models claims that 'The models use only the subjects who have widths in all six outfits', but {key} "
            f"scores {block['n_subjects']} subjects against at most "
            f"{min(by_outfit.values())} with features")
    shod = {b["n_subjects"] for b in results()["configurations"].values() if b["scale_rule"] != "barefoot_always"}
    assert shod == {primary()["n_subjects"]}, (
        f"sec:models claims 'These subjects number {primary()['n_subjects']} under each scale rule that adds a heel "
        f"height', as tab:sensitivity prints; the two rules score {shod}")

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
        f"sec:rig claims that 'The subjects stood barefoot in the measurement suit and wore shoes in their own "
        f"outfits', and the supplement's sec:shoes that 'A rise in every own outfit means that the subjects wore shoes "
        f"in their own outfits and not in the suit', from the "
        f"median rise over pairs of photographs from one camera in each of the five outfits; median ratios {ratios}")

def test_shoes_rise_less_than_the_heel():
    rig = mp.load("rig.json")
    gain = max(100 * (v["median"] - 1) for v in rig["height_px_ratio_to_suit"].values())
    heel = rig["heel_share_of_stature_pct"]["median"]
    assert gain < heel, (
        f"sec:rig claims 'The shoes raised the subjects by less than the recorded heel height' and 'The primary rule "
        f"therefore overstates the rise in the own outfits', comparing, as the supplement's sec:shoes does, the rise "
        f"in the height in pixels with the recorded heel height's median share of stature; largest rise {gain:.2f}%, "
        f"heel share {heel:.2f}%")

# sec:features

def test_torso_polygon_in_the_side_pillars():
    share = {p: v["with_torso"] / v["images"] for p, v in mp.load("rig.json")["torso_by_pillar"].items()}
    side, other = max(share[p] for p in ("C", "G")), min(v for p, v in share.items() if p not in ("C", "G"))
    assert side < 0.05 < 0.95 < other, (
        f"the supplement's sec:widths prints the shares, and "
        f"sec:intro claims that the torso's polygon 'is missing from almost every photograph taken from the subject's "
        f"sides'; the torso shares are {share}")

def test_pillar_e_rarely_gives_a_half_width():
    by = mp.load("rig.json")["torso_by_pillar"]
    e, a = by["E"]["with_head_torso_foot"], by["A"]["with_head_torso_foot"]
    assert e < 0.05 * a, (
        f"sec:features claims 'Pillar E's photographs rarely show a foot, so $a$ rests almost entirely on pillar A', "
        f"and the supplement's sec:widths that 'Pillar E gives a half-width in only {e}' of its standing photographs; "
        f"pillar A gives {a}")

def test_torso_polygon_mostly_misses_the_hip():
    hip = {g: v["hip_level_inside_torso"] / v["images"] for g, v in mp.load("rig.json")["hip_level_in_pillar_A"].items()}
    assert max(hip.values()) < 0.5, (
        f"sec:features claims that 'in most of pillar A's photographs, the polygon does not reach the level that the "
        f"hip height locates', and the supplement's sec:widths prints the shares; the shares whose torso polygon "
        f"spans the hip level are {hip}")

def test_no_height_for_the_chest_girth():
    header = mp.load("rig.json")["tape_header"]
    assert "젖가슴둘레" in header and not any("젖꼭지" in c for c in header), (
        f"sec:features claims that 'the records give no height for the chest'; the record's columns are {header}")

# sec:results

def test_suit_reduction_above_zero():
    suit = primary()["per_outfit"][r5.SUIT]["reduction_ci95"]
    assert suit[0] > 0, (
        f"tab:outfits prints the suit's reduction of {macros(PARAM_FILES[0])['redSuit']} pp with a 95% confidence "
        f"interval above zero, and sec:intro and the abstract set the own outfits' reductions beside it; the suit's "
        f"interval is {suit}")

def test_own_reductions_in_rmse():
    pg = primary()["per_outfit"]
    above = [g for g in r5.OWN_CLOTHES if pg[g]["reduction_rmse_cm_ci95"][0] > 0]
    below = [mp.OUTFIT_NAMES[g] for g in r5.OWN_CLOTHES if g not in above]
    prose = re.sub(r"\s+", " ", body())
    assert (len(above) == WORDS["four"] and below == ["Winter"]
            and "lie above zero in four of the five own outfits, all but the winter outfit" in prose), (
        f"sec:results claims 'In RMSE, the intervals of the main variant's reductions lie above zero in four of the "
        f"five own outfits, all but the winter outfit'; the own outfits whose RMSE interval lies above zero are "
        f"{above}")

def test_shortfall_holds_in_every_configuration():
    starts = {k: min(own(b, "shortfall_ci95", 0)) for k, b in results()["configurations"].items()}
    assert all(v > 0 for v in starts.values()), (
        f"sec:results claims that 'The 95% confidence interval of each own outfit's shortfall has a lower bound of "
        f"{macros(PARAM_FILES[0])['shortfallLoMin']}-{macros(PARAM_FILES[0])['shortfallLoMax']} pp' and that 'In the five other variants of the analysis' the interval of every own outfit's "
        f"shortfall also lies above zero, as the abstract, sec:intro and sec:conclusion state in each variant; the "
        f"lowest lower bounds are {starts}")

def test_no_own_reduction_above_zero_in_any_variant():
    configs = results()["configurations"]
    above = {k: [g for g in r5.OWN_CLOTHES if b["per_outfit"][g]["reduction_ci95"][0] > 0] for k, b in configs.items()}
    assert not any(above.values()), (
        f"sec:results claims 'In MAPE, the interval of each own outfit's reduction includes zero in all six "
        f"variants'; "
        f"own outfits whose interval lies above zero: {above}")

def test_own_reductions_below_half_of_the_suit():
    share = {k: max(own(b, "reduction_pp")) / b["per_outfit"][r5.SUIT]["reduction_pp"]
             for k, b in results()["configurations"].items()}
    draws = results()["self_report"]["draws"]
    share_draws = max(max(own(d, "reduction_pp")) / d["per_outfit"][r5.SUIT]["reduction_pp"] for d in draws)
    seeds = primary()["per_outfit"]
    own_max = max(seeds[g]["reduction_pp_range_seeds_1_9"][1] for g in r5.OWN_CLOTHES)
    suit_min = seeds[r5.SUIT]["reduction_pp_range_seeds_1_9"][0]
    assert all(v < 0.5 for v in share.values()) and share_draws < 0.5 and own_max < suit_min / 2, (
        f"sec:results claims that 'the own outfits lose most of what the widths add in the suit', each own outfit's "
        f"reduction being less than half of the suit's, in the main variant, 'in the five other variants of the "
        f"analysis', under the 9 further splits into folds, and with the self-report errors; the largest own "
        f"reduction as a share of the suit's is {share}, {share_draws:.3f} over the draws, and over the further "
        f"splits the own outfits reach {own_max:.3f} against the suit's lowest {suit_min:.3f}")

def test_self_report_shortfall_in_every_draw():
    draws = results()["self_report"]["draws"]
    lows = [min(own(d, "shortfall_ci95", 0)) for d in draws]
    reds = [min(own(d, "reduction_ci95", 0)) for d in draws]
    assert len(draws) == mp.red.N_DRAWS and min(lows) > 0 and min(reds) > 0, (
        f"sec:results claims, for the self-report errors in {mp.red.N_DRAWS} random draws, that 'The interval of "
        f"each own outfit's shortfall lies above zero in each of those variants and draws' and that 'the interval of "
        f"each own outfit's reduction in MAPE lies above zero in every draw'; the lowest lower bounds per draw are "
        f"{reds} and {lows}")

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

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}

def test_counts_in_words():
    res = results()["configurations"]
    spelled = {"six outfits": len(r5.OUTFITS), "five outfits": len(r5.OWN_CLOTHES),
               "three scale rules": len(r5.SCALE_RULES), "two forms in which the waist enters": len(mp.red.FEATURE_SETS),
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

def test_nonlinear_models_keep_the_shortfall():
    nl = mp.load("nonlinear.json")
    lin, prim = nl["models"]["linear"], primary()
    same = all(lin["per_outfit"][g]["reduction_pp"] == prim["per_outfit"][g]["reduction_pp"] and
               lin["per_outfit"][g]["reduction_ci95"] == prim["per_outfit"][g]["reduction_ci95"] for g in r5.OUTFITS)
    lows = {k: min(own(nl["models"][k], "shortfall_ci95", 0)) for k in mp.NONLINEAR}
    share = {k: max(own(nl["models"][k], "reduction_pp")) / nl["models"][k]["per_outfit"][r5.SUIT]["reduction_pp"]
             for k in mp.NONLINEAR}
    assert (same and nl["n_subjects"] == prim["n_subjects"] and all(v > 0 for v in lows.values())
            and all(v < 0.5 for v in share.values())), (
        f"sec:results claims that the shortfall's interval 'also lies above zero when a second-order polynomial "
        f"regression or gradient-boosted trees' replace ordinary least squares, and the supplement's sec:nonlinear "
        f"that under both models 'the own outfits lose most of the suit's reduction', on the main variant's "
        f"subjects, folds and resamples (ordinary least squares in code/nonlinear.py reproduces the main variant: "
        f"{same}); the lowest lower bounds are {lows} and the largest own reductions as a share of the suit's {share}")

def test_width_model_errs_more_than_feng():
    feng = float(macros(PARAM_FILES[1])["fengWaistMape"])
    mape = {g: r["mape"] for g, r in primary()["per_outfit"].items()}
    assert all(v > feng for v in mape.values()), (
        f"sec:results claims that 'The width models' errors exceed that of the waist model that Feng et al. "
        f"proposed', whose MAPE is {feng}%, in the measurement suit and in the own outfits; the width models' MAPEs are "
        f"{mape}")

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
        f"The data availability statement says that 'The code that computes this article's results from the "
        f"dataset's polygons and tape measurements is available at {RELEASE}', but its main branch differs from this tree "
        f"in {differ}")
