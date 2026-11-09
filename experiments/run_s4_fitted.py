#!/usr/bin/env python3
"""W7 T7.5 (exploratory, NOT pre-registered): the S4 world driven by the ASSISTments-fitted
profile (config/fitted_assist09.json: prior 0.74, learn 0.07, class guess/slip). 4-node, B=15,
calm and missed_day, arms adapt / no_replan / static, N = 200 paired learners (seeds 1000-1199).
Writes experiments/results/w7_s4_fitted.json.
"""

from __future__ import annotations

import json
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES, s4_fitted_params  # noqa: E402
from experiments.stats import paired_summary  # noqa: E402

PROFILE = os.path.join(repo_root, "config", "fitted_assist09.json")


def main():
    e = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    kw = {"bkt_params": s4_fitted_params(PROFILE)}
    out = {
        "metadata": {
            **stamp(),
            "profile": "config/fitted_assist09.json",
            "n": 200,
            "status": "exploratory, not pre-registered",
        }
    }
    for sc_name in ("calm", "missed_day"):
        sc = get_scenario(sc_name, e, e.init_learner(), goal="C4", budget=15)
        runs = {
            a: [
                run_episode(e, s, sc, a, PROFILES["nominal"], world="S4", sim_kw=kw)
                for s in range(1000, 1200)
            ]
            for a in ("adapt", "no_replan", "static")
        }
        cell = {}
        for a, rs in runs.items():
            cell[a] = {
                "goal_mastery_rate": round(sum(r["goal_mastered"] for r in rs) / len(rs), 4),
                "all_required_rate": round(
                    sum(r["all_required_mastered"] for r in rs) / len(rs), 4
                ),
                "mean_minutes": round(sum(r["minutes_used"] for r in rs) / len(rs), 2),
                "executed_prereq_violations": sum(r["executed_prereq_violations"] for r in rs),
                "vs_static_goal_mastery": paired_summary(
                    [float(r["goal_mastered"]) for r in rs],
                    [float(r["goal_mastered"]) for r in runs["static"]],
                ),
            }
        out[sc_name] = cell
    json.dump(
        out,
        open(os.path.join(repo_root, "experiments/results/w7_s4_fitted.json"), "w"),
        indent=2,
        sort_keys=True,
    )
    print(json.dumps({k: v for k, v in out.items() if k != "metadata"}, indent=1))


if __name__ == "__main__":
    main()
