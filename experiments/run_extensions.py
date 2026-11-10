#!/usr/bin/env python3
"""W8 pre-registered extension evaluations (FINAL_A5 §7), odd seeds 2001-2399:
  D.1  review cap + goal-path relevance on synth-20 forgetting cells
  O.1  Elo/IRT vs BKT measurement model in the adapt_final loop
  O.2  HLR-lite half-life: fit on HLR seeds (S3), evaluate in forgetting_21 cells
  O.3  BKT forgets: S3 in-loop Brier with/without the fitted forget parameter
  O.4  CP-SAT: only if OR-Tools is installed (recorded as not run otherwise)
Writes experiments/results/w8_extensions.json and experiments/results/w8_hlr_fit.json."""

from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402
from experiments.stats import brier_score, paired_summary, roc_auc  # noqa: E402
from experiments.w8_common import FINAL_FLAGS, HLR_SEEDS, REPORT_SEEDS, engine, goal_of  # noqa: E402

SELECT = os.path.join(repo_root, "experiments/results/w8_calibration_select.json")
HLR_FIT = os.path.join(repo_root, "experiments/results/w8_hlr_fit.json")


def winner():
    sel = json.load(open(SELECT))
    c = sel["candidates"][sel["winner"]]
    return c["profile"], dict(c["overrides"])


def final(world, cur, **extra):
    kind, ov = winner()
    prof = (
        "w7_default"
        if kind == "w7_default"
        else f"fitted_{world if world in ('S0', 'S1', 'S4') else 'S0'}"
    )
    return engine(cur, prof, **{**ov, **FINAL_FLAGS, **extra})


def run_unit(u):
    tag, world, cur, budget, scen, horizon, arm, eng_kw, seeds = u
    base = engine(cur)
    sc = get_scenario(
        scen, base, base.init_learner(), goal=goal_of(base), budget=budget, horizon=horizon
    )
    kind = eng_kw.pop("_kind")
    e = engine(cur, **eng_kw) if kind == "plain" else final(world, cur, **eng_kw)
    prof = PROFILES["fast_forgetter" if scen == "forgetting_21" else "nominal"]
    rows, att = [], []
    for s in seeds:
        r = run_episode(e, s, sc, arm, prof, world=world)
        att += r["attempts"]
        rows.append({"seed": s, "goal": float(r["goal_mastered"]), "theta": r["goal_true_mastery"],
                     "allreq": float(r["all_required_mastered"]), "viol": r["executed_prereq_violations"],
                     "ret": r["retention"], "util": r["minute_utilisation"]})  # fmt: skip
    return tag, rows, att


def summarise(rows, att):
    pairs = [tuple(p) for p in att]
    n = len(rows)
    return {
        "n": n,
        "goal_mastery_rate": round(sum(r["goal"] for r in rows) / n, 4),
        "mean_goal_theta": round(sum(r["theta"] for r in rows) / n, 4),
        "all_required_rate": round(sum(r["allreq"] for r in rows) / n, 4),
        "mean_retention": round(sum(r["ret"] for r in rows) / n, 4),
        "minute_utilisation": round(sum(r["util"] for r in rows) / n, 4),
        "executed_violations": sum(r["viol"] for r in rows),
        "brier": brier_score(pairs),
        "auc": roc_auc(pairs),
    }


def fit_hlr():
    """HLR-lite: p(recall) = 2^(-gap/h), h = 2^(w . [1, sqrt(1+correct), sqrt(1+wrong)]), least squares
    by grid search on the first exercise after a gap >= 1 day (S3, forgetting_21, HLR seeds)."""
    rows = []
    for cur in ("4-node", "8-node"):
        e = engine(cur)
        sc = get_scenario(
            "forgetting_21", e, e.init_learner(), goal=goal_of(e), budget=15, horizon=21
        )
        for arm in ("static_loop", "random_eligible"):
            for s in HLR_SEEDS:
                log = run_episode(e, s, sc, arm, PROFILES["fast_forgetter"], world="S3")[
                    "activity_log"
                ]
                last, nc, nw = {}, {}, {}
                for c, _, is_lesson, _d, y, day in log:
                    if not is_lesson:
                        if c in last and day - last[c] >= 1:
                            rows.append((day - last[c], nc.get(c, 0), nw.get(c, 0), int(y)))
                        nc[c] = nc.get(c, 0) + int(y)
                        nw[c] = nw.get(c, 0) + (1 - int(y))
                    last[c] = day
    a = np.array(rows, float)
    gap, xc, xw, y = a[:, 0], np.sqrt(1 + a[:, 1]), np.sqrt(1 + a[:, 2]), a[:, 3]
    best = None
    for w0 in np.arange(-1, 6.01, 0.25):
        for w1 in np.arange(-1, 2.01, 0.25):
            for w2 in np.arange(-2, 1.01, 0.25):
                h = np.clip(2.0 ** np.minimum(w0 + w1 * xc + w2 * xw, 20), 0.5, 365)
                err = float(np.mean((2.0 ** (-gap / h) - y) ** 2))
                if best is None or err < best[0]:
                    best = (err, (float(w0), float(w1), float(w2)))
    out = {"metadata": {**stamp(), "seeds": "even 8000-8398", "n_observations": len(rows)}, "weights": best[1],
           "brier": round(best[0], 5), "baseline_brier_mean": round(float(np.mean((y - y.mean()) ** 2)), 5)}  # fmt: skip
    with open(HLR_FIT, "w") as f:
        json.dump(out, f, indent=1)
    return out


