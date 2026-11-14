#!/usr/bin/env python3
"""W8 G.3 / B.4: build docs/FINAL_RESULTS.md and docs/figures/final_*.png from results files only.

Inputs (experiments/results/): final_grid.json, w8_calibration_select.json, w8_fits.json,
w8_policy_eval.json, w8_extensions.json, w8_cpsat_eval.json, w8_probe_baseline.json, w8_agent_eval_*.json.
Every number in the output is read from those files.
"""

from __future__ import annotations

import glob
import json
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from experiments.stats import kaplan_meier  # noqa: E402

RES = os.path.join(repo_root, "experiments", "results")
FIG = os.path.join(repo_root, "docs", "figures")
ARMS = [
    "adapt_final",
    "adapt_final_dx",
    "adapt_cal",
    "adapt_w7",
    "static_loop",
    "static",
    "random_eligible",
    "no_replan",
]
ADAPT = ["adapt_final", "adapt_final_dx", "adapt_cal", "adapt_w7"]
WORLDS = ["S0", "S1", "S4", "S4F"]


def load(name):
    p = os.path.join(RES, name)
    return json.load(open(p)) if os.path.exists(p) else None


def f3(x, d=3):
    return "—" if x is None else f"{x:.{d}f}"


def ci(p):
    return f"{p['diff']:+.3f} [{p['ci95'][0]:+.3f}, {p['ci95'][1]:+.3f}]"


def sig(p):
    return 1 if p["ci95"][0] > 0 else -1 if p["ci95"][1] < 0 else 0


def parse(cell):
    w, cur, b, scen, h = cell.split("|")
    return {"world": w, "cur": cur, "budget": b, "scen": scen, "h": h}


def pooled_calib(cells, world, arm):
    sse = n = 0.0
    pos, neg, sp, sy = [0] * 20, [0] * 20, [0.0] * 20, [0] * 20
    for k, c in cells.items():
        if parse(k)["world"] != world or arm not in c["arms"]:
            continue
        a = c["arms"][arm]
        if a.get("brier") is None:
            continue
        sse += a["brier"] * a["n_attempts"]
        n += a["n_attempts"]
        b = a["calibration_bins"]
        for i in range(20):
            pos[i] += b["pos"][i]
            neg[i] += b["neg"][i]
            sp[i] += b["sum_p"][i]
            sy[i] += b["sum_y"][i]
    tp, tn = sum(pos), sum(neg)
    wins, below = 0.0, 0
    for i in range(20):
        wins += pos[i] * (below + 0.5 * neg[i])
        below += neg[i]
    bins = [
        (sp[i] / (pos[i] + neg[i]), sy[i] / (pos[i] + neg[i]), pos[i] + neg[i])
        for i in range(20)
        if pos[i] + neg[i]
    ]
    return {
        "brier": sse / n if n else None,
        "auc": wins / (tp * tn) if tp and tn else None,
        "n": int(n),
        "bins": bins,
    }


