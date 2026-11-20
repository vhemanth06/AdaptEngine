#!/usr/bin/env python3
"""Plan 3, F1-T8 (D58, D61 Stage 2): sweep vs bisection diagnostic, with and without confirmation.

Pre-registration: docs/preregistration/F1_2026-11-20.md. Three parts, all with DEFAULT_CONFIG plus
the arm's overrides (heuristic item model unless stated):

1. Tuning (tuning seeds 2000-2099, world S0, curricula 8-node-x10 and synth-20-x10): closed-loop
   bisect_confirm over bisection_stop_confidence x bisection_n_ceiling; the best goal-mastery rate
   (ties: fewer total minutes, then the defaults) is frozen for every bisection arm below.
2. Diagnostic matrix (held-out odd seeds 101-599; worlds S0, S2, S4 as the W7 matrix, since S1 and
   S3 share S0's starting knowledge): arms sweep_p020 (D59 default), sweep_p024
   (population_prior_config), bisect, bisect_indep (independent_p0 prior), prior_only,
   fixed@n (round-robin at the bisection arm's item count); plus scripted learners (advanced,
   advanced_minus_goal, mid, novice). Brier / log-loss / AUC vs truth, items, false-confirm rate,
   false-fail rate of true knowers.
3. Closed loop (seeds 1000-1199, calm, budget 15, the diagnostic runs first): worlds S0-S4, arms
   sweep, bisect_noconfirm, bisect_confirm; the F2 Stage-2 2x2 {sweep, bisect_confirm} x
   {heuristic, fitted_assist09} in S0-S4 and S4-assist09. Goal / all-required mastery, total
   minutes (diagnostic + plan), executed violations (D46), idle days, confirmation false passes.

Curricula: 4-node, 8-node, synth-20, synth-50, 8-node-x10, synth-20-x10, synth-50-x10.
8-node-x10 content: reviewed by the owner (D93; AI-checked, pending under D88 before).

    python experiments/run_f1_grid.py           # full run -> experiments/results/f1_grid.json
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
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.diag_eval import run_fixed_diagnostic  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.run_f2_grid import CURRICULA, REVIEWED, world_spec  # noqa: E402
from experiments.run_w7_grid import curriculum_paths, goal_of  # noqa: E402
from experiments.sim import PROFILES, TRUE_MASTERY_CUTOFF, WORLDS, keyed_uniform, make_sim  # noqa: E402
from experiments.stats import log_loss, paired_summary, roc_auc  # noqa: E402

PREREGISTRATION = "docs/preregistration/F1_2026-11-20.md"
ASSIST = "config/fitted_assist09.json"
BISECT = {"diagnostic_method": "bisection"}
DIAG_ARMS = {
    "sweep_p020": {},
    "sweep_p024": {"prior_mode": "population", "population_p0": 0.24},
    "bisect": {**BISECT, "confirm_diag_confident": True},  # flags only; p is the same as without
    "bisect_indep": {**BISECT, "bisection_prior": "independent_p0", "confirm_diag_confident": True},
}
LOOP_ARMS = {
    "sweep": {},
    "bisect_noconfirm": BISECT,
    "bisect_confirm": {**BISECT, "confirm_diag_confident": True},
}
TWO_BY_TWO = {
    "sweep_fitted": {"model_profile": ASSIST},
    "bisect_confirm_fitted": {**BISECT, "confirm_diag_confident": True, "model_profile": ASSIST},
}
DIAG_WORLDS = ("S0", "S2", "S4")
LOOP_WORLDS = WORLDS
TUNE = {"stop": (0.7, 0.8, 0.9), "ceiling": (13, 20, 40)}
TUNE_CURRICULA = ("8-node-x10", "synth-20-x10")
SCRIPTED = ("advanced", "advanced_minus_goal", "mid", "novice")
BUDGET, SCENARIO = 15, "calm"

_ENGINES: dict = {}
FROZEN: dict = {}  # tuned bisection settings, set before workers fork


def engine_for(cur: str, overrides: dict) -> Engine:
    key = (cur, tuple(sorted(overrides.items())), tuple(sorted(FROZEN.items())))
    if key not in _ENGINES:
        cp, ap = curriculum_paths(cur)
        extra = FROZEN if overrides.get("diagnostic_method") == "bisection" else {}
        cfg = dataclasses.replace(DEFAULT_CONFIG, **{**extra, **overrides})
        _ENGINES[key] = Engine.from_files(
            os.path.join(repo_root, cp) if not os.path.isabs(cp) else cp,
            os.path.join(repo_root, ap) if not os.path.isabs(ap) else ap,
            config=cfg,
            allow_unreviewed=cur not in REVIEWED,
        )
    return _ENGINES[key]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


# ---------------------------------------------------------------- closed loop


def loop_cell(unit):
    world, cur, arm, overrides, seeds, frozen = unit
    FROZEN.clear()
    FROZEN.update(frozen)
    e = engine_for(cur, overrides)
    sim_world, kw = world_spec(world)
    sc = get_scenario(SCENARIO, e, e.init_learner(), goal=goal_of(e), budget=BUDGET)
    rows = []
    for s in seeds:
        r = run_episode(
            e, s, sc, "adapt", PROFILES["nominal"], world=sim_world, sim_kw=kw, diagnose=True
        )
        rows.append(
            {
                "goal": float(r["goal_mastered"]),
                "all_required": float(r["all_required_mastered"]),
                "minutes": r["minutes_used"] + r["diag_minutes"],
                "plan_minutes": r["minutes_used"],
                "diag_items": r["diag_items"],
                "exec_viol": r["executed_prereq_violations"],
                "idle_days": r["idle_days"],
                "confirmed_diag": len(r["confirmed_at_diag"]),
                "false_confirm_diag": r["false_confirm_at_diag"],
                "confirmed_end": len(r["confirmed_at_end"]),
                "false_confirm_end": r["false_confirm_at_end"],
            }
        )
    return (world, cur, arm), rows


def summarise_loop(rows):
    conf_d = sum(r["confirmed_diag"] for r in rows)
    conf_e = sum(r["confirmed_end"] for r in rows)
    return {
        "n": len(rows),
        "goal_mastery_rate": _mean([r["goal"] for r in rows]),
        "all_required_rate": _mean([r["all_required"] for r in rows]),
        "mean_total_minutes": _mean([r["minutes"] for r in rows]),
        "mean_plan_minutes": _mean([r["plan_minutes"] for r in rows]),
        "mean_diag_items": _mean([r["diag_items"] for r in rows]),
        "executed_prereq_violations": sum(r["exec_viol"] for r in rows),
        "idle_days": sum(r["idle_days"] for r in rows),
        "confirmed_at_diag": conf_d,
        "false_confirm_rate_at_diag": round(sum(r["false_confirm_diag"] for r in rows) / conf_d, 4)
        if conf_d
        else None,
        "confirmed_at_end": conf_e,
        "confirmation_false_pass_rate": round(sum(r["false_confirm_end"] for r in rows) / conf_e, 4)
        if conf_e
        else None,
    }


def paired_loop(a, b):
    return {
        k: paired_summary([r[k] for r in a], [r[k] for r in b])
        for k in ("goal", "all_required", "minutes")
    }


# ---------------------------------------------------------------- diagnostic matrix


def _scores(e, state, truth: dict, n_items):
    pairs = [(state.concepts[c].p, truth[c]) for c in truth]
    conf = [c for c in truth if state.concepts[c].confirmed]
    knowers = [c for c in truth if truth[c]]
    return {
        "brier": sum((p - y) ** 2 for p, y in pairs) / len(pairs),
        "pairs": pairs,
        "items": n_items,
        "confirmed": len(conf),
        "false_confirm": sum(not truth[c] for c in conf),
        "knowers": len(knowers),
        "false_fail": sum(state.concepts[c].p < 0.5 for c in knowers),
    }


def diag_cell(unit):
    world, cur, seeds, frozen = unit
    FROZEN.clear()
    FROZEN.update(frozen)
    prof = PROFILES["nominal"]
    sim_world, kw = world_spec(world)
    base = engine_for(cur, {})
    out: dict = {}
    for s in seeds:
        truth = None
        for arm, ov in DIAG_ARMS.items():
            e = engine_for(cur, ov)
            sim = make_sim(e, s, prof, sim_world, **kw)
            r = e.diagnose(
                e.init_learner(),
                lambda a, sim=sim: sim.respond(
                    a.target_concept, a.activity_id, a.difficulty, "diag"
                ),
                session_id=str(s),
            )
            truth = {c: v >= TRUE_MASTERY_CUTOFF for c, v in sim.initial.items()}
            out.setdefault(arm, []).append(_scores(e, r.state, truth, r.total_items))
        out.setdefault("prior_only", []).append(_scores(base, base.init_learner(), truth, 0))
        st, k = run_fixed_diagnostic(base, s, prof, out["bisect"][-1]["items"], sim_world)
        out.setdefault("fixed@n", []).append(_scores(base, st, truth, k))
    return (world, cur), out


def scripted_truth(e, profile: str) -> set:
    order = list(e.graph.topological_order())
    goal = goal_of(e)
    if profile == "advanced":
        return set(order)
    if profile == "advanced_minus_goal":
        return set(order) - {goal} - set(e.graph.descendants(goal))
    if profile == "mid":
        return set(order[: len(order) // 2])  # a prefix of a topological order is a down-set
    return set()


def scripted_cell(unit):
    cur, seeds, frozen = unit
    FROZEN.clear()
    FROZEN.update(frozen)
    out: dict = {}
    for arm in ("sweep_p020", "bisect"):
        e = engine_for(cur, DIAG_ARMS[arm])
        for prof in SCRIPTED:
            known = scripted_truth(e, prof)
            truth = {c: c in known for c in e.graph.concepts()}
            for s in seeds:
                count: dict = {}

                def answer(a, s=s, known=known, count=count):
                    n = count[a.activity_id] = count.get(a.activity_id, -1) + 1
                    k = a.target_concept in known
                    p = e.model.predict_correct(1.0 if k else 0.0, a.difficulty)
                    return keyed_uniform(s, "script", a.activity_id, n) < p

                r = e.diagnose(e.init_learner(), answer, session_id=str(s))
                out.setdefault(f"{arm}/{prof}", []).append(
                    _scores(e, r.state, truth, r.total_items)
                )
    return cur, out


def summarise_diag(rows):
    pairs = [p for r in rows for p in r["pairs"]]
    conf = sum(r["confirmed"] for r in rows)
    know = sum(r["knowers"] for r in rows)
    return {
        "n": len(rows),
        "brier": _mean([r["brier"] for r in rows]),
        "log_loss": log_loss(pairs),
        "auc": roc_auc(pairs),
        "items": _mean([r["items"] for r in rows]),
        "false_confirm_rate": round(sum(r["false_confirm"] for r in rows) / conf, 4)
        if conf
        else None,
        "false_fail_rate_true_knowers": round(sum(r["false_fail"] for r in rows) / know, 4)
        if know
        else None,
    }


# ---------------------------------------------------------------- driver


def _pool_map(fn, units, procs):
    if procs > 1:
        with mp.get_context("fork").Pool(procs) as pool:
            return dict(pool.map(fn, units, chunksize=1))
    return dict(map(fn, units))


def tune(seeds, procs) -> tuple[dict, list]:
    units, keys = [], []
    for stop in TUNE["stop"]:
        for ceiling in TUNE["ceiling"]:
            frozen = {"bisection_stop_confidence": stop, "bisection_n_ceiling": ceiling}
            for cur in TUNE_CURRICULA:
                units.append(
                    ("S0", cur, f"{stop}/{ceiling}", LOOP_ARMS["bisect_confirm"], seeds, frozen)
                )
            keys.append((stop, ceiling))
    cells = _pool_map(loop_cell, units, procs)
    table = []
    for stop, ceiling in keys:
        rows = [r for cur in TUNE_CURRICULA for r in cells[("S0", cur, f"{stop}/{ceiling}")]]
        table.append(
            {
                "bisection_stop_confidence": stop,
                "bisection_n_ceiling": ceiling,
                "goal_mastery_rate": _mean([r["goal"] for r in rows]),
                "mean_total_minutes": _mean([r["minutes"] for r in rows]),
            }
        )
    default = (DEFAULT_CONFIG.bisection_stop_confidence, DEFAULT_CONFIG.bisection_n_ceiling)
    best = min(
        table,
        key=lambda t: (
            -t["goal_mastery_rate"],
            t["mean_total_minutes"],
            (t["bisection_stop_confidence"], t["bisection_n_ceiling"]) != default,
            t["bisection_stop_confidence"],
            t["bisection_n_ceiling"],
        ),
    )
    return {k: best[k] for k in ("bisection_stop_confidence", "bisection_n_ceiling")}, table


def main(
    out_path,
    n_diag=250,
    n_episodes=200,
    n_tune=100,
    n_scripted=100,
    curricula=CURRICULA,
    loop_worlds=LOOP_WORLDS,
    diag_worlds=DIAG_WORLDS,
    procs=1,
) -> dict:
    for cur in set(curricula) | set(TUNE_CURRICULA):
        curriculum_paths(cur)  # write synthetic curricula once, before workers fork
    frozen, tune_table = tune(tuple(range(2000, 2000 + n_tune)), procs)
    diag_seeds = tuple(range(101, 101 + 2 * n_diag, 2))
    ep_seeds = tuple(range(1000, 1000 + n_episodes))
    sc_seeds = tuple(range(101, 101 + 2 * n_scripted, 2))

    loop_units = [
        (w, c, arm, ov, ep_seeds, frozen)
        for w in loop_worlds
        for c in curricula
        for arm, ov in {**LOOP_ARMS, **TWO_BY_TWO}.items()
    ] + [
        ("S4-assist09", c, arm, ov, ep_seeds, frozen)
        for c in curricula
        for arm, ov in {
            "sweep": {},
            "bisect_confirm": LOOP_ARMS["bisect_confirm"],
            **TWO_BY_TWO,
        }.items()
    ]
    loops = _pool_map(loop_cell, loop_units, procs)
    diags = _pool_map(
        diag_cell, [(w, c, diag_seeds, frozen) for w in diag_worlds for c in curricula], procs
    )
    scripted = _pool_map(scripted_cell, [(c, sc_seeds, frozen) for c in curricula], procs)

    worlds_loop = (*loop_worlds, "S4-assist09")
    res: dict = {
        "metadata": {
            **stamp(),
            "preregistration": PREREGISTRATION,
            "config_hash_default": config_hash(DEFAULT_CONFIG),
            "frozen_bisection_settings": frozen,
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
            "tuning_seeds": [2000, 2000 + n_tune - 1],
            "scripted_seeds": [sc_seeds[0], sc_seeds[-1], "odd"],
            "scenario": SCENARIO,
            "budget": BUDGET,
        },
        "tuning": tune_table,
        "diagnostic": {
            w: {
                c: {arm: summarise_diag(rows) for arm, rows in diags[(w, c)].items()}
                for c in curricula
            }
            for w in diag_worlds
        },
        "scripted": {c: {k: summarise_diag(v) for k, v in scripted[c].items()} for c in curricula},
        "closed_loop": {},
    }
    for w in worlds_loop:
        res["closed_loop"][w] = {}
        for c in curricula:
            arms = {a: rows for (ww, cc, a), rows in loops.items() if ww == w and cc == c}
            cell = {a: summarise_loop(rows) for a, rows in arms.items()}
            pairs = {}
            for a, b in (
                ("bisect_confirm", "sweep"),
                ("bisect_noconfirm", "sweep"),
                ("bisect_confirm", "bisect_noconfirm"),
                ("sweep_fitted", "sweep"),
                ("bisect_confirm_fitted", "sweep"),
                ("bisect_confirm_fitted", "bisect_confirm"),
            ):
                if a in arms and b in arms:
                    pairs[f"{a}_minus_{b}"] = paired_loop(arms[a], arms[b])
            cell["paired"] = pairs
            res["closed_loop"][w][c] = cell
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, sort_keys=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(repo_root, "experiments/results/f1_grid.json"))
    ap.add_argument("--n-diag", type=int, default=250)
    ap.add_argument("--n-episodes", type=int, default=200)
    ap.add_argument("--n-tune", type=int, default=100)
    ap.add_argument("--n-scripted", type=int, default=100)
    ap.add_argument("--curricula", nargs="*", default=list(CURRICULA))
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    r = main(a.out, a.n_diag, a.n_episodes, a.n_tune, a.n_scripted, a.curricula, procs=a.procs)
    print("frozen:", r["metadata"]["frozen_bisection_settings"])
    for w, row in r["closed_loop"].items():
        for c, cell in row.items():
            print(
                w,
                c,
                {
                    a: (v["goal_mastery_rate"], v["mean_total_minutes"])
                    for a, v in cell.items()
                    if a != "paired"
                },
            )