def main():
    t0, meta = time.time(), stamp()
    hlr = fit_hlr()
    w = tuple(hlr["weights"])
    S = REPORT_SEEDS
    units = []

    def add(tag, world, cur, budget, scen, horizon, arm, kw):
        for i in range(0, len(S), 50):
            units.append((tag, world, cur, budget, scen, horizon, arm, dict(kw), S[i : i + 50]))

    for world in ("S0", "S1"):  # D.1
        for b in (10, 15):
            cell = f"D1|{world}|synth-20|B{b}"
            add(
                f"{cell}|adapt",
                world,
                "synth-20",
                b,
                "forgetting_21",
                21,
                "adapt",
                {"_kind": "plain"},
            )
            add(f"{cell}|adapt_cap", world, "synth-20", b, "forgetting_21", 21, "adapt",
                {"_kind": "plain", "review_cap_fraction": 0.25, "review_goal_path_only": True})  # fmt: skip
            add(
                f"{cell}|no_review",
                world,
                "synth-20",
                b,
                "forgetting_21",
                21,
                "no_review",
                {"_kind": "plain"},
            )
    for world in ("S0", "S1", "S4"):  # O.1
        cell = f"O1|{world}|4-node|B15"
        add(f"{cell}|bkt", world, "4-node", 15, "calm", 14, "adapt", {"_kind": "final"})
        add(
            f"{cell}|elo",
            world,
            "4-node",
            15,
            "calm",
            14,
            "adapt",
            {"_kind": "final", "mastery_model": "elo"},
        )
    for world in ("S0", "S3"):  # O.2
        for cur in ("4-node", "8-node"):
            cell = f"O2|{world}|{cur}|B15"
            add(f"{cell}|fixed", world, cur, 15, "forgetting_21", 21, "adapt", {"_kind": "final"})
            add(
                f"{cell}|hlr",
                world,
                cur,
                15,
                "forgetting_21",
                21,
                "adapt",
                {"_kind": "final", "half_life_model": "hlr", "hlr_weights": w},
            )
            add(
                f"{cell}|no_review",
                world,
                cur,
                15,
                "forgetting_21",
                21,
                "no_review",
                {"_kind": "final"},
            )
    cell = "O3|S3|4-node|B15"  # O.3
    add(
        f"{cell}|no_forget",
        "S3",
        "4-node",
        15,
        "forgetting_21",
        21,
        "adapt",
        {"_kind": "plain_profile_S3"},
    )
    units = [
        (
            u[0],
            *u[1:7],
            (
                {"_kind": "plain", "profile": "fitted_S3"}
                if u[7].get("_kind") == "plain_profile_S3"
                else u[7]
            ),
            u[8],
        )
        for u in units
    ]
    for i in range(0, len(S), 50):
        units.append(
            (
                f"{cell}|forget",
                "S3",
                "4-node",
                15,
                "forgetting_21",
                21,
                "adapt",
                {"_kind": "plain", "profile": "fitted_S3_forget"},
                S[i : i + 50],
            )
        )
    rows, att = {}, {}
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        for tag, r, a in pool.imap_unordered(run_unit, units):
            rows.setdefault(tag, []).extend(r)
            att.setdefault(tag, []).extend(a)
    res = {"metadata": {**meta, "preregistration": "docs/preregistration/FINAL_A5_2026-11-10.md §7", "seeds": "odd 2001-2399"},
           "hlr_fit": hlr, "cells": {}}  # fmt: skip
    for tag in sorted(rows):
        cell, arm = tag.rsplit("|", 1)
        rs = sorted(rows[tag], key=lambda r: r["seed"])
        res["cells"].setdefault(cell, {})[arm] = summarise(rs, att[tag])
        res["cells"][cell].setdefault("_rows", {})[arm] = rs
    for cell, d in res["cells"].items():
        rr = d.pop("_rows")
        ref = {"D1": "no_review", "O1": "bkt", "O2": "no_review", "O3": "no_forget"}[
            cell.split("|")[0]
        ]
        d["paired_vs_" + ref] = {
            arm: {
                "goal_mastery": paired_summary(
                    [r["goal"] for r in rr[arm]], [r["goal"] for r in rr[ref]]
                ),
                "goal_theta": paired_summary(
                    [r["theta"] for r in rr[arm]], [r["theta"] for r in rr[ref]]
                ),
            }
            for arm in rr
            if arm != ref
        }
    try:
        import ortools  # noqa: F401

        res["O4"] = "OR-Tools installed: run experiments/run_cpsat_eval.py"
    except ImportError:
        res["O4"] = "not run: OR-Tools is not installed (optional [solver] extra)"
    res["metadata"]["runtime_s"] = round(time.time() - t0, 1)
    with open(os.path.join(repo_root, "experiments/results/w8_extensions.json"), "w") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    for cell, d in res["cells"].items():
        print(
            cell,
            {
                a: (
                    v["goal_mastery_rate"],
                    v["mean_goal_theta"],
                    v["brier"],
                    v["executed_violations"],
                )
                for a, v in d.items()
                if not a.startswith("paired")
            },
        )


if __name__ == "__main__":
    main()
