#!/usr/bin/env python3
"""W7 T4.4: full evaluation grid as pre-registered in docs/preregistration/W7_T4.1_2026-11-08.md.

Worlds S0-S4 x curricula (4-node, 8-node, synth-20) x budgets (5, 10, 15, 30) x scenarios
(4 W6 + 4 stress) x arms, N = 200 paired learners per cell; headline cell (S1, 4-node, B=15,
calm) and its S0 counterpart at N = 1000. Runs in parallel processes; deterministic.
Writes experiments/results/w7_grid.json (code_hash + timestamp; no git).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import tempfile
import time
from multiprocessing import Pool

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES, WORLDS  # noqa: E402
from experiments.stats import brier_score, paired_summary, roc_auc  # noqa: E402
from experiments.synth_curriculum import write_synthetic_curriculum  # noqa: E402

ARMS = ("adapt", "adapt_expected", "no_review", "no_replan", "static")
H7_ARMS = ("adapt_h7", "no_review_h7")
SCENARIOS = (
    "calm",
    "missed_day",
    "budget_drop",
    "deadline_cut",
    "missed_2days",
    "budget_crash",
    "deadline_halved",
    "forgetting_21",
)
BUDGETS = (5, 10, 15, 30)
CURRICULA = ("4-node", "8-node", "synth-20")
SEEDS = tuple(range(1000, 1200))
HEADLINE_SEEDS = tuple(range(1000, 2000))
HEADLINE = {("S1", "4-node", 15, "calm"), ("S0", "4-node", 15, "calm")}
# arm -> (engine variant, run_episode arm)
ARM_SPEC = {
    "adapt": ("default", "adapt"),
    "adapt_expected": ("expected", "adapt"),
    "no_review": ("default", "no_review"),
    "no_replan": ("default", "no_replan"),
    "static": ("default", "static"),
    "adapt_h7": ("h7", "adapt"),
    "no_review_h7": ("h7", "no_review"),
}
VARIANTS = {
    "default": {},
    "expected": {"projection_mode": "expected"},
    "h7": {"half_life_days": 7.0},
}

_ENGINES: dict = {}
_SYNTH: dict = {}  # synth-20 paths, written once by the parent before workers fork


def curriculum_paths(cur: str):
    if cur == "4-node":
        return ("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
    if cur == "8-node":
        return ("data/curriculum/curriculum_8node.json", "data/curriculum/activities_8node.json")
    if "paths" not in _SYNTH:
        _SYNTH["paths"] = write_synthetic_curriculum(tempfile.mkdtemp(), 20, seed=2026)
    return _SYNTH["paths"]


def engine(cur: str, variant: str) -> Engine:
    key = (cur, variant)
    if key not in _ENGINES:
        cp, ap = curriculum_paths(cur)
        cfg = dataclasses.replace(DEFAULT_CONFIG, **VARIANTS[variant])
        _ENGINES[key] = Engine.from_files(cp, ap, config=cfg, allow_unreviewed=cur == "synth-20")
    return _ENGINES[key]


def goal_of(e: Engine) -> str:
    return max(e.graph.concepts(), key=lambda c: (len(e.graph.ancestors(c)), c))


def run_unit(unit):
    world, cur, budget, scen, arm, seeds = unit
    base = engine(cur, "default")
    goal = goal_of(base)
    sc = get_scenario(scen, base, base.init_learner(), goal=goal, budget=budget)
    variant, run_arm = ARM_SPEC[arm]
    e = engine(cur, variant)
    prof = PROFILES["fast_forgetter" if scen == "forgetting_21" else "nominal"]
    out = []
    for s in seeds:
        r = run_episode(e, s, sc, run_arm, prof, world=world)
        out.append(
            {
                "seed": s,
                "goal_mastered": r["goal_mastered"],
                "goal_theta": r["goal_true_mastery"],
                "all_required": r["all_required_mastered"],
                "minutes": r["minutes_used"],
                "minutes_to_mastery": r["minutes_to_goal_mastery"],
                "exec_viol": r["executed_prereq_violations"],
                "plan_viol": r["plan_prereq_violations"],
                "budget_viol": r["budget_violations"],
                "deadline_viol": r["deadline_violations"],
                "idle_days": r["idle_days"],
                "ret_reviewed": r["retention_reviewed"],
                "ret_not_reviewed": r["retention_not_reviewed"],
                "coverage": r["plan_trace_coverage"],
                "attempts": r["attempts"],
                "traj": r["goal_theta_by_minutes"],
            }
        )
    return (world, cur, budget, scen, arm, sc.deadline), out


def theta_at(traj, minutes):
    v = traj[0][1]
    for m, th in traj:
        if m > minutes:
            break
        v = th
    return v


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def summarise_arm(rows):
    pairs = [tuple(p) for r in rows for p in r["attempts"]]
    reach = [r["minutes_to_mastery"] for r in rows]
    return {
        "n": len(rows),
        "goal_mastery_rate": mean([float(r["goal_mastered"]) for r in rows]),
        "mean_goal_theta": mean([r["goal_theta"] for r in rows]),
        "all_required_rate": mean([float(r["all_required"]) for r in rows]),
        "mean_minutes": mean([r["minutes"] for r in rows]),
        "reach_rate": mean([float(x is not None) for x in reach]),
        "mean_minutes_to_mastery": mean(reach),
        "executed_prereq_violations": sum(r["exec_viol"] for r in rows),
        "learners_with_executed_violations": sum(1 for r in rows if r["exec_viol"]),
        "plan_prereq_violations": sum(r["plan_viol"] for r in rows),
        "budget_violations": sum(r["budget_viol"] for r in rows),
        "deadline_violations": sum(r["deadline_viol"] for r in rows),
        "idle_days": sum(r["idle_days"] for r in rows),
        "retention_reviewed": mean([r["ret_reviewed"] for r in rows]),
        "retention_not_reviewed": mean([r["ret_not_reviewed"] for r in rows]),
        "brier": brier_score(pairs),
        "auc": roc_auc(pairs),
        "trace_coverage": mean([r["coverage"] for r in rows]),
    }


def paired(a_rows, b_rows):
    eq = [
        theta_at(a["traj"], m) - theta_at(b["traj"], m)
        for a, b in zip(a_rows, b_rows)
        for m in [min(a["minutes"], b["minutes"])]
    ]
    return {
        "goal_mastery": paired_summary(
            [float(r["goal_mastered"]) for r in a_rows], [float(r["goal_mastered"]) for r in b_rows]
        ),
        "goal_theta": paired_summary(
            [r["goal_theta"] for r in a_rows], [r["goal_theta"] for r in b_rows]
        ),
        "goal_theta_equal_minutes": paired_summary(eq, [0.0] * len(eq)),
        "all_required": paired_summary(
            [float(r["all_required"]) for r in a_rows], [float(r["all_required"]) for r in b_rows]
        ),
    }


def units(worlds, curricula):
    for world in worlds:
        for cur in curricula:
            for budget in BUDGETS:
                for scen in SCENARIOS:
                    if scen == "budget_drop" and budget == 5:
                        continue
                    if scen == "budget_crash" and budget != 30:
                        continue
                    seeds = HEADLINE_SEEDS if (world, cur, budget, scen) in HEADLINE else SEEDS
                    arms = ARMS + (H7_ARMS if scen == "forgetting_21" else ())
                    for arm in arms:
                        for i in range(0, len(seeds), 100):
                            yield (world, cur, budget, scen, arm, seeds[i : i + 100])


def main(out_path, worlds, curricula, procs):
    t0 = time.time()
    provenance = stamp()  # code_hash at start: the code the episodes actually ran
    curriculum_paths("synth-20")
    raw: dict = {}
    with Pool(procs) as pool:
        for key, rows in pool.imap_unordered(run_unit, list(units(worlds, curricula)), 4):
            raw.setdefault(key, []).extend(rows)
    cells: dict = {}
    for (world, cur, budget, scen, arm, deadline), rows in raw.items():
        rows.sort(key=lambda r: r["seed"])
        cid = f"{world}|{cur}|B{budget}|{scen}"
        cells.setdefault(cid, {"deadline": deadline, "arms": {}, "_rows": {}})
        cells[cid]["arms"][arm] = summarise_arm(rows)
        cells[cid]["_rows"][arm] = rows
    for c in cells.values():
        rows = c.pop("_rows")
        c["paired_vs_static"] = {a: paired(rows[a], rows["static"]) for a in rows if a != "static"}
        c["paired_adapt_vs"] = {
            b: paired(rows["adapt"], rows[b]) for b in ("no_review", "no_replan", "adapt_expected")
        }
        if "adapt_h7" in rows:
            c["paired_adapt_h7_vs_no_review_h7"] = paired(rows["adapt_h7"], rows["no_review_h7"])
    res = {
        "metadata": {
            **provenance,
            "preregistration": "docs/preregistration/W7_T4.1_2026-11-08.md",
            "worlds": list(worlds),
            "curricula": list(curricula),
            "budgets": list(BUDGETS),
            "scenarios": list(SCENARIOS),
            "n_per_cell": len(SEEDS),
            "headline_cells": sorted("|".join(map(str, h)) for h in HEADLINE),
            "n_headline": len(HEADLINE_SEEDS),
            "runtime_s": round(time.time() - t0, 1),
            "processes": procs,
        },
        "cells": dict(sorted(cells.items())),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(repo_root, "experiments/results/w7_grid.json"))
    ap.add_argument("--worlds", nargs="*", default=list(WORLDS))
    ap.add_argument("--curricula", nargs="*", default=list(CURRICULA))
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    r = main(a.out, a.worlds, a.curricula, a.procs)
    print("cells:", len(r["cells"]), "runtime_s:", r["metadata"]["runtime_s"])
