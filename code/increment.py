"""How much the waist outline adds to stature, weight, sex and age in predicting the tape waist girth, in the
measurement suit and in each of the subjects' own outfits.

Per subject and outfit, the features are the torso polygon's frontal width 2a·S and diagonal width 2m·S at the
waist level, in cm: a is pillar A's half-width, m the mean half-width over the diagonal pillars, each averaged over
the camera heights, and S the height in cm that the image shows (키 plus the heel under the scale rule). The sensitivity
analysis replaces the widths with the ellipse girth, the ellipse with semi-axes a and b = √(2m² − a²), whose 45°
projection is m. The baseline regresses the tape waist girth
on 키, 몸무게, 성별 and 나이; the increment of outfit g is the baseline's MAPE minus the MAPE of the baseline plus
outfit g's features, out of fold, and the loss of g is the suit's increment minus g's. Writes results/increment.json.

Degrees of freedom (none fitted beyond the regressions' coefficients, which are fitted out of fold):
- N_FOLDS, CV_SEED: CHOSEN. Five folds over subjects, one partition shared by every model and outfit.
- PARTITION_SEEDS: CHOSEN. Nine further fold seeds, for the spread of each increment over partitions.
- N_BOOT, BOOT_SEED: CHOSEN. Paired bootstrap of subjects, with the out-of-fold predictions held fixed.
- PRIMARY_RULE: MEASURED by rig.py, whose ratio of heights in pixels shows the heel of the subjects' own shoes.
- PRIMARY_FEATURES: CHOSEN. The two widths; the ellipse girth is the sensitivity.

BASELINE: ordinary least squares on 키, 몸무게, 성별 and 나이, with the outline features added for each outfit |
obvious alternative: a nonlinear learner on the same inputs | tuning: none, one configuration | discharge:
sec:models, which states that the models this note tests (Feng et al.; Bartol et al.) are linear
"""
import json
import math
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold

import read_560 as r5

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "increment.json")
N_FOLDS, CV_SEED = 5, 0
PARTITION_SEEDS = range(1, 10)
N_BOOT, BOOT_SEED = 2000, 0
PRIMARY_RULE = "shod_own_clothes"
PRIMARY_FEATURES = "widths"
FEATURE_SETS = ("widths", "girth")

def features(images, tape, rule):
    """Per (subject, outfit): the frontal and diagonal widths and the ellipse girth, in cm. A camera height counts
    when it carries pillar A and at least one diagonal pillar with 2m² > a²; each feature is averaged over the camera
    heights that count."""
    cells = defaultdict(lambda: defaultdict(dict))
    for r in images:
        if r[rule] is not None:
            cells[(r["subject"], r["outfit"])][r["camera_height"]][r["pillar"]] = r[rule]
    out, rows_kept, rows_total = {}, 0, 0
    for (s, g), by_height in cells.items():
        A, M, G = [], [], []
        for h in by_height.values():
            rows_total += 1
            diag = [h[p] for p in r5.DIAGONAL if p in h]
            if "A" not in h or not diag or 2 * np.mean(diag) ** 2 <= h["A"] ** 2:
                continue
            rows_kept += 1
            a, m = h["A"], float(np.mean(diag))
            A.append(a)
            M.append(m)
            G.append(r5.ramanujan(a, math.sqrt(2 * m ** 2 - a ** 2)))
        if A:
            S = tape[s]["stature"] + r5.heel_for(tape[s], g, rule)
            out[(s, g)] = {"widths": [2 * np.mean(A) * S, 2 * np.mean(M) * S], "girth": [float(np.mean(G)) * S]}
    return out, rows_kept, rows_total

def oof(X, y, seed):
    """Out-of-fold predictions of ordinary least squares, five folds over subjects."""
    p = np.empty(len(y))
    for tr, te in KFold(N_FOLDS, shuffle=True, random_state=seed).split(X):
        p[te] = LinearRegression().fit(X[tr], y[tr]).predict(X[te])
    return p

def ape(p, y):
    return 100 * np.abs(p - y) / y

def rmse(p, y):
    return float(np.sqrt(np.mean((p - y) ** 2)))

def ci(x):
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]

