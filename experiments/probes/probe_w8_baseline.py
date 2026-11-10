#!/usr/bin/env python3
"""W8 task 0.2: reproduce the Week 7 review probes and save them as the W8 starting point.

Runs the same procedures as probe_w8.py §D, probe_w8_calib.py and probe_w8_sweep.py (copied
unchanged from the review) on seeds 100-299, 4-node, B = 15, calm, nominal profile and writes
experiments/results/w8_probe_baseline.json (code_hash + timestamp; no git).
"""

from __future__ import annotations

import dataclasses
import json
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path[:0] = [p for p in (ROOT, os.path.join(ROOT, "src")) if p not in sys.path]
os.chdir(ROOT)

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.core.schema import ActivityType, Event, EventType, PlanContext  # noqa: E402
from adaptengine.learner.state import ExecutionLog, is_evidence_mastered  # noqa: E402
from experiments import arms  # noqa: E402
from experiments.probes import probe_w8 as P  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES, TRUE_MASTERY_CUTOFF, make_sim  # noqa: E402
from experiments.stats import paired_bootstrap_ci  # noqa: E402

PROF, GOAL, B = PROFILES["nominal"], "C4", 15
SEEDS = range(100, 300)


def calib(eng, world, deadline):
    """probe_w8_calib.py: minutes used, idle days, belief vs truth on required concepts."""
    rows = []
    for seed in SEEDS:
        sim = make_sim(eng, seed, PROF, world=world)
        state, log = eng.init_learner(), ExecutionLog()
        minutes = idle = 0
        first_believed = None
        for day in range(1, deadline + 1):
            used = 0
            while used < B:
                ctx = PlanContext(goal=GOAL, deadline_day=deadline, budget=B, current_day=day)
                today, _ = eng.next_activities(state, log, ctx)
                if today is None:
                    break
                surprised = False
                for aid in today.activities:
                    a = eng.activities[aid]
                    if used + a.duration > B:
                        break
                    ok = (
                        sim.respond(a.target_concept, aid, a.difficulty, tag="run")
                        if a.type == ActivityType.EXERCISE
                        else None
                    )
                    ev = Event(
                        day=day,
                        kind=EventType.COMPLETED,
                        activity_id=aid,
                        minutes_elapsed=a.duration,
                        correct=ok,
                    )
                    state, log = eng.record(state, log, ev)
                    sim.apply_activity(a.target_concept, a.type == ActivityType.LESSON, day)
                    used += a.duration
                    minutes += a.duration
                    if first_believed is None and is_evidence_mastered(
                        state.concepts[GOAL], eng.config
                    ):
                        first_believed = sim.theta[GOAL]
                    if ok is False:
                        surprised = True
                        break
                if not surprised:
                    break
            if used == 0:
                idle += 1
        need = {GOAL} | eng.graph.ancestors(GOAL)
        believed = {c: is_evidence_mastered(state.concepts[c], eng.config) for c in need}
        true = {c: sim.theta[c] >= TRUE_MASTERY_CUTOFF for c in need}
        rows.append((minutes, idle, believed, true, first_believed))
    fm = sum(1 for r in rows for c in r[2] if r[2][c] and not r[3][c])
    tot_b = sum(1 for r in rows for c in r[2] if r[2][c])
    fb = [r[4] for r in rows if r[4] is not None]
    return {
        "deadline_days": deadline,
        "minutes_available": deadline * B,
        "mean_minutes_used": round(statistics.mean(r[0] for r in rows), 1),
        "mean_idle_days": round(statistics.mean(r[1] for r in rows), 2),
        "goal_believed_mastered": sum(r[2][GOAL] for r in rows),
        "goal_truly_mastered": sum(r[3][GOAL] for r in rows),
        "false_mastery_rate": round(fm / max(1, tot_b), 4),
        "mean_true_goal_theta_at_first_declared": round(statistics.mean(fb), 3),
        "share_below_cutoff_at_first_declared": round(
            sum(1 for x in fb if x < TRUE_MASTERY_CUTOFF) / len(fb), 3
        ),
    }


def delta_vs_static_loop(eng, sc, world, ref=None):
    sl = ref or [P.static_loop(eng, s, sc, world) for s in SEEDS]
    ad = [P.closed_loop(eng, s, sc, world) for s in SEEDS]
    d = [float(a["goal"]) - float(b["goal"]) for a, b in zip(ad, sl)]
    lo, hi = paired_bootstrap_ci(d)
    return sl, {
        "static_loop_goal_mastery": statistics.mean(float(x["goal"]) for x in sl),
        "adapt_goal_mastery": statistics.mean(float(x["goal"]) for x in ad),
        "delta": round(statistics.mean(d), 3),
        "ci95": [round(lo, 3), round(hi, 3)],
        "all_required_static_loop": statistics.mean(float(x["allreq"]) for x in sl),
        "all_required_adapt": statistics.mean(float(x["allreq"]) for x in ad),
        "violations_static_loop": sum(x["viol"] for x in sl),
        "violations_adapt": sum(x["viol"] for x in ad),
        "mean_minutes_adapt": round(statistics.mean(x["minutes"] for x in ad), 1),
    }


def main():
    eng = Engine.from_files(P.C4, P.A4)
    s0 = eng.init_learner()
    sc4 = arms.get_scenario("calm", eng, s0, goal=GOAL, budget=B)
    sc8 = dataclasses.replace(sc4, deadline=sc4.deadline * 2)
    out = {"metadata": {**stamp(), "seeds": [100, 299], "curriculum": "4-node", "budget": B}}
    out["calibration_probe"] = {w: calib(eng, w, sc8.deadline) for w in ("S0", "S1")}
    out["static_loop"] = {}
    refs = {}
    for world in ("S1", "S0"):
        for label, sc in (("4d", sc4), ("8d", sc8)):
            refs[(world, label)], out["static_loop"][f"{world}_{label}"] = delta_vs_static_loop(
                eng, sc, world
            )
    best = dataclasses.replace(
        DEFAULT_CONFIG, guess_coef=0.55, t_lesson=0.05, t_exercise=0.02, k_responses=3
    )
    e_best = Engine.from_files(P.C4, P.A4, config=best)
    out["sweep_best"] = {
        "config": {"guess_coef": 0.55, "t_lesson": 0.05, "t_exercise": 0.02, "k_responses": 3},
        "S1_8d": delta_vs_static_loop(e_best, sc8, "S1", refs[("S1", "8d")])[1],
    }
    path = os.path.join(ROOT, "experiments/results/w8_probe_baseline.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
