"""Replan latency benchmark (experiments/run_replan_latency.py).

Measures latency of full replanning vs frontier replanning across curricula
(4-node, 8-node, synth-20, synth-50) and event types.
Outputs experiments/results/replan_latency.json.
"""

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.schema import ActivityType, Event, EventType, PlanContext  # noqa: E402
from adaptengine.learner.state import ExecutionLog  # noqa: E402
from adaptengine.planner.workload import WorkloadCache  # noqa: E402
from experiments.synth_curriculum import write_synthetic_curriculum  # noqa: E402


def get_git_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode("ascii")
            .strip()
        )
    except Exception:
        return "unknown"


def benchmark_cell(
    engine: Engine,
    goal: str,
    deadline: int,
    budget: int,
    event_kind: str,
    repeats: int,
) -> Dict[str, Any]:
    ctx = PlanContext(goal=goal, deadline_day=deadline, budget=budget, current_day=1)
    state = engine.init_learner()
    log = ExecutionLog()

    # Pre-event plan for stability calculation
    plan0 = engine.replan(state, log, ctx)
    day_map0 = {aid: day.day for day in plan0.days for aid in day.activities}

    # Warm cache untimed on pre-event state
    warm = WorkloadCache()
    engine.replan(state, log, ctx, workload_cache=warm)

    # Build and apply event
    exercises = [a for a in engine.activities.values() if a.type == ActivityType.EXERCISE]
    if event_kind == "missed_day":
        evt = Event(day=1, kind=EventType.MISSED)
    elif event_kind == "failed_assessment":
        ex = exercises[0]
        evt = Event(
            day=1,
            kind=EventType.FAILED_ASSESSMENT,
            activity_id=ex.activity_id,
            minutes_elapsed=ex.duration,
        )
    elif event_kind == "budget_change":
        evt = Event(day=1, kind=EventType.BUDGET_CHANGED, value=10 if budget != 10 else 15)
    elif event_kind == "deadline_change":
        evt = Event(day=1, kind=EventType.DEADLINE_CHANGED, value=deadline + 2)
    else:
        raise ValueError(f"Unknown event kind: {event_kind}")

    state, log = engine.record(state, log, evt)

    # Untimed warm-up
    warm_copy = warm.copy()
    _ = engine.replan(state, log, ctx)
    _ = engine.replan(state, log, ctx, workload_cache=warm_copy)

    times_full: List[float] = []
    times_front: List[float] = []
    last_hits = 0
    last_misses = 0
    last_plan = None

    for _ in range(repeats):
        t0 = time.perf_counter_ns()
        plan_full = engine.replan(state, log, ctx)
        t1 = time.perf_counter_ns()
        times_full.append((t1 - t0) / 1e6)

        c = warm.copy()
        t0 = time.perf_counter_ns()
        plan_front = engine.replan(state, log, ctx, workload_cache=c)
        t1 = time.perf_counter_ns()
        times_front.append((t1 - t0) / 1e6)

        assert plan_full == plan_front, "Plan mismatch between full and frontier replanning!"
        last_hits = c.hits
        last_misses = c.misses
        last_plan = plan_full

    # Calculate stability
    total_acts = sum(len(d.activities) for d in last_plan.days)
    matching_acts = sum(
        1 for d in last_plan.days for aid in d.activities if day_map0.get(aid) == d.day
    )
    stability = round(matching_acts / total_acts, 4) if total_acts > 0 else 1.0

    times_full_sorted = sorted(times_full)
    times_front_sorted = sorted(times_front)
    p95_idx = int(0.95 * len(times_full_sorted))

    med_full = round(statistics.median(times_full), 3)
    p95_full = round(times_full_sorted[p95_idx], 3)
    med_front = round(statistics.median(times_front), 3)
    p95_front = round(times_front_sorted[p95_idx], 3)
    speedup = round(med_full / med_front, 3) if med_front > 0 else 1.0

    return {
        "event_kind": event_kind,
        "median_full_ms": med_full,
        "p95_full_ms": p95_full,
        "median_frontier_ms": med_front,
        "p95_frontier_ms": p95_front,
        "speedup": speedup,
        "cache_hits": last_hits,
        "cache_misses": last_misses,
        "stability": stability,
    }


def run_benchmark(quick: bool = False) -> Dict[str, Any]:
    repeats = 5 if quick else 30
    curricula_configs = [
        (
            "4-node",
            os.path.join(REPO_ROOT, "data/curriculum/curriculum_4node.json"),
            os.path.join(REPO_ROOT, "data/curriculum/activities_4node.json"),
            "C4",
            10,
            False,
        ),
        (
            "8-node",
            os.path.join(REPO_ROOT, "data/curriculum/curriculum_8node.json"),
            os.path.join(REPO_ROOT, "data/curriculum/activities_8node.json"),
            "C8",
            15,
            True,
        ),
    ]

    temp_dir = None
    if not quick:
        temp_dir = tempfile.TemporaryDirectory()
        cp20, ap20 = write_synthetic_curriculum(temp_dir.name, 20, seed=2026)
        cp50, ap50 = write_synthetic_curriculum(temp_dir.name, 50, seed=2026)
        curricula_configs.extend(
            [
                ("synth-20", cp20, ap20, "C20", 25, True),
                ("synth-50", cp50, ap50, "C50", 60, True),
            ]
        )

    event_kinds = ["missed_day", "failed_assessment", "budget_change", "deadline_change"]
    results_by_curriculum = {}

    for name, cp, ap, goal, deadline, allow_unreviewed in curricula_configs:
        engine = Engine.from_files(cp, ap, allow_unreviewed=allow_unreviewed)
        curriculum_results = []
        for ek in event_kinds:
            cell_res = benchmark_cell(
                engine=engine,
                goal=goal,
                deadline=deadline,
                budget=15,
                event_kind=ek,
                repeats=repeats,
            )
            curriculum_results.append(cell_res)
        results_by_curriculum[name] = curriculum_results

    if temp_dir is not None:
        temp_dir.cleanup()

    return {
        "metadata": {
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "git_sha": get_git_sha(),
            "repeats": repeats,
            "quick": quick,
        },
        "curricula": results_by_curriculum,
    }


def main():
    parser = argparse.ArgumentParser(description="Replan latency benchmark.")
    parser.add_argument(
        "--quick", action="store_true", help="Run quick benchmark (fewer repeats, 4/8-node only)."
    )
    args = parser.parse_args()

    data = run_benchmark(quick=args.quick)
    out_dir = os.path.join(REPO_ROOT, "experiments", "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "replan_latency.json")

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Replan latency benchmark written to {out_path}")
    print(f"Git SHA: {data['metadata']['git_sha']}")
    for curr, rows in data["curricula"].items():
        print(f"\n--- {curr} ---")
        for r in rows:
            print(
                f"  {r['event_kind']:<18}: full {r['median_full_ms']:>6.2f}ms | front {r['median_frontier_ms']:>6.2f}ms | speedup {r['speedup']:>5.2f}x | hits {r['cache_hits']:>2} | misses {r['cache_misses']:>2} | stab {r['stability']:>4.2f}"
            )


if __name__ == "__main__":
    main()
