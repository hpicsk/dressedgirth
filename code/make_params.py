"""Writes paper/params.tex, every number of the manuscript as a macro, and the tabulars of its three tables,
paper/tab_outfits.tex, paper/tab_sensitivity.tex and paper/tab_self_report.tex, from the result tables in results/.

The files are generated: edit this script, never them. Each block of params.tex declares the population that its
macros are measured over (`% Population:`), and a `[population: ...]` note on a line overrides the block's for that
macro; `none` marks a number that counts no population. test_assertions.py regenerates the files and compares.
"""
import json
import os

import reduction as red
import read_560 as r5

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "..", "results")
PAPER = os.path.join(HERE, "..", "paper")
OUT = os.path.join(PAPER, "params.tex")
TABLES = {"tab_outfits.tex": "outfits", "tab_sensitivity.tex": "sensitivity", "tab_self_report.tex": "self_report"}

POPULATIONS = {
    "tape": "the dataset's tape records (신체정보데이터.zip), the subjects that carry every field the analysis reads",
    "images": ("the standing-pose label files of pillars A, B, D, E, F and H that carry the head, the torso and a "
               "foot, of the subjects in the tape population"),
    "rig-images": "the standing-pose label files of all 32 cameras that carry the head and a foot",
    "pose-images": "the standing-pose label files of all 32 cameras",
    "hip-images": ("the standing-pose label files of pillar A that carry the head, a foot and the torso, of the tape "
                   "subjects whose record gives the hip height"),
    "subjects": ("the subjects with the widths in all six outfits, under the scale rule that the "
                 "configuration names (the primary rule unless a macro's name says otherwise)"),
    "none": "a number that counts no population",
}
# The sentences that print numbers of two populations on purpose, each with its reason; test_assertions.py fails a
# sentence that prints numbers of two populations without a line here.
CROSSINGS = [
    (("statureGainMin", "statureGainMax", "heelShareMedian"),
     "the rise in the height in pixels, over pairs of photographs, against the recorded heel height over the tape "
     "subjects: the comparison that makes the primary scale rule and the rule that adds no heel height bounds on the "
     "shoes' rise"),
]
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
    """Widths and their growth: one decimal, in cm."""
    return f"{x:.1f}".replace("-", "$-$")

def rmse(x):
    """Root-mean-square errors and their differences: two decimals, in cm."""
    return f"{x:.2f}".replace("-", "$-$")

def count(n):
    return f"{n:,}".replace(",", "{,}")

def config(rule, features):
    return load("reduction.json")["configurations"][f"{rule} | {features}"]

def own(block, key, k=None):
    """The values of one per-outfit field over the five own outfits."""
    vals = [block["per_outfit"][g][key] for g in r5.OWN_CLOTHES]
    return [v[k] for v in vals] if k is not None else vals

