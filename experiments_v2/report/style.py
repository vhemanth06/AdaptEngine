"""The only place for colours, fonts, sizes and figure dimensions (D100).

Restyle: edit this file, then `make v2-figures` (seconds; no experiment re-runs).
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Okabe-Ito colour-blind-safe palette (the same one the demo UI uses)
OKABE_ITO = {
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "black": "#000000",
    "grey": "#999999",
}
P = OKABE_ITO

# One fixed colour per arm (anything not listed falls back to grey)
ARM_COLORS = {
    "adapt": P["blue"],
    "no_review": P["sky"],
    "no_replan": P["orange"],
    "static": P["grey"],
    "adapt_h7": P["blue"],
    "no_review_h7": P["sky"],
    "prior_only": P["grey"],
    "sweep": P["orange"],
    "bisection": P["blue"],
    "fixed@n": P["yellow"],
    "irt_cat_global@n": P["purple"],
    "irt_cat_per_concept@n": P["vermillion"],
    "heuristic": P["orange"],
    "heuristic_class_D6": P["orange"],
    "fitted_class_profile": P["blue"],
    "fitted_per_skill": P["green"],
    "fitted_assist09": P["blue"],
    "fitted_ct": P["green"],
    "bisect_noconfirm": P["sky"],
    "bisect_confirm": P["blue"],
    "sweep_fitted": P["vermillion"],
    "bisect_noconfirm_fitted": P["purple"],
    "bisect_confirm_fitted": P["green"],
    "greedy": P["orange"],
    "hybrid": P["green"],
    "cpsat": P["blue"],
    "S0": P["blue"],
    "S1": P["orange"],
    "S2": P["green"],
    "S3": P["vermillion"],
    "S4": P["purple"],
    "S4-assist09": P["sky"],
}
MARKERS = {"S0": "o", "S2": "s", "S4": "^", "S1": "D", "S3": "v", "S4-assist09": "P"}
DIVERGING = "RdBu"  # heatmaps of differences (centred on 0)
SEQUENTIAL = "Blues"

FONT_FAMILY = "DejaVu Sans"
FONT_SIZE = 8
TITLE_SIZE = 9
LINE_WIDTH = 1.2
MARKER_SIZE = 4
SINGLE_COL = 3.4  # inches
DOUBLE_COL = 7.0
ASPECT = 0.68  # height / width for single panels
PNG_DPI = 300
GRID_COLOR = "#DDDDDD"


def color(name: str) -> str:
    return ARM_COLORS.get(name, P["grey"])


def setup() -> None:
    plt.rcParams.update(
        {
            "font.family": FONT_FAMILY,
            "font.size": FONT_SIZE,
            "axes.titlesize": TITLE_SIZE,
            "axes.labelsize": FONT_SIZE,
            "xtick.labelsize": FONT_SIZE - 1,
            "ytick.labelsize": FONT_SIZE - 1,
            "legend.fontsize": FONT_SIZE - 1,
            "legend.frameon": False,
            "lines.linewidth": LINE_WIDTH,
            "lines.markersize": MARKER_SIZE,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID_COLOR,
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "pdf.fonttype": 42,
            "svg.hashsalt": "adaptengine",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.03,
        }
    )


def figure(width: float = SINGLE_COL, height: float | None = None, ncols: int = 1, nrows: int = 1):
    return plt.subplots(nrows, ncols, figsize=(width, height or width * ASPECT), squeeze=False)


def save(fig, out_dir: str, name: str) -> list[str]:
    """Write <name>.pdf and <name>.png with fixed metadata, so re-rendering is byte-identical."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for ext, meta in (
        (
            "pdf",
            {
                "CreationDate": None,
                "ModDate": None,
                "Producer": "AdaptEngine",
                "Creator": "AdaptEngine",
            },
        ),
        ("png", {"Software": None}),
    ):
        p = os.path.join(out_dir, f"{name}.{ext}")
        fig.savefig(p, dpi=PNG_DPI, metadata=meta)
        paths.append(p)
    plt.close(fig)
    return paths
