#!/usr/bin/env bash
# Every stage in order: the result tables in results/, paper/params.tex, the three table bodies and the figure, the claim
# checks and the PDF. AIHUB_ROOT names the directory that holds the AI Hub downloads (README.md).
set -euo pipefail
: "${AIHUB_ROOT:?set AIHUB_ROOT to the directory that holds the AI Hub downloads}"
cd "$(dirname "$0")/code"

python rig.py          # pillar placement, the ratio of heights in pixels, the heel share and the torso counts
                       # -> results/rig.json
python reduction.py    # the baseline and width models under every scale rule and form of the waist input, and
                       # the main variant with self-report errors -> results/reduction.json
python make_params.py  # -> paper/params.tex, paper/tab_outfits.tex, paper/tab_sensitivity.tex,
                       #    paper/tab_self_report.tex
python fig_rig.py      # -> paper/fig_rig.pdf

cd ..
python -m pytest -q test_assertions.py
cd paper
latexmk -pdf -interaction=nonstopmode -halt-on-error supplement main
