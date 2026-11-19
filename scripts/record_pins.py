#!/usr/bin/env python3
"""Plan 0 (P0-T1/T2): record regression pins for "default unchanged" tests.

A pin file holds, for one EngineConfig: sweep-diagnostic outcomes on the 4- and 8-node
curricula, a small slice of the diagnostic matrix (experiments/results/w7_diag_matrix.json, S0),
one closed-loop next_activities episode, and the scripts/poc_demo.py output. Floats round-trip
exactly through JSON, so tests compare with ==.

    python scripts/record_pins.py population -> tests/fixtures/pins/population_prior.json
                                                (population_prior_config())
    python scripts/record_pins.py default    -> tests/fixtures/pins/default.json  (DEFAULT_CONFIG)

population_prior.json was recorded before any Plan 0 change; it must never be re-recorded
(tests/test_baseline_pins.py checks population_prior_config() against it).
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import os
import re
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG, EngineConfig  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.run_diag_matrix import run_world  # noqa: E402
from experiments.sim import PROFILES, make_sim  # noqa: E402

PIN_DIR = os.path.join(repo_root, "tests", "fixtures", "pins")
CURRICULA = {
    "4node": ("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"),
    "8node": ("data/curriculum/curriculum_8node.json", "data/curriculum/activities_8node.json"),
}
DIAG_SEEDS = tuple(range(101, 121, 2))  # 10 held-out (odd) simulated learners
MATRIX_SEEDS = tuple(range(101, 111, 2))  # 5 learners: a cheap slice of the diagnostic matrix


def _engine(name: str, cfg: EngineConfig) -> Engine:
    cur, act = CURRICULA[name]
    return Engine.from_files(os.path.join(repo_root, cur), os.path.join(repo_root, act), config=cfg)


def _diag_record(result) -> dict:
    return {
        "total_items": result.total_items,
        "items": [i.activity_id for i in result.item_log],
        "concepts": {
            c: [uc.p, uc.responses, uc.status.value]
            for c, uc in sorted(result.state.concepts.items())
        },
    }


def diagnostic_pins(cfg: EngineConfig) -> dict:
    out = {}
    prof = PROFILES["nominal"]
    for name in CURRICULA:
        eng = _engine(name, cfg)
        runs = {
            "all_wrong": eng.diagnose(eng.init_learner(), lambda a: False, session_id="pin"),
            "all_right": eng.diagnose(eng.init_learner(), lambda a: True, session_id="pin"),
        }
        for s in DIAG_SEEDS:
            sim = make_sim(eng, s, prof)
            runs[f"sim{s}"] = eng.diagnose(
                eng.init_learner(),
                lambda a, sim=sim: sim.respond(
                    a.target_concept, a.activity_id, a.difficulty, "diag"
                ),
                session_id=str(s),
            )
        out[name] = {k: _diag_record(r) for k, r in runs.items()}
    return out


def matrix_pins(cfg: EngineConfig) -> dict:
    return run_world("S0", list(MATRIX_SEEDS), PROFILES["nominal"], base=cfg)


def episode_pins(cfg: EngineConfig) -> dict:
    eng = _engine("4node", cfg)
    sc = get_scenario("missed_day", eng, eng.init_learner(), goal="C4", budget=15)
    res = run_episode(eng, seed=42, scenario=sc, arm="adapt", profile=PROFILES["nominal"])
    return json.loads(json.dumps(res, sort_keys=True, default=str))


def plan_pins(cfg: EngineConfig) -> dict:
    """Serialized plans with full traces, from cold start and after an all-wrong diagnostic."""
    from adaptengine.core.schema import PlanContext
    from adaptengine.planner import serialize_plan

    out = {}
    for name, goal in (("4node", "C4"), ("8node", "C8")):
        eng = _engine(name, cfg)
        ctx = PlanContext(goal=goal, deadline_day=14, budget=15, current_day=1)
        cold = eng.init_learner()
        diag = eng.diagnose(cold, lambda a: False, session_id="pin").state
        out[name] = {}
        for label, state in (("cold_start", cold), ("after_all_wrong_diag", diag)):
            plan = serialize_plan(eng.plan(state, ctx), cfg)
            del plan["config_hash"]  # changes whenever a plan adds a config field (rule 8)
            out[name][label] = json.loads(json.dumps(plan, sort_keys=True, default=str))
    return out


def poc_pins(cfg: EngineConfig) -> str:
    from scripts.poc_demo import run_demo

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_demo(config=cfg)
    return re.sub(r"adaptengine_poc_\w+", "adaptengine_poc_X", buf.getvalue())


def compute_pins(cfg: EngineConfig) -> dict:
    return {
        "diagnostic": diagnostic_pins(cfg),
        "diag_matrix_S0": matrix_pins(cfg),
        "episode": episode_pins(cfg),
        "plans": plan_pins(cfg),
        "config": json.loads(json.dumps(dataclasses.asdict(cfg))),
        "poc_demo": poc_pins(cfg),
    }


def main(which: str) -> str:
    if which == "population":
        from adaptengine.core.config import population_prior_config

        cfg, path = population_prior_config(), os.path.join(PIN_DIR, "population_prior.json")
    elif which == "default":
        cfg, path = DEFAULT_CONFIG, os.path.join(PIN_DIR, "default.json")
    else:
        raise SystemExit("usage: record_pins.py {population|default}")
    os.makedirs(PIN_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(compute_pins(cfg), f, indent=1, sort_keys=True)
        f.write("\n")
    return path


if __name__ == "__main__":
    print(main(sys.argv[1] if len(sys.argv) > 1 else ""))