def figures(g):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(FIG, exist_ok=True)
    cells = g["cells"]
    out = []
    # 1. forest plot: adapt_final vs static_loop, B15, h14 cells
    rows = [
        (k, c["paired_vs_static_loop"]["adapt_final"]["goal_mastery"])
        for k, c in sorted(cells.items())
        if "|B15|" in k and k.endswith("|h14") and "adapt_final" in c["paired_vs_static_loop"]
    ]
    if rows:
        fig, ax = plt.subplots(figsize=(7, 0.35 * len(rows) + 1))
        for i, (k, p) in enumerate(rows):
            col = "#059669" if sig(p) > 0 else "#e11d48" if sig(p) < 0 else "#71717a"
            ax.plot(p["ci95"], [i, i], color=col, lw=2)
            ax.plot([p["diff"]], [i], "o", color=col)
        ax.axvline(0, color="#999", ls="--", lw=1)
        ax.set_yticks(
            range(len(rows)),
            [k.replace("|B15", "").replace("|h14", "") for k, _ in rows],
            fontsize=8,
        )
        ax.invert_yaxis()
        ax.set_xlabel("goal mastery: adapt (final) − static_loop (95% CI)")
        ax.set_title("Final grid, B = 15, 14-day horizon (odd seeds)")
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, "final_forest_vs_static_loop.png"), dpi=150)
        plt.close(fig)
        out.append("final_forest_vs_static_loop.png")
    # 2. violations (log scale)
    tot = {
        a: sum(c["arms"][a]["executed_prereq_violations"] for c in cells.values() if a in c["arms"])
        for a in ARMS
    }
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.barh(
        ARMS,
        [v + 1 for v in tot.values()],
        color=["#4f46e5" if a in ADAPT else "#e11d48" for a in ARMS],
    )
    ax.set_xscale("log")
    ax.invert_yaxis()
    for i, v in enumerate(tot.values()):
        ax.text(v + 1, i, f" {v:,}", va="center", fontsize=8)
    ax.set_xlabel("executed prerequisite violations + 1, all cells (log)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "final_violations_log.png"), dpi=150)
    plt.close(fig)
    out.append("final_violations_log.png")
    # 3. false mastery and utilisation by arm and world (h14, B15, calm)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
    for ax, key, title in (
        (axes[0], "false_mastery_rate", "false-mastery rate"),
        (axes[1], "minute_utilisation", "minute utilisation"),
    ):
        for j, w in enumerate(WORLDS):
            vals = []
            for a in ARMS:
                c = cells.get(f"{w}|4-node|B15|calm|h14", {}).get("arms", {}).get(a, {})
                vals.append(c.get(key) or 0)
            ax.bar([i + j * 0.2 for i in range(len(ARMS))], vals, width=0.2, label=w)
        ax.set_xticks(
            [i + 0.3 for i in range(len(ARMS))], ARMS, rotation=45, ha="right", fontsize=7
        )
        ax.set_title(f"{title} (4-node, B 15, calm, 14 d)")
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "final_false_mastery_utilisation.png"), dpi=150)
    plt.close(fig)
    out.append("final_false_mastery_utilisation.png")
    # 4. KM curves for the headline cell
    head = cells.get("S1|4-node|B15|calm|h14")
    if head:
        fig, ax = plt.subplots(figsize=(6, 3.6))
        for a in ("adapt_final", "adapt_w7", "static_loop", "static", "random_eligible"):
            ps = head["arms"].get(a, {}).get("per_seed")
            if not ps:
                continue
            t = [x if x is not None else m for x, m in zip(ps["ttm"], ps["minutes"])]
            e = [x is not None for x in ps["ttm"]]
            curve = kaplan_meier(t, e)
            xs, ys = [0.0], [1.0]
            for x, s in curve[1:]:
                xs += [x, x]
                ys += [ys[-1], s]
            xs.append(max(t))
            ys.append(ys[-1])
            ax.plot(xs, [1 - y for y in ys], label=a)
        ax.set_xlabel("minutes")
        ax.set_ylabel("share reaching goal mastery (KM)")
        ax.set_title("Headline: S1, 4-node, B 15, calm, 14 d (N = 1000)")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, "final_km_headline.png"), dpi=150)
        plt.close(fig)
        out.append("final_km_headline.png")
    # 5. reliability diagrams per world
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.2))
    for ax, w in zip(axes, WORLDS):
        ax.plot([0, 1], [0, 1], "--", color="#999", lw=1)
        for a, col in (("adapt_w7", "#56B4E9"), ("adapt_final", "#4f46e5")):
            pc = pooled_calib(cells, w, a)
            if pc["bins"]:
                ax.plot(
                    [b[0] for b in pc["bins"]],
                    [b[1] for b in pc["bins"]],
                    "o-",
                    color=col,
                    ms=3,
                    label=f"{a} (Brier {pc['brier']:.3f})",
                )
        ax.set_title(w)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.legend(fontsize=6)
    fig.supxlabel("engine P(correct)")
    fig.supylabel("observed rate")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "final_reliability.png"), dpi=150)
    plt.close(fig)
    out.append("final_reliability.png")
    return out