def score(feats, tape, feature_set):
    """Every model scored on the subjects that carry the features in all six outfits."""
    subjects = sorted(s for s in {s for s, _ in feats} if all((s, g) in feats for g in r5.OUTFITS))
    y = np.array([tape[s]["waist"] for s in subjects])
    X_base = np.array([[tape[s]["stature"], tape[s]["weight"], tape[s]["sex"] == "M", tape[s]["age"]]
                       for s in subjects], float)
    W = np.array([[tape[s]["weight"]] for s in subjects])
    F = {g: np.array([feats[(s, g)][feature_set] for s in subjects]) for g in r5.OUTFITS}
    p_base = oof(X_base, y, CV_SEED)
    p = {g: oof(np.hstack([X_base, F[g]]), y, CV_SEED) for g in r5.OUTFITS}
    p_w = {g: oof(np.hstack([W, F[g]]), y, CV_SEED) for g in r5.OUTFITS}
    e_base = ape(p_base, y)
    idx = np.random.default_rng(BOOT_SEED).integers(0, len(y), size=(N_BOOT, len(y)))
    boot_base = e_base[idx].mean(axis=1)
    boot_increment = {g: boot_base - ape(p[g], y)[idx].mean(axis=1) for g in r5.OUTFITS}
    increment = {g: float(e_base.mean() - ape(p[g], y).mean()) for g in r5.OUTFITS}
    spread = {g: [] for g in r5.OUTFITS}
    for seed in PARTITION_SEEDS:
        e_seed = ape(oof(X_base, y, seed), y).mean()
        for g in r5.OUTFITS:
            spread[g].append(float(e_seed - ape(oof(np.hstack([X_base, F[g]]), y, seed), y).mean()))
    block = {"n_subjects": len(subjects), "mape_baseline": float(e_base.mean()), "rmse_baseline": rmse(p_base, y),
             "per_outfit": {}}
    for g in r5.OUTFITS:
        e_w = ape(p_w[g], y)
        row = {"mape": float(ape(p[g], y).mean()), "rmse": rmse(p[g], y),
               "increment_pp": increment[g], "increment_ci95": ci(boot_increment[g]),
               "increment_rmse_cm": block["rmse_baseline"] - rmse(p[g], y),
               "increment_pp_range_seeds_1_9": [min(spread[g]), max(spread[g])],
               # the weight-and-widths model: weight and the outline features alone, two of the three kinds of
               # input of Feng et al.'s model
               "weight_outline_mape": float(e_w.mean()),
               "weight_outline_minus_baseline_ci95": ci(e_w[idx].mean(axis=1) - boot_base)}
        if g != r5.SUIT:
            row["loss_pp"] = increment[r5.SUIT] - increment[g]
            row["loss_ci95"] = ci(boot_increment[r5.SUIT] - boot_increment[g])
            if feature_set == "widths":  # the width growth: what the outfit adds to each width, within subject
                d = F[g] - F[r5.SUIT]
                row["width_shift_cm_median"] = [float(v) for v in np.median(d, axis=0)]
                row["width_shift_cm_iqr"] = [[float(v) for v in np.percentile(d[:, k], [25, 75])] for k in range(2)]
        block["per_outfit"][g] = row
    return block

def main():
    tape = r5.read_tape()
    with ProcessPoolExecutor(r5.POOL) as ex:
        images = [row for rows in ex.map(r5.read_zip, [(z, tape) for z in r5.label_zips()]) for row in rows]
    result = {"images_read": len(images), "subjects_with_tape": len(tape), "configurations": {}}
    for rule in r5.SCALE_RULES:
        feats, kept, total = features(images, tape, rule)
        by_outfit = {g: sum(gg == g for _, gg in feats) for g in r5.OUTFITS}
        for fs in FEATURE_SETS:
            block = score(feats, tape, fs)
            block.update({"scale_rule": rule, "features": fs, "rows_kept": kept, "rows_total": total,
                          "subjects_with_features_by_outfit": by_outfit})
            result["configurations"][f"{rule} | {fs}"] = block
    result["primary"] = f"{PRIMARY_RULE} | {PRIMARY_FEATURES}"
    with open(OUT, "w") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print(json.dumps(result["configurations"][result["primary"]], ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
