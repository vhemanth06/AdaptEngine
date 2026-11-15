#!/usr/bin/env python3
"""E4: LinUCB bandit re-ranker on the shipped product engine.

  python experiments/run_policy.py train [--smoke]   # -> config/policy_frozen.json + policy_train.json
  python experiments/run_policy.py eval  [--smoke]   # -> policy_eval.json + policy_logs/*.jsonl
Options: --frozen-path (train: write, eval: read), --out-dir, --processes (eval).
train: one BanditPolicy("updating") (lam 1, alpha 0.3, tau 0.1, zero weights), run sequentially over
TRAIN_SEEDS x cells. eval: variants deterministic / frozen / updating / random on REPORT_SEEDS
(paired), OPE of the frozen policy from the random and updating logs vs its simulated value.
Eval runs per (variant, cell, seed chunk) in parallel; every episode gets a fresh policy, so
"updating" starts each episode from the frozen weights and learns only within it (FINAL_A5 §6). Cells: S1, S4 x 4node_x10, 8node_x10,
B 15, calm, 14 d. --smoke: 2 seeds, cell S1|4node_x10, outputs get a _smoke suffix (logs go to
policy_logs_smoke/).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from adaptengine.policy import BanditPolicy  # noqa: E402
from experiments.common import (  # noqa: E402
    REPO_ROOT,
    REPORT_SEEDS,
    TRAIN_SEEDS,
    product_engine,
    run_parallel,
    write_result,
)
from experiments.policy import ope, run_policy_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.stats import km_median, km_rmst, paired_summary  # noqa: E402

CELLS = tuple((w, c) for c in ("4node_x10", "8node_x10") for w in ("S1", "S4"))
VARIANTS = ("deterministic", "frozen", "updating", "random")
FROZEN = os.path.join(REPO_ROOT, "config", "policy_frozen.json")
CHUNK = 25


def make_policy(variant, seed, frozen_path):
    if variant == "deterministic":
        return None
    if variant == "random":
        return BanditPolicy("random", seed=seed)
    return BanditPolicy.load(frozen_path, mode=variant, seed=seed)


def train(a) -> dict:
    t0 = time.time()
    seeds, cells = (TRAIN_SEEDS[:2], CELLS[:1]) if a.smoke else (TRAIN_SEEDS, CELLS)
    pol = BanditPolicy("updating", lam=1.0, alpha=0.3, tau=0.1)
    engines = {c: product_engine(c, policy=pol) for c in {c for _, c in cells}}
    curve = []
    for i, s in enumerate(seeds):
        for world, cur in cells:
            pol.seed = s
            res = run_policy_episode(engines[cur], s, world, cur, pol)
            dec = res["decisions"]
            curve.append({
                "seed": s, "world": world, "curriculum": cur, "goal": res["goal_mastered"],
                "decisions": len(dec),
                "mean_reward": sum(d["reward"] for d in dec) / max(1, len(dec)),
                "violations": res["executed_prereq_violations"],
            })  # fmt: skip
        if (i + 1) % 25 == 0:
            print(f"{i + 1}/{len(seeds)} seeds, updates {pol.n_updates}, {time.time() - t0:.0f}s",
                  flush=True)  # fmt: skip
    weights = dict(zip(pol.to_dict()["feature_names"], pol.weights()))
    meta = {
        **stamp(), "engine": "product", "episodes": len(curve),
        "trained_on": f"TRAIN_SEEDS[:{len(seeds)}] x {[f'{w}|{c}' for w, c in cells]}",
    }  # fmt: skip
    os.makedirs(os.path.dirname(os.path.abspath(a.frozen_path)), exist_ok=True)
    pol.save(a.frozen_path, meta={"meta": meta, "weights": weights})
    out = {"n_updates": pol.n_updates, "weights": weights, "curve": curve,
           "meta": {"runtime_s": round(time.time() - t0, 1)}}  # fmt: skip
    write_result("policy_train_smoke" if a.smoke else "policy_train", out, a.out_dir)
    print("saved", a.frozen_path, "updates", pol.n_updates,
          "violations", sum(c["violations"] for c in curve))  # fmt: skip
    return out


def run_unit(u):
    variant, world, cur, seeds, frozen_path = u
    rows, decs = [], []
    for s in seeds:
        pol = make_policy(
            variant, s, frozen_path
        )  # fresh per episode: updating learns within it only
        r = run_policy_episode(product_engine(cur, policy=pol), s, world, cur, pol)
        d = r["decisions"]
        rows.append({
            "seed": s, "goal": float(r["goal_mastered"]), "allreq": float(r["all_required_mastered"]),
            "viol": r["executed_prereq_violations"], "budget_viol": r["budget_violations"],
            "ttm": r["minutes_to_goal_mastery"], "minutes": r["minutes_used"],
            "avail": r["minutes_available"], "n_dec": len(d),
            "agree": sum(x["chosen"] == x["deterministic_choice"] for x in d),
        })  # fmt: skip
        decs += d
    return (variant, world, cur), rows, decs


def evaluate(a) -> dict:
    t0 = time.time()
    seeds, cells = (REPORT_SEEDS[:2], CELLS[:1]) if a.smoke else (REPORT_SEEDS, CELLS)
    for _, cur in cells:  # pre-warm so forked workers inherit the engines
        product_engine(cur)
    units = [
        (v, w, c, seeds[i : i + CHUNK], a.frozen_path)
        for v in VARIANTS
        for w, c in cells
        for i in range(0, len(seeds), CHUNK)
    ]
    rows, decs = {}, {}
    for key, r, d in run_parallel(run_unit, units, a.processes):
        rows.setdefault(key, []).extend(r)
        decs.setdefault(key, []).extend(d)
    frozen = BanditPolicy.load(a.frozen_path, mode="frozen")
    log_dir = os.path.join(a.out_dir, "policy_logs_smoke" if a.smoke else "policy_logs")
    os.makedirs(log_dir, exist_ok=True)
    res = {"meta": {"seeds": f"REPORT_SEEDS[:{len(seeds)}]"}, "cells": {}}
    for w, c in cells:
        cell = {}
        for v in VARIANTS:
            rs = sorted(rows[(v, w, c)], key=lambda r: r["seed"])
            ds = decs[(v, w, c)]
            with open(os.path.join(log_dir, f"{v}_{w}_{c}.jsonl"), "w") as f:
                for d in sorted(ds, key=lambda d: (d["seed"], d["day"])):
                    f.write(json.dumps(d) + "\n")
            times = [r["ttm"] if r["ttm"] is not None else r["minutes"] for r in rs]
            ev = [r["ttm"] is not None for r in rs]
            cell[v] = {
                "n": len(rs),
                "goal_mastery_rate": round(sum(r["goal"] for r in rs) / len(rs), 4),
                "all_required_rate": round(sum(r["allreq"] for r in rs) / len(rs), 4),
                "executed_violations": sum(r["viol"] for r in rs),
                "budget_violations": sum(r["budget_viol"] for r in rs),
                "km_median_minutes_to_mastery": km_median(times, ev),
                "km_rmst_minutes_to_mastery": km_rmst(times, ev, max(r["avail"] for r in rs)),
                "decisions": len(ds),
                "mean_learning_progress": round(sum(d["reward"] for d in ds) / len(ds), 5)
                if ds else None,
                "agreement_with_deterministic": round(
                    sum(r["agree"] for r in rs) / max(1, sum(r["n_dec"] for r in rs)), 4
                ),
            }  # fmt: skip
        det = sorted(rows[("deterministic", w, c)], key=lambda r: r["seed"])
        for v in VARIANTS[1:]:
            rs = sorted(rows[(v, w, c)], key=lambda r: r["seed"])
            cell[v]["vs_deterministic"] = {
                "goal_mastery": paired_summary([r["goal"] for r in rs], [r["goal"] for r in det]),
                "all_required": paired_summary(
                    [r["allreq"] for r in rs], [r["allreq"] for r in det]
                ),
            }
        sim_value = cell["frozen"]["mean_learning_progress"]
        cell["ope_frozen"] = {"simulated_value": sim_value}
        for logger in ("random", "updating"):
            est = ope(decs[(logger, w, c)], frozen)
            est["abs_error"] = {
                k: round(abs(est[k] - sim_value), 5)
                if est[k] is not None and sim_value is not None else None
                for k in ("ips", "snips", "dr")
            }  # fmt: skip
            cell["ope_frozen"][f"from_{logger}"] = est
        res["cells"][f"{w}|{c}"] = cell
    res["meta"]["runtime_s"] = round(time.time() - t0, 1)
    write_result("policy_eval_smoke" if a.smoke else "policy_eval", res, a.out_dir)
    return res


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("train", "eval"))
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--frozen-path", default=None)
    ap.add_argument("--out-dir", default=os.path.join(REPO_ROOT, "experiments", "results"))
    ap.add_argument("--processes", type=int, default=None)
    a = ap.parse_args(argv)
    if a.frozen_path is None:  # a smoke run must never touch the real config/policy_frozen.json
        a.frozen_path = os.path.join(a.out_dir, "policy_frozen_smoke.json") if a.smoke else FROZEN
    return (train if a.cmd == "train" else evaluate)(a)


if __name__ == "__main__":
    main()
