"""The main variant's reductions and shortfalls with nonlinear models in place of ordinary least squares, which the
supplement reports (sec:nonlinear) and the Results cite by the lowest lower bound of the shortfall's interval.

Objection answered: a nonlinear model might draw more from the own outfits' widths than ordinary least squares does,
so that the own outfits' shortfall is a property of the linear model. The models: a second-order polynomial regression
on the standardized inputs, and scikit-learn's HistGradientBoostingRegressor at its defaults. Each is scored exactly as
reduction.score scores ordinary least squares: the same subjects (the main variant's, with widths in all six outfits
under the primary scale rule), the same five-fold split, and the same paired bootstrap of subjects. Writes
results/nonlinear.json.

Comparison, committed before the run (2026-11-16, commit b5a2342 under the tag reserve/nonlinear-models), and what
each outcome means for the paper:
- The claim that this run re-tests is the paper's headline: in each own outfit, the widths' reduction in MAPE falls
  short of the measurement suit's reduction, with the 95% interval of the shortfall above zero, and the shortfall is
  more than half of the suit's reduction (the own outfits remove most of it).
- Answers the objection (first held in the reserve; published in the supplement on 2026-11-16, after the paper's
  comparison with Feng et al., whose Table 9 compares nonlinear learners): under both nonlinear models, the lower bound
  of every own outfit's shortfall interval is above zero and every own outfit's shortfall exceeds half of the suit's
  reduction under the same model.
- Against the claim (place-defensive-work, question 1, so the Results and not the reserve): under either model, the
  lower bound of an own outfit's shortfall interval is at or below zero, or a shortfall is at most half of the suit's
  reduction. The headline is then narrowed to linear models and the run reaches the Results with the claim rewritten.

Degrees of freedom: none fitted beyond each model's own fit, which is out of fold.
- POLY_DEGREE: CHOSEN. The lowest degree that adds interactions and curvature to the linear model.
- HGB_SEED: CHOSEN. HistGradientBoostingRegressor's random_state; its other settings are the library's defaults.

BASELINE: ordinary least squares (reduction.py) | obvious alternative: a nonlinear learner on the same inputs |
tuning: none, the library's defaults, one configuration per model | discharge: run (this file)
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import read_560 as r5  # noqa: E402
import reduction as red  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "nonlinear.json")
POLY_DEGREE = 2
HGB_SEED = 0
MODELS = {
    "linear": LinearRegression,
    "poly2": lambda: make_pipeline(StandardScaler(), PolynomialFeatures(POLY_DEGREE), LinearRegression()),
    "hgb_default": lambda: HistGradientBoostingRegressor(random_state=HGB_SEED),
}

def oof(make, X, y):
    """Out-of-fold predictions on reduction.py's split."""
    p = np.empty(len(y))
    for tr, te in KFold(red.N_FOLDS, shuffle=True, random_state=red.CV_SEED).split(X):
        p[te] = make().fit(X[tr], y[tr]).predict(X[te])
    return p

def score(make, X_base, F, y):
    e_base = red.ape(oof(make, X_base, y), y)
    e = {g: red.ape(oof(make, np.hstack([X_base, F[g]]), y), y) for g in r5.OUTFITS}
    idx = np.random.default_rng(red.BOOT_SEED).integers(0, len(y), size=(red.N_BOOT, len(y)))
    boot = {g: e_base[idx].mean(axis=1) - e[g][idx].mean(axis=1) for g in r5.OUTFITS}
    red_pp = {g: float(e_base.mean() - e[g].mean()) for g in r5.OUTFITS}
    out = {"mape_baseline": float(e_base.mean()), "per_outfit": {}}
    for g in r5.OUTFITS:
        row = {"mape": float(e[g].mean()), "reduction_pp": red_pp[g], "reduction_ci95": red.ci(boot[g])}
        if g != r5.SUIT:
            row["shortfall_pp"] = red_pp[r5.SUIT] - red_pp[g]
            row["shortfall_ci95"] = red.ci(boot[r5.SUIT] - boot[g])
        out["per_outfit"][g] = row
    own = [out["per_outfit"][g] for g in r5.OWN_CLOTHES]
    out["answers_objection"] = bool(all(r["shortfall_ci95"][0] > 0 for r in own) and
                                    all(r["shortfall_pp"] > red_pp[r5.SUIT] / 2 for r in own))
    return out

def main():
    tape = r5.read_tape()
    with ProcessPoolExecutor(r5.POOL) as ex:
        images = [row for rows in ex.map(r5.read_zip, [(z, tape) for z in r5.label_zips()]) for row in rows]
    feats, _, _ = red.features(images, tape, red.PRIMARY_RULE)
    subjects = sorted(s for s in {s for s, _ in feats} if all((s, g) in feats for g in r5.OUTFITS))
    y = np.array([tape[s]["waist"] for s in subjects])
    X_base = np.array([[tape[s]["stature"], tape[s]["weight"], tape[s]["sex"] == "M", tape[s]["age"]]
                       for s in subjects], float)
    F = {g: np.array([feats[(s, g)]["widths"] for s in subjects]) for g in r5.OUTFITS}
    result = {"n_subjects": len(subjects), "models": {k: score(m, X_base, F, y) for k, m in MODELS.items()}}
    with open(OUT, "w") as fh:
        json.dump(result, fh, indent=1)
    print(json.dumps(result, indent=1))

if __name__ == "__main__":
    main()
