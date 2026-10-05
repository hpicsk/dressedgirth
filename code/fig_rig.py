"""Writes paper/fig_rig.pdf, the figure of the camera rig and the waist widths (sec:rig, sec:features).

(a) The rig seen from above: the eight pillars at their angles from the subject's front, each labeled with the ratio
    that rig.py measures, the median lower-leg distance relative to pillar A's, signed by the leg order. The ratio is
    close to cos θ, the length at which a camera at angle θ from the front sees a horizontal distance across the front.
(b) A front view: the height in pixels, the waist level and the torso polygon's horizontal extent at that level.
(c) The waist section seen from above as an ellipse with semi-axes a and b: the half-width that pillar A sees, and the
    half-width m that a diagonal pillar sees, with 2m² = a² + b².
Panel (a) prints results/rig.json; panels (b) and (c) are schematic, and no number of the analysis reads their
shapes. test_assertions.py regenerates the file and compares the bytes.
"""
import io
import json
import os

import matplotlib

matplotlib.use("pdf")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Ellipse, FancyArrowPatch, Polygon  # noqa: E402

import read_560 as r5  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RIG = os.path.join(HERE, "..", "results", "rig.json")
OUT = os.path.join(HERE, "..", "paper", "fig_rig.pdf")

PILLAR_ANGLE = {p: 360 * i / len(r5.PILLARS) for i, p in enumerate(r5.PILLARS)}  # degrees from the front, as rig.py
# places the pillars; the figure draws them in the order of their camera numbers (sec:rig)
USED = r5.WIDTH_PILLARS
WIDTH_IN, HEIGHT_IN = 6.85, 2.55  # two journal columns
FONT_PT, SMALL_PT = 8, 7
INK, MID, LIGHT = "0.0", "0.45", "0.85"  # gray levels, so that the figure reads in print
# Schematic shapes, in the axes' own units: drawing proportions only.
RIG_RADIUS, LABEL_RADIUS = 1.0, 1.32
SECTION_A, SECTION_B = 0.20, 0.13  # the waist section drawn at the rig's centre
FIGURE_TOP, WAIST_LEVEL = 1.0, 0.61  # panel (b): head top and waist level, feet at 0
ELLIPSE_A, ELLIPSE_B = 1.0, 0.62  # panel (c)
CAMERA_R = 1.55  # panel (c): where the two cameras are drawn

def ratios():
    with open(RIG) as fh:
        return json.load(fh)["leg_offset_ratio_to_A"]

def arrow(ax, start, end, style="<->", color=INK, lw=0.8):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=7, color=color, lw=lw,
                                 shrinkA=0, shrinkB=0))

def rig(ax):
    """Panel (a): front is up; a pillar at θ degrees from the front stands at (sin θ, cos θ)."""
    r = ratios()
    ax.add_patch(plt.Circle((0, 0), RIG_RADIUS, fill=False, ls=":", lw=0.6, color=MID))
    ax.add_patch(Ellipse((0, 0), 2 * SECTION_A, 2 * SECTION_B, fill=True, fc=LIGHT, ec=INK, lw=0.8))
    arrow(ax, (0, SECTION_B), (0, 0.55), style="-|>")
    ax.text(-0.05, 0.42, "front", fontsize=SMALL_PT, ha="right", va="center")
    for p, deg in PILLAR_ANGLE.items():
        t = np.radians(deg)
        x, y = np.sin(t), np.cos(t)
        used = p in USED
        ax.plot([x], [y], marker="s", ms=6, mfc=INK if used else "white", mec=INK, mew=0.8)
        lx, ly = LABEL_RADIUS * x, LABEL_RADIUS * y
        ax.text(lx, ly + 0.07, p, fontsize=FONT_PT, fontweight="bold", ha="center", va="center")
        ax.text(lx, ly - 0.09, f"{r[p]:.2f}".replace("-", "−"), fontsize=SMALL_PT, ha="center",
                va="center")
    for deg in (0, 45, 90, 135, 180):
        t = np.radians(deg)
        if deg:
            ax.plot([0.26 * np.sin(t), 0.9 * np.sin(t)], [0.26 * np.cos(t), 0.9 * np.cos(t)], lw=0.4, color=MID,
                    ls="--")
    ax.text(0.50, 0.36, "45°", fontsize=SMALL_PT, color=MID, ha="left", va="center")
    ax.text(0.58, 0.04, "90°", fontsize=SMALL_PT, color=MID, ha="center", va="bottom")
    ax.text(0.50, -0.36, "135°", fontsize=SMALL_PT, color=MID, ha="left", va="center")
    ax.set_xlim(-1.55, 1.55)
    ax.set_ylim(-1.55, 1.55)

