"""Writes paper/params.tex, every number of the manuscript as a macro, and the tabulars of its two tables,
paper/tab_garments.tex and paper/tab_sensitivity.tex, from the result tables in results/.

The files are generated: edit this script, never them. Each block of params.tex declares the population that its
macros are measured over (`% Population:`), and a `[population: ...]` note on a line overrides the block's for that
macro; `none` marks a number that counts no population. test_assertions.py regenerates the files and compares.
"""
import json
import os

import increment as inc
import read_560 as r5

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "..", "results")
PAPER = os.path.join(HERE, "..", "paper")
OUT = os.path.join(PAPER, "params.tex")
TABLES = {"tab_garments.tex": "outfits", "tab_sensitivity.tex": "sensitivity"}

POPULATIONS = {
    "tape": "dataset 560's tape records (신체정보데이터.zip), the subjects that carry every field the analysis reads",
    "images": ("the standing-pose label files of pillars A, B, D, F and H that carry the head, the torso and a foot, "
               "of the subjects in the tape population"),
    "rig-images": "the standing-pose label files of all 32 cameras that carry the head and a foot",
    "pose-images": "the standing-pose label files of all 32 cameras",
    "hip-images": ("the standing-pose label files of pillar A that carry the head, a foot and the torso, of the tape "
                   "subjects whose record gives the hip height"),
    "rows": ("the combinations of subject, outfit and camera height in the images population, under the primary "
             "scale rule"),
    "subjects": ("the subjects with the outline features in all six outfits, under the scale rule that the "
                 "configuration names (the primary rule unless a macro's name says otherwise)"),
    "none": "a number that counts no population",
}
OUTFIT_NAMES = {"01": "Measurement suit", "02": "Spring/autumn 1", "03": "Spring/autumn 2", "04": "Summer 1",
                "05": "Summer 2", "06": "Winter"}
RULE_NAMES = {"shod_own_clothes": "Own outfits", "shod_always": "Every outfit", "barefoot_always": "None"}
FEATURE_NAMES = {"widths": "Widths", "girth": "Ellipse girth"}

def load(name):
    with open(os.path.join(RESULTS, name)) as fh:
        return json.load(fh)

def pp(x):
    """Percentages and percentage points: two decimals, with a true minus sign."""
    return f"{x:.2f}".replace("-", "$-$")

def cm(x):
    """Widths and their shifts: one decimal, in cm."""
    return f"{x:.1f}".replace("-", "$-$")

def rmse(x):
    """Root-mean-square errors and their differences: two decimals, in cm."""
    return f"{x:.2f}".replace("-", "$-$")

def count(n):
    return f"{n:,}".replace(",", "{,}")

def config(rule, features):
    return load("increment.json")["configurations"][f"{rule} | {features}"]

def own(block, key, k=None):
    """The values of one per-outfit field over the five own outfits."""
    vals = [block["per_outfit"][g][key] for g in r5.OWN_CLOTHES]
    return [v[k] for v in vals] if k is not None else vals

