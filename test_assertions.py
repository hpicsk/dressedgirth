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
import make_params as mp  # noqa: E402
import read_560 as r5  # noqa: E402

PAPER = os.path.join(ROOT, "paper")
MAIN = os.path.join(PAPER, "main.tex")
PARAM_FILES = (os.path.join(PAPER, "params.tex"), os.path.join(PAPER, "params_manual.tex"))
NEWCOMMAND = re.compile(r"\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}")

def text(path):
    with open(path) as fh:
        return fh.read()

def macros(path):
    """{name: value} of a parameter file's \\newcommand lines."""
    return {m.group(1): m.group(2) for m in map(NEWCOMMAND.match, text(path).splitlines()) if m}

def body():
    """main.tex without its comments."""
    return re.sub(r"(?<!\\)%.*", "", text(MAIN))

def results():
    return mp.load("increment.json")

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

def test_every_macro_used():
    used = set(re.findall(r"\\([A-Za-z]+)", body()))
    unused = sorted(name for path in PARAM_FILES for name in macros(path) if name not in used)
    assert not unused, f"macros that main.tex never prints: {unused}"

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
            f"sec:models claims that the subjects with the features in all six outfits are those on which 'Every model "
            f"is fitted and scored', but {key} scores {block['n_subjects']} subjects against at most "
            f"{min(by_outfit.values())} with features")
    shod = {b["n_subjects"] for b in results()["configurations"].values() if b["scale_rule"] != "barefoot_always"}
    assert shod == {primary()["n_subjects"]}, (
        f"sec:models claims 'Under each scale rule that adds a heel height, {primary()['n_subjects']} subjects have the "
        f"features in all six outfits', as tab:sensitivity prints; the two rules score {shod}")

# sec:rig

def test_pillar_order():
    rig = mp.load("rig.json")["leg_offset_by_pillar"]
    assert rig["A"] < 0 < rig["E"], (
        f"sec:rig claims 'In pillar A, the centroid of the subject's right lower-leg polygon lies left of the centroid "
        f"of the left lower-leg polygon' and that the order reverses in pillar E; offsets A {rig['A']:.3f}, "
        f"E {rig['E']:.3f}")
    assert all(rig[p] < 0 for p in ("B", "H")) and all(rig[p] > 0 for p in ("D", "F")), (
        f"sec:rig claims 'Pillars B and H show the order of pillar A, and pillars D and F that of pillar E'; "
        f"offsets {rig}")
    ratio = mp.load("rig.json")["leg_offset_ratio_to_A"]
    assert min(abs(ratio[p]) for p in r5.DIAGONAL) > max(abs(ratio[p]) for p in ("C", "G")), (
        f"sec:rig places the diagonal pillars at ±45° and ±135° and C and G at the sides; ratios {ratio}")

def test_subjects_taller_in_own_outfits():
    ratios = mp.load("rig.json")["height_px_ratio_to_suit"]
    assert all(v["median"] > 1 for v in ratios.values()), (
        f"sec:rig claims 'the height in pixels in each own outfit exceeds the height in the measurement suit'; "
        f"median ratios {ratios}")

# sec:features

def test_torso_outline_in_the_side_pillars():
    share = {p: v["with_torso"] / v["images"] for p, v in mp.load("rig.json")["torso_by_pillar"].items()}
    side, other = max(share[p] for p in ("C", "G")), min(v for p, v in share.items() if p not in ("C", "G"))
    assert side < 0.05 < 0.95 < other, (
        f"sec:intro claims the labelers' outlines show the torso 'but rarely from the sides', and sec:features that the torso "
        f"outline 'gives widths but no depths'; the torso shares are {share}")

def test_torso_outline_mostly_misses_the_hip():
    hip = {g: v["hip_level_inside_torso"] / v["images"] for g, v in mp.load("rig.json")["hip_level_in_pillar_A"].items()}
    assert max(hip.values()) < 0.5, (
        f"sec:intro claims the labelers' outlines 'reach the waist but mostly not the hip'; the shares of pillar A's photographs "
        f"whose torso polygon spans the hip level are {hip}")

def test_no_height_for_the_chest_girth():
    header = mp.load("rig.json")["tape_header"]
    assert "젖가슴둘레" in header and not any("젖꼭지" in c for c in header), (
        f"sec:features claims 'The records give the chest girth, which passes through the bust points, but not the "
        f"height of the bust points'; the record's columns are {header}")

# sec:results

def test_widths_lower_the_error_in_every_outfit():
    pg = primary()["per_outfit"]
    low = {g: pg[g]["increment_ci95"][0] for g in r5.OUTFITS}
    assert all(v > 0 for v in low.values()), (
        f"sec:results claims 'In the measurement suit, the widths lower the MAPE' and 'In the subjects' own clothes, the "
        f"widths lower the MAPE', sec:intro 'The widths lowered the regression's mean absolute percentage error', and "
        f"the abstract 'In each of the subjects' five own outfits, they lowered it'; the interval starts are {low}")

def test_loss_holds_in_every_configuration():
    starts = {k: min(own(b, "loss_ci95", 0)) for k, b in results()["configurations"].items()}
    assert all(v > 0 for v in starts.values()), (
        f"sec:results claims that 'under the two other scale rules with the widths and under each of the three rules "
        f"with the ellipse girth, every own outfit's loss interval starts above zero', and the abstract that 'The "
        f"clothing lowered the contribution under each of three rules'; the lowest interval starts are {starts}")

def test_increment_bound_over_every_configuration():
    bound = float(macros(PARAM_FILES[0])["incOwnMaxAll"])
    blocks = results()["configurations"].values()
    seen = max(max(own(b, "increment_pp") + own(b, "increment_pp_range_seeds_1_9", 1)) for b in blocks)
    assert round(seen, 2) <= bound, (
        f"sec:results claims 'No own outfit's increment exceeds {bound} pp under any scale rule, with either the "
        f"widths or the ellipse girth, or under any fold split', and sec:conclusion that the outline lowered it 'by at "
        f"most {bound} in any variant of the analysis'; the largest is {seen:.4f}")

def test_clothes_widen_the_outline():
    shifts = own(primary(), "width_shift_cm_median")
    assert all(v > 0 for pair in shifts for v in pair), (
        f"sec:results claims 'The subjects' own clothes widen the outline at the waist'; median growths {shifts}")

def test_weight_and_widths_below_the_baseline_in_own_clothes():
    starts = own(primary(), "weight_outline_minus_baseline_ci95", 0)
    assert all(v > 0 for v in starts), (
        f"sec:intro claims that 'A regression on weight and the own outfits' widths alone ... predicted the girth less "
        f"accurately than the regression on stature, weight, sex and age', as do the abstract and sec:conclusion; "
        f"the interval starts are {starts}")

def test_five_own_outfits():
    assert len(r5.OWN_CLOTHES) == 5, (
        "sec:data claims five outfits of the subjects' own clothes, and sec:results reports 'the five outfits'")

# sec:models

def test_scikit_learn_version():
    pinned = re.search(r"^scikit-learn==(\S+)$", text(os.path.join(ROOT, "requirements.txt")), re.M).group(1)
    printed = macros(PARAM_FILES[1])["sklearnVersion"]
    assert printed == pinned, (
        f"sec:models claims 'scikit-learn's KFold (version {printed})', but requirements.txt pins {pinned}")

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
        f"dataset's label files is available at {RELEASE}', but its main branch differs from this tree in {differ}")
