#!/usr/bin/env python3
"""Plan 4, F3-T8 (D72): greedy vs hybrid vs pure CP-SAT. The full grid runs in Plan 7 (D90).

    python experiments/run_f3_grid.py --tune      # work-unit tuning -> results/f3_tuning.json
    python experiments/run_f3_grid.py             # full grid (Plan 7) -> results/f3_grid.json

Grid (pre-registration docs/preregistration/F3_2026-11-20.md): planners greedy / hybrid / cpsat,
worlds S0-S4, curricula 4-node, 8-node, synth-20, synth-50, 8-node-x10, synth-20-x10,
synth-50-x10, budgets 5/10/15/30, the W7 scenarios (incl. the stress scenarios), arm adapt,
seeds 1000-1199; pure CP-SAT only on the pre-registered subset PURE_SUBSET. Per cell: the first
plan's verdict and projected finish day, closed-loop outcomes, executed violations (D46), and the
exact vs bound-based shortfall. Planning latency is measured separately (it is not deterministic).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import multiprocessing as mp
import os
import statistics
import sys
import time

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG, config_hash  # noqa: E402
from adaptengine.core.schema import PlanContext  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.run_f2_grid import CURRICULA, REVIEWED  # noqa: E402
from experiments.run_w7_grid import BUDGETS, SCENARIOS, curriculum_paths, goal_of  # noqa: E402
from experiments.sim import PROFILES, WORLDS  # noqa: E402

PREREGISTRATION = "docs/preregistration/F3_2026-11-20.md"
PLANNERS = ("greedy", "hybrid", "cpsat")
PURE_SUBSET = {  # pure CP-SAT cells (D72), named before any run
    "curricula": ("4-node", "8-node", "8-node-x10"),
    "budgets": (10, 15),
    "scenarios": ("calm", "missed_day", "deadline_cut"),
}
TUNE_UNITS = (1.0, 2.0, 5.0, 10.0, 20.0)
# F3-T8 rule, in one place: the smallest work-unit limit proven on most (> 50%) tuning plans
TUNE_RULE = "smallest work units with > 50% proven"
TUNE_THRESHOLD = 0.5


def choose_work_units(share: dict) -> float:
    """First (smallest) value whose share is strictly above TUNE_THRESHOLD; else the largest."""
    ordered = sorted(share, key=float)
    return float(next((wu for wu in ordered if share[wu] > TUNE_THRESHOLD), ordered[-1]))


TUNE_CURRICULA = ("8-node", "synth-20")
_ENGINES: dict = {}


F1X3 = {"worlds": ("S0", "S4"), "curricula": ("8-node", "8-node-x10"), "budget": 15}
F1_ARMS = {"diagnostic_method": "bisection", "confirm_diag_confident": True}


def engine_for(cur: str, planner: str, **kw) -> Engine:
    key = (cur, planner, tuple(sorted(kw.items())))
    if key not in _ENGINES:
        cp, ap = curriculum_paths(cur)
        cfg = dataclasses.replace(DEFAULT_CONFIG, planner_method=planner, **kw)
        _ENGINES[key] = Engine.from_files(
            os.path.join(repo_root, cp) if not os.path.isabs(cp) else cp,
            os.path.join(repo_root, ap) if not os.path.isabs(ap) else ap,
            config=cfg,
            allow_unreviewed=cur not in REVIEWED,
        )
    return _ENGINES[key]


def in_pure_subset(cur, budget, scen) -> bool:
    s = PURE_SUBSET
    return cur in s["curricula"] and budget in s["budgets"] and scen in s["scenarios"]


def cell(unit):
    world, cur, budget, scen, planner, seeds, *f1 = unit
    e = engine_for(cur, planner, **(F1_ARMS if f1 else {}))
    sc = get_scenario(scen, e, e.init_learner(), goal=goal_of(e), budget=budget)
    if sc is None:
        return (*unit[:5], bool(f1)), None
    first = e.plan(
        e.init_learner(), PlanContext(goal=sc.goal, deadline_day=sc.deadline, budget=budget)
    )
    rows = []
    for s in seeds:
        prof = PROFILES["fast_forgetter" if scen == "forgetting_21" else "nominal"]
        r = run_episode(e, s, sc, "adapt", prof, world=world, diagnose=bool(f1))
        rows.append(
            {
                k: r[k]
                for k in (
                    "goal_mastered",
                    "all_required_mastered",
                    "minutes_used",
                    "idle_days",
                    "executed_prereq_violations",
                    "retention_reviewed",
                )
            }
        )
    return (*unit[:5], bool(f1)), {
        "verdict": first.status.value,
        "reason": first.reason,
        "projected_finish_day": first.days[-1].day if first.days else None,
        "reviews_in_first_plan": sum(
            1
            for t in first.trace
            if t.get("decision") == "SELECTED"
            and t.get("reason") in ("REVIEW_DUE", "REVIEW_SCHEDULED")
        ),
        "shortfall_days": first.shortfall_days,
        "n": len(rows),
        "goal_mastery_rate": round(sum(r["goal_mastered"] for r in rows) / len(rows), 4),
        "all_required_rate": round(sum(r["all_required_mastered"] for r in rows) / len(rows), 4),
        "mean_minutes": round(sum(r["minutes_used"] for r in rows) / len(rows), 3),
        "idle_days": sum(r["idle_days"] for r in rows),
        "retention_reviewed": _mean([r["retention_reviewed"] for r in rows]),
        "executed_prereq_violations": sum(r["executed_prereq_violations"] for r in rows),
    }


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def units(worlds, curricula, seeds, budgets=BUDGETS, scenarios=SCENARIOS):
    for w in worlds:
        for c in curricula:
            for b in budgets:
                for s in scenarios:
                    for p in PLANNERS:
                        if p == "cpsat" and not in_pure_subset(c, b, s):
                            continue
                        yield (w, c, b, s, p, seeds)
    for w in F1X3["worlds"]:  # F1 x F3 subset: bisection diagnostic + confirmation, each planner
        for c in F1X3["curricula"]:
            if c in curricula and w in worlds:
                for p in PLANNERS:
                    yield (w, c, F1X3["budget"], "calm", p, seeds, "f1")


def latency(curricula, n=5) -> dict:
    """Mean and sd of one Engine.plan call on the cold-start state per planner (W7 T6.1 style)."""
    out = {}
    for c in curricula:
        for p in PLANNERS:
            e = engine_for(c, p)
            ctx = PlanContext(goal=goal_of(e), deadline_day=14, budget=15)
            ts = []
            for _ in range(n):
                t = time.perf_counter()
                e.plan(e.init_learner(), ctx)
                ts.append(time.perf_counter() - t)
            out[f"{c}/{p}"] = {
                "mean_s": round(statistics.mean(ts), 4),
                "sd_s": round(statistics.pstdev(ts), 4),
            }
    return out


def tune(out_path=None) -> dict:
    """Smallest cpsat_max_work_units with every objective level proven on most (> 50%) of the
    tuning plans (8-node and synth-20 cold-start plans over budgets x deadlines), as F3-T8."""
    rows = []
    for c in TUNE_CURRICULA:
        curriculum_paths(c)
        g = engine_for(c, "greedy")
        goal = goal_of(g)
        for b in BUDGETS:
            base = g.plan(g.init_learner(), PlanContext(goal=goal, deadline_day=60, budget=b))
            need = base.days[-1].day if base.days else 1
            for dl in sorted({max(2, need - 1), need, need + 2}):
                for wu in TUNE_UNITS:
                    e = engine_for(c, "cpsat", cpsat_max_work_units=wu)
                    p = e.plan(e.init_learner(), PlanContext(goal=goal, deadline_day=dl, budget=b))
                    rec = next(t for t in p.trace if t.get("decision") == "CPSAT_SOLVE")
                    proven = rec["status"] in ("OPTIMAL", "INFEASIBLE") and all(
                        o["status"] == "OPTIMAL" for o in rec["objectives"]
                    )
                    rows.append(
                        {
                            "curriculum": c,
                            "budget": b,
                            "deadline": dl,
                            "work_units": wu,
                            "status": rec["status"],
                            "proven": proven,
                        }
                    )
    share = {
        wu: sum(r["proven"] for r in rows if r["work_units"] == wu)
        / sum(r["work_units"] == wu for r in rows)
        for wu in TUNE_UNITS
    }
    chosen = choose_work_units(share)
    res = {
        "metadata": {**stamp(), "rule": TUNE_RULE, "chosen": chosen},
        "share_proven": {str(k): round(v, 4) for k, v in share.items()},
        "plans": rows,
    }
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    return res


def main(
    out_path,
    n_episodes=200,
    worlds=WORLDS,
    curricula=CURRICULA,
    procs=1,
    f1_path=None,
    budgets=BUDGETS,
    scenarios=SCENARIOS,
    latency_n=5,
) -> dict:
    seeds = tuple(range(1000, 1000 + n_episodes))
    for c in curricula:
        curriculum_paths(c)
    f1 = {}
    if f1_path and os.path.exists(f1_path):
        with open(f1_path, encoding="utf-8") as f:
            f1 = json.load(f)
    same_seeds = f1.get("metadata", {}).get("episode_seeds") == [seeds[0], seeds[-1]]
    us, reused = [], {}
    for u in units(worlds, curricula, seeds, budgets, scenarios):
        is_f1_greedy = len(u) == 7 and u[4] == "greedy"
        hit = reusable_f1_cell(f1, u[0], u[1], "bisect_confirm") if is_f1_greedy else None
        if hit is not None and same_seeds:  # identical cell already run in the F1 grid (D90)
            reused[(*u[:5], True)] = {**hit, "reused_from": f1_path}
        else:
            us.append(u)
    if procs > 1:
        with mp.get_context("fork").Pool(procs) as pool:
            cells = dict(pool.map(cell, us, chunksize=1))
    else:
        cells = dict(map(cell, us))
    cells.update(reused)
    res = {
        "metadata": {
            **stamp(),
            "preregistration": PREREGISTRATION,
            "config_hash_default": config_hash(DEFAULT_CONFIG),
            "cpsat_max_work_units": DEFAULT_CONFIG.cpsat_max_work_units,
            "pure_cpsat_subset": PURE_SUBSET,
            "episode_seeds": [seeds[0], seeds[-1]],
        },
        "latency": latency(curricula, latency_n),
        "cells": [
            {
                "world": w,
                "curriculum": c,
                "budget": b,
                "scenario": s,
                "planner": p,
                "f1_bisection": f,
                **v,
            }
            for (w, c, b, s, p, f), v in sorted(cells.items(), key=lambda kv: str(kv[0]))
            if v
        ],
    }
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    return res


def reusable_f1_cell(f1_results: dict, world: str, cur: str, arm: str):
    """Plan 7: an F1 closed-loop cell that is identical to an F1 x F3 cell (same world,
    curriculum, calm, budget 15, seeds, config) is reused instead of re-run."""
    return f1_results.get("closed_loop", {}).get(world, {}).get(cur, {}).get(arm)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--n-episodes", type=int, default=200)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    if a.tune:
        r = tune(a.out or os.path.join(repo_root, "experiments/results/f3_tuning.json"))
        print(r["share_proven"], "chosen:", r["metadata"]["chosen"])
    else:
        main(
            a.out or os.path.join(repo_root, "experiments/results/f3_grid.json"),
            a.n_episodes,
            procs=a.procs,
            f1_path=os.path.join(repo_root, "experiments/results/f1_grid.json"),
        )
