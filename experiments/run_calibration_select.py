#!/usr/bin/env python3
"""W8 B.3: pre-registered calibration selection (docs/preregistration/FINAL_A5_2026-11-10.md §3).

Candidates C0, F1-F5 (with C.1 + C.2 on) in the adapt closed loop; worlds S0, S1, S4 x 4-node,
8-node; B = 15, calm, 14 days; even selection seeds. Primary: in-loop Brier (pooled per cell,
mean over cells). Within 0.002 of the minimum: highest mean paired goal-mastery difference vs
static_loop. Writes experiments/results/w8_calibration_select.json.
"""

from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Pool

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402
from experiments.stats import brier_score, paired_summary, roc_auc  # noqa: E402
from experiments.w8_common import FINAL_FLAGS, SELECT_SEEDS, engine, goal_of  # noqa: E402

WORLDS, CURRICULA = ("S0", "S1", "S4"), ("4-node", "8-node")
TIE_MARGIN = 0.002
CANDIDATES = {  # id -> (profile kind, overrides)
    "C0": ("w7_default", {"k_responses": 2, "theta": 0.85}),
    "F1": ("fitted", {"k_responses": 2, "theta": 0.85}),
    "F2": ("fitted", {"k_responses": 3, "theta": 0.85}),
    "F3": ("fitted", {"k_responses": 2, "theta": 0.95}),
    "F4": ("fitted", {"k_responses": 3, "theta": 0.95}),
    "F5": ("fitted", {"k_responses": 2, "theta": 0.85, "horizon_aware_mastery": True}),
}


def candidate_engine(cand: str, world: str, cur: str):
    kind, ov = CANDIDATES[cand]
    profile = (
        "w7_default" if kind == "w7_default" else f"fitted_{world if world != 'S4F' else 'S4'}"
    )
    return engine(cur, profile, **{**ov, **FINAL_FLAGS})


def run_unit(u):
    cand, world, cur, seeds = u
    base = engine(cur)
    sc = get_scenario("calm", base, base.init_learner(), goal=goal_of(base), budget=15, horizon=14)
    e = base if cand == "static_loop" else candidate_engine(cand, world, cur)
    arm = "static_loop" if cand == "static_loop" else "adapt"
    rows = []
    for s in seeds:
        r = run_episode(e, s, sc, arm, PROFILES["nominal"], world=world)
        rows.append({"seed": s, "goal": float(r["goal_mastered"]), "attempts": r["attempts"],
                     "viol": r["executed_prereq_violations"], "util": r["minute_utilisation"]})  # fmt: skip
    return (cand, world, cur), rows


def main(out_path):
    t0 = time.time()
    meta = {
        **stamp(),
        "preregistration": "docs/preregistration/FINAL_A5_2026-11-10.md §3",
        "seeds": "even 4000-4398",
    }
    units = [
        (c, w, cur, SELECT_SEEDS[i : i + 50])
        for c in list(CANDIDATES) + ["static_loop"]
        for w in WORLDS
        for cur in CURRICULA
        for i in range(0, len(SELECT_SEEDS), 50)
    ]
    raw: dict = {}
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        for key, rows in pool.imap_unordered(run_unit, units):
            raw.setdefault(key, []).extend(rows)
    for v in raw.values():
        v.sort(key=lambda r: r["seed"])
    res = {}
    for c in CANDIDATES:
        cells = {}
        for w in WORLDS:
            for cur in CURRICULA:
                rows, ref = raw[(c, w, cur)], raw[("static_loop", w, cur)]
                pairs = [tuple(p) for r in rows for p in r["attempts"]]
                cells[f"{w}|{cur}"] = {
                    "brier": brier_score(pairs),
                    "auc": roc_auc(pairs),
                    "goal_mastery": round(sum(r["goal"] for r in rows) / len(rows), 4),
                    "vs_static_loop": paired_summary(
                        [r["goal"] for r in rows], [r["goal"] for r in ref]
                    ),
                    "executed_violations": sum(r["viol"] for r in rows),
                    "utilisation": round(sum(r["util"] for r in rows) / len(rows), 4),
                }
        res[c] = {
            "overrides": CANDIDATES[c][1],
            "profile": CANDIDATES[c][0],
            "cells": cells,
            "primary_mean_brier": round(sum(x["brier"] for x in cells.values()) / len(cells), 5),
            "secondary_mean_diff_vs_static_loop": round(
                sum(x["vs_static_loop"]["diff"] for x in cells.values()) / len(cells), 5
            ),
        }
    best = min(r["primary_mean_brier"] for r in res.values())
    tied = [c for c in CANDIDATES if res[c]["primary_mean_brier"] - best <= TIE_MARGIN]
    winner = max(
        tied,
        key=lambda c: (res[c]["secondary_mean_diff_vs_static_loop"], -list(CANDIDATES).index(c)),
    )
    out = {
        "metadata": {**meta, "runtime_s": round(time.time() - t0, 1)},
        "rule": "min mean in-loop Brier; within 0.002 -> max mean paired goal-mastery diff vs static_loop; then table order",
        "candidates": res,
        "min_primary": best,
        "tied_within_margin": tied,
        "winner": winner,
    }
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    for c, r in res.items():
        print(c, r["primary_mean_brier"], r["secondary_mean_diff_vs_static_loop"])
    print("tied:", tied, "WINNER:", winner, "runtime", out["metadata"]["runtime_s"])


if __name__ == "__main__":
    main(os.path.join(repo_root, "experiments/results/w8_calibration_select.json"))