def blocks():
    res = load("increment.json")
    prim = res["configurations"][res["primary"]]
    suit = prim["per_outfit"][r5.SUIT]
    yield ("Design constants (code/increment.py, code/read_560.py)", "none", [
        ("nFolds", str(inc.N_FOLDS)), ("nPartitionSeeds", str(len(inc.PARTITION_SEEDS))),
        ("nBoot", count(inc.N_BOOT))])
    yield ("Counts (code/increment.py)", "subjects", [
        ("nTapeSubjects", count(res["subjects_with_tape"]), "tape"),
        ("nRows", count(prim["rows_total"]), "rows"), ("nRowsKept", count(prim["rows_kept"]), "rows"),
        ("nSubjects", count(prim["n_subjects"])),
        ("nSuitSubjects", count(prim["subjects_with_features_by_outfit"][r5.SUIT]), "tape"),
        ("nOwnSubjectsMin", count(min(prim["subjects_with_features_by_outfit"][g] for g in r5.OWN_CLOTHES)), "tape"),
        ("nOwnSubjectsMax", count(max(prim["subjects_with_features_by_outfit"][g] for g in r5.OWN_CLOTHES)), "tape")])
    yield ("Primary configuration: heel in own clothes only, the two widths (code/increment.py)", "subjects", [
        ("mapeBaseline", pp(prim["mape_baseline"])), ("rmseBaseline", rmse(prim["rmse_baseline"])),
        ("mapeSuit", pp(suit["mape"])), ("rmseSuit", rmse(suit["rmse"])),
        ("incSuit", pp(suit["increment_pp"])), ("incSuitLo", pp(suit["increment_ci95"][0])),
        ("incSuitHi", pp(suit["increment_ci95"][1])),
        ("mapeOwnMin", pp(min(own(prim, "mape")))), ("mapeOwnMax", pp(max(own(prim, "mape")))),
        ("incOwnMin", pp(min(own(prim, "increment_pp")))), ("incOwnMax", pp(max(own(prim, "increment_pp")))),
        ("incOwnLoMin", pp(min(own(prim, "increment_ci95", 0)))),
        ("incOwnLoMax", pp(max(own(prim, "increment_ci95", 0)))),
        ("lossMin", pp(min(own(prim, "loss_pp")))), ("lossMax", pp(max(own(prim, "loss_pp")))),
        ("lossLoMin", pp(min(own(prim, "loss_ci95", 0)))), ("lossLoMax", pp(max(own(prim, "loss_ci95", 0)))),
        ("incSuitSeedMin", pp(suit["increment_pp_range_seeds_1_9"][0])),
        ("incSuitSeedMax", pp(suit["increment_pp_range_seeds_1_9"][1])),
        ("incOwnSeedMin", pp(min(own(prim, "increment_pp_range_seeds_1_9", 0)))),
        ("incOwnSeedMax", pp(max(own(prim, "increment_pp_range_seeds_1_9", 1)))),
        ("mapeWeightSuit", pp(suit["weight_outline_mape"])),
        ("weightSuitDiffLo", pp(suit["weight_outline_minus_baseline_ci95"][0])),
        ("weightSuitDiffHi", pp(suit["weight_outline_minus_baseline_ci95"][1])),
        ("mapeWeightOwnMin", pp(min(own(prim, "weight_outline_mape")))),
        ("mapeWeightOwnMax", pp(max(own(prim, "weight_outline_mape")))),
        ("weightOwnDiffLoMin", pp(min(own(prim, "weight_outline_minus_baseline_ci95", 0)))),
        ("shiftFrontMin", cm(min(own(prim, "width_shift_cm_median", 0)))),
        ("shiftFrontMax", cm(max(own(prim, "width_shift_cm_median", 0)))),
        ("shiftDiagMin", cm(min(own(prim, "width_shift_cm_median", 1)))),
        ("shiftDiagMax", cm(max(own(prim, "width_shift_cm_median", 1)))),
        ("shiftQuartileLo", cm(min(q[k][0] for q in own(prim, "width_shift_cm_iqr") for k in (0, 1)))),
        ("shiftQuartileHi", cm(max(q[k][1] for q in own(prim, "width_shift_cm_iqr") for k in (0, 1))))])
    widths = [config(r, "widths") for r in r5.SCALE_RULES]
    girth = [config(r, "girth") for r in r5.SCALE_RULES]
    yield ("Sensitivities: the other scale rules and the ellipse girth (code/increment.py)", "subjects", [
        ("nSubjectsNoHeel", count(config("barefoot_always", "widths")["n_subjects"])),
        ("incOwnMaxAll", pp(max(max(own(b, "increment_pp") + own(b, "increment_pp_range_seeds_1_9", 1))
                                for b in widths + girth)))])
    rig = load("rig.json")
    diag = [abs(rig["leg_offset_ratio_to_A"][p]) for p in r5.DIAGONAL]
    side = [abs(rig["leg_offset_ratio_to_A"][p]) for p in ("C", "G")]
    gain = [100 * (v["median"] - 1) for v in rig["height_px_ratio_to_suit"].values()]
    torso = {p: 100 * v["with_torso"] / v["images"] for p, v in rig["torso_by_pillar"].items()}
    hip = [100 * v["hip_level_inside_torso"] / v["images"] for v in rig["hip_level_in_pillar_A"].values()]
    yield ("The rig (code/rig.py)", "rig-images", [
        ("legRatioDiagMin", f"{min(diag):.2f}"), ("legRatioDiagMax", f"{max(diag):.2f}"),
        ("legRatioSideMax", f"{max(side):.2f}"),
        ("statureGainMin", f"{min(gain):.1f}"), ("statureGainMax", f"{max(gain):.1f}"),
        ("nPhotographedSubjects", count(rig["tape_subjects_photographed"]), "tape"),
        ("torsoSideMax", f"{max(torso[p] for p in ('C', 'G')):.1f}", "pose-images"),
        ("torsoOtherMin", f"{min(v for p, v in torso.items() if p not in ('C', 'G')):.1f}", "pose-images"),
        ("hipShareMin", f"{min(hip):.0f}", "hip-images"), ("hipShareMax", f"{max(hip):.0f}", "hip-images")])

