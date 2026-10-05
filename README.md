# Waist widths in everyday clothing and waist girth

Analysis code and data for a short communication on the dataset *Whole Body Shape and Dimension Measurement Data for
Koreans*, which AI Hub lists as 한국인 전신 형상 및 치수 측정 데이터(성인).
In the dataset, each subject was photographed in a measurement suit and in five outfits of the subject's own clothes,
and the waist girth was measured with a tape. Adding the waist widths to a regression of the tape waist girth on
stature, weight, sex and age lowers the regression's error in the measurement suit, and lowers it by a small fraction
of that in the subjects' own clothes; the manuscript's Results give the numbers.

## Layout

```
paper/              LaTeX manuscript: main.tex and supplement.tex, title.tex (the title that both print), refs.bib,
                    vancouver-sage.bst (the journal's reference style), params.tex, the table bodies tab_*.tex and the
                    figure fig_rig.pdf (generated), params_manual.tex (hand-edited)
code/               read_560.py (the readers), rig.py and reduction.py (each writes a result table into results/),
                    make_params.py and fig_rig.py (write the generated files in paper/)
results/            the result tables that make_params.py and test_assertions.py read
test_assertions.py  every manuscript claim, checked against results/ and paper/
reproduce.sh        every stage in order, from the downloaded label files to the checked PDF
requirements.txt    the Python packages, at the versions that produced results/
```

The corpus lives under `$AIHUB_ROOT`, which every script requires and none defaults; the AI Hub terms restrict
redistribution, so none of it is committed. The dataset is available from AI Hub (https://www.aihub.or.kr) on
application. The scripts read its label zips and `신체정보데이터.zip` from `$AIHUB_ROOT/560_labels`, as AI Hub
distributes them; no image file is read.

## Reproduce

1. Install the packages: `pip install -r requirements.txt` (Python 3.12).
2. Run every stage: `AIHUB_ROOT=<download directory> ./reproduce.sh`. The stages are deterministic.
3. The run checks every number in the manuscript against results/ with `pytest test_assertions.py`, then builds
   paper/main.pdf and paper/supplement.pdf. One check fetches this repository's main branch and compares it with the
   checkout, so it needs a network connection.
