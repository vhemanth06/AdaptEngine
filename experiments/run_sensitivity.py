#!/usr/bin/env python3
"""W7 WP5: sensitivity of the closed-loop engine to its heuristic parameters.

T5.2 one-at-a-time scans, T5.3 theta x k factorial, T5.4 alternative mastery criteria.
Cells: worlds S0, S1 x curricula 4-node, 8-node; budget 15; calm; arm adapt (static reference
once per cell); N = 200 paired learners (seeds 1000-1199). The horizon of each cell is fixed
from DEFAULT_CONFIG so every configuration is compared at the same deadline.
Writes experiments/results/w7_sensitivity.json (code_hash + timestamp; no git).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from multiprocessing import Pool

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402
from experiments.stats import paired_summary  # noqa: E402

CURRICULA = {
    "4-node": ("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"),
    "8-node": ("data/curriculum/curriculum_8node.json", "data/curriculum/activities_8node.json"),
}
WORLDS = ("S0", "S1")
SEEDS = tuple(range(1000, 1200))
BUDGET = 15
SCANS = {
    "theta": (0.70, 0.75, 0.80, 0.85, 0.90, 0.95),
    "k_responses": (1, 2, 3, 4),
    "half_life_days": (7.0, 14.0, 30.0, 60.0),
    "p0": (0.10, 0.20, 0.30, 0.40),
    "t_lesson": (0.10, 0.20, 0.30),
    "recall_threshold": (0.70, 0.80, 0.90),
    "remediation_threshold": (0.30, 0.40, 0.50),
}
FACTORIAL = [{"theta": t, "k_responses": k} for t in (0.75, 0.85, 0.95) for k in (1, 2, 3)]
CRITERIA = {
    "bkt_threshold": {"mastery_criterion": "bkt_threshold"},
    "n_consecutive_2": {"mastery_criterion": "n_consecutive", "n_consecutive": 2},
    "n_consecutive_3": {"mastery_criterion": "n_consecutive", "n_consecutive": 3},
    "two_threshold": {"mastery_criterion": "two_threshold"},
}


def configs():
    out = {"baseline": {}}
    for name, values in SCANS.items():
        for v in values:
            out[f"{name}={v}"] = {name: v}
    for f in FACTORIAL:
        out[f"theta={f['theta']}|k={f['k_responses']}"] = f
    for name, kw in CRITERIA.items():
        out[f"criterion={name}"] = kw
    return out


def run_unit(unit):
    world, cur, label, kw, arm = unit
    cp, ap = CURRICULA[cur]
    base = Engine.from_files(cp, ap)
    goal = max(base.graph.concepts(), key=lambda c: (len(base.graph.ancestors(c)), c))
    sc = get_scenario("calm", base, base.init_learner(), goal=goal, budget=BUDGET)
    e = Engine.from_files(cp, ap, config=dataclasses.replace(DEFAULT_CONFIG, **kw))
    rows = []
    for s in SEEDS:
        r = run_episode(e, s, sc, arm, PROFILES["nominal"], world=world)
        rows.append(
            (
                float(r["goal_mastered"]),
                r["goal_true_mastery"],
                r["minutes_used"],
                r["executed_prereq_violations"],
                float(r["all_required_mastered"]),
            )
        )
    return (world, cur, label, arm), rows


def mean(xs):
    return round(sum(xs) / len(xs), 4)


def main(out_path, procs):
    t0 = time.time()
    provenance = stamp()
    cfgs = configs()
    units = [
        (w, c, lab, kw, "adapt") for w in WORLDS for c in CURRICULA for lab, kw in cfgs.items()
    ]
    units += [(w, c, "static", {}, "static") for w in WORLDS for c in CURRICULA]
    with Pool(procs) as pool:
        raw = dict(pool.imap_unordered(run_unit, units))
    cells = {}
    for w in WORLDS:
        for c in CURRICULA:
            base = raw[(w, c, "baseline", "adapt")]
            rows = {}
            for lab in list(cfgs) + ["static"]:
                r = raw[(w, c, lab, "static" if lab == "static" else "adapt")]
                rows[lab] = {
                    "goal_mastery_rate": mean([x[0] for x in r]),
                    "mean_goal_theta": mean([x[1] for x in r]),
                    "mean_minutes": mean([x[2] for x in r]),
                    "executed_prereq_violations": sum(x[3] for x in r),
                    "all_required_rate": mean([x[4] for x in r]),
                    "vs_baseline_goal_mastery": paired_summary(
                        [x[0] for x in r], [x[0] for x in base]
                    ),
                    "vs_baseline_minutes": paired_summary([x[2] for x in r], [x[2] for x in base]),
                }
            cells[f"{w}|{c}"] = rows
    res = {
        "metadata": {
            **provenance,
            "worlds": list(WORLDS),
            "curricula": list(CURRICULA),
            "budget": BUDGET,
            "scenario": "calm (horizon fixed from DEFAULT_CONFIG)",
            "n": len(SEEDS),
            "scans": {k: list(v) for k, v in SCANS.items()},
            "runtime_s": round(time.time() - t0, 1),
        },
        "cells": cells,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out", default=os.path.join(repo_root, "experiments/results/w7_sensitivity.json")
    )
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    r = main(a.out, a.procs)
    print("runtime_s", r["metadata"]["runtime_s"])