def render():
    lines = ["% params.tex: the numbers that the manuscript prints from results/, written by code/make_params.py;",
             "% edit the script, never this file. Each number counts the population that its block names",
             "% (\"% Population:\"), or the one that a [population: ...] note on its line names.", "%"]
    lines += [f"% Population {name}: {text}" for name, text in POPULATIONS.items()]
    for title, block_frame, items in blocks():
        lines += ["", f"% {title}", f"% Population: {block_frame}"]
        for name, value, *frame in items:
            note = f"  % [population: {frame[0]}]" if frame and frame[0] != block_frame else ""
            lines.append(f"\\newcommand{{\\{name}}}{{{value}}}{note}")
    return "\n".join(lines) + "\n"

def ci(v):
    return f"{pp(v[0])}--{pp(v[1])}"

OUTFITS_HEAD = r"""\begin{tabular}{lrrlrrlrrr}
\toprule
 & Width & \multicolumn{3}{c}{Increment} & \multicolumn{2}{c}{Loss} & Weight + & \multicolumn{2}{c}{Width growth} \\
\cmidrule(lr){3-5}\cmidrule(lr){6-7}\cmidrule(lr){9-10}
Outfit & model & pp & 95\% interval & cm & pp & 95\% interval & widths & Frontal & Diagonal \\
\midrule
"""
SENSITIVITY_HEAD = r"""\begin{tabular}{llrlrrrr}
\toprule
 & & & & \multicolumn{2}{c}{Own outfits} & \multicolumn{2}{c}{Loss} \\
\cmidrule(lr){5-6}\cmidrule(lr){7-8}
Feature & Heel added & $n$ & Suit & Range & Above 0 & Range & Lowest start \\
\midrule
"""
TAIL = "\\bottomrule\n\\end{tabular}\n"

def outfits():
    """The tabular of tab:garments: one row per outfit, primary configuration."""
    res = load("increment.json")
    prim = res["configurations"][res["primary"]]
    rows = []
    for g in r5.OUTFITS:
        r = prim["per_outfit"][g]
        loss = f"{pp(r['loss_pp'])} & {ci(r['loss_ci95'])}" if g != r5.SUIT else "-- & --"
        shift = " & ".join(cm(v) for v in r["width_shift_cm_median"]) if g != r5.SUIT else "-- & --"
        rows.append(f"{OUTFIT_NAMES[g]} & {pp(r['mape'])} & {pp(r['increment_pp'])} & {ci(r['increment_ci95'])} & "
                    f"{rmse(r['increment_rmse_cm'])} & {loss} & {pp(r['weight_outline_mape'])} & {shift} \\\\")
    return OUTFITS_HEAD + "\n".join(rows) + "\n" + TAIL

def sensitivity():
    """The tabular of tab:sensitivity: one row per configuration, primary first."""
    res = load("increment.json")
    keys = [res["primary"]] + [k for k in res["configurations"] if k != res["primary"]]
    rows = []
    for k in keys:
        b = res["configurations"][k]
        suit = b["per_outfit"][r5.SUIT]
        above = sum(lo > 0 for lo in own(b, "increment_ci95", 0))
        rows.append(f"{FEATURE_NAMES[b['features']]} & {RULE_NAMES[b['scale_rule']]} & {count(b['n_subjects'])} & "
                    f"{pp(suit['increment_pp'])} ({ci(suit['increment_ci95'])}) & "
                    f"{pp(min(own(b, 'increment_pp')))}--{pp(max(own(b, 'increment_pp')))} & {above} & "
                    f"{pp(min(own(b, 'loss_pp')))}--{pp(max(own(b, 'loss_pp')))} & "
                    f"{pp(min(own(b, 'loss_ci95', 0)))} \\\\")
    return SENSITIVITY_HEAD + "\n".join(rows) + "\n" + TAIL

def main():
    with open(OUT, "w") as fh:
        fh.write(render())
    for name, fn in TABLES.items():
        with open(os.path.join(PAPER, name), "w") as fh:
            fh.write(globals()[fn]())

if __name__ == "__main__":
    main()
