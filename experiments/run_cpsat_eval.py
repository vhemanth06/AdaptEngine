#!/usr/bin/env python3
"""W8 O.4 (D60, FINAL_A5 §7): CP-SAT vs greedy/oracle plan length and latency on synth-20/50.

For each synthetic curriculum (seed 2026, deepest goal, fresh learner) and budget, `L` is the last
day of the default (greedy) plan under a 1000-day deadline. Three deadlines are then planned with
the default engine (greedy, or greedy -> branch-and-bound oracle when greedy misses the deadline)
and with `scheduler = "cpsat"`:
  - loose  (L+7): greedy is feasible with a week of slack
  - greedy (L):   tightest deadline greedy meets
  - tight  (L-1): greedy misses, so the default engine takes the oracle path
Every plan gets the same audits (planned prerequisite order, budget, duplicate occurrences).
Both arms run with `maintenance_reviews = False`: otherwise greedy fills every day up to the
deadline with due reviews and "plan length" is just the deadline. CP-SAT and the oracle pack only
the new-learning workload, so greedy plans can still hold in-plan reviews; `n_activities` shows it.
Writes experiments/results/w8_cpsat_eval.json with code_hash (no git). Needs the [solver] extra.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import statistics
import sys
import tempfile
import time

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.core.schema import PlanContext  # noqa: E402
from adaptengine.planner import cpsat  # noqa: E402
from experiments.checks import (  # noqa: E402
    count_budget_violations,
    count_duplicate_activities,
    count_plan_prereq_violations,
)
from experiments.provenance import stamp  # noqa: E402
from experiments.run_w7_latency import deepest_goal  # noqa: E402
from experiments.synth_curriculum import write_synthetic_curriculum  # noqa: E402

OUT = os.path.join(repo_root, "experiments/results/w8_cpsat_eval.json")
BASE_CFG = dataclasses.replace(DEFAULT_CONFIG, maintenance_reviews=False)
CPSAT_CFG = dataclasses.replace(BASE_CFG, scheduler="cpsat")
FIND_L_DEADLINE = 1000


def engine_pair(n: int, tmp: str) -> tuple[Engine, Engine]:
    cp, ap = write_synthetic_curriculum(os.path.join(tmp, str(n)), n, seed=2026)
    return (
        Engine.from_files(cp, ap, config=BASE_CFG, allow_unreviewed=True),
        Engine.from_files(cp, ap, config=CPSAT_CFG, allow_unreviewed=True),
    )


def summarise(e: Engine, ctx: PlanContext, repeats: int) -> dict:
    s0 = e.init_learner()
    plan = e.plan(s0, ctx)  # warm-up, and the plan that is audited
    ms = []
    for _ in range(repeats):
        t = time.perf_counter()
        e.plan(s0, ctx)
        ms.append((time.perf_counter() - t) * 1000.0)
    days = plan.days if plan.days else plan.best_effort_days
    solver = [t for t in plan.trace if t.get("decision") == "SCHEDULER"]
    return {
        "status": plan.status.value,
        "reason": plan.reason,
        "last_day": days[-1].day if days else None,
        "n_days_used": len(days),
        "n_activities": sum(len(d.activities) for d in days),
        "minutes": sum(d.duration for d in days),
        "prereq_violations": count_plan_prereq_violations(e, s0, days),
        "budget_violations": count_budget_violations(e, days, ctx.budget),
        "duplicate_occurrences": count_duplicate_activities(days),
        "solver_note": solver[-1] if solver else None,
        "plan_ms_mean": round(statistics.mean(ms), 3),
        "plan_ms_sd": round(statistics.stdev(ms), 3) if len(ms) > 1 else 0.0,
    }


def run(sizes=(20, 50), budgets=(5, 10, 15, 30), repeats: int = 5) -> dict:
    cells = {}
    with tempfile.TemporaryDirectory() as tmp:
        for n in sizes:
            base, cps = engine_pair(n, tmp)
            goal = deepest_goal(base)
            for b in budgets:
                loose = base.plan(base.init_learner(), PlanContext(goal, FIND_L_DEADLINE, b))
                L = loose.days[-1].day
                for label, dl in (("loose", L + 7), ("greedy", L), ("tight", L - 1)):
                    ctx = PlanContext(goal=goal, deadline_day=dl, budget=b)
                    d, c = summarise(base, ctx, repeats), summarise(cps, ctx, repeats)
                    cells[f"synth-{n}|b{b}|{label}"] = {
                        "deadline_day": dl,
                        "greedy_last_day_loose": L,
                        "default": d,
                        "cpsat": c,
                        "same_status": d["status"] == c["status"],
                        "cpsat_days_saved": (
                            d["last_day"] - c["last_day"]
                            if d["status"] == c["status"] == "FEASIBLE"
                            else None
                        ),
                    }
    return cells


def headline(cells: dict) -> dict:
    vals = list(cells.values())
    both = [v for v in vals if v["cpsat_days_saved"] is not None]
    # Fair packing comparison: both plans hold the same minutes. Otherwise greedy kept in-plan
    # reviews that CP-SAT (like the oracle) does not schedule, so its "saving" is dropped work.
    same = [v for v in both if v["default"]["minutes"] == v["cpsat"]["minutes"]]
    used = [v for v in vals if v["cpsat"]["reason"] == "CPSAT_ASSIGNMENT"]
    audits = ("prereq_violations", "budget_violations")
    return {
        "cells": len(vals),
        "status_agreement": sum(v["same_status"] for v in vals),
        "both_feasible": len(both),
        "cpsat_shorter": sum(v["cpsat_days_saved"] > 0 for v in both),
        "cpsat_longer": sum(v["cpsat_days_saved"] < 0 for v in both),
        "max_days_saved": max((v["cpsat_days_saved"] for v in both), default=None),
        "same_workload_cells": len(same),
        "same_workload_cpsat_shorter": sum(v["cpsat_days_saved"] > 0 for v in same),
        "same_workload_max_days_saved": max((v["cpsat_days_saved"] for v in same), default=None),
        "cpsat_dropped_review_minutes_cells": sum(
            v["cpsat"]["minutes"] < v["default"]["minutes"] for v in both
        ),
        "audit_violations_default": sum(v["default"][k] for v in vals for k in audits),
        "audit_violations_cpsat": sum(v["cpsat"][k] for v in vals for k in audits),
        "cpsat_used": len(used),
        "cpsat_timeouts_fell_back": sum(
            (v["cpsat"]["solver_note"] or {}).get("status") == "UNKNOWN" for v in vals
        ),
        "median_ms_default_when_cpsat_used": (
            round(statistics.median(v["default"]["plan_ms_mean"] for v in used), 2)
            if used
            else None
        ),
        "median_ms_cpsat_when_used": (
            round(statistics.median(v["cpsat"]["plan_ms_mean"] for v in used), 2) if used else None
        ),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    if not cpsat.available():
        sys.exit("OR-Tools is not installed: pip install -e '.[solver]'")
    import ortools

    t0 = time.time()
    cells = run(repeats=a.repeats)
    res = {
        "metadata": {
            **stamp(),
            "ortools": ortools.__version__,
            "repeats": a.repeats,
            "runtime_s": round(time.time() - t0, 1),
            "maintenance_reviews": False,
            "protocol": "FINAL_A5 §7 O.4: plan length and latency vs greedy/oracle on "
            "synth-20/50, same audits",
        },
        "headline": headline(cells),
        "cells": cells,
    }
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    print(json.dumps(res["headline"], indent=1))
    for k, v in cells.items():
        d, c = v["default"], v["cpsat"]
        print(
            f"{k:24s} default {d['reason']:24s} last {d['last_day']} {d['plan_ms_mean']:9.2f} ms"
            f" | cpsat {c['reason']:28s} last {c['last_day']} {c['plan_ms_mean']:9.2f} ms"
        )
