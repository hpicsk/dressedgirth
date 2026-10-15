"""Readers for the AI Hub dataset Whole Body Shape and Dimension Measurement Data for Koreans (한국인 전신 형상 및 치수
측정 데이터): the tape measurements, and for each image of the standing pose the half-width of the torso polygon at the
measured waist height.

The label zips and 신체정보데이터.zip are read from $AIHUB_ROOT/560_labels, as AI Hub distributes them (README.md).
The corpus path is resolved at use, so a module that imports this one, as the tests do, needs no corpus.
"""
import csv
import glob
import io
import json
import math
import os
import zipfile
from collections import Counter

import numpy as np

POSE = "01"  # CHOSEN: 차렷, the standing pose, the only one whose torso polygon the frontal and diagonal pillars carry
SUIT = "01"  # the creators' code for 측정복, the measurement suit (guide: Cloth 01)
OWN_CLOTHES = ["02", "03", "04", "05", "06"]  # 춘추복1, 춘추복2, 하복1, 하복2, 동복: the subjects' own outfits
OUTFITS = [SUIT] + OWN_CLOTHES
CAMERAS_PER_PILLAR = 4  # the guide, 제작 도구: 총 8각으로 한 각(기둥)에 4대의 카메라로 구성
PILLARS = "ABCDEFGH"  # the guide's 8 pillars, named in the order of their camera numbers (sec:rig)
CAMERAS = CAMERAS_PER_PILLAR * len(PILLARS)  # the guide: DSLR 32대
FRONT_BACK = ("A", "E")  # MEASURED by rig.py: 0° and 180° from A, which the subject faces
DIAGONAL = ("B", "D", "F", "H")  # MEASURED by rig.py: ±45° and ±135° from A
# CHOSEN: one definition for both half-widths, each the mean over every pillar that sees it: a over the two pillars on
# the front-back axis, of which E sees A's extent from behind, and m over the four diagonal pillars, of which D and F
# see the extents of H and B from behind
WIDTH_PILLARS = FRONT_BACK + DIAGONAL
SCALE_RULES = ("shod_own_clothes", "shod_always", "barefoot_always")  # which images add 신발굽높이 to 키
# The foot polygons under each spelling that the label files use, mapped to the foot: of the standing-pose files that
# carry 머리 and 몸통, pillar A names the feet 오른쪽발/왼쪽발 in 3,675, B in 2,212, D in 5,302 and H in 3,260, and
# 오른발/왼발 in the rest; no file uses both. Pillars C, E, F and G use 오른발/왼발 only, and 21,056 of pillar E's files
# carry no foot polygon under either spelling.
FOOT_LABELS = {"오른발": "right", "왼발": "left", "오른쪽발": "right", "왼쪽발": "left"}
POOL = 12  # worker processes; the result does not depend on it