def grid_section(g, L):
    cells, md = g["cells"], g["metadata"]
    L += [
        "## 1. Final grid (WP-G)",
        "",
        f"Source: `experiments/results/final_grid.json` (code hash `{md['code_hash'][:12]}…`, {md['timestamp_utc']}, runtime {md['runtime_s']} s on {md['processes']} processes). "
        f"Pre-registration: `{md['preregistration']}`. {len(cells)} cells; N = {md['n_per_cell']} odd seeds per cell, headline `{md['headline_cell']}` N = {md['n_headline']}. "
        f"adapt-final = B.3 winner **{md['calibration_winner']}** ({md['winner_profile']} profile, {md['winner_overrides']}) + {md['final_flags']}.",
        "",
        "### 1.1 Primary: executed prerequisite violations (all cells)",
        "",
        "| Arm | Executed violations | Learners with ≥ 1 | Budget violations |",
        "|---|---|---|---|",
    ]
    for a in ARMS:
        v = sum(
            c["arms"][a]["executed_prereq_violations"] for c in cells.values() if a in c["arms"]
        )
        lv = sum(
            c["arms"][a]["learners_with_executed_violations"]
            for c in cells.values()
            if a in c["arms"]
        )
        bv = sum(c["arms"][a]["budget_violations"] for c in cells.values() if a in c["arms"])
        L.append(f"| {a} | {v:,} | {lv:,} | {bv:,} |")
    L += [
        "",
        "### 1.2 Primary: goal mastery vs `static_loop` (count of cells by 95% CI)",
        "",
        "| Arm | Horizon | Better | n.s. | Worse | Mean Δ |",
        "|---|---|---|---|---|---|",
    ]
    for a in ADAPT + ["static", "random_eligible", "no_replan"]:
        for h in ("hw7", "h7", "h14", "h21"):
            ps = [
                c["paired_vs_static_loop"][a]["goal_mastery"]
                for k, c in cells.items()
                if k.endswith("|" + h) and a in c["paired_vs_static_loop"]
            ]
            if ps:
                s = [sig(p) for p in ps]
                L.append(
                    f"| {a} | {h[1:]} | {s.count(1)} | {s.count(0)} | {s.count(-1)} | {sum(p['diff'] for p in ps) / len(ps):+.3f} |"
                )
    L += [
        "",
        "All-required mastery vs `static_loop`:",
        "",
        "| Arm | Better | n.s. | Worse | Mean Δ |",
        "|---|---|---|---|---|",
    ]
    for a in ADAPT:
        ps = [
            c["paired_vs_static_loop"][a]["all_required"]
            for c in cells.values()
            if a in c["paired_vs_static_loop"]
        ]
        s = [sig(p) for p in ps]
        L.append(
            f"| {a} | {s.count(1)} | {s.count(0)} | {s.count(-1)} | {sum(p['diff'] for p in ps) / len(ps):+.3f} |"
        )
    L += [
        "",
        "### 1.3 adapt-final vs adapt-W7, ablation and diagnostic (goal mastery, cells by CI)",
        "",
        "| Comparison | Better | n.s. | Worse | Mean Δ |",
        "|---|---|---|---|---|",
    ]
    for key in (
        "adapt_final_vs_adapt_w7",
        "adapt_cal_vs_adapt_w7",
        "adapt_final_vs_adapt_cal",
        "adapt_final_dx_vs_adapt_final",
        "adapt_final_vs_static",
    ):
        ps = [c["paired"][key]["goal_mastery"] for c in cells.values() if key in c["paired"]]
        if ps:
            s = [sig(p) for p in ps]
            L.append(
                f"| {key} | {s.count(1)} | {s.count(0)} | {s.count(-1)} | {sum(p['diff'] for p in ps) / len(ps):+.3f} |"
            )
    head = cells.get("S1|4-node|B15|calm|h14")
    if head:
        L += [
            "",
            "### 1.4 Headline cell: S1 | 4-node | B = 15 | calm | 14 days (N = 1000)",
            "",
            "| Arm | Goal mastery | All required | False mastery | Utilisation | KM median min | RMST min | Brier | AUC | Δ goal vs static_loop |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for a in ARMS:
            s = head["arms"].get(a)
            if not s:
                continue
            p = head["paired_vs_static_loop"].get(a)
            L.append(
                f"| {a} | {f3(s['goal_mastery_rate'])} | {f3(s['all_required_rate'])} | {f3(s['false_mastery_rate'])} | {f3(s['minute_utilisation'], 2)} | "
                f"{s['km_median_minutes_to_mastery'] if s['km_median_minutes_to_mastery'] is not None else 'censored'} | {f3(s['km_rmst_minutes_to_mastery'], 1)} | "
                f"{f3(s['brier'])} | {f3(s['auc'])} | {ci(p['goal_mastery']) if p else '—'} |"
            )
        for key in (
            "adapt_final_vs_adapt_w7",
            "adapt_final_dx_vs_adapt_final",
            "adapt_final_vs_adapt_cal",
        ):
            if key in head["paired"]:
                L.append(
                    f"\n{key}: goal {ci(head['paired'][key]['goal_mastery'])}, all-required {ci(head['paired'][key]['all_required'])}."
                )
    L += [
        "",
        "### 1.5 Secondary outcomes by arm (mean over cells, by horizon)",
        "",
        "| Arm | Horizon | False mastery | Utilisation | Idle days (total) | KM RMST min |",
        "|---|---|---|---|---|---|",
    ]
    for a in ARMS:
        for h in ("h7", "h14", "h21"):
            xs = [c["arms"][a] for k, c in cells.items() if k.endswith("|" + h) and a in c["arms"]]
            if not xs:
                continue
            fm = [x["false_mastery_rate"] for x in xs if x["false_mastery_rate"] is not None]
            L.append(
                f"| {a} | {h[1:]} | {f3(sum(fm) / len(fm)) if fm else '—'} | {f3(sum(x['minute_utilisation'] for x in xs) / len(xs), 2)} | "
                f"{f3(sum(x['idle_days_total'] for x in xs) / len(xs), 2)} | {f3(sum(x['km_rmst_minutes_to_mastery'] for x in xs) / len(xs), 1)} |"
            )
    L += [
        "",
        "### 1.6 B.4 In-loop prediction quality before vs after calibration (pooled over each world's cells)",
        "",
        "| World | adapt-W7 Brier | adapt-final Brier | adapt-W7 AUC | adapt-final AUC | attempts (final) |",
        "|---|---|---|---|---|---|",
    ]
    for w in WORLDS:
        a, b = pooled_calib(cells, w, "adapt_w7"), pooled_calib(cells, w, "adapt_final")
        L.append(
            f"| {w} | {f3(a['brier'])} | {f3(b['brier'])} | {f3(a['auc'])} | {f3(b['auc'])} | {b['n']:,} |"
        )
    dx = [
        c["paired"]["adapt_final_dx_vs_adapt_final"]["goal_mastery"]
        for k, c in cells.items()
        if "adapt_final_dx_vs_adapt_final" in c["paired"] and parse(k)["scen"] != "forgetting_21"
    ]
    hd = head["paired"].get("adapt_final_dx_vs_adapt_final") if head else None
    if dx and hd:
        mean_dx = sum(p["diff"] for p in dx) / len(dx)
        optional = (
            hd["goal_mastery"]["ci95"][0] <= 0 <= hd["goal_mastery"]["ci95"][1]
            and abs(mean_dx) <= 0.02
        )
        L += ["", "### 1.7 E.2 / D52 diagnostic decision value", "", f"Headline adapt_final_dx − adapt_final: goal {ci(hd['goal_mastery'])}; mean over {len(dx)} non-forgetting cells {mean_dx:+.3f}. "
              f"Pre-registered rule (CI includes 0 and |mean| ≤ 0.02): **{'met: the diagnostic becomes optional' if optional else ('not met because the diagnostic is significantly worse (it costs study minutes); the rule did not define this case, see D52' if hd['goal_mastery']['ci95'][1] < 0 else 'not met')}**."]  # fmt: skip


def other_sections(L):
    sel = load("w8_calibration_select.json")
    if sel:
        L += [
            "",
            "## 2. Calibration selection (B.3, even seeds)",
            "",
            "| Candidate | Mean Brier | Mean Δ vs static_loop |",
            "|---|---|---|",
        ]
        for c, r in sel["candidates"].items():
            L.append(
                f"| {c}{' **(winner)**' if c == sel['winner'] else ''} | {r['primary_mean_brier']:.4f} | {r['secondary_mean_diff_vs_static_loop']:+.4f} |"
            )
        L.append(
            f"\nWithin 0.002 of the minimum: {', '.join(sel['tied_within_margin'])}; winner {sel['winner']} (code `{sel['metadata']['code_hash'][:12]}…`)."
        )
    pe = load("w8_policy_eval.json")
    if pe:
        L += [
            "",
            "## 3. A2 bandit policy (J.6, odd seeds)",
            "",
            "| Cell | Variant | Goal mastery | All required | Exec. viol. | Mean LP | Agreement with det. | Δ goal vs det. |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for cell, c in pe["cells"].items():
            for v in ("deterministic", "bandit_frozen", "bandit_updating", "random"):
                x = c[v]
                d = x.get("vs_deterministic", {}).get("goal_mastery")
                L.append(
                    f"| {cell} | {v} | {f3(x['goal_mastery_rate'])} | {f3(x['all_required_rate'])} | {x['executed_violations']} | {f3(x['mean_learning_progress'], 4)} | {f3(x['agreement_with_deterministic'])} | {ci(d) if d else '—'} |"
                )
        L += [
            "",
            "OPE of the frozen policy (value = mean learning progress per decision):",
            "",
            "| Cell | Simulated | Logger | IPS | SNIPS | DR | |error| IPS / SNIPS / DR |",
            "|---|---|---|---|---|---|---|",
        ]
        for cell, c in pe["cells"].items():
            o = c["ope_frozen"]
            for lg in ("from_random", "from_bandit_updating"):
                e = o[lg]
                er = e["abs_error"]
                L.append(
                    f"| {cell} | {f3(o['simulated_value'], 4)} | {lg[5:]} | {f3(e['ips'], 4)} | {f3(e['snips'], 4)} | {f3(e['dr'], 4)} | {f3(er['ips'], 4)} / {f3(er['snips'], 4)} / {f3(er['dr'], 4)} |"
                )
    ex = load("w8_extensions.json")
    if ex:
        L += ["", "## 4. Extensions (D.1, O.1–O.4, odd seeds)", "", f"HLR-lite fit: weights {ex['hlr_fit']['weights']}, Brier {ex['hlr_fit']['brier']} vs constant-rate baseline {ex['hlr_fit']['baseline_brier_mean']} ({ex['hlr_fit']['metadata']['n_observations']} post-gap answers).", "",
              "| Cell | Arm | Goal mastery | Mean goal θ | Retention | Brier | AUC | Exec. viol. | Δ goal vs reference |", "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
        for cell, d in ex["cells"].items():
            ref_key = next(k for k in d if k.startswith("paired_vs_"))
            for arm, x in d.items():
                if arm.startswith("paired"):
                    continue
                p = d[ref_key].get(arm)
                L.append(
                    f"| {cell} | {arm} | {f3(x['goal_mastery_rate'])} | {f3(x['mean_goal_theta'])} | {f3(x['mean_retention'])} | {f3(x['brier'])} | {f3(x['auc'])} | {x['executed_violations']} | {ci(p['goal_mastery']) if p else '(reference)'} |"
                )
        cs = load("w8_cpsat_eval.json")
        if not cs:
            L.append(f"\nO.4 CP-SAT: {ex['O4']}.")
        else:
            h, m = cs["headline"], cs["metadata"]
            L += [
                "",
                f"O.4 CP-SAT (`w8_cpsat_eval.json`, OR-Tools {m['ortools']}, maintenance reviews off in both arms): "
                f"{h['cells']} cells, same status in {h['status_agreement']}; CP-SAT plan used in {h['cpsat_used']}, "
                f"timed out (5 s) and fell back in {h['cpsat_timeouts_fell_back']}. Audit violations: default "
                f"{h['audit_violations_default']}, CP-SAT {h['audit_violations_cpsat']}. Both feasible in "
                f"{h['both_feasible']}: CP-SAT shorter in {h['cpsat_shorter']}, longer in {h['cpsat_longer']}. "
                f"Same workload (fair packing) in {h['same_workload_cells']}: shorter in "
                f"{h['same_workload_cpsat_shorter']}, by at most {h['same_workload_max_days_saved']} day(s); in "
                f"{h['cpsat_dropped_review_minutes_cells']} cells the CP-SAT plan is shorter partly because it omits "
                f"in-plan reviews. Median planning time where CP-SAT was used: {h['median_ms_cpsat_when_used']} ms "
                f"vs {h['median_ms_default_when_cpsat_used']} ms default.",
                "",
                "| Cell | Default reason | Default last day | Default min | Default ms | CP-SAT reason | CP-SAT last day | CP-SAT min | CP-SAT ms |",
                "|---|---|---|---|---|---|---|---|---|",
            ]  # fmt: skip
            for cell, v in cs["cells"].items():
                d, c = v["default"], v["cpsat"]
                L.append(
                    f"| {cell.replace('|', chr(92) + '|')} | {d['reason']} | {d['last_day']} | {d['minutes']} | {d['plan_ms_mean']} | {c['reason']} | {c['last_day']} | {c['minutes']} | {c['plan_ms_mean']} |"
                )
    for path in sorted(glob.glob(os.path.join(RES, "w8_agent_eval_*.json"))):
        a = json.load(open(path))
        L += [
            "",
            f"## 5. Agents ({os.path.basename(path)}): {a['metadata']['label']}",
            "",
            "```json",
            json.dumps({k: v for k, v in a.items() if k != "metadata"}, indent=1),
            "```",
        ]


def main():
    g = load("final_grid.json")
    L = [
        "# AdaptEngine — Final Results (Week 8)",
        "",
        "Generated by `python experiments/make_final_results.py` from `experiments/results/*.json`; no number is edited by hand. Learners are simulated (worlds S0, S1, S4, S4-fitted); results are synthetic.",
        "",
    ]
    if g:
        figs = figures(g)
        grid_section(g, L)
        L += ["", "Figures: " + ", ".join(f"`docs/figures/{f}`" for f in figs)]
    other_sections(L)
    with open(os.path.join(repo_root, "docs", "FINAL_RESULTS.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote docs/FINAL_RESULTS.md")


if __name__ == "__main__":
    main()
