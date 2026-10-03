#!/usr/bin/env bash
# Every stage in order: the result tables in results/, paper/params.tex and the two table bodies, the claim checks and
# the PDF. AIHUB_ROOT names the directory that holds the AI Hub downloads (README.md).
set -euo pipefail
: "${AIHUB_ROOT:?set AIHUB_ROOT to the directory that holds the AI Hub downloads}"
cd "$(dirname "$0")/code"

python rig.py          # pillar placement, the ratio of heights in pixels and the torso counts -> results/rig.json
python increment.py    # the baseline and width models under every scale rule and feature -> results/increment.json
python make_params.py  # -> paper/params.tex, paper/tab_garments.tex, paper/tab_sensitivity.tex

cd ..
python -m pytest -q test_assertions.py
cd paper
latexmk -pdf -interaction=nonstopmode -halt-on-error main