def blocks():
    res = load("reduction.json")
    prim = res["configurations"][res["primary"]]
    suit = prim["per_outfit"][r5.SUIT]
    yield ("Design constants (code/reduction.py, code/read_560.py)", "none", [
        ("nFolds", str(red.N_FOLDS)), ("nPartitionSeeds", str(len(red.PARTITION_SEEDS))),
        ("nBoot", count(red.N_BOOT)), ("camerasTotal", str(r5.CAMERAS)), ("pillarsTotal", str(len(r5.PILLARS))),
        ("camerasPerPillar", str(r5.CAMERAS_PER_PILLAR)), ("ciLevel", str(red.CI_LEVEL)),
        ("ciLowerPct", f"{(100 - red.CI_LEVEL) / 2:g}"), ("ciUpperPct", f"{(100 + red.CI_LEVEL) / 2:g}"),
        ("selfReportSdCm", f"{red.SELF_REPORT_SD_CM:g}"),
        ("selfReportSdKg", f"{red.SELF_REPORT_SD_KG:g}"), ("nDraws", str(red.N_DRAWS))])
    yield ("Counts (code/reduction.py)", "subjects", [
        ("nTapeSubjects", count(res["subjects_with_tape"]), "tape"),
        ("nSubjects", count(prim["n_subjects"])),
        ("nSuitSubjects", count(prim["subjects_with_features_by_outfit"][r5.SUIT]), "tape"),
        ("nOwnSubjectsMin", count(min(prim["subjects_with_features_by_outfit"][g] for g in r5.OWN_CLOTHES)), "tape"),
        ("nOwnSubjectsMax", count(max(prim["subjects_with_features_by_outfit"][g] for g in r5.OWN_CLOTHES)), "tape")])
    yield ("Primary configuration: heel in own clothes only, the two widths (code/reduction.py)", "subjects", [
        ("mapeBaseline", pp(prim["mape_baseline"])),
        ("redSuit", pp(suit["reduction_pp"])),
        ("redOwnMin", pp(min(own(prim, "reduction_pp")))), ("redOwnMax", pp(max(own(prim, "reduction_pp")))),
        ("shortfallMin", pp(min(own(prim, "shortfall_pp")))), ("shortfallMax", pp(max(own(prim, "shortfall_pp")))),
        ("growthIqrMin", cm(min(q[k][1] - q[k][0] for q in own(prim, "width_growth_cm_iqr") for k in (0, 1)))),
        ("growthIqrMax", cm(max(q[k][1] - q[k][0] for q in own(prim, "width_growth_cm_iqr") for k in (0, 1))))])
    yield ("Sensitivities: the other scale rules and the ellipse girth (code/reduction.py)", "subjects", [
        ("nSubjectsNoHeel", count(config("barefoot_always", "widths")["n_subjects"]))])
    draws = res["self_report"]["draws"]
    yield ("Self-reported stature and weight: the main variant with the self-report error (code/reduction.py)",
           "subjects", [
        ("selfBaseMin", pp(min(d["mape_baseline"] for d in draws))),
        ("selfBaseMax", pp(max(d["mape_baseline"] for d in draws))),
        ("selfRedSuitMin", pp(min(d["per_outfit"][r5.SUIT]["reduction_pp"] for d in draws))),
        ("selfRedSuitMax", pp(max(d["per_outfit"][r5.SUIT]["reduction_pp"] for d in draws))),
        ("selfRedOwnMin", pp(min(min(own(d, "reduction_pp")) for d in draws))),
        ("selfRedOwnMax", pp(max(max(own(d, "reduction_pp")) for d in draws)))])
    rig = load("rig.json")
    gain = [100 * (v["median"] - 1) for v in rig["height_px_ratio_to_suit"].values()]
    torso = {p: 100 * v["with_torso"] / v["images"] for p, v in rig["torso_by_pillar"].items()}
    hip = [100 * v["hip_level_inside_torso"] / v["images"] for v in rig["hip_level_in_pillar_A"].values()]
    yield ("The rig (code/rig.py)", "rig-images", [
        ("statureGainMin", f"{min(gain):.1f}"), ("statureGainMax", f"{max(gain):.1f}"),
        ("heelShareMedian", f"{rig['heel_share_of_stature_pct']['median']:.1f}", "tape"),
        ("nPhotographedSubjects", count(rig["tape_subjects_photographed"]), "tape"),
        ("torsoSideMax", f"{max(torso[p] for p in ('C', 'G')):.1f}", "pose-images"),
        ("torsoOtherMin", f"{min(v for p, v in torso.items() if p not in ('C', 'G')):.1f}", "pose-images"),
        ("hipShareMin", f"{min(hip):.0f}", "hip-images"), ("hipShareMax", f"{max(hip):.0f}", "hip-images"),
        ("footImagesE", count(rig["torso_by_pillar"]["E"]["with_head_torso_foot"]), "pose-images")])

def render():
    lines = ["% params.tex: the numbers that the manuscript prints from results/, written by code/make_params.py;",
             "% edit the script, never this file. Each number counts the population that its block names",
             "% (\"% Population:\"), or the one that a [population: ...] note on its line names.", "%"]
    lines += [f"% Population {name}: {text}" for name, text in POPULATIONS.items()]
    lines += [f"% Crossing {' '.join(names)}: {why}" for names, why in CROSSINGS]
    for title, block_frame, items in blocks():
        lines += ["", f"% {title}", f"% Population: {block_frame}"]
        for name, value, *frame in items:
            note = f"  % [population: {frame[0]}]" if frame and frame[0] != block_frame else ""
            lines.append(f"\\newcommand{{\\{name}}}{{{value}}}{note}")
    return "\n".join(lines) + "\n"

def ci(v):
    return f"{pp(v[0])}--{pp(v[1])}"

