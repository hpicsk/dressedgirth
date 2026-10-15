"""Where the pillars stand, and whether the subjects wear shoes, read from the label polygons of the standing pose.

The label files carry no camera angle. The guide places read_560.CAMERAS cameras on the pillars of read_560.PILLARS,
read_560.CAMERAS_PER_PILLAR to a pillar, and numbers the cameras in pillar order. Two measurements place the pillars
and fix the scale rule of read_560.py:
- the mean horizontal coordinate of the lower right leg polygon's vertices minus that of the lower left leg's, in
  units of the subject's height in pixels, in the measurement suit: its sign says whether the camera sees the subject's front or back, and its size relative to
  pillar A's says how far the camera stands from the frontal axis (cos 45° ≈ 0.71 at ±45° and ±135°, 0 at the sides);
- the height in pixels in each own outfit over the height in pixels in the measurement suit, per subject and camera:
  a ratio above 1 is the heel of the subject's own shoes.
Three further counts say which girths and views the torso polygon allows: the share of standing-pose images that
carry 몸통 in each pillar, the number that carry 머리, 몸통 and a foot, which the widths need, and the share of pillar
A's images whose 몸통 spans the tape hip level (엉덩이높이 under the
primary scale rule); the tape header, which names the heights that the records give, is written beside them.
It also counts the tape subjects who appear in the standing-pose images, and gives the recorded heel height
(신발굽높이) as a share of 키 over the tape subjects, to compare with the rise in the height in pixels.
Writes results/rig.json.
"""
import json
import os
import zipfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import read_560 as r5
import reduction as red

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "rig.json")
LEGS = ("아래오른쪽다리", "아래왼쪽다리")  # lower right leg, lower left leg

def read(z):
    """Per standing-pose image with 머리 and a foot: subject, outfit, camera, the height in pixels, the leg offset in
    units of the height in pixels when both lower legs are labelled, and the vertical span of 몸통 above the bottom of
    the feet in the same units when 몸통 is labelled. Beside them, per standing-pose image: its camera, whether it
    carries 몸통, and whether it carries 머리, 몸통 and a foot, which the widths of read_560.read_zip need."""
    out, torso = [], []
    with zipfile.ZipFile(z) as zf:
        for m in zf.namelist():
            if not m.endswith(".json"):
                continue
            pose, outfit, subject, camera = os.path.basename(m)[:-5].split("_")
            raw = zf.read(m)
            if pose != r5.POSE or not raw:
                continue
            d = json.loads(raw)
            L = {x["polygon"]["label"]: r5.pts(x["polygon"]["location"]) for x in d["labelingInfo"]}
            feet = [L[k] for k in r5.FOOT_LABELS if k in L]
            torso.append((int(camera), "몸통" in L, "몸통" in L and "머리" in L and bool(feet)))
            if "머리" not in L or not feet:
                continue
            bottom = max(F[:, 1].max() for F in feet)
            H = bottom - L["머리"][:, 1].min()
            offset = (L[LEGS[0]][:, 0].mean() - L[LEGS[1]][:, 0].mean()) / H if all(k in L for k in LEGS) else None
            span = (float((bottom - L["몸통"][:, 1].max()) / H), float((bottom - L["몸통"][:, 1].min()) / H)) \
                if "몸통" in L else None
            out.append((subject, outfit, int(camera), float(H), offset, span))
    return out, torso

def main():
    with ProcessPoolExecutor(r5.POOL) as ex:
        parts = list(ex.map(read, r5.label_zips()))
    images = [row for rows, _ in parts for row in rows]
    torso = [flag for _, flags in parts for flag in flags]
    offsets = defaultdict(list)
    height = {}
    for subject, outfit, camera, H, offset, _ in images:
        height[(subject, outfit, camera)] = H
        if outfit == r5.SUIT and offset is not None:
            offsets[camera].append(offset)
    by_camera = {c: float(np.median(v)) for c, v in sorted(offsets.items())}
    by_pillar = {p: float(np.mean([v for c, v in by_camera.items() if r5.pillar_of(c) == p])) for p in r5.PILLARS}
    ratio = {}
    for g in r5.OWN_CLOTHES:
        rs = [H / height[(s, r5.SUIT, c)] for (s, gg, c), H in height.items() if gg == g and (s, r5.SUIT, c) in height]
        ratio[g] = {"n_image_pairs": len(rs), "median": float(np.median(rs)),
                    "iqr": [float(np.percentile(rs, 25)), float(np.percentile(rs, 75))]}
    tape = r5.read_tape()
    torso_by_pillar = {p: {"images": sum(r5.pillar_of(c) == p for c, _, _ in torso),
                           "with_torso": sum(r5.pillar_of(c) == p and has for c, has, _ in torso),
                           "with_head_torso_foot": sum(r5.pillar_of(c) == p and full for c, _, full in torso)}
                       for p in r5.PILLARS}
    hip = {g: {"images": 0, "hip_level_inside_torso": 0} for g in r5.OUTFITS}
    for subject, outfit, camera, _, _, span in images:
        t = tape.get(subject)
        if r5.pillar_of(camera) != "A" or span is None or t is None or t["hip_height"] is None:
            continue
        heel = r5.heel_for(t, outfit, red.PRIMARY_RULE)
        hip[outfit]["images"] += 1
        hip[outfit]["hip_level_inside_torso"] += span[0] <= (t["hip_height"] + heel) / (t["stature"] + heel) <= span[1]
    photographed = {row[0] for row in images} & tape.keys()
    heel_share = [100 * t["heel"] / t["stature"] for t in tape.values()]
    result = {"images_read": len(images),
              "tape_subjects_photographed": len(photographed),
              "leg_offset_median_by_camera": by_camera,
              "leg_offset_by_pillar": by_pillar,
              "leg_offset_ratio_to_A": {p: v / by_pillar["A"] for p, v in by_pillar.items()},
              "height_px_ratio_to_suit": ratio,
              "heel_cm_median": float(np.median([t["heel"] for t in tape.values()])),
              "heel_share_of_stature_pct": {"n_subjects": len(heel_share), "median": float(np.median(heel_share)),
                                            "iqr": [float(np.percentile(heel_share, 25)),
                                                    float(np.percentile(heel_share, 75))]},
              "torso_by_pillar": torso_by_pillar,
              "hip_level_in_pillar_A": hip,
              "tape_header": list(r5.tape_header())}
    with open(OUT, "w") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
