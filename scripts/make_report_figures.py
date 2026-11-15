#!/usr/bin/env python3
"""Report-ready figures from the E1–E3 results (read-only on experiments/results/*.json).

  python scripts/make_report_figures.py      # -> docs/figures/report/fig*.png + .pdf

Lives outside experiments/ so it is not covered by the pre-registered experiment hash.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES = os.path.join(ROOT, "experiments", "results")
OUT = os.path.join(ROOT, "docs", "figures", "report")

# Reference palette (dataviz skill, light mode)
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASE = "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # first three slots: valid all-pairs
NEUTRAL = "#898781"  # reference arm (static_loop)
WIN, TIE, LOSS = "#2a78d6", "#d6d5cf", "#e34948"  # diverging poles + neutral midpoint
DIVERGING = LinearSegmentedColormap.from_list("bwr", ["#b8312f", "#e34948", "#f0efec", "#2a78d6", "#184f95"])

ARM_LABEL = {
    "product": "product (shipped)",
    "product_nodx": "product, no diagnostic",
    "product_norev": "product, no reviews",
    "product_consol": "product + consolidation",
    "product_noreplan": "product, no replanning",
    "w8_final": "w8_final (old W8 config)",
    "static": "static plan",
    "static_loop": "static_loop",
    "random_eligible": "random eligible",
}
HEADLINE = "S1|4node_x10|B15|calm|h14"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 9,
        "axes.facecolor": SURFACE,
        "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": BASE,
        "axes.labelcolor": INK2,
        "axes.titlecolor": INK,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK2,
        "ytick.labelcolor": INK2,
        "axes.grid": False,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "legend.labelcolor": INK2,
    }
)


def load(name):
    with open(os.path.join(RES, f"{name}.json")) as f:
        return json.load(f)


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.join(OUT, name + ".{png,pdf}"))


def verdict(ci):
    lo, hi = ci
    return "win" if lo > 0 else "loss" if hi < 0 else "tie"


def fig1_win_tie_loss(g):
    """Cells where each arm beats / ties / loses to static_loop (paired 95% CI), primary grid."""
    arms = ["product", "product_nodx", "product_norev", "product_consol", "w8_final"]
    prim = [c for c in g["cells"].values() if c["grid"] == "primary"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 2.9), sharey=True)
    for ax, metric, title in zip(
        axes, ("goal_mastery", "all_required"), ("Goal concept mastered", "All required concepts mastered")
    ):
        counts = {a: defaultdict(int) for a in arms}
        for c in prim:
            for a in arms:
                counts[a][verdict(c["paired_vs_static_loop"][a][metric]["ci95"])] += 1
        y = np.arange(len(arms))[::-1]
        left = np.zeros(len(arms))
        for key, col, lab in (("win", WIN, "better"), ("tie", TIE, "no clear difference"), ("loss", LOSS, "worse")):
            v = np.array([counts[a][key] for a in arms])
            ax.barh(y, v, left=left, color=col, height=0.62, edgecolor=SURFACE, linewidth=1.5, label=lab)
            for yi, li, vi in zip(y, left, v):
                if vi >= 14:
                    ax.text(li + vi / 2, yi, str(vi), ha="center", va="center", fontsize=8,
                            color="#ffffff" if col != TIE else INK)
            left += v
        ax.set_title(title)
        ax.set_xlim(0, len(prim))
        ax.set_xlabel(f"primary cells (of {len(prim)})")
        ax.set_yticks(y, [ARM_LABEL[a] for a in arms])
        ax.tick_params(axis="y", length=0)
    axes[0].legend(loc="upper center", bbox_to_anchor=(1.05, -0.28), ncol=3)
    fig.suptitle("Versus static_loop, paired 95% bootstrap CI per cell (200 seeds each)",
                 x=0.01, ha="left", fontsize=9, color=INK2, y=1.02)
    save(fig, "fig1_win_tie_loss_vs_static_loop")


def fig2_headline_deltas(g):
    """Headline cell (N=1000): paired difference vs static_loop for every arm, with 95% CI."""
    cell = g["cells"][HEADLINE]
    arms = ["product", "product_nodx", "product_norev", "product_consol", "w8_final",
            "product_noreplan", "static", "random_eligible"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), sharey=True)
    y = np.arange(len(arms))[::-1]
    for ax, metric, title in zip(axes, ("goal_mastery", "all_required"),
                                 ("Goal concept mastered", "All required concepts mastered")):
        for yi, a in zip(y, arms):
            d = cell["paired_vs_static_loop"][a][metric]
            lo, hi = d["ci95"]
            col = SERIES[0] if a != "w8_final" else SERIES[1]
            ax.plot([lo, hi], [yi, yi], color=col, lw=2, solid_capstyle="round")
            ax.plot(d["diff"], yi, "o", ms=6, color=col, mec=SURFACE, mew=1.5)
            ax.text(hi + 0.015, yi, f"{d['diff']:+.3f}", va="center", fontsize=7.5, color=INK2)
        ax.axvline(0, color=BASE, lw=1)
        ax.grid(axis="x")
        ax.set_axisbelow(True)
        ax.set_title(title)
        ax.set_xlabel("difference vs static_loop (rate)")
        ax.set_xlim(-0.75, 0.45)
        ax.set_yticks(y, [ARM_LABEL[a] for a in arms])
        ax.tick_params(axis="y", length=0)
    fig.suptitle(f"Headline cell {HEADLINE}, N = 1000 paired learners; dot = mean, bar = 95% CI",
                 x=0.01, ha="left", fontsize=9, color=INK2, y=1.02)
    save(fig, "fig2_headline_paired_differences")


def fig3_km(g):
    """Headline cell: cumulative share of learners with the goal mastered vs minutes studied."""
    arms = [("product", SERIES[0], "-"), ("w8_final", SERIES[1], "-"),
            ("product_consol", SERIES[2], "-"), ("static_loop", NEUTRAL, "--")]
    cell = g["cells"][HEADLINE]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for a, col, ls in arms:
        pts = np.array(cell["arms"][a]["km_curve"])
        t, s = pts[:, 0], 1 - pts[:, 1]
        x = cell["arms"][a]
        ax.plot(t, s, drawstyle="steps-post", color=col, lw=1.8, ls=ls, solid_joinstyle="miter",
                label=f"{ARM_LABEL[a]}  (goal rate {x['goal_mastery_rate']:.2f}, "
                f"budget used {x['minute_utilisation']:.2f})")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.set_ylim(0, 1)
    ax.set_xlim(0, None)
    ax.set_xlabel("minutes of study")
    ax.set_ylabel("share with goal mastered")
    ax.set_title("Time to goal mastery, headline cell (Kaplan–Meier)")
    ax.legend(loc="lower right")
    ax.text(0, -0.2, "Starts at ~0.25: learners who already knew the goal on day 0. Unmastered episodes are "
            "censored at minutes used,\nso an arm that stops early (product uses 64% of its budget) gets an "
            "optimistic curve; compare the goal rates in the legend.", transform=ax.transAxes, fontsize=7,
            color=MUTED, va="top")
    save(fig, "fig3_km_headline")


def fig4_heatmap(g):
    """Mean paired Δ all-required mastery vs static_loop by world × (curriculum, horizon)."""
    worlds = ["S0", "S1", "S4", "S4F"]
    cols = [(c, h) for c in ("4node_x10", "8node_x10") for h in ("hw7", "h7", "h14", "h21")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 2.9), sharey=True)
    for ax, arm in zip(axes, ("product", "w8_final")):
        acc = defaultdict(list)
        for cid, c in g["cells"].items():
            if c["grid"] != "primary":
                continue
            w, cur, _b, _s, h = cid.split("|")
            acc[(w, cur, h)].append(c["paired_vs_static_loop"][arm]["all_required"]["diff"])
        m = np.array([[np.mean(acc[(w, cur, h)]) for cur, h in cols] for w in worlds])
        im = ax.imshow(m, cmap=DIVERGING, vmin=-0.5, vmax=0.5, aspect="auto")
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                ax.text(j, i, f"{m[i, j]:+.2f}", ha="center", va="center", fontsize=7.5,
                        color="#ffffff" if abs(m[i, j]) > 0.3 else INK)
        ax.set_xticks(range(len(cols)), [f"{h}\n{cur.split('_')[0]}" for cur, h in cols], fontsize=7.5)
        ax.set_yticks(range(len(worlds)), worlds)
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.axvline(3.5, color=SURFACE, lw=3)
        ax.set_title(ARM_LABEL[arm])
    cb = fig.colorbar(im, ax=axes, shrink=0.9, pad=0.02)
    cb.set_label("Δ all-required mastery vs static_loop", color=INK2)
    cb.outline.set_visible(False)
    fig.suptitle("Mean of per-cell paired differences over budgets and scenarios (blue = adaptive arm better)",
                 x=0.01, ha="left", fontsize=9, color=INK2, y=1.04)
    save(fig, "fig4_heatmap_allreq_vs_static_loop")


def fig5_diag_auc(d):
    """E2: diagnostic AUC per arm across the 16 world × curriculum cells."""
    arms = ["product", "product_goalpath", "fixed@n", "random@n", "irt_cat@n",
            "frontier", "concept_sweep_w7", "state_space"]
    label = {
        "product": "product (all concepts)",
        "product_goalpath": "product, goal path (shipped)",
        "fixed@n": "fixed order, same items",
        "random@n": "random order, same items",
        "irt_cat@n": "IRT-CAT, same items",
        "frontier": "frontier",
        "concept_sweep_w7": "concept sweep (W7/W8)",
        "state_space": "state space (≤12 concepts)",
    }
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    y = np.arange(len(arms))[::-1]
    for yi, a in zip(y, arms):
        v = [c["arms"][a]["auc"] for c in d["cells"].values() if a in c["arms"]]
        ax.plot(v, [yi] * len(v), "o", ms=4, color=SERIES[0], alpha=0.35, mew=0)
        ax.plot(np.mean(v), yi, "D", ms=7, color=INK, mec=SURFACE, mew=1.5)
        ax.text(1.02, yi, f"{np.mean(v):.3f}  (n={len(v)})", va="center", fontsize=7.5, color=INK2,
                transform=ax.get_yaxis_transform())
    ax.axvline(0.5, color=BASE, lw=1, ls="--")
    ax.text(0.503, -0.6, "chance", fontsize=7, color=MUTED)
    ax.set_xlim(0.45, 0.95)
    ax.set_ylim(-0.8, len(arms) - 0.5)
    ax.set_yticks(y, [label[a] for a in arms])
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x")
    ax.set_axisbelow(True)
    ax.set_xlabel("AUC for day-0 mastery (truth θ ≥ 0.70)")
    ax.set_title("Diagnostic accuracy: dots = cells, diamond = mean")
    save(fig, "fig5_diagnostic_auc")


def fig6_sensitivity(s):
    """E3: paired Δ goal mastery vs product for each one-at-a-time config, over the 6 cells."""
    cfgs = defaultdict(list)
    for c in s["cells"].values():
        for k, v in c["paired_vs_product"].items():
            cfgs[k].append(v["goal_mastery"]["diff"])
    rows = sorted(cfgs.items(), key=lambda kv: np.mean(kv[1]))
    fig, ax = plt.subplots(figsize=(6.4, 0.24 * len(rows) + 1))
    for yi, (k, v) in enumerate(rows):
        m = np.mean(v)
        col = NEUTRAL if k == "static_loop" or abs(m) < 5e-4 else (WIN if m > 0 else LOSS)
        ax.plot([min(v), max(v)], [yi, yi], color=col, lw=1.5, alpha=0.5, solid_capstyle="round")
        ax.plot(m, yi, "o", ms=5, color=col, mec=SURFACE, mew=1)
    ax.axvline(0, color=BASE, lw=1)
    ax.set_yticks(range(len(rows)), [k for k, _ in rows], fontsize=7.5)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x")
    ax.set_axisbelow(True)
    ax.set_xlabel("Δ goal mastery vs product (dot = mean of 6 cells, line = min–max)")
    ax.set_title("Sensitivity: one setting changed at a time from product")
    save(fig, "fig6_sensitivity")


def main():
    g = load("grid")
    fig1_win_tie_loss(g)
    fig2_headline_deltas(g)
    fig3_km(g)
    fig4_heatmap(g)
    fig5_diag_auc(load("diag_matrix"))
    fig6_sensitivity(load("sensitivity"))


if __name__ == "__main__":
    main()
