#!/usr/bin/env python3
"""Build docs/WEEK7_RESULTS.md (tables) and docs/figures/w7_*.png from the W7 results files.

Every number comes from experiments/results/*.json; nothing is typed by hand. Run after
run_w7_grid.py, run_sensitivity.py, run_diag_matrix.py, run_diag_selection.py,
run_w7_latency.py and the fitting scripts. Needs matplotlib (`pip install -e .[figures]`).
"""

from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES = os.path.join(ROOT, "experiments", "results")
FIG = os.path.join(ROOT, "docs", "figures")
WORLDS = ("S0", "S1", "S2", "S3", "S4")
SCEN = (
    "calm",
    "missed_day",
    "budget_drop",
    "deadline_cut",
    "missed_2days",
    "budget_crash",
    "deadline_halved",
    "forgetting_21",
)
# Okabe-Ito (colour-blind safe)
OI = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]


def load(name):
    p = os.path.join(RES, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def ci(d):
    return f"{d['diff']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]"


def sig(d):
    lo, hi = d["ci95"]
    return "+" if lo > 0 else "−" if hi < 0 else "≈"


def pct(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def grid_section(g, out):
    cells, meta = g["cells"], g["metadata"]
    out.append("## 1. Closed-loop evaluation grid (T4.4)\n")
    out.append(
        f"Source: `experiments/results/w7_grid.json` (`python experiments/run_w7_grid.py`), "
        f"code_hash `{meta['code_hash'][:12]}…`, {len(cells)} cells, runtime "
        f"{meta['runtime_s']} s on {meta['processes']} processes. Pre-registration: "
        f"`{meta['preregistration']}`. N = {meta['n_per_cell']} paired learners per cell; "
        f"headline cells N = {meta['n_headline']}.\n"
    )
    # H1
    tot = {
        a: sum(c["arms"][a]["executed_prereq_violations"] for c in cells.values() if a in c["arms"])
        for a in ("adapt", "adapt_expected", "no_review", "no_replan", "static")
    }
    out.append("### 1.1 H1 — executed prerequisite violations, summed over every cell\n")
    out.append("| Arm | Executed violations (all cells) |\n|---|---|")
    out += [f"| {a} | {v} |" for a, v in tot.items()]
    out.append("")
    # Headline
    out.append("### 1.2 Headline cells (4-node, B = 15, calm, N = 1000)\n")
    for w in ("S1", "S0"):
        c = cells[f"{w}|4-node|B15|calm"]
        out.append(f"**{w}** (horizon {c['deadline']} days)\n")
        out.append(
            "| Arm | Goal mastery rate | Mean goal θ | All required | Minutes | Exec. viol. "
            "(learners) | Idle days | adapt-arm − static: mastery / θ / θ at equal minutes |"
        )
        out.append("|---|---|---|---|---|---|---|---|")
        for a, r in c["arms"].items():
            pv = c["paired_vs_static"].get(a)
            diff = (
                f"{ci(pv['goal_mastery'])} / {ci(pv['goal_theta'])} / "
                f"{ci(pv['goal_theta_equal_minutes'])}"
                if pv
                else "—"
            )
            out.append(
                f"| {a} | {pct(r['goal_mastery_rate'])} | {r['mean_goal_theta']:.4f} | "
                f"{pct(r['all_required_rate'])} | {r['mean_minutes']:.1f} | "
                f"{r['executed_prereq_violations']} ({r['learners_with_executed_violations']}) | "
                f"{r['idle_days']} | {diff} |"
            )
        out.append("")
    # Robustness matrix
    for cur in ("4-node", "8-node", "synth-20"):
        out.append(
            f"### 1.3 Robustness matrix — {cur}, B = 15: adapt − static goal mastery rate "
            "[95% CI]; executed violations adapt / static\n"
        )
        out.append("| Scenario | " + " | ".join(WORLDS) + " |")
        out.append("|---|" + "---|" * len(WORLDS))
        for sc in SCEN:
            row = []
            for w in WORLDS:
                c = cells.get(f"{w}|{cur}|B15|{sc}")
                if not c:
                    row.append("n/a")
                    continue
                d = c["paired_vs_static"]["adapt"]["goal_mastery"]
                row.append(
                    f"{ci(d)}; {c['arms']['adapt']['executed_prereq_violations']}"
                    f"/{c['arms']['static']['executed_prereq_violations']}"
                )
            out.append(f"| {sc} | " + " | ".join(row) + " |")
        out.append("")
    # Win/tie/loss summary over all cells
    out.append("### 1.4 Summary over every cell: adapt vs static goal mastery rate (paired CI)\n")
    out.append("| World | Curriculum | adapt better | no sig. difference | adapt worse |")
    out.append("|---|---|---|---|---|")
    for w in WORLDS:
        for cur in ("4-node", "8-node", "synth-20"):
            s = [
                sig(c["paired_vs_static"]["adapt"]["goal_mastery"])
                for k, c in cells.items()
                if k.startswith(f"{w}|{cur}|")
            ]
            out.append(f"| {w} | {cur} | {s.count('+')} | {s.count('≈')} | {s.count('−')} |")
    out.append("")
    # Forgetting
    out.append("### 1.5 Spaced review (forgetting_21, fast_forgetter, 21 days, B = 15)\n")
    out.append(
        "| World | Curriculum | adapt − no_review θ (h = 30) | adapt_h7 − no_review_h7 θ "
        "(h = 7) | retention reviewed / not (adapt_h7) |"
    )
    out.append("|---|---|---|---|---|")
    for w in WORLDS:
        for cur in ("4-node", "8-node", "synth-20"):
            c = cells.get(f"{w}|{cur}|B15|forgetting_21")
            if not c:
                continue
            a7 = c["arms"]["adapt_h7"]
            out.append(
                f"| {w} | {cur} | {ci(c['paired_adapt_vs']['no_review']['goal_theta'])} | "
                f"{ci(c['paired_adapt_h7_vs_no_review_h7']['goal_theta'])} | "
                f"{a7['retention_reviewed']} / {a7['retention_not_reviewed']} |"
            )
    out.append("")
    # Expected projection
    out.append("### 1.6 Expected-workload projection (T2.5): adapt − adapt_expected, B = 15\n")
    out.append("| World | " + " | ".join(SCEN[:4]) + " |")
    out.append("|---|" + "---|" * 4)
    for w in WORLDS:
        row = [
            ci(cells[f"{w}|4-node|B15|{sc}"]["paired_adapt_vs"]["adapt_expected"]["goal_mastery"])
            for sc in SCEN[:4]
        ]
        out.append(f"| {w} (4-node) | " + " | ".join(row) + " |")
    out.append("")
    # Calibration of P(correct)
    out.append("### 1.7 Engine P(correct) on executed attempts (adapt, 4-node, B = 15, calm)\n")
    out.append("| World | Brier | AUC |\n|---|---|---|")
    for w in WORLDS:
        r = cells[f"{w}|4-node|B15|calm"]["arms"]["adapt"]
        out.append(f"| {w} | {r['brier']} | {r['auc']} |")
    out.append("")
    # Figure: forest plot
    fig, ax = plt.subplots(figsize=(9, 7))
    y = 0
    labels = []
    for wi, w in enumerate(WORLDS):
        for sc in SCEN:
            c = cells.get(f"{w}|4-node|B15|{sc}")
            if not c:
                continue
            d = c["paired_vs_static"]["adapt"]["goal_mastery"]
            ax.errorbar(
                d["diff"],
                y,
                xerr=[[d["diff"] - d["ci95"][0]], [d["ci95"][1] - d["diff"]]],
                fmt="o",
                color=OI[wi],
                capsize=2,
            )
            labels.append(f"{w} {sc}")
            y += 1
    ax.axvline(0, color="grey", lw=1)
    ax.set_yticks(range(len(labels)), labels, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("adapt − static goal true-mastery rate (paired 95% CI)")
    ax.set_title("4-node, budget 15, N = 200 (headline cells N = 1000)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "w7_forest_adapt_vs_static.png"), dpi=130)
    plt.close(fig)
    out.append("![adapt vs static forest plot](figures/w7_forest_adapt_vs_static.png)\n")


def prereg_section(pre, g, out, fix1=None):
    out.append("### 1.8 Pre-registered run vs re-run after the Defect-7 fix (H1)\n")
    out.append(
        f"The registered run (`w7_grid_prereg.json`, code_hash `{pre['metadata']['code_hash'][:12]}…`)"
        " found executed violations in the review-enabled arms; the scheduler fix (reviews and "
        "remediation obey the prerequisite gate) was applied and the grid re-run "
        f"(`w7_grid.json`, code_hash `{g['metadata']['code_hash'][:12]}…`). Both are reported.\n"
    )
    runs = [pre] + ([fix1] if fix1 else []) + [g]
    heads = (
        ["registered run"]
        + (["after fix 1 (tiers 0/1 gated)"] if fix1 else [])
        + ["final (gate = prerequisite satisfied)"]
    )
    out.append("| Arm | " + " | ".join(f"Executed violations, {h} (cells)" for h in heads) + " |")
    out.append("|---|" + "---|" * len(heads))
    for a in (
        "adapt",
        "adapt_expected",
        "no_review",
        "adapt_h7",
        "no_review_h7",
        "no_replan",
        "static",
    ):
        row = []
        for d in runs:
            cs = [
                c["arms"][a]["executed_prereq_violations"]
                for c in d["cells"].values()
                if a in c["arms"]
            ]
            row.append(f"{sum(cs)} ({sum(1 for x in cs if x)})")
        out.append(f"| {a} | " + " | ".join(row) + " |")
    out.append("")


def s4fitted_section(r, out):
    out.append("## 5. S4-fitted world (T7.5, exploratory, not pre-registered)\n")
    out.append(
        f"Profile `{r['metadata']['profile']}`; 4-node, B = 15, N = {r['metadata']['n']}; "
        f"code_hash `{r['metadata']['code_hash'][:12]}…`.\n"
    )
    out.append(
        "| Scenario | Arm | Goal mastery | Δ vs static [95% CI] | All required | Minutes | "
        "Exec. viol. |"
    )
    out.append("|---|---|---|---|---|---|---|")
    for sc in ("calm", "missed_day"):
        for a, v in r[sc].items():
            out.append(
                f"| {sc} | {a} | {pct(v['goal_mastery_rate'])} | {ci(v['vs_static_goal_mastery'])}"
                f" | {pct(v['all_required_rate'])} | {v['mean_minutes']} | "
                f"{v['executed_prereq_violations']} |"
            )
    out.append("")


def fit_section(fits, sim, out):
    out.append("## 6. Calibration: heuristic vs fitted BKT parameters (T3.5, T6.3, T7.3, T7.6)\n")
    out.append("| Data | Model | RMSE | Brier | Log-loss | AUC | ECE |")
    out.append("|---|---|---|---|---|---|---|")
    for name, f in fits.items():
        if not f:
            continue
        for m, v in f["heldout"]["pooled_oof"].items():
            out.append(
                f"| {name} | {m} | {v['rmse']:.4f} | {v['brier']:.4f} | {v['logloss']:.4f} | "
                f"{v['auc']:.4f} | {v['ece']:.4f} |"
            )
    if sim:
        for w in ("S0", "S4"):
            for m, v in sim[w]["heldout"].items():
                out.append(
                    f"| simulated {w} (held-out learners) | {m} | {v['rmse']:.4f} | {v['brier']:.4f}"
                    f" | {v['logloss']:.4f} | {v['auc']:.4f} | {v['ece']:.4f} |"
                )
    out.append("")
    f = fits.get("ASSISTments 2009 (5-fold by student)")
    if f:
        fig, ax = plt.subplots(figsize=(5, 5))
        for i, m in enumerate(("fitted_class_profile", "heuristic_class_D6")):
            rel = [b for b in f["heldout"]["pooled_oof"][m]["reliability"] if b["n"]]
            ax.plot(
                [b["mean_pred"] for b in rel],
                [b["obs_rate"] for b in rel],
                "o-",
                color=OI[i],
                label=m,
            )
        ax.plot([0, 1], [0, 1], color="grey", lw=1, ls="--", label="perfect calibration")
        ax.set_xlabel("predicted P(correct)")
        ax.set_ylabel("observed rate")
        ax.set_title("ASSISTments 2009, held-out reliability")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, "w7_reliability_assist09.png"), dpi=130)
        plt.close(fig)
        out.append("![reliability ASSISTments](figures/w7_reliability_assist09.png)\n")


def sensitivity_section(s, out):
    out.append("## 2. Sensitivity analysis (WP5)\n")
    m = s["metadata"]
    out.append(
        f"Source: `experiments/results/w7_sensitivity.json` (`python experiments/run_sensitivity.py`)"
        f", code_hash `{m['code_hash'][:12]}…`; {m['scenario']}, budget {m['budget']}, "
        f"N = {m['n']}, arm adapt (static shown for reference).\n"
    )
    for cell, rows in s["cells"].items():
        out.append(f"### {cell}\n")
        out.append(
            "| Setting | Goal mastery | Δ vs baseline [95% CI] | Minutes | Δ minutes [95% CI] | "
            "Exec. viol. | All required |"
        )
        out.append("|---|---|---|---|---|---|---|")
        for lab, r in rows.items():
            out.append(
                f"| {lab} | {pct(r['goal_mastery_rate'])} | {ci(r['vs_baseline_goal_mastery'])} | "
                f"{r['mean_minutes']:.1f} | {ci(r['vs_baseline_minutes'])} | "
                f"{r['executed_prereq_violations']} | {pct(r['all_required_rate'])} |"
            )
        out.append("")
    # Tornado on S1|4-node
    for cell in s["cells"]:
        rows = s["cells"][cell]
        base = rows["baseline"]["goal_mastery_rate"]
        spans = []
        for p in m["scans"]:
            vals = [rows[f"{p}={v}"]["goal_mastery_rate"] for v in m["scans"][p]]
            spans.append((p, min(vals) - base, max(vals) - base))
        spans.sort(key=lambda t: t[2] - t[1])
        fig, ax = plt.subplots(figsize=(7, 3.6))
        for i, (p, lo, hi) in enumerate(spans):
            ax.barh(i, hi - lo, left=lo, color=OI[0])
        ax.set_yticks(range(len(spans)), [t[0] for t in spans])
        ax.axvline(0, color="grey", lw=1)
        ax.set_xlabel(f"goal true-mastery rate − baseline ({100 * base:.1f}%)")
        ax.set_title(f"Tornado: one-at-a-time scans, {cell}")
        fig.tight_layout()
        name = f"w7_tornado_{cell.replace('|', '_')}.png"
        fig.savefig(os.path.join(FIG, name), dpi=130)
        plt.close(fig)
        out.append(f"![tornado {cell}](figures/{name})\n")


def diag_section(sel, mat, out):
    out.append("## 3. Diagnostic (WP3)\n")
    if sel:
        w = sel["winner"]
        out.append(
            "### 3.1 Pre-registered selection (T3.3)\n\nWinner: "
            + ", ".join(f"`{k}={w[k]}`" for k in sorted(w) if k not in ("brier", "items"))
            + "\n"
        )
        out.append("| Arm (held-out) | Brier | Log-loss | AUC | Next-resp. Brier | Items |")
        out.append("|---|---|---|---|---|---|")
        for k, r in sel["heldout"].items():
            out.append(
                f"| {k} | {r['brier']} | {r['log_loss']} | {r['auc']} | "
                f"{r['next_response_brier']} | {r['items']} |"
            )
        out.append("")
        out += [f"- {k}: {ci(v)}" for k, v in sel["heldout_paired"].items()]
        out.append("")
    if mat:
        out.append("### 3.2 Matrix across worlds (T3.7)\n")
        names = list(mat["worlds"]["S0"])
        out.append("| Arm | " + " | ".join(f"{w} Brier (AUC)" for w in mat["worlds"]) + " |")
        out.append("|---|" + "---|" * len(mat["worlds"]))
        for n in names:
            out.append(
                f"| {n} | "
                + " | ".join(
                    f"{mat['worlds'][w][n]['brier']:.4f} ({mat['worlds'][w][n]['auc']})"
                    for w in mat["worlds"]
                )
                + " |"
            )
        out.append("")


def latency_section(lat, out):
    out.append("## 4. Measured improvement: planning latency (T6.1)\n")
    b, a = lat["before_T6_1"]["results"], lat["after_T6_1"]["results"]
    out.append(
        f"Plan identity: {lat['plan_identity']['plans_compared']} plans compared, "
        f"{lat['plan_identity']['different']} different.\n"
    )
    out.append("| Case | Before (ms, mean ± sd) | After | Speed-up |\n|---|---|---|---|")
    for k in b:
        key = "full_plan_ms" if "full_plan_ms" in b[k] else "plan_ms"
        out.append(
            f"| {k} | {b[k][key][0]} ± {b[k][key][1]} | {a[k][key][0]} ± {a[k][key][1]} | "
            f"{b[k][key][0] / a[k][key][0]:.2f}× |"
        )
    out.append("")


def main():
    os.makedirs(FIG, exist_ok=True)
    out = [
        "# AdaptEngine — Week 7 Results\n",
        "Generated by `python experiments/make_w7_results.py` from `experiments/results/*.json`."
        " Do not edit by hand.\n",
    ]
    g = load("w7_grid.json")
    if g:
        grid_section(g, out)
        pre = load("w7_grid_prereg.json")
        if pre:
            prereg_section(pre, g, out, load("w7_grid_fix1.json"))
    s = load("w7_sensitivity.json")
    if s:
        sensitivity_section(s, out)
    diag_section(load("w7_diag_selection.json"), load("w7_diag_matrix.json"), out)
    lat = load("w7_latency.json")
    if lat:
        latency_section(lat, out)
    s4 = load("w7_s4_fitted.json")
    if s4:
        s4fitted_section(s4, out)
    fit_section(
        {
            "ASSISTments 2009 (5-fold by student)": load("bkt_fit_assist09.json"),
            "Cognitive Tutor (5-fold by student)": load("bkt_fit_ct.json"),
        },
        load("bkt_fit_sim.json"),
        out,
    )
    path = os.path.join(ROOT, "docs", "WEEK7_RESULTS.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("wrote", path)


if __name__ == "__main__":
    main()