def pillar_of(camera):
    """The pillar that holds a camera, cameras 1-4 on A, 5-8 on B and so on."""
    return PILLARS[(camera - 1) // CAMERAS_PER_PILLAR]

def corpus():
    """The directory of the dataset's label zips; a missing $AIHUB_ROOT is the error message."""
    return os.path.join(os.environ["AIHUB_ROOT"], "560_labels")

def label_zips():
    return sorted(z for z in glob.glob(f"{corpus()}/**/*.zip", recursive=True) if not z.endswith("신체정보데이터.zip"))

def decode(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp949")

def num(s):
    try:
        return float(s.replace(",", "."))
    except (AttributeError, ValueError):
        return None

def tape_files():
    """The rows of each csv file in 신체정보데이터.zip."""
    (z,) = glob.glob(f"{corpus()}/**/신체정보데이터.zip", recursive=True)
    with zipfile.ZipFile(z) as zf:
        return [list(csv.reader(io.StringIO(decode(zf.read(m))))) for m in zf.namelist() if m.endswith(".csv")]

def tape_header(files=None):
    """The measurement columns under the most common header of the csv files, after 측정월, 측정일 and 모델번호."""
    return Counter(tuple(r[1][3:]) for r in files or tape_files()).most_common(1)[0][0]

def read_tape():
    """Per subject: 키, 허리높이, 신발굽높이, 허리둘레, 몸무게 and 나이 as numbers, 성별, and 엉덩이높이 where given,
    which only rig.py reads. The csv files differ in their header
    text, so each column is read by its position under the most common header (tape_header). Subjects missing one of
    the first seven fields, or with a sex other than F or M, are left out."""
    files = tape_files()
    names = ["측정월", "측정일", "모델번호"] + list(tape_header(files))
    tape = {}
    for rows in files:
        for values in rows[2:]:
            if not any(v.strip() for v in values):
                continue
            rec = dict(zip(names, values))
            v = {"stature": num(rec["키"]), "waist_height": num(rec["허리높이"]), "heel": num(rec["신발굽높이"]),
                 "waist": num(rec["허리둘레"]), "weight": num(rec["몸무게"]), "age": num(rec["나이"]),
                 "sex": rec["성별"].strip()}
            if None not in v.values() and v["sex"] in ("F", "M"):
                tape[rec["모델번호"].strip()] = {**v, "hip_height": num(rec["엉덩이높이"])}
    return tape

def pts(s):
    return np.array(list(map(float, s.split()))).reshape(-1, 2)

def chord(P, y):
    """Outer extent of the polygon along the horizontal line at y, or None if the line misses it."""
    xs = []
    for (x1, y1), (x2, y2) in zip(P, np.roll(P, -1, axis=0)):
        if y1 != y2 and (y1 - y) * (y2 - y) <= 0:
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    return max(xs) - min(xs) if len(xs) >= 2 else None

def heel_for(t, outfit, rule):
    """The heel added to 키 under a scale rule. The subjects are taken to stand barefoot in the measurement suit and
    in their own shoes otherwise (sec:rig), so shod_own_clothes is the primary rule and the other two are its
    sensitivities."""
    if rule == "shod_always":
        return t["heel"]
    if rule == "barefoot_always":
        return 0.0
    return 0.0 if outfit == SUIT else t["heel"]

def read_zip(args):
    """Per image of the standing pose in the pillars of WIDTH_PILLARS: the height in pixels (top of 머리 to the bottom of
    the lower foot), and under each scale rule the torso polygon's half-width at the waist level in units of the height
    in pixels. The waist level sits at (허리높이 + heel) / (키 + heel) of the height in pixels above the bottom of the
    feet."""
    z, tape = args
    out = []
    with zipfile.ZipFile(z) as zf:
        for m in zf.namelist():
            if not m.endswith(".json"):
                continue
            pose, outfit, subject, camera = os.path.basename(m)[:-5].split("_")
            camera = int(camera)
            pillar = pillar_of(camera)
            if pose != POSE or pillar not in WIDTH_PILLARS or subject not in tape:
                continue
            raw = zf.read(m)
            if not raw:
                continue
            L = {x["polygon"]["label"]: pts(x["polygon"]["location"]) for x in json.loads(raw)["labelingInfo"]}
            feet = [L[k] for k in FOOT_LABELS if k in L]
            if "머리" not in L or "몸통" not in L or not feet:
                continue
            top, bottom = L["머리"][:, 1].min(), max(F[:, 1].max() for F in feet)
            H = bottom - top
            t = tape[subject]
            row = {"subject": subject, "outfit": outfit, "pillar": pillar,
                   "camera_height": (camera - 1) % CAMERAS_PER_PILLAR + 1, "H": H}
            for rule in SCALE_RULES:
                heel = heel_for(t, outfit, rule)
                c = chord(L["몸통"], bottom - (t["waist_height"] + heel) / (t["stature"] + heel) * H)
                row[rule] = None if c is None else c / 2 / H
            out.append(row)
    return out

def ramanujan(a, b):
    """Ramanujan's first approximation to the perimeter of an ellipse with semi-axes a and b."""
    return math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))
