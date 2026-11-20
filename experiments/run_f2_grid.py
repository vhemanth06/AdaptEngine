#!/usr/bin/env python3
"""Plan 2, F2-T6 (D61): Stage-1 evaluation of the fitted item model under the sweep diagnostic.

Item-model profiles: heuristic (D6), fitted_assist09 (D60's recommended profile) and fitted_ct
(robustness). Every cell runs the same engine (DEFAULT_CONFIG: sweep diagnostic, greedy closed
loop) with only EngineConfig.model_profile changed.

Worlds: S0-S4 and S4-assist09 (the S4 world driven by config/fitted_assist09.json, as
experiments/run_s4_fitted.py). Curricula: 4-node, 8-node, synth-20, synth-50, 8-node-x10,
synth-20-x10, synth-50-x10.

Per cell (world, curriculum, profile):
- diagnostic, odd seeds 101..: Brier of the end p against binary truth 1[theta >= 0.70], items;
  next-answer prediction (every exercise answered once more by an independent draw): Brier,
  log-loss, AUC, ECE;
- closed-loop episodes, arm adapt, scenario calm, budget 15, seeds 1000..: goal mastery,
  all-required mastery, minutes, executed prerequisite violations (D46), Brier/AUC/ECE of the
  engine's P(correct) on executed attempts.
Paired differences fitted - heuristic over learners, with 95% bootstrap CIs.

Pre-registration: docs/preregistration/F2_2026-11-20.md.
8-node-x10 content: reviewed by the owner (D93; AI-checked, pending under D88 before).

    python experiments/run_f2_grid.py                     # full run -> experiments/results/f2_grid.json
    python experiments/run_f2_grid.py --n-diag 2 --n-episodes 2 --worlds S0 --curricula 4-node --out X
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import multiprocessing as mp
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG, config_hash  # noqa: E402
from adaptengine.learner.profiles import load_profile  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.diag_eval import binary_score  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.run_w7_grid import curriculum_paths, goal_of  # noqa: E402
from experiments.sim import PROFILES, WORLDS, make_sim, s4_fitted_params  # noqa: E402
from experiments.stats import brier_score, ece, log_loss, paired_summary, roc_auc  # noqa: E402

PREREGISTRATION = "docs/preregistration/F2_2026-11-20.md"
PROFILE_FILES = {
    "heuristic": "heuristic",
    "fitted_assist09": "config/fitted_assist09.json",
    "fitted_ct": "config/fitted_ct.json",
}
ALL_WORLDS = (*WORLDS, "S4-assist09")
CURRICULA = (
    "4-node",
    "8-node",
    "synth-20",
    "synth-50",
    "8-node-x10",
    "synth-20-x10",
    "synth-50-x10",
)
REVIEWED = ("4-node", "8-node", "8-node-x10")  # 8-node-x10 reviewed by the owner (D93)
BUDGET, SCENARIO = 15, "calm"


def world_spec(world: str) -> tuple[str, dict]:
    """Simulator world and SimLearner kwargs for a world name."""
    if world == "S4-assist09":
        path = os.path.join(repo_root, PROFILE_FILES["fitted_assist09"])
        return "S4", {"bkt_params": s4_fitted_params(path)}
    return world, {}


_ENGINES: dict = {}


def engine_for(cur: str, profile: str) -> Engine:
    key = (cur, profile)
    if key not in _ENGINES:
        cp, ap = curriculum_paths(cur)
        cfg = dataclasses.replace(DEFAULT_CONFIG, model_profile=PROFILE_FILES[profile])
        _ENGINES[key] = Engine.from_files(
            os.path.join(repo_root, cp) if not os.path.isabs(cp) else cp,
            os.path.join(repo_root, ap) if not os.path.isabs(ap) else ap,
            config=cfg,
            allow_unreviewed=cur not in REVIEWED,
        )
    return _ENGINES[key]


def run_cell(unit) -> tuple:
    world, cur, profile, diag_seeds, ep_seeds = unit
    e, prof = engine_for(cur, profile), PROFILES["nominal"]
    sim_world, kw = world_spec(world)
    diag = []
    for s in diag_seeds:
        sim = make_sim(e, s, prof, sim_world, **kw)
        r = e.diagnose(
            e.init_learner(),
            lambda a, sim=sim: sim.respond(a.target_concept, a.activity_id, a.difficulty, "diag"),
            session_id=str(s),
        )
        sc = binary_score(e, r.state, s, prof, sim_world, sim_kw=kw)
        diag.append(
            {
                **{k: sc[k] for k in ("brier", "next_brier")},
                "items": r.total_items,
                "pairs": sc["pairs"],
                "probe": sc["probe_pairs"],
            }
        )
    scen = get_scenario(SCENARIO, e, e.init_learner(), goal=goal_of(e), budget=BUDGET)
    eps = []
    for s in ep_seeds:
        r = run_episode(e, s, scen, "adapt", prof, world=sim_world, sim_kw=kw)
        eps.append(
            {
                "goal_mastered": float(r["goal_mastered"]),
                "all_required": float(r["all_required_mastered"]),
                "minutes": r["minutes_used"],
                "exec_viol": r["executed_prereq_violations"],
                "attempts": [tuple(p) for p in r["attempts"]],
            }
        )
    return (world, cur, profile), {"diag": diag, "episodes": eps}


def _mean(xs):
    return round(sum(xs) / len(xs), 4) if xs else None


def summarise(cell: dict) -> dict:
    d, ep = cell["diag"], cell["episodes"]
    probe = [p for r in d for p in r["probe"]]
    attempts = [p for r in ep for p in r["attempts"]]
    return {
        "diagnostic": {
            "n": len(d),
            "brier": _mean([r["brier"] for r in d]),
            "auc": roc_auc([p for r in d for p in r["pairs"]]),
            "items": _mean([r["items"] for r in d]),
        },
        "next_answer": {
            "brier": brier_score(probe),
            "log_loss": log_loss(probe),
            "auc": roc_auc(probe),
            "ece": ece(probe),
        },
        "episodes": {
            "n": len(ep),
            "goal_mastery_rate": _mean([r["goal_mastered"] for r in ep]),
            "all_required_rate": _mean([r["all_required"] for r in ep]),
            "mean_minutes": _mean([r["minutes"] for r in ep]),
            "executed_prereq_violations": sum(r["exec_viol"] for r in ep),
            "attempt_brier": brier_score(attempts),
            "attempt_auc": roc_auc(attempts),
            "attempt_ece": ece(attempts),
        },
    }


def paired(fit: dict, heur: dict) -> dict:
    def col(cell, part, k):
        return [r[k] for r in cell[part]]

    return {
        "diag_brier": paired_summary(col(fit, "diag", "brier"), col(heur, "diag", "brier")),
        "next_answer_brier": paired_summary(
            col(fit, "diag", "next_brier"), col(heur, "diag", "next_brier")
        ),
        "diag_items": paired_summary(col(fit, "diag", "items"), col(heur, "diag", "items")),
        "goal_mastery": paired_summary(
            col(fit, "episodes", "goal_mastered"), col(heur, "episodes", "goal_mastered")
        ),
        "minutes": paired_summary(
            col(fit, "episodes", "minutes"), col(heur, "episodes", "minutes")
        ),
    }


def main(out_path, n_diag, n_episodes, worlds=ALL_WORLDS, curricula=CURRICULA, procs=1) -> dict:
    diag_seeds = tuple(range(101, 101 + 2 * n_diag, 2))
    ep_seeds = tuple(range(1000, 1000 + n_episodes))
    for cur in curricula:
        curriculum_paths(cur)  # write synthetic curricula once, before workers fork
    units = [
        (w, c, p, diag_seeds, ep_seeds) for w in worlds for c in curricula for p in PROFILE_FILES
    ]
    if procs > 1:
        with mp.get_context("fork").Pool(procs) as pool:
            cells = dict(pool.map(run_cell, units, chunksize=1))
    else:
        cells = dict(map(run_cell, units))
    res: dict = {
        "metadata": {
            **stamp(),
            "preregistration": PREREGISTRATION,
            "config_hash_heuristic": config_hash(DEFAULT_CONFIG),
            "profiles": {
                p: (None if f == "heuristic" else {"path": f, **load_profile(f).provenance()})
                for p, f in PROFILE_FILES.items()
            },
            "content_review": {
                c: "reviewed"
                if c in REVIEWED
                else "AI-checked, human review pending (D88)"
                if c == "8-node-x10"
                else "synthetic, unreviewed"
                for c in curricula
            },
            "diag_seeds": [diag_seeds[0], diag_seeds[-1], "odd"],
            "episode_seeds": [ep_seeds[0], ep_seeds[-1]],
            "scenario": SCENARIO,
            "budget": BUDGET,
            "arm": "adapt",
        },
        "worlds": {},
    }
    for w in worlds:
        res["worlds"][w] = {}
        for c in curricula:
            row = {p: summarise(cells[(w, c, p)]) for p in PROFILE_FILES}
            row["paired_vs_heuristic"] = {
                p: paired(cells[(w, c, p)], cells[(w, c, "heuristic")])
                for p in PROFILE_FILES
                if p != "heuristic"
            }
            res["worlds"][w][c] = row
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(repo_root, "experiments/results/f2_grid.json"))
    ap.add_argument("--n-diag", type=int, default=250)
    ap.add_argument("--n-episodes", type=int, default=200)
    ap.add_argument("--worlds", nargs="*", default=list(ALL_WORLDS))
    ap.add_argument("--curricula", nargs="*", default=list(CURRICULA))
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    r = main(a.out, a.n_diag, a.n_episodes, a.worlds, a.curricula, a.procs)
    for w, row in r["worlds"].items():
        for c, cell in row.items():
            print(
                f"{w:12s} {c:13s} "
                + " ".join(
                    f"{p}: diag {cell[p]['diagnostic']['brier']} next {cell[p]['next_answer']['brier']}"
                    f" goal {cell[p]['episodes']['goal_mastery_rate']}"
                    for p in PROFILE_FILES
                )
            )
