#!/usr/bin/env python3
"""W8 J.6: policy evaluation (FINAL_A5 §6). Variants deterministic / bandit_frozen /
bandit_updating / random on paired odd seeds; S1, S4 x 4-node, 8-node; adapt_final, B = 15,
calm, 14 days. Decision logs -> experiments/results/policy_logs/*.jsonl; OPE of the frozen policy
from the random and updating logs vs its simulated value. Writes w8_policy_eval.json."""

from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Pool

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.policy import BanditPolicy  # noqa: E402
from experiments.ope import estimate  # noqa: E402
from experiments.policy_runner import make_policy, run_policy_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.stats import km_median, km_rmst, paired_summary  # noqa: E402
from experiments.w8_common import REPORT_SEEDS  # noqa: E402

VARIANTS = ("deterministic", "bandit_frozen", "bandit_updating", "random")
CELLS = (("S1", "4-node"), ("S4", "4-node"), ("S1", "8-node"), ("S4", "8-node"))
FROZEN = os.path.join(repo_root, "config", "policy_frozen.json")
LOGS = os.path.join(repo_root, "experiments", "results", "policy_logs")


def run_unit(u):
    variant, world, cur, seeds = u
    rows, decs = [], []
    for s in seeds:
        res, dec = run_policy_episode(cur, world, s, make_policy(variant, s, FROZEN))
        rows.append({"seed": s, "goal": float(res["goal_mastered"]), "allreq": float(res["all_required_mastered"]),
                     "viol": res["executed_prereq_violations"], "budget_viol": res["budget_violations"],
                     "ttm": res["minutes_to_goal_mastery"], "minutes": res["minutes_used"], "avail": res["minutes_available"],
                     "agree": sum(d["chosen"] == d["deterministic_choice"] for d in dec), "n_dec": len(dec)})  # fmt: skip
        decs += dec
    return (variant, world, cur), rows, decs


def main(
    seeds=REPORT_SEEDS, out=os.path.join(repo_root, "experiments/results/w8_policy_eval.json")
):
    t0, meta = time.time(), stamp()
    os.makedirs(LOGS, exist_ok=True)
    units = [
        (v, w, c, seeds[i : i + 25])
        for v in VARIANTS
        for w, c in CELLS
        for i in range(0, len(seeds), 25)
    ]
    rows, decs = {}, {}
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        for key, r, d in pool.imap_unordered(run_unit, units):
            rows.setdefault(key, []).extend(r)
            decs.setdefault(key, []).extend(d)
    frozen = BanditPolicy.load(FROZEN, mode="frozen")
    res = {
        "metadata": {
            **meta,
            "preregistration": "docs/preregistration/FINAL_A5_2026-11-10.md §6",
            "seeds": "odd 2001-2399",
        },
        "cells": {},
    }
    for w, c in CELLS:
        cell = {}
        for v in VARIANTS:
            rs = sorted(rows[(v, w, c)], key=lambda r: r["seed"])
            ds = decs[(v, w, c)]
            with open(os.path.join(LOGS, f"{v}_{w}_{c}.jsonl"), "w") as f:
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
                if ds
                else None,
                "agreement_with_deterministic": round(
                    sum(r["agree"] for r in rs) / max(1, sum(r["n_dec"] for r in rs)), 4
                ),
            }
        det = sorted(rows[("deterministic", w, c)], key=lambda r: r["seed"])
        for v in VARIANTS[1:]:
            rs = sorted(rows[(v, w, c)], key=lambda r: r["seed"])
            cell[v]["vs_deterministic"] = {
                "goal_mastery": paired_summary([r["goal"] for r in rs], [r["goal"] for r in det]),
                "all_required": paired_summary(
                    [r["allreq"] for r in rs], [r["allreq"] for r in det]
                ),
            }
        sim_value = cell["bandit_frozen"]["mean_learning_progress"]
        cell["ope_frozen"] = {"simulated_value": sim_value}
        for logger in ("random", "bandit_updating"):
            est = estimate(decs[(logger, w, c)], frozen)
            est["abs_error"] = {
                k: (
                    round(abs(est[k] - sim_value), 5)
                    if est[k] is not None and sim_value is not None
                    else None
                )
                for k in ("ips", "snips", "dr")
            }
            cell["ope_frozen"][f"from_{logger}"] = est
        res["cells"][f"{w}|{c}"] = cell
    res["metadata"]["runtime_s"] = round(time.time() - t0, 1)
    with open(out, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    for k, cell in res["cells"].items():
        print(
            k, {v: (cell[v]["goal_mastery_rate"], cell[v]["executed_violations"]) for v in VARIANTS}
        )
        print(
            "   OPE",
            {
                lg: {m: cell["ope_frozen"][lg][m] for m in ("ips", "snips", "dr")}
                for lg in ("from_random", "from_bandit_updating")
            },
            "sim",
            cell["ope_frozen"]["simulated_value"],
        )


if __name__ == "__main__":
    main()
