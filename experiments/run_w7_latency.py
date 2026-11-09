#!/usr/bin/env python3
"""W7 T6.1: planning latency and plan identity for the precomputed graph indices.

`--snapshot PATH` writes a digest of every plan in a fixed grid (4-node, 8-node, synth-20,
synth-50 x budgets x deadlines x events, plus 50 random event walks per small curriculum);
`--compare PATH` checks the current code produces identical digests. Timing mode reports mean
full-plan / frontier-replan latency per curriculum and the oracle path (synth-50, budget 10,
budget-change) separately. Writes JSON with code_hash (no git).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import statistics
import sys
import tempfile
import time

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.schema import ActivityType, Event, EventType, PlanContext  # noqa: E402
from adaptengine.learner.state import ExecutionLog  # noqa: E402
from adaptengine.planner import serialize_plan  # noqa: E402
from adaptengine.planner.workload import WorkloadCache  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.synth_curriculum import write_synthetic_curriculum  # noqa: E402


def engines():
    out = {
        "4-node": Engine.from_files(
            "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
        ),
        "8-node": Engine.from_files(
            "data/curriculum/curriculum_8node.json", "data/curriculum/activities_8node.json"
        ),
    }
    tmp = tempfile.mkdtemp()
    for n in (20, 50):
        cp, ap = write_synthetic_curriculum(os.path.join(tmp, str(n)), n, seed=2026)
        out[f"synth-{n}"] = Engine.from_files(cp, ap, allow_unreviewed=True)
    return out


def deepest_goal(e) -> str:
    """Goal with the most ancestors (ties: largest id) so the whole path is planned."""
    return max(e.graph.concepts(), key=lambda c: (len(e.graph.ancestors(c)), c))


def digest(plan) -> str:
    return hashlib.sha256(json.dumps(serialize_plan(plan), sort_keys=True).encode()).hexdigest()


def snapshot(engs) -> dict:
    out = {}
    for name, e in engs.items():
        goal = deepest_goal(e)
        s0 = e.init_learner()
        for b in (5, 10, 15, 30):
            for dl in (3, 6, 12, 40):
                out[f"{name}|b{b}|d{dl}"] = digest(
                    e.plan(s0, PlanContext(goal=goal, deadline_day=dl, budget=b))
                )
        if name in ("synth-20", "synth-50"):
            continue
        rng = random.Random(f"walk|{name}")
        for w in range(50):  # random event walks through record() + replan()
            state, log = s0, ExecutionLog()
            ctx = PlanContext(goal=goal, deadline_day=20, budget=rng.choice((10, 15, 30)))
            for day in range(1, 6):
                today, plan = e.next_activities(
                    state,
                    log,
                    PlanContext(goal=goal, deadline_day=20, budget=ctx.budget, current_day=day),
                )
                out[f"{name}|walk{w}|day{day}"] = digest(plan)
                for aid in today.activities if today else ():
                    a = e.activities[aid]
                    ok = None if a.type == ActivityType.LESSON else rng.random() < 0.6
                    state, log = e.record(
                        state, log, Event(day, EventType.COMPLETED, aid, a.duration, ok)
                    )
                if rng.random() < 0.2:
                    state, log = e.record(state, log, Event(day, EventType.MISSED))
    return out


def timed(fn, repeats):
    ts = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t) * 1000.0)
    return round(statistics.mean(ts), 3), round(statistics.stdev(ts), 3) if len(ts) > 1 else 0.0


def timing(engs, repeats) -> dict:
    res = {}
    for name, e in engs.items():
        goal = deepest_goal(e)
        s0 = e.init_learner()
        ctx = PlanContext(goal=goal, deadline_day=200, budget=15)
        log = ExecutionLog().append(Event(1, EventType.MISSED))
        cache = WorkloadCache()
        e.replan(s0, log, ctx, workload_cache=cache)  # warm the frontier cache
        res[name] = {
            "full_plan_ms": timed(lambda: e.plan(s0, ctx), repeats),
            "frontier_replan_ms": timed(
                lambda: e.replan(s0, log, ctx, workload_cache=cache.copy()), repeats
            ),
        }
    # Oracle path, reported separately: synth-50, budget 10, deadline 58 (greedy needs 59 days)
    e = engs["synth-50"]
    s0 = e.init_learner()
    ctx = PlanContext(goal=deepest_goal(e), deadline_day=58, budget=10)
    res["synth-50_oracle_b10_d58"] = {
        "reason": e.plan(s0, ctx).reason,
        "plan_ms": timed(lambda: e.plan(s0, ctx), max(3, repeats // 5)),
    }
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    ap.add_argument("--compare")
    ap.add_argument("--timing-out")
    ap.add_argument("--repeats", type=int, default=20)
    a = ap.parse_args()
    engs = engines()
    if a.snapshot:
        json.dump(snapshot(engs), open(a.snapshot, "w"), indent=0, sort_keys=True)
    if a.compare:
        old, new = json.load(open(a.compare)), snapshot(engs)
        diff = [k for k in old if old[k] != new.get(k)]
        print(f"plans compared: {len(old)}; different: {len(diff)}", diff[:5])
    if a.timing_out:
        t = {**stamp(), "repeats": a.repeats, "results": timing(engs, a.repeats)}
        json.dump(t, open(a.timing_out, "w"), indent=2, sort_keys=True)
        print(json.dumps(t["results"], indent=1))
