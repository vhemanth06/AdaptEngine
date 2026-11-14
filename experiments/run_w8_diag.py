#!/usr/bin/env python3
"""W8: goal-search diagnostic vs prior-only / W6 shipped / T3.3 default, per curriculum and world.
Writes experiments/results/w8_diag_matrix.json."""

from __future__ import annotations

import argparse
import json
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.core.profiles import GOAL_SEARCH_DIAGNOSTIC  # noqa: E402
from experiments.diag_eval import W6_DIAGNOSTIC, binary_score, summarize  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES, make_sim  # noqa: E402
from experiments.w8_common import engine  # noqa: E402

VARIANTS = {
    "w6_shipped": W6_DIAGNOSTIC,
    "default_t33": {},
    "goal_search": GOAL_SEARCH_DIAGNOSTIC,
}


def run_world(cur: str, world: str, seeds, prof) -> dict:
    engines = {k: engine(cur, "w7_default", **v) for k, v in VARIANTS.items()}
    base = engines["default_t33"]
    rows: dict[str, list] = {}
    items: dict[str, list] = {}

    def add(name, eng, st, n, s):
        rows.setdefault(name, []).append(binary_score(eng, st, s, prof, world))
        items.setdefault(name, []).append(n)

    for s in seeds:
        add("prior_only", base, base.init_learner(), 0, s)
        for name, eng in engines.items():
            sim = make_sim(eng, s, prof, world)

            def provider(a, sim=sim):
                return sim.respond(a.target_concept, a.activity_id, a.difficulty, tag="diag")

            r = eng.diagnose(eng.init_learner(), provider, None, session_id=str(s))
            add(name, eng, r.state, r.total_items, s)

    return summarize(rows, items)


def main(out_path: str, n: int, curricula: list[str]) -> dict:
    prof = PROFILES["nominal"]
    seeds = list(range(101, 101 + 2 * n, 2))  # held-out (odd) learners
    res = {
        "metadata": {**stamp(), "seeds": [seeds[0], seeds[-1], "odd"], "n_learners": len(seeds)},
        "curricula": {
            c: {w: run_world(c, w, seeds, prof) for w in ("S0", "S2", "S4")} for c in curricula
        },
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, sort_keys=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(repo_root, "experiments/results/w8_diag_matrix.json"))
    ap.add_argument("--n", type=int, default=250)
    ap.add_argument("--curricula", nargs="*", default=["4-node", "8-node"])
    a = ap.parse_args()
    main(a.out, a.n, a.curricula)