OUTFITS_HEAD = r"""\begin{tabular}{lrrlrlrlrr}
\toprule
 & Width & \multicolumn{4}{c}{Reduction} & \multicolumn{2}{c}{Shortfall} & \multicolumn{2}{c}{Width growth} \\
\cmidrule(lr){3-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}
Outfit & model & pp & \ciLevel\% interval & cm & \ciLevel\% interval & pp & \ciLevel\% interval & Frontal & Diagonal \\
\midrule
"""
SENSITIVITY_HEAD = r"""\begin{tabular}{llrlrrrrrr}
\toprule
 & & & & \multicolumn{2}{c}{Own outfits} & \multicolumn{2}{c}{Shortfall} & \multicolumn{2}{c}{Other fold splits} \\
\cmidrule(lr){5-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}
Added & Heel added & $n$ & Suit & Range & Above 0 & Range & Lowest bound & Suit & Own outfits \\
\midrule
"""
TAIL = "\\bottomrule\n\\end{tabular}\n"

def outfits():
    """The tabular of tab:outfits: one row per outfit, primary configuration."""
    res = load("reduction.json")
    prim = res["configurations"][res["primary"]]
    rows = []
    for g in r5.OUTFITS:
        r = prim["per_outfit"][g]
        shortfall = f"{pp(r['shortfall_pp'])} & {ci(r['shortfall_ci95'])}" if g != r5.SUIT else "-- & --"
        growth = " & ".join(cm(v) for v in r["width_growth_cm_median"]) if g != r5.SUIT else "-- & --"
        rows.append(f"{OUTFIT_NAMES[g]} & {pp(r['mape'])} & {pp(r['reduction_pp'])} & {ci(r['reduction_ci95'])} & "
                    f"{rmse(r['reduction_rmse_cm'])} & {rmse(r['reduction_rmse_cm_ci95'][0])}--"
                    f"{rmse(r['reduction_rmse_cm_ci95'][1])} & {shortfall} & {growth} \\\\")
    return OUTFITS_HEAD + "\n".join(rows) + "\n" + TAIL

def sensitivity():
    """The tabular of tab:sensitivity: one row per configuration, primary first."""
    res = load("reduction.json")
    keys = [res["primary"]] + [k for k in res["configurations"] if k != res["primary"]]
    rows = []
    for k in keys:
        b = res["configurations"][k]
        suit = b["per_outfit"][r5.SUIT]
        above = sum(lo > 0 for lo in own(b, "reduction_ci95", 0))
        rows.append(f"{FEATURE_NAMES[b['features']]} & {RULE_NAMES[b['scale_rule']]} & {count(b['n_subjects'])} & "
                    f"{pp(suit['reduction_pp'])} ({ci(suit['reduction_ci95'])}) & "
                    f"{pp(min(own(b, 'reduction_pp')))}--{pp(max(own(b, 'reduction_pp')))} & {above} & "
                    f"{pp(min(own(b, 'shortfall_pp')))}--{pp(max(own(b, 'shortfall_pp')))} & "
                    f"{pp(min(own(b, 'shortfall_ci95', 0)))} & "
                    f"{pp(suit['reduction_pp_range_seeds_1_9'][0])}--{pp(suit['reduction_pp_range_seeds_1_9'][1])} & "
                    f"{pp(min(own(b, 'reduction_pp_range_seeds_1_9', 0)))}--"
                    f"{pp(max(own(b, 'reduction_pp_range_seeds_1_9', 1)))} \\\\")
    return SENSITIVITY_HEAD + "\n".join(rows) + "\n" + TAIL

SELF_REPORT_HEAD = r"""\begin{tabular}{lrlrrlr}
\toprule
 & \multicolumn{3}{c}{Reduction} & \multicolumn{3}{c}{Shortfall} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-7}
Outfit & Mean & Range & Lowest bound & Mean & Range & Lowest bound \\
\midrule
"""

def self_report():
    """The tabular of tab:selfreport: one row per outfit, over the draws of the self-report error."""
    draws = load("reduction.json")["self_report"]["draws"]
    rows = []
    for g in r5.OUTFITS:
        cells = []
        for key in ("reduction", "shortfall"):
            if g == r5.SUIT and key == "shortfall":
                cells.append("-- & -- & --")
                continue
            v = [d["per_outfit"][g][f"{key}_pp"] for d in draws]
            lo = min(d["per_outfit"][g][f"{key}_ci95"][0] for d in draws)
            cells.append(f"{pp(sum(v) / len(v))} & {pp(min(v))}--{pp(max(v))} & {pp(lo)}")
        rows.append(f"{OUTFIT_NAMES[g]} & {cells[0]} & {cells[1]} \\\\")
    return SELF_REPORT_HEAD + "\n".join(rows) + "\n" + TAIL

def main():
    with open(OUT, "w") as fh:
        fh.write(render())
    for name, fn in TABLES.items():
        with open(os.path.join(PAPER, name), "w") as fh:
            fh.write(globals()[fn]())

if __name__ == "__main__":
    main()
