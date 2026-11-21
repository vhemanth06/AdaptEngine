"""E1 — Safety and outcomes grid (report 5.1, 5.4, 5.6).

Does the engine ever teach out of order, and does adapting pay off compared with not adapting?
Arms (no diagnostic): adapt, no_review, no_replan, static; adapt_h7 and no_review_h7 in
forgetting_21 cells. Worlds S0-S4 x 4-node, 8-node, 8node_x10, synth-20 x budgets 5/10/15/30 x
the 8 scenarios. N = 200 (seeds 1000-1199); headline cells N = 1000 (seeds 1000-1999).

    python -m experiments_v2.runners.e1_safety_outcomes [--smoke] [--procs N] [--out PATH]
"""

from __future__ import annotations

from ..core import curricula as C
from ..core import metrics as M
from ..core.arms import E1_ARMS, E1_H7_ARMS
from ..core.episode import first_plan, run_episode, theta_at
from ..core.parallel import pmap
from ..core.scenarios import BUDGETS, SCENARIOS, applies, make_scenario, profile_for
from ..core.simulator import WORLDS
from . import common

EXP, NAME = "E1", "E1_safety_outcomes"
CURRICULA = ("4-node", "8-node", "8node_x10", "synth-20")
HEADLINE = {(w, c, 15, "calm") for w in ("S1", "S0") for c in ("4-node", "8node_x10")}
CONTRAST_KEYS = ("goal_mastered", "all_required", "minutes", "goal_theta")


def cells(smoke: bool) -> list:
    if smoke:
        return [
            ("S1", "4-node", 15, "calm"),
            ("S0", "4-node", 15, "missed_day"),
            ("S0", "4-node", 15, "forgetting_21"),
        ]
    out = []
    for w in WORLDS:
        for c in CURRICULA:
            for b in BUDGETS:
                for s in SCENARIOS:
                    if applies(s, b):
                        out.append((w, c, b, s))
    return out


def seeds_for(key, smoke: bool) -> tuple:
    if smoke:
        return common.SMOKE_EPISODE_SEEDS
    return common.HEADLINE_SEEDS if key in HEADLINE else common.EPISODE_SEEDS


def arms_for(scenario: str) -> dict:
    return {**E1_ARMS, **(E1_H7_ARMS if scenario == "forgetting_21" else {})}


def run_cell(unit) -> dict:
    (world, cur, budget, scen), seeds = unit
    base = C.engine(cur)
    sc = make_scenario(scen, base, C.goal_of(base), budget)
    prof = profile_for(scen)
    arms, rows = {}, {}
    for name, arm in arms_for(scen).items():
        e = C.engine(cur, arm.config())
        urgency = {c: 0.0 for c in e.graph.concepts()} if arm.no_review else None
        fp = first_plan(e, e.init_learner(), sc, urgency) if arm.mode != "static" else None
        rows[name] = [run_episode(e, s, sc, arm, world, prof, first=fp) for s in seeds]
        arms[name] = common.arm_entry(rows[name])
    st = rows["static"]
    for name in arms:
        if name != "static":  # goal theta at equal minutes: both arms at the smaller minute count
            arms[name]["per_learner"]["goal_theta_equal_minutes_vs_static"] = [
                round(theta_at(a["traj"], m) - theta_at(b["traj"], m), 4)
                for a, b in zip(rows[name], st)
                for m in [min(a["minutes"], b["minutes"])]
            ]
    contrasts = {
        f"{a}_minus_{b}": common.contrast(arms[a], arms[b], CONTRAST_KEYS)
        for a, b in (("adapt", "static"), ("adapt", "no_replan"), ("adapt", "no_review"))
    }
    eq = arms["adapt"]["per_learner"]["goal_theta_equal_minutes_vs_static"]
    contrasts["adapt_minus_static"]["goal_theta_equal_minutes"] = M.paired(eq, [0.0] * len(eq))
    if "adapt_h7" in arms:
        contrasts["adapt_h7_minus_no_review_h7"] = common.contrast(
            arms["adapt_h7"], arms["no_review_h7"], CONTRAST_KEYS
        )
        for a in ("adapt_h7", "no_review_h7"):
            contrasts.setdefault("retention", {})[a] = {
                "reviewed": arms[a]["metrics"]["retention_reviewed"],
                "not_reviewed": arms[a]["metrics"]["retention_not_reviewed"],
            }
    key = {
        "world": world,
        "curriculum": cur,
        "budget": budget,
        "scenario": scen,
        "deadline": sc.deadline,
        "profile": prof,
        "headline": (world, cur, budget, scen) in HEADLINE,
    }
    return {"key": key, "arms": arms, "contrasts": contrasts}


def _ci(c):
    return f"{c['diff']:+.4f} [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]"


