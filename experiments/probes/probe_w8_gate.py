#!/usr/bin/env python3
"""WP-A exit gate: reproduce the W8 probe numbers through experiments.arms (static_loop arm,
fixed horizons, false-mastery and utilisation metrics). Prints a JSON summary."""

import json
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path[:0] = [p for p in (ROOT, os.path.join(ROOT, "src")) if p not in sys.path]
os.chdir(ROOT)

from adaptengine.api import Engine  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402
from experiments.stats import paired_bootstrap_ci  # noqa: E402

eng = Engine.from_files(
    "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
)
out = {}
for world in ("S0", "S1"):
    for h in (4, 8):
        sc = get_scenario("calm", eng, eng.init_learner(), goal="C4", budget=15, horizon=h)
        ad = [run_episode(eng, s, sc, "adapt", PROFILES["nominal"], world) for s in range(100, 300)]
        sl = [
            run_episode(eng, s, sc, "static_loop", PROFILES["nominal"], world)
            for s in range(100, 300)
        ]
        d = [float(a["goal_mastered"]) - float(b["goal_mastered"]) for a, b in zip(ad, sl)]
        out[f"{world}_{h}d"] = {
            "delta_vs_static_loop": round(statistics.mean(d), 3),
            "ci95": paired_bootstrap_ci(d),
            "adapt_minutes": round(statistics.mean(r["minutes_used"] for r in ad), 1),
            "false_mastery_rate_pooled": round(
                sum(r["false_mastered"] for r in ad) / sum(r["believed_mastered"] for r in ad), 4
            ),
            "violations_static_loop": sum(r["executed_prereq_violations"] for r in sl),
            "violations_adapt": sum(r["executed_prereq_violations"] for r in ad),
        }
print(json.dumps(out, indent=1))