def front_view(ax):
    """Panel (b): a schematic outline standing on the line y = 0, its head's top at FIGURE_TOP."""
    head = Ellipse((0, 0.93), 0.11, 0.14, fc=LIGHT, ec=MID, lw=0.6)
    torso = Polygon([(-0.13, 0.82), (0.13, 0.82), (0.115, 0.66), (0.10, WAIST_LEVEL), (0.125, 0.50),
                     (-0.125, 0.50), (-0.10, WAIST_LEVEL), (-0.115, 0.66)], closed=True, fc=LIGHT, ec=INK, lw=0.9)
    legs = [Polygon([(s * 0.02, 0.50), (s * 0.12, 0.50), (s * 0.09, 0.03), (s * 0.04, 0.03)], closed=True,
                    fc=LIGHT, ec=MID, lw=0.6) for s in (-1, 1)]
    feet = [Polygon([(s * 0.03, 0.03), (s * 0.10, 0.03), (s * 0.12, 0.0), (s * 0.03, 0.0)], closed=True,
                    fc=LIGHT, ec=MID, lw=0.6) for s in (-1, 1)]
    arms = [Polygon([(s * 0.13, 0.82), (s * 0.17, 0.80), (s * 0.20, 0.50), (s * 0.16, 0.50)], closed=True,
                    fc=LIGHT, ec=MID, lw=0.6) for s in (-1, 1)]
    for patch in [head, *legs, *feet, *arms, torso]:
        ax.add_patch(patch)
    ax.plot([0.10, 0.34], [WAIST_LEVEL, WAIST_LEVEL], ls="--", lw=0.6, color=MID)
    ax.plot([-0.10, 0.10], [WAIST_LEVEL, WAIST_LEVEL], lw=2.0, color=INK, solid_capstyle="butt")
    ax.annotate("", xy=(-0.10, WAIST_LEVEL + 0.10), xytext=(0.10, WAIST_LEVEL + 0.10),
                arrowprops={"arrowstyle": "<->", "lw": 0.6, "shrinkA": 0, "shrinkB": 0})
    ax.text(0.0, WAIST_LEVEL + 0.12, "2a", fontsize=FONT_PT, ha="center", va="bottom", style="italic")
    ax.annotate("torso polygon", xy=(0.125, 0.79), xytext=(0.17, 1.04), fontsize=SMALL_PT, ha="left", va="center",
                arrowprops={"arrowstyle": "-", "lw": 0.5, "shrinkA": 1, "shrinkB": 0})
    for y in (FIGURE_TOP, 0.0):
        ax.plot([-0.42, 0.42], [y, y], lw=0.4, color=MID)
    arrow(ax, (-0.36, 0.0), (-0.36, FIGURE_TOP))
    ax.text(-0.39, 0.4 * FIGURE_TOP, "height in pixels", fontsize=SMALL_PT, rotation=90, ha="right", va="center")
    arrow(ax, (0.36, 0.0), (0.36, WAIST_LEVEL))
    ax.text(0.39, 0.5 * WAIST_LEVEL, r"$\dfrac{h+e}{H+e}$", fontsize=FONT_PT + 1, ha="left", va="center")
    ax.text(0.39, WAIST_LEVEL, "waist\nlevel", fontsize=SMALL_PT, ha="left", va="center")
    ax.set_xlim(-0.62, 0.72)
    ax.set_ylim(-0.08, 1.12)

def section(ax):
    """Panel (c): front is up. A camera at θ from the front sees the half-width sqrt(a² cos²θ + b² sin²θ), the
    distance from the centre to either of the section's two tangents that run along the camera's line of sight."""
    a, b = ELLIPSE_A, ELLIPSE_B
    m = np.sqrt((a ** 2 + b ** 2) / 2)
    ax.add_patch(Ellipse((0, 0), 2 * a, 2 * b, fc=LIGHT, ec=INK, lw=0.9))
    arrow(ax, (0, 0), (a, 0), style="-|>")
    ax.text(0.5 * a, 0.05, "a", fontsize=FONT_PT, ha="center", va="bottom", style="italic")
    arrow(ax, (0, 0), (0, b), style="-|>")
    ax.text(-0.05, 0.55 * b, "b", fontsize=FONT_PT, ha="right", va="center", style="italic")
    for s in (-1, 1):  # pillar A's tangents, x = ±a, along its line of sight
        ax.plot([s * a, s * a], [-0.55, CAMERA_R - 0.12], lw=0.5, ls=":", color=INK)
    t = np.radians(45)
    sight = np.array([np.sin(t), np.cos(t)])  # from the centre toward a camera at 45° from the front
    u = np.array([sight[1], -sight[0]])  # that camera's horizontal image axis
    for s in (-1, 1):  # its two tangents, along its line of sight
        c = s * m * u
        ax.plot([c[0] - 0.75 * sight[0], c[0] + 1.05 * sight[0]], [c[1] - 0.75 * sight[1], c[1] + 1.05 * sight[1]],
                lw=0.5, ls="--", color=INK)
    arrow(ax, (0, 0), tuple(m * u), style="-|>")
    ax.text(m * u[0] - 0.10, m * u[1] - 0.02, "m", fontsize=FONT_PT, ha="right", va="top", style="italic")
    for (x, y), name in (((0, CAMERA_R), "A"), (tuple(CAMERA_R * sight), "B")):
        ax.plot([x], [y], marker="s", ms=6, mfc=INK, mec=INK)
        ax.text(x + 0.12, y, name, fontsize=FONT_PT, fontweight="bold", ha="left", va="center")
    ax.text(-0.45, -1.0, r"$2m^2 = a^2 + b^2$", fontsize=FONT_PT, ha="center", va="center")
    ax.set_xlim(-1.35, 1.65)
    ax.set_ylim(-1.2, 1.75)

def figure():
    """The figure's PDF bytes."""
    plt.rcParams.update({"font.size": FONT_PT, "font.family": "DejaVu Sans", "mathtext.fontset": "dejavusans",
                         "pdf.fonttype": 42})
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH_IN, HEIGHT_IN), gridspec_kw={"width_ratios": [1.15, 0.85, 1.0]})
    for ax, draw in zip(axes, (rig, front_view, section)):
        draw(ax)
        ax.set_aspect("equal")
        ax.axis("off")
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.02, top=0.98, wspace=0.08)
    for ax, tag in zip(axes, "abc"):
        fig.text(ax.get_position().x0, 0.96, f"({tag})", fontsize=FONT_PT, ha="left", va="top")
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf", metadata={"CreationDate": None, "Creator": None, "Producer": None})
    plt.close(fig)
    return buf.getvalue()

def main():
    with open(OUT, "wb") as fh:
        fh.write(figure())

if __name__ == "__main__":
    main()
