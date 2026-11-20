#!/usr/bin/env python3
"""Plan 3.5, P3.5-T1: safety re-check of the F1 planner fix. NOT the registered F1 result.

Re-runs every closed-loop cell of F1 run 1 (experiments/results/f1_grid_run1.json) that had at
least one executed prerequisite violation, with the current code, run 1's frozen bisection
settings and run 1's seeds, with all of run 1's learners by default (N = 200; --n for fewer). Every cell must have
0 executed prerequisite violations. Writes experiments/results/f1_safety_check.json.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from experiments.provenance import stamp  # noqa: E402
from experiments.run_f1_grid import LOOP_ARMS, TWO_BY_TWO, loop_cell  # noqa: E402
from experiments.run_w7_grid import curriculum_paths  # noqa: E402

RUN1 = os.path.join(repo_root, "experiments/results/f1_grid_run1.json")
LABEL = "safety re-check, not the registered result"


def violation_cells(run1: dict) -> list[tuple[str, str, str]]:
    return sorted(
        (w, c, a)
        for w, row in run1["closed_loop"].items()
        for c, cell in row.items()
        for a, v in cell.items()
        if a != "paired" and v["executed_prereq_violations"]
    )


def main(out_path, n: int = 200, procs: int = 1) -> dict:
    with open(RUN1, encoding="utf-8") as f:
        run1 = json.load(f)
    frozen = run1["metadata"]["frozen_bisection_settings"]
    first = run1["metadata"]["episode_seeds"][0]
    seeds = tuple(range(first, first + n))
    cells = violation_cells(run1)
    arms = {**LOOP_ARMS, **TWO_BY_TWO}
    for c in {c for _, c, _ in cells}:
        curriculum_paths(c)  # write synthetic curricula once, before workers fork
    units = [(w, c, a, arms[a], seeds, frozen) for w, c, a in cells]
    if procs > 1:
        with mp.get_context("fork").Pool(procs) as pool:
            out = dict(pool.map(loop_cell, units, chunksize=1))
    else:
        out = dict(map(loop_cell, units))
    res = {
        "metadata": {
            **stamp(),
            "label": LABEL,
            "source": "experiments/results/f1_grid_run1.json",
            "frozen_bisection_settings": frozen,
            "seeds": [seeds[0], seeds[-1]],
            "n_per_cell": n,
            "n_cells": len(cells),
        },
        "cells": [
            {
                "world": w,
                "curriculum": c,
                "arm": a,
                "run1_violations": run1["closed_loop"][w][c][a]["executed_prereq_violations"],
                "executed_prereq_violations": sum(r["exec_viol"] for r in out[(w, c, a)]),
                "n": len(out[(w, c, a)]),
            }
            for w, c, a in cells
        ],
    }
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out", default=os.path.join(repo_root, "experiments/results/f1_safety_check.json")
    )
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    r = main(a.out, a.n, a.procs)
    bad = [x for x in r["cells"] if x["executed_prereq_violations"]]
    print(f"{len(r['cells'])} cells, N={a.n}: {len(bad)} with violations")
    for x in bad:
        print(x)