def hypotheses(cells_out: list) -> dict:
    def total(arms, metric):
        return sum(
            c["arms"][a]["metrics"][metric] for c in cells_out for a in arms if a in c["arms"]
        )

    ex = total(("adapt", "no_review"), "executed_prereq_violations")
    pl = total(("adapt", "no_review"), "plan_level_violations")
    plans = sum(
        c["arms"][a]["metrics"]["plan_checks"]["plans"]
        for c in cells_out
        for a in ("adapt", "no_review")
    )
    h2 = [c for c in cells_out if c["key"]["headline"] and c["key"]["world"] == "S1"]
    h3 = [
        c
        for c in cells_out
        if c["key"]["scenario"] in ("missed_day", "missed_2days") and c["key"]["budget"] == 15
    ]
    h4 = [c for c in cells_out if "adapt_h7_minus_no_review_h7" in c["contrasts"]]
    h4_diff = [
        c
        for c in h4
        if any(
            M.direction(c["contrasts"]["adapt_h7_minus_no_review_h7"][k]) != "no_difference"
            for k in ("goal_mastered", "goal_theta", "all_required")
        )
    ]

    def label(c):
        k = c["key"]
        return f"{k['world']}|{k['curriculum']}|B{k['budget']}|{k['scenario']}"

    def gm(c, name):
        return c["contrasts"][name]["goal_mastered"]

    return {
        "H1": {
            "held": ex == 0,
            "evidence": f"executed violations adapt+no_review over {len(cells_out)} cells: {ex}",
        },
        "H2": {
            "held": bool(h2) and all(gm(c, "adapt_minus_static")["ci95"][1] >= 0 for c in h2),
            "evidence": "; ".join(
                f"{label(c)} adapt-static goal mastery {_ci(gm(c, 'adapt_minus_static'))}"
                for c in h2
            ),
            "rule": "upper CI bound >= 0 (adapt not lower than static)",
        },
        "H3": {
            "held": bool(h3) and all(gm(c, "adapt_minus_no_replan")["ci95"][0] > 0 for c in h3),
            "evidence": f"{sum(gm(c, 'adapt_minus_no_replan')['ci95'][0] > 0 for c in h3)} of {len(h3)} cells with CI above 0; not above 0: "
            + ", ".join(
                label(c) + " " + _ci(gm(c, "adapt_minus_no_replan"))
                for c in h3
                if gm(c, "adapt_minus_no_replan")["ci95"][0] <= 0
            ),
        },
        "H4": {
            "held": bool(h4_diff),
            "evidence": f"{len(h4_diff)} of {len(h4)} forgetting_21 cells where adapt_h7 - no_review_h7 differs (CI excludes 0) on goal mastery, goal theta or all-required: "
            + ", ".join(label(c) for c in h4_diff),
        },
        "H5": {
            "held": pl == 0,
            "evidence": f"plan-level violations adapt+no_review: {pl} over {plans} plans checked",
        },
    }


def static_wins(cells_out: list) -> list:
    """Cells where static beats adapt on goal mastery (CI below 0); explained in NOTES.md."""
    out = []
    for c in cells_out:
        d = c["contrasts"]["adapt_minus_static"]["goal_mastered"]
        if d["ci95"][1] < 0:
            k, a, s = c["key"], c["arms"]["adapt"]["metrics"], c["arms"]["static"]["metrics"]
            out.append(
                {
                    **{x: k[x] for x in ("world", "curriculum", "budget", "scenario", "deadline")},
                    "diff": d["diff"],
                    "ci95": d["ci95"],
                    "adapt_minutes": a["mean_minutes"],
                    "static_minutes": s["mean_minutes"],
                    "adapt_goal": a["goal_mastery_rate"],
                    "static_goal": s["goal_mastery_rate"],
                }
            )
    return out


def calibration_by_world(cells_out: list) -> dict:
    """Mastery prediction on executed attempts, adapt arm, pooled over each world's cells."""
    out = {}
    for w in sorted({c["key"]["world"] for c in cells_out}):
        hist = M.merge_histograms(
            c["arms"]["adapt"]["metrics"]["attempt_histogram"]
            for c in cells_out
            if c["key"]["world"] == w
        )
        out[w] = M.score_histogram(hist)
    return out


def main(argv=None) -> dict:
    args = common.parse(EXP, argv)
    run, out = common.start(EXP, NAME, args)
    for c in CURRICULA:
        C.paths(c)  # synthetic files written before workers fork
    keys = cells(args.smoke)
    cells_out = pmap(run_cell, [(k, seeds_for(k, args.smoke)) for k in keys], args.procs)
    calib = calibration_by_world(cells_out)
    for c in cells_out:
        for a in c["arms"].values():
            a["metrics"].pop("attempt_histogram")
    design = {
        "question": "Does the engine ever teach out of order, and does adapting pay off?",
        "arms": {n: a.describe() for n, a in {**E1_ARMS, **E1_H7_ARMS}.items()},
        "h7_arms_only_in": "forgetting_21",
        "worlds": list(WORLDS),
        "curricula": list(CURRICULA),
        "budgets": list(BUDGETS),
        "scenarios": list(SCENARIOS),
        "profile": "nominal; fast_forgetter in forgetting_21",
        "seeds": {
            "episodes": [1000, 1199],
            "headline": [1000, 1999],
            "headline_cells": sorted("|".join(map(str, h)) for h in HEADLINE),
        }
        if not args.smoke
        else {"episodes": list(common.SMOKE_EPISODE_SEEDS)},
        "horizon": "new-content days of an uncapped DEFAULT_CONFIG plan + 2, minimum 3",
    }
    return common.finish(
        run,
        out,
        design=design,
        content_review={c: C.content_review(c) for c in CURRICULA},
        cells=cells_out,
        hypotheses=hypotheses(cells_out),
        attempt_calibration_by_world=calib,
        static_wins_goal_mastery=static_wins(cells_out),
    )


if __name__ == "__main__":
    main()
