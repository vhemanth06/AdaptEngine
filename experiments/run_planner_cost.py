#!/usr/bin/env python3
"""E6: planner cost on the shipped product engine.

  python experiments/run_planner_cost.py {cpsat,replan,plan,diag,all} [--smoke] [--out-dir D]
Each subcommand read-modify-writes its key in planner_cost.json (smoke: planner_cost_smoke.json).
  cpsat  greedy vs CP-SAT (vs the branch-and-bound oracle the default engine falls back to when
         greedy misses a deadline) on synth-20/50-x10: plan length, latency, audits.
         L = last day of the greedy plan under a 1000-day deadline; deadlines {L, ceil(.9L), ceil(.8L)}.
  replan full vs frontier replanning latency, CURRICULA x event types.
  plan   initial planning latency, CURRICULA x budgets {5,15,30} x deadlines {7,14,28}.
  diag   wall time of one shipped goal-path product diagnostic (goal + ancestors) per curriculum.
Latency = median of repeated perf_counter timings in ms; everything runs single-process.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from adaptengine.core.schema import ActivityType, Event, EventType, PlanContext  # noqa: E402
from adaptengine.learner.state import ExecutionLog  # noqa: E402
from adaptengine.planner import cpsat  # noqa: E402
from adaptengine.planner.workload import WorkloadCache  # noqa: E402
from experiments.checks import (  # noqa: E402
    count_budget_violations,
    count_duplicate_activities,
    count_plan_prereq_violations,
)
from experiments.common import (  # noqa: E402
    CURRICULA,
    REPORT_SEEDS,
    goal_of,
    product_engine,
    write_result,
)
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES, make_sim  # noqa: E402

SYNTH = ("synth-20-x10", "synth-50-x10")
# Copied verbatim from the archived run_replan_latency.py.
EVENT_KINDS = ["missed_day", "failed_assessment", "budget_change", "deadline_change"]
REPLAN_DEADLINE = {"4node_x10": 20, "8node_x10": 30, "synth-20-x10": 40, "synth-50-x10": 80}
FIND_L_DEADLINE = 1000


def _ms(fn, repeats, setup=None):
    """Median ms of fn. setup (untimed) builds fresh per-call args, e.g. a cache copy."""

    def once():
        arg = setup() if setup else None
        t = time.perf_counter()
        fn(arg) if setup else fn()
        return (time.perf_counter() - t) * 1000.0

    once()  # untimed warm-up
    return round(statistics.median([once() for _ in range(repeats)]), 3)


def _plan_cell(e, ctx, repeats):
    s0 = e.init_learner()
    plan = e.plan(s0, ctx)
    days = plan.days or plan.best_effort_days
    return {
        "status": plan.status.value,
        "reason": plan.reason,
        "last_day": days[-1].day if days else None,
        "n_activities": sum(len(d.activities) for d in days),
        "minutes": sum(d.duration for d in days),
        "prereq_violations": count_plan_prereq_violations(e, s0, days),
        "budget_violations": count_budget_violations(e, days, ctx.budget),
        "duplicate_occurrences": count_duplicate_activities(days),
        "median_ms": _ms(lambda: e.plan(s0, ctx), repeats),
    }


def run_cpsat(smoke, repeats):
    if not cpsat.available():
        return {"skipped": "ortools is not importable (pip install -e '.[solver]')"}
    import ortools

    budget = 15
    curs = SYNTH[:1] if smoke else SYNTH
    fracs = (1.0,) if smoke else (1.0, 0.9, 0.8)
    cells = {}
    for cur in curs:
        g = product_engine(cur, maintenance_reviews=False)
        c = product_engine(cur, maintenance_reviews=False, scheduler="cpsat")
        goal = goal_of(g)
        L = g.plan(g.init_learner(), PlanContext(goal, FIND_L_DEADLINE, budget)).days[-1].day
        for f in fracs:
            dl = math.ceil(f * L)
            ctx = PlanContext(goal=goal, deadline_day=dl, budget=budget)
            gr, cp = _plan_cell(g, ctx, repeats), _plan_cell(c, ctx, repeats)
            # "oracle" = the branch-and-bound path the greedy-scheduler engine takes when greedy
            # misses the deadline (reason says so); there is no separate oracle engine.
            cells[f"{cur}|dl{dl}"] = {
                "L": L,
                "deadline_day": dl,
                "budget": budget,
                "greedy_or_oracle": gr,
                "cpsat": cp,
                "oracle_path_used": "ORACLE" in (gr["reason"] or "").upper(),
            }
    return {
        "ortools": ortools.__version__,
        "maintenance_reviews": False,
        "repeats": repeats,
        "cells": cells,
    }


def run_replan(smoke, repeats):
    out = {}
    for cur in ("synth-20-x10",) if smoke else CURRICULA:
        e = product_engine(cur)
        goal, dl, budget = goal_of(e), REPLAN_DEADLINE[cur], 15
        ctx = PlanContext(goal=goal, deadline_day=dl, budget=budget, current_day=1)
        rows = []
        for kind in EVENT_KINDS[:2] if smoke else EVENT_KINDS:
            state, log = e.init_learner(), ExecutionLog()
            warm = WorkloadCache()
            e.replan(state, log, ctx, workload_cache=warm)
            ex = [a for a in e.activities.values() if a.type == ActivityType.EXERCISE][0]
            evt = {
                "missed_day": Event(day=1, kind=EventType.MISSED),
                "failed_assessment": Event(
                    day=1,
                    kind=EventType.FAILED_ASSESSMENT,
                    activity_id=ex.activity_id,
                    minutes_elapsed=ex.duration,
                ),
                "budget_change": Event(day=1, kind=EventType.BUDGET_CHANGED, value=10),
                "deadline_change": Event(day=1, kind=EventType.DEADLINE_CHANGED, value=dl + 2),
            }[kind]
            state, log = e.record(state, log, evt)
            full = _ms(lambda: e.replan(state, log, ctx), repeats)
            front = _ms(
                lambda wc: e.replan(state, log, ctx, workload_cache=wc),
                repeats,
                setup=warm.copy,
            )
            same = e.replan(state, log, ctx) == e.replan(
                state, log, ctx, workload_cache=warm.copy()
            )
            rows.append(
                {
                    "event_kind": kind,
                    "median_full_ms": full,
                    "median_frontier_ms": front,
                    "speedup": round(full / front, 3) if front > 0 else None,
                    "plans_equal": same,
                }
            )
        out[cur] = {"goal": goal, "deadline": dl, "budget": budget, "rows": rows}
    return {"repeats": repeats, "curricula": out}


def run_plan(smoke, repeats):
    out = {}
    for cur in ("synth-20-x10",) if smoke else CURRICULA:
        e = product_engine(cur)
        s0, goal = e.init_learner(), goal_of(e)
        for b in (5,) if smoke else (5, 15, 30):
            for d in (7,) if smoke else (7, 14, 28):
                ctx = PlanContext(goal=goal, deadline_day=d, budget=b)
                out[f"{cur}|b{b}|d{d}"] = {
                    "median_ms": _ms(lambda: e.plan(s0, ctx), repeats),
                    "status": e.plan(s0, ctx).status.value,
                }
    return {"repeats": repeats, "cells": out}


def run_diag(smoke, learners):
    out = {}
    for cur in ("synth-20-x10",) if smoke else CURRICULA:
        e = product_engine(cur)
        goal, ts = goal_of(e), []
        for seed in REPORT_SEEDS[:learners]:
            sim = make_sim(e, seed, PROFILES["nominal"], "S1")
            t = time.perf_counter()
            e.diagnose(
                e.init_learner(),
                lambda a: sim.respond(
                    a.target_concept, a.activity_id, a.difficulty or 0.5, tag="diag"
                ),
                goal_concepts=[goal],  # the shipped goal-path flow (diagnostic_scope goal_path)
                session_id=str(seed),
            )
            ts.append((time.perf_counter() - t) * 1000.0)
        out[cur] = {"n_learners": len(ts), "median_ms": round(statistics.median(ts), 3)}
    return {"world": "S1", "profile": "nominal", "scope": "goal_path", "curricula": out}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("cpsat", "replan", "plan", "diag", "all"))
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args(argv)
    reps, learners = (2, 3) if a.smoke else (5, 50)
    runners = {
        "cpsat": lambda: run_cpsat(a.smoke, reps),
        "replan": lambda: run_replan(a.smoke, reps),
        "plan": lambda: run_plan(a.smoke, reps),
        "diag": lambda: run_diag(a.smoke, learners),
    }
    name = "planner_cost_smoke" if a.smoke else "planner_cost"
    base = a.out_dir or os.path.join(os.path.dirname(__file__), "results")
    path = os.path.join(base, f"{name}.json")
    payload = json.load(open(path)) if os.path.exists(path) else {}
    for key in runners if a.cmd == "all" else (a.cmd,):
        t0 = time.time()
        res = runners[key]()
        res["meta"] = {**stamp(), "smoke": a.smoke, "runtime_s": round(time.time() - t0, 1)}
        payload[key] = res
    payload.setdefault("meta", {})["smoke"] = a.smoke
    write_result(name, payload, a.out_dir)
    return payload


if __name__ == "__main__":
    main()
