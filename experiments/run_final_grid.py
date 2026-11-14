#!/usr/bin/env python3
"""W8 G.1/G.2: the pre-registered final grid (docs/preregistration/FINAL_A5_2026-11-10.md §4-§5).

Parallel, resumable (per-unit checkpoint JSONL), deterministic; writes code_hash + timestamp.
  python experiments/run_final_grid.py --smoke          # 2 cells, 20 seeds (G.1 smoke run)
  python experiments/run_final_grid.py                  # full grid -> experiments/results/final_grid.json
Options: --worlds, --curricula, --horizons, --budgets, --profile (override the B.3 winner's
profile family, e.g. w7_default), --procs, --out, --checkpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.core.profiles import GOAL_SEARCH_DIAGNOSTIC, STRICT_MASTERY  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES, s4_fitted_params  # noqa: E402
from experiments.stats import km_median, km_rmst, paired_summary  # noqa: E402
from experiments.w8_common import FINAL_FLAGS, HEADLINE_SEEDS, REPORT_SEEDS, engine, goal_of  # noqa: E402

WORLDS = ("S0", "S1", "S4", "S4F")
CURRICULA = ("4-node", "8-node")
BUDGETS = (10, 15)
SCENARIOS = ("calm", "missed_day", "missed_2days")
HORIZONS = ("w7", 7, 14, 21)
ARMS = (
    "adapt_w7", "adapt_final", "adapt_final_dx", "adapt_cal",
    "static", "static_loop", "random_eligible", "no_replan",
)  # fmt: skip
HEADLINE = ("S1", "4-node", 15, "calm", 14)
SELECT = os.path.join(repo_root, "experiments/results/w8_calibration_select.json")
N_BINS = 20  # calibration histogram bins (Brier exact via sums; AUC from bins)


def smoke_name(path):
    """Insert _smoke before the first dot of the basename: final_grid.ckpt.jsonl -> final_grid_smoke.ckpt.jsonl."""
    d, b = os.path.split(path)
    stem, dot, ext = b.partition(".")
    return os.path.join(d, f"{stem}_smoke{dot}{ext}")


def winner_spec(profile_override=None):
    sel = json.load(open(SELECT))
    c = sel["candidates"][sel["winner"]]
    return sel["winner"], profile_override or c["profile"], dict(c["overrides"])


def arm_engine(arm, world, cur, spec):
    _, kind, ov = spec
    prof = "w7_default" if kind == "w7_default" else f"fitted_{'S4' if world == 'S4F' else world}"
    if arm in ("adapt_final", "adapt_final_dx"):
        extra = {"diagnostic_scope": "goal_path"} if arm == "adapt_final_dx" else {}
        return engine(cur, prof, **{**ov, **FINAL_FLAGS, **extra}), (
            "adapt_dx" if arm == "adapt_final_dx" else "adapt"
        )
    if arm in ("adapt_strict_dx", "adapt_strict_gs"):
        extra = GOAL_SEARCH_DIAGNOSTIC if arm == "adapt_strict_gs" else {}
        return engine(
            cur, prof, **{**ov, **FINAL_FLAGS, "diagnostic_scope": "goal_path", **STRICT_MASTERY, **extra}
        ), "adapt_dx"
    if arm == "adapt_cal":
        return engine(cur, prof, **ov), "adapt"
    return engine(cur), ("adapt" if arm == "adapt_w7" else arm)


def calib(attempts):
    """Exact Brier sums and a histogram for AUC / reliability."""
    pos, neg = [0] * N_BINS, [0] * N_BINS
    sp, sy, se = [0.0] * N_BINS, [0] * N_BINS, 0.0
    for p, y in attempts:
        b = min(N_BINS - 1, int(p * N_BINS))
        (pos if y else neg)[b] += 1
        sp[b] += p
        sy[b] += int(y)
        se += (p - float(y)) ** 2
    return {"pos": pos, "neg": neg, "sum_p": sp, "sum_y": sy, "sse": se, "n": len(attempts)}


def run_unit(u):
    world, cur, budget, scen, horizon, arm, seeds, spec = u
    base = engine(cur)
    goal = goal_of(base)
    sc = get_scenario(scen, base, base.init_learner(), goal=goal, budget=budget, horizon=horizon)
    e, run_arm = arm_engine(arm, world, cur, spec)
    prof = PROFILES["fast_forgetter" if scen == "forgetting_21" else "nominal"]
    sim_w, sim_kw = (
        (
            "S4",
            {
                "bkt_params": s4_fitted_params(
                    os.path.join(repo_root, "config/fitted_assist09.json")
                )
            },
        )
        if world == "S4F"
        else (world, None)
    )
    rows, att = [], []
    for s in seeds:
        r = run_episode(e, s, sc, run_arm, prof, world=sim_w, sim_kw=sim_kw)
        att += r["attempts"]
        rows.append({
            "seed": s, "goal": r["goal_mastered"], "theta": r["goal_true_mastery"],
            "allreq": r["all_required_mastered"], "minutes": r["minutes_used"],
            "avail": r["minutes_available"], "util": r["minute_utilisation"],
            "ttm": r["minutes_to_goal_mastery"], "exec_viol": r["executed_prereq_violations"],
            "budget_viol": r["budget_violations"], "fm": r["false_mastered"], "believed": r["believed_mastered"],
            "idle_total": r["idle_days_total"], "idle_unm": r["idle_days_unmastered"], "dx": r["dx_minutes"],
        })  # fmt: skip
    return [world, cur, budget, scen, horizon, arm, sc.deadline], rows, calib(att)


def cells_spec(worlds, curricula, budgets, horizons):
    for w in worlds:
        for cur in curricula:
            for b in budgets:
                for scen in SCENARIOS:
                    for h in horizons:
                        yield w, cur, b, scen, h
                yield w, cur, b, "forgetting_21", 21


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def auc_from_bins(pos, neg):
    tp, tn = sum(pos), sum(neg)
    if not tp or not tn:
        return None
    wins, below = 0.0, 0
    for b in range(N_BINS):
        wins += pos[b] * (below + 0.5 * neg[b])
        below += neg[b]
    return round(wins / (tp * tn), 4)


def summarise(rows, cal):
    tau = max(r["avail"] for r in rows)
    times = [r["ttm"] if r["ttm"] is not None else r["minutes"] for r in rows]
    events = [r["ttm"] is not None for r in rows]
    believed = sum(r["believed"] for r in rows)
    return {
        "n": len(rows),
        "goal_mastery_rate": mean([float(r["goal"]) for r in rows]),
        "all_required_rate": mean([float(r["allreq"]) for r in rows]),
        "mean_goal_theta": mean([r["theta"] for r in rows]),
        "executed_prereq_violations": sum(r["exec_viol"] for r in rows),
        "learners_with_executed_violations": sum(1 for r in rows if r["exec_viol"]),
        "budget_violations": sum(r["budget_viol"] for r in rows),
        "false_mastery_rate": round(sum(r["fm"] for r in rows) / believed, 4) if believed else None,
        "minute_utilisation": mean([r["util"] for r in rows]),
        "mean_minutes": mean([r["minutes"] for r in rows]),
        "idle_days_total": mean([r["idle_total"] for r in rows]),
        "idle_days_unmastered": mean([r["idle_unm"] for r in rows]),
        "mean_dx_minutes": mean([r["dx"] for r in rows]),
        "reach_rate": mean([float(e) for e in events]),
        "km_median_minutes_to_mastery": km_median(times, events),
        "km_rmst_minutes_to_mastery": km_rmst(times, events, tau),
        "km_tau": tau,
        "brier": round(cal["sse"] / cal["n"], 4) if cal["n"] else None,
        "auc": auc_from_bins(cal["pos"], cal["neg"]),
        "n_attempts": cal["n"],
        "calibration_bins": {k: cal[k] for k in ("pos", "neg", "sum_p", "sum_y")},
        "per_seed": {
            "seed": [r["seed"] for r in rows],
            "goal": [int(r["goal"]) for r in rows],
            "allreq": [int(r["allreq"]) for r in rows],
            "ttm": [r["ttm"] for r in rows],
            "minutes": [r["minutes"] for r in rows],
        },  # fmt: skip
    }


def merge_cal(a, b):
    if a is None:
        return json.loads(json.dumps(b))
    for k in ("pos", "neg", "sum_p", "sum_y"):
        a[k] = [x + y for x, y in zip(a[k], b[k])]
    a["sse"] += b["sse"]
    a["n"] += b["n"]
    return a


def main(a):
    t0 = time.time()
    spec = winner_spec(a.profile)
    provenance = stamp()
    horizons = [h if h == "w7" else int(h) for h in a.horizons]
    units = []
    for w, cur, b, scen, h in cells_spec(a.worlds, a.curricula, a.budgets, horizons):
        seeds = HEADLINE_SEEDS if (w, cur, b, scen, h) == HEADLINE else REPORT_SEEDS
        if a.smoke:
            seeds = seeds[:20]
        for arm in a.arms:
            for i in range(0, len(seeds), 50):
                units.append((w, cur, b, scen, h, arm, seeds[i : i + 50], spec))
    done = {}
    if os.path.exists(a.checkpoint):
        with open(a.checkpoint) as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("code_hash") == provenance["code_hash"]:
                    done[json.dumps(rec["unit"])] = rec

    def ukey(u):
        return json.dumps(list(u[:6]) + [u[6][0]])

    todo = [u for u in units if ukey(u) not in done]
    print(
        f"units: {len(units)} total, {len(units) - len(todo)} from checkpoint, {len(todo)} to run",
        flush=True,
    )
    with open(a.checkpoint, "a") as ck, Pool(a.procs) as pool:
        for i, (key, rows, cal) in enumerate(pool.imap_unordered(run_unit, todo, 1)):
            first = rows[0]["seed"]
            rec = {
                "unit": key[:6] + [first],
                "deadline": key[6],
                "rows": rows,
                "cal": cal,
                "code_hash": provenance["code_hash"],
            }
            ck.write(json.dumps(rec) + "\n")
            ck.flush()
            done[json.dumps(rec["unit"])] = rec
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(todo)} units, {time.time() - t0:.0f}s", flush=True)
    raw: dict = {}
    for rec in done.values():
        w, cur, b, scen, h, arm, _ = rec["unit"]
        cell = f"{w}|{cur}|B{b}|{scen}|h{h}"
        if (w, cur, b, scen, h) not in {
            c for c in cells_spec(a.worlds, a.curricula, a.budgets, horizons)
        }:
            continue
        slot = raw.setdefault(cell, {"deadline": rec["deadline"], "arms": {}})
        arm_slot = slot["arms"].setdefault(arm, {"rows": [], "cal": None})
        arm_slot["rows"] += rec["rows"]
        arm_slot["cal"] = merge_cal(arm_slot["cal"], rec["cal"])
    cells = {}
    for cell, slot in sorted(raw.items()):
        rows = {arm: sorted(v["rows"], key=lambda r: r["seed"]) for arm, v in slot["arms"].items()}
        out = {
            "deadline": slot["deadline"],
            "arms": {arm: summarise(rows[arm], slot["arms"][arm]["cal"]) for arm in rows},
        }

        def pair(x, y):
            return {
                "goal_mastery": paired_summary(
                    [float(r["goal"]) for r in rows[x]], [float(r["goal"]) for r in rows[y]]
                ),
                "all_required": paired_summary(
                    [float(r["allreq"]) for r in rows[x]], [float(r["allreq"]) for r in rows[y]]
                ),
            }

        out["paired_vs_static_loop"] = {
            arm: pair(arm, "static_loop")
            for arm in rows
            if arm != "static_loop" and "static_loop" in rows
        }
        out["paired"] = {
            f"{x}_vs_{y}": pair(x, y)
            for x, y in (
                ("adapt_final", "adapt_w7"),
                ("adapt_final_dx", "adapt_final"),
                ("adapt_cal", "adapt_w7"),
                ("adapt_final", "adapt_cal"),
                ("adapt_final", "static"),
            )
            if x in rows and y in rows
        }
        cells[cell] = out
    res = {
        "metadata": {
            **provenance,
            "preregistration": "docs/preregistration/FINAL_A5_2026-11-10.md",
            "calibration_winner": spec[0],
            "winner_profile": spec[1],
            "winner_overrides": spec[2],
            "final_flags": FINAL_FLAGS,
            "worlds": list(a.worlds),
            "curricula": list(a.curricula),
            "budgets": list(a.budgets),
            "scenarios": list(SCENARIOS) + ["forgetting_21"],
            "horizons": [str(h) for h in horizons],
            "arms": list(a.arms),
            "n_per_cell": 20 if a.smoke else len(REPORT_SEEDS),
            "headline_cell": "|".join(map(str, HEADLINE)),
            "n_headline": 20 if a.smoke else len(HEADLINE_SEEDS),
            "runtime_s": round(time.time() - t0, 1),
            "processes": a.procs,
            "smoke": a.smoke,
        },  # fmt: skip
        "cells": cells,
    }
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    print("cells:", len(cells), "runtime_s:", res["metadata"]["runtime_s"])
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(repo_root, "experiments/results/final_grid.json"))
    ap.add_argument(
        "--checkpoint", default=os.path.join(repo_root, "experiments/results/final_grid.ckpt.jsonl")
    )
    ap.add_argument("--worlds", nargs="*", default=list(WORLDS))
    ap.add_argument("--curricula", nargs="*", default=list(CURRICULA))
    ap.add_argument("--budgets", nargs="*", type=int, default=list(BUDGETS))
    ap.add_argument("--horizons", nargs="*", default=[str(h) for h in HORIZONS])
    ap.add_argument("--profile", default=None)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--arms", nargs="*", choices=ARMS + ("adapt_strict_dx", "adapt_strict_gs"), default=list(ARMS))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.smoke:
        a.worlds, a.curricula, a.budgets, a.horizons = ["S1"], ["4-node"], [15], ["14"]
        a.out, a.checkpoint = smoke_name(a.out), smoke_name(a.checkpoint)
    main(a)
