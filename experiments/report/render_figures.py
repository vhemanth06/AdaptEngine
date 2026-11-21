"""report/data/*.csv -> report/figures/*.pdf and *.png. Reads only report/data/ (V2-TC11).

All styling comes from style.py; restyle with `make exp-figures`.

    python -m experiments.report.render_figures [--data DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict

from . import style as S

V2 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(V2, "report", "data")
OUT = os.path.join(V2, "report", "figures")


def rows(data_dir: str, name: str) -> list[dict]:
    with open(os.path.join(data_dir, f"{name}.csv"), encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["status"] == "ok"]


def num(v):
    return None if v in ("", None) else float(v)


def _empty(ax, text="not run"):
    ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes, color=S.P["grey"])
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(False)


def f1(data_dir, out):
    rs = rows(data_dir, "f1_violations")
    fig, ax = S.figure()
    ax = ax[0][0]
    if not rs:
        _empty(ax)
    else:
        arms = [r["arm"] for r in rs]
        vals = [num(r["executed_violations"]) for r in rs]
        ax.bar(arms, [v + 1 for v in vals], color=[S.color(a) for a in arms])
        ax.set_yscale("log")
        for i, v in enumerate(vals):
            ax.text(i, v + 1, f"{int(v)}", ha="center", va="bottom", fontsize=S.FONT_SIZE - 1)
        ax.set_ylabel("executed violations + 1 (log)")
        ax.tick_params(axis="x", rotation=30)
    ax.set_title("Executed prerequisite violations per arm (E1)")
    return S.save(fig, out, "F1_violations")


def f2(data_dir, out):
    rs = rows(data_dir, "f2_diagnostic_detail")
    fig, ax = S.figure(S.DOUBLE_COL / 1.6)
    ax = ax[0][0]
    if not rs:
        _empty(ax)
    else:
        acc = defaultdict(list)
        for r in rs:
            acc[(r["arm"], r["world"])].append((num(r["questions"]), num(r["brier"])))
        seen = set()
        for (arm, w), pts in sorted(acc.items()):
            q = sum(p[0] for p in pts) / len(pts)
            b = sum(p[1] for p in pts) / len(pts)
            ax.scatter(
                q,
                b,
                color=S.color(arm),
                marker=S.MARKERS.get(w, "o"),
                s=22,
                label=arm if arm not in seen else None,
            )
            seen.add(arm)
        for w, m in S.MARKERS.items():
            if any(k[1] == w for k in acc):
                ax.scatter([], [], color=S.P["black"], marker=m, s=18, label=w)
        ax.set_xlabel("questions asked (mean over curricula)")
        ax.set_ylabel("Brier vs true mastery")
        ax.legend(ncol=2, loc="best")
    ax.set_title("Diagnostic accuracy vs question cost (E2)")
    return S.save(fig, out, "F2_brier_vs_questions")


def _reliability(ax, rs, key, title):
    ax.plot([0, 1], [0, 1], color=S.P["grey"], linestyle="--", linewidth=0.8)
    groups = defaultdict(list)
    for r in rs:
        if r["n"] not in ("", "0"):
            groups[r[key]].append((num(r["mean_p"]), num(r["freq"])))
    for g, pts in sorted(groups.items()):
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", color=S.color(g), label=g)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("predicted P(correct)")
    ax.set_ylabel("observed frequency")
    ax.set_title(title)
    if groups:
        ax.legend(loc="upper left")


def f3(data_dir, out):
    rs = rows(data_dir, "f3_reliability_realdata")
    fig, axes = S.figure(S.DOUBLE_COL, S.DOUBLE_COL * 0.42, ncols=2)
    for ax, (ds, title) in zip(
        axes[0], (("assist09", "ASSISTments 2009"), ("ct", "Cognitive Tutor"))
    ):
        sub = [r for r in rs if r["dataset"] == ds]
        if sub:
            _reliability(ax, sub, "model", title + " (held out)")
        else:
            _empty(ax, f"{title}: not run")
    return S.save(fig, out, "F3_reliability_realdata")


def f3b(data_dir, out):
    rs = rows(data_dir, "f3b_attempt_reliability")
    fig, ax = S.figure()
    ax = ax[0][0]
    if rs:
        _reliability(ax, rs, "world", "Engine P(correct) on executed attempts (E1)")
    else:
        _empty(ax)
    return S.save(fig, out, "F3b_reliability_attempts")


def f4(data_dir, out):
    rs = rows(data_dir, "f4_goal_vs_minutes")
    fig, ax = S.figure(S.DOUBLE_COL / 1.6)
    ax = ax[0][0]
    if not rs:
        _empty(ax)
    else:
        seen = set()
        for r in rs:
            arm, w = r["arm"], r["world"]
            ax.scatter(
                num(r["total_minutes"]),
                num(r["goal_mastery"]),
                color=S.color(arm),
                marker=S.MARKERS.get(w, "o"),
                s=22,
                label=arm if arm not in seen else None,
            )
            seen.add(arm)
        for w, m in S.MARKERS.items():
            if any(r["world"] == w for r in rs):
                ax.scatter([], [], color=S.P["black"], marker=m, s=18, label=w)
        ax.set_xlabel("total minutes (diagnostic + study), mean over curricula")
        ax.set_ylabel("goal mastery rate")
        ax.legend(ncol=2, loc="best")
    ax.set_title("Goal mastery vs total minutes (E4)")
    return S.save(fig, out, "F4_goal_vs_minutes")


def f5(data_dir, out):
    rs = rows(data_dir, "f5_retention")
    fig, ax = S.figure()
    ax = ax[0][0]
    if not rs:
        _empty(ax)
    else:
        x = range(len(rs))
        w = 0.38
        ax.bar(
            [i - w / 2 for i in x],
            [num(r["retention_reviewed"]) or 0 for r in rs],
            w,
            label="reviewed",
            color=S.P["blue"],
        )
        ax.bar(
            [i + w / 2 for i in x],
            [num(r["retention_not_reviewed"]) or 0 for r in rs],
            w,
            label="not reviewed",
            color=S.P["orange"],
        )
        ax.set_xticks(list(x), [r["arm"] for r in rs], rotation=20)
        ax.set_ylabel("retention (final θ / peak θ)")
        ax.set_ylim(0, 1)
        ax.legend()
    ax.set_title("Spaced review, forgetting_21 cells (E1)")
    return S.save(fig, out, "F5_retention")


def f6(data_dir, out):
    cold, rep = rows(data_dir, "t13_cold_latency"), rows(data_dir, "t13b_replan_latency")
    fig, axes = S.figure(S.DOUBLE_COL, S.DOUBLE_COL * 0.4, ncols=2)
    for ax, rs, title in (
        (axes[0][0], cold, "Cold start"),
        (axes[0][1], rep, "Replan (mean over events)"),
    ):
        if not rs:
            _empty(ax)
            continue
        curricula = list(dict.fromkeys(r["curriculum"] for r in rs))
        planners = list(dict.fromkeys(r["planner"] for r in rs))
        w = 0.8 / len(planners)
        for j, p in enumerate(planners):
            vals = []
            for c in curricula:
                v = [num(r["mean_ms"]) for r in rs if r["curriculum"] == c and r["planner"] == p]
                vals.append(sum(v) / len(v) if v else 0)
            ax.bar(
                [i + (j - (len(planners) - 1) / 2) * w for i in range(len(curricula))],
                vals,
                w,
                label=p,
                color=S.color(p),
            )
        ax.set_xticks(range(len(curricula)), curricula, rotation=20)
        ax.set_yscale("log")
        ax.set_ylabel("ms (log)")
        ax.set_title(title)
        ax.legend()
    return S.save(fig, out, "F6_latency")


def _heat(ax, fig, xs, ys, val, title, xlabel, ylabel, cmap, center=True):
    import numpy as np

    m = np.full((len(ys), len(xs)), np.nan)
    for (x, y), v in val.items():
        if v is not None:
            m[ys.index(y), xs.index(x)] = v
    lim = np.nanmax(np.abs(m)) if np.isfinite(m).any() else 1
    im = ax.imshow(
        m, cmap=cmap, vmin=-lim if center else None, vmax=lim if center else None, aspect="auto"
    )
    ax.set_xticks(range(len(xs)), [str(x) for x in xs], rotation=30, ha="right")
    ax.set_yticks(range(len(ys)), [str(y) for y in ys])
    for i in range(len(ys)):
        for j in range(len(xs)):
            if np.isfinite(m[i, j]):
                ax.text(
                    j,
                    i,
                    f"{m[i, j]:+.2f}" if center else f"{m[i, j]:.2f}",
                    ha="center",
                    va="center",
                    fontsize=S.FONT_SIZE - 2,
                )
    ax.grid(False)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, shrink=0.8)


def f7(data_dir, out):
    rs = rows(data_dir, "f7_adapt_static_heatmap")
    fig, ax = S.figure(S.DOUBLE_COL, S.DOUBLE_COL * 0.38)
    ax = ax[0][0]
    if not rs:
        _empty(ax)
    else:
        scen = list(dict.fromkeys(r["scenario"] for r in rs))
        worlds = sorted({r["world"] for r in rs})
        _heat(
            ax,
            fig,
            scen,
            worlds,
            {(r["scenario"], r["world"]): num(r["mean_diff"]) for r in rs},
            "Adapt − static goal mastery, mean over curricula and budgets (E1)",
            "scenario",
            "world",
            S.DIVERGING,
        )
    return S.save(fig, out, "F7_adapt_static_heatmap")


def f8(data_dir, out):
    rs = rows(data_dir, "f8_theta_k")
    fig, ax = S.figure()
    ax = ax[0][0]
    if not rs:
        _empty(ax)
    else:
        ks = sorted({int(num(r["k"])) for r in rs})
        ts = sorted({num(r["theta"]) for r in rs})
        _heat(
            ax,
            fig,
            ks,
            ts,
            {(int(num(r["k"])), num(r["theta"])): num(r["minus_static"]) for r in rs},
            "θ × k: adapt − static goal mastery (E6)",
            "k (responses)",
            "θ (threshold)",
            S.DIVERGING,
        )
    return S.save(fig, out, "F8_theta_k")


def f9(data_dir, out):
    rs = rows(data_dir, "f9_scans")
    params = [p for p in dict.fromkeys(r["parameter"] for r in rs) if p not in ("baseline",)]
    n = max(1, len(params))
    ncols = 4
    nrows = (n + ncols - 1) // ncols
    fig, axes = S.figure(S.DOUBLE_COL, S.DOUBLE_COL * 0.24 * nrows, ncols=ncols, nrows=nrows)
    flat = [a for row in axes for a in row]
    if not params:
        _empty(flat[0])
    for ax, p in zip(flat, params):
        sub = [r for r in rs if r["parameter"] == p]
        series = defaultdict(list)
        for r in sub:
            series[(r["world"], r["curriculum"])].append((r["value"], num(r["goal_mastery"])))
        for (w, c), pts in sorted(series.items()):
            ax.plot(
                [x for x, _ in pts],
                [y for _, y in pts],
                marker="o",
                color=S.color(w),
                linestyle="-" if c == "8node_x10" else ":" if c == "4-node" else "--",
                label=f"{w} {c}",
            )
        ax.set_title(p)
        ax.set_ylim(0, 1)
        ax.tick_params(axis="x", rotation=30)
    for ax in flat[len(params) :]:
        ax.axis("off")
    if params:
        flat[0].set_ylabel("goal mastery rate")
        flat[0].legend(fontsize=S.FONT_SIZE - 2, loc="lower left")
    return S.save(fig, out, "F9_scans")


FIGURES = (f1, f2, f3, f3b, f4, f5, f6, f7, f8, f9)


def main(data_dir: str = DATA, out_dir: str = OUT) -> list[str]:
    S.setup()
    out = []
    for fn in FIGURES:
        out += fn(data_dir, out_dir)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    print(f"{len(main(a.data, a.out))} figure files written")
