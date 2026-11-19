#!/usr/bin/env python3
"""Plan 1, F5-T6 (D86): sanity baseline on 8-node vs 8-node-x10 (more exercises only).

The W7 baseline engine (sweep diagnostic, greedy planner, DEFAULT_CONFIG) on both curricula,
worlds S0-S4, with the W7 seeds:
- diagnostic: odd seeds 101.. (as experiments/run_diag_matrix.py), Brier / AUC / items against
  binary truth (W7 T3.1), paired x10 - 8node;
- closed-loop episodes: adapt arm, budget 15, scenarios calm and missed_day, seeds 1000..
  (as experiments/run_w7_grid.py), paired x10 - 8node.

Pre-registration: docs/preregistration/F5_2026-11-20.md (registered before the full run, D47).
8-node-x10 is recorded as PENDING_HUMAN_REVIEW (D88) and loaded with allow_unreviewed=True; the
result file says whether each curriculum file passed the review gate.

    python experiments/run_f5_baseline.py              # full run -> experiments/results/f5_baseline.json
    python experiments/run_f5_baseline.py --n-diag 2 --n-episodes 2 --out /tmp/f5.json   # smoke
"""

from __future__ import annotations

import argparse
import json
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.core.config import config_hash  # noqa: E402
from adaptengine.core.errors import UnreviewedContentError  # noqa: E402
from adaptengine.curriculum.loader import load_activities, load_curriculum  # noqa: E402
from experiments.diag_eval import binary_score  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.run_w7_grid import (  # noqa: E402
    curriculum_paths,
    engine,
    paired,
    run_unit,
    summarise_arm,
)
from experiments.sim import PROFILES, WORLDS, make_sim  # noqa: E402
from experiments.stats import paired_summary, roc_auc  # noqa: E402

PREREGISTRATION = "docs/preregistration/F5_2026-11-20.md"
PENDING_LABEL = "AI-checked, human review pending (D88); loaded with allow_unreviewed=True"
CURRICULA = ("8-node", "8-node-x10")
SCENARIOS = ("calm", "missed_day")
BUDGET = 15


def review_status(cur: str) -> str:
    cp, ap = curriculum_paths(cur)
    try:
        load_activities(os.path.join(repo_root, ap), load_curriculum(os.path.join(repo_root, cp)))
    except UnreviewedContentError as e:
        if "pending human review" in str(e):
            return PENDING_LABEL
        return "unreviewed (loaded with allow_unreviewed=True)"
    return "reviewed"


def diagnostic_rows(cur: str, world: str, seeds) -> list[dict]:
    e, prof = engine(cur, "default"), PROFILES["nominal"]
    rows = []
    for s in seeds:
        sim = make_sim(e, s, prof, world)
        r = e.diagnose(
            e.init_learner(),
            lambda a, sim=sim: sim.respond(a.target_concept, a.activity_id, a.difficulty, "diag"),
            session_id=str(s),
        )
        rows.append({**binary_score(e, r.state, s, prof, world), "items": r.total_items})
    return rows


def summarise_diag(rows) -> dict:
    pairs = [p for r in rows for p in r["pairs"]]
    return {
        "n": len(rows),
        "brier": round(sum(r["brier"] for r in rows) / len(rows), 4),
        "next_response_brier": round(sum(r["next_brier"] for r in rows) / len(rows), 4),
        "auc": roc_auc(pairs),
        "items": round(sum(r["items"] for r in rows) / len(rows), 3),
    }


def main(out_path: str | None, n_diag: int, n_episodes: int, worlds=WORLDS) -> dict:
    diag_seeds = list(range(101, 101 + 2 * n_diag, 2))
    ep_seeds = tuple(range(1000, 1000 + n_episodes))
    res: dict = {
        "metadata": {
            **stamp(),
            "preregistration": PREREGISTRATION,
            "config_hash": config_hash(engine("8-node", "default").config),
            "curricula": {c: list(curriculum_paths(c)) for c in CURRICULA},
            "content_review": {c: review_status(c) for c in CURRICULA},
            "diag_seeds": [diag_seeds[0], diag_seeds[-1], "odd"],
            "episode_seeds": [ep_seeds[0], ep_seeds[-1]],
            "budget": BUDGET,
            "arm": "adapt",
        },
        "worlds": {},
    }
    for world in worlds:
        diag = {c: diagnostic_rows(c, world, diag_seeds) for c in CURRICULA}
        w: dict = {
            "diagnostic": {c: summarise_diag(diag[c]) for c in CURRICULA},
            "diagnostic_paired_x10_minus_8node": {
                k: paired_summary(
                    [r[k] for r in diag["8-node-x10"]], [r[k] for r in diag["8-node"]]
                )
                for k in ("brier", "items")
            },
            "episodes": {},
        }
        for scen in SCENARIOS:
            rows = {c: run_unit((world, c, BUDGET, scen, "adapt", ep_seeds))[1] for c in CURRICULA}
            w["episodes"][scen] = {
                **{c: summarise_arm(rows[c]) for c in CURRICULA},
                "paired_x10_minus_8node": paired(rows["8-node-x10"], rows["8-node"]),
            }
        res["worlds"][world] = w
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out", default=os.path.join(repo_root, "experiments/results/f5_baseline.json")
    )
    ap.add_argument("--n-diag", type=int, default=250)
    ap.add_argument("--n-episodes", type=int, default=200)
    ap.add_argument("--worlds", nargs="*", default=list(WORLDS))
    a = ap.parse_args()
    r = main(a.out, a.n_diag, a.n_episodes, a.worlds)
    for world, w in r["worlds"].items():
        d = w["diagnostic"]
        print(f"{world}: diag Brier 8node {d['8-node']['brier']} x10 {d['8-node-x10']['brier']}")
