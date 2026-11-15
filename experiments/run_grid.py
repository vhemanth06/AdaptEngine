#!/usr/bin/env python3
"""E1: closed-loop grid. The shipped product engine vs ablations and baselines across worlds.

  python experiments/run_grid.py --smoke            # 2 cells, 20 report seeds, all arms
  python experiments/run_grid.py --grid primary     # -> experiments/results/grid.json
Options: --grid primary|stress|both, --resume, --out-dir, --processes.
Every engine is built through common.product_engine; the checkpoint is one JSON line per
(cell, arm, seed) in <out-dir>/grid.ckpt.jsonl (grid_smoke.ckpt.jsonl for --smoke).
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.common import (  # noqa: E402
    CURRICULA,
    HEADLINE_SEEDS,
    REPORT_SEEDS,
    curriculum_paths,
    goal_of,
    product_engine,
    run_parallel,
    world_kw,
    write_result,
)
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402
from experiments.stats import (  # noqa: E402
    km_median,
    kaplan_meier,
    km_rmst,
    paired_bootstrap_ci,
    roc_auc,
)

_W8_FINAL = dict(
    theta=0.85,
    k_responses=2,
    horizon_aware_mastery=True,
    consolidation=True,
    selection_scope="concept_sweep",
    concept_cap=2,
    n_max=6,
    diag_budget_per_concept=0.0,
)


ARMS = {
    "product": (lambda cur, world: product_engine(cur), "adapt_dx"),
    "product_nodx": (lambda cur, world: product_engine(cur), "adapt"),
    "product_consol": (lambda cur, world: product_engine(cur, consolidation=True), "adapt_dx"),
    "product_norev": (lambda cur, world: product_engine(cur), "no_review"),
    "product_noreplan": (lambda cur, world: product_engine(cur), "no_replan"),
    "w8_final": (
        lambda cur, world: product_engine(
            cur, profile=f"fitted_{'S4' if world == 'S4F' else world}", **_W8_FINAL
        ),
        "adapt_dx",
    ),
    "static": (lambda cur, world: product_engine(cur), "static"),
    "static_loop": (lambda cur, world: product_engine(cur), "static_loop"),
    "random_eligible": (lambda cur, world: product_engine(cur), "random_eligible"),
}

PRIMARY_WORLDS = ("S0", "S1", "S4", "S4F")
PRIMARY_CURS = ("4node_x10", "8node_x10")
PRIMARY_BUDGETS = (10, 15)
PRIMARY_SCEN = ("calm", "missed_day", "missed_2days")
PRIMARY_HORIZONS = ("w7", 7, 14, 21)
STRESS_WORLDS = ("S0", "S1", "S2", "S3", "S4")
STRESS_CURS = ("4node_x10", "8node_x10", "synth-20-x10")
STRESS_BUDGETS = (5, 15, 30)
STRESS_SCEN = ("budget_drop", "deadline_cut", "budget_crash", "deadline_halved")
STRESS_ARMS = ("product", "product_noreplan", "static_loop")
HEADLINE = ("S1", "4node_x10", 15, "calm", 14)
CHUNK = 50
N_BINS = 100


ABLATION_ARMS = ("product_nodx", "product_consol", "product_norev", "product_noreplan", "w8_final")


def cell_id(w, cur, b, scen, h):
    return f"{w}|{cur}|B{b}|{scen}|h{h}"


def grid_cells(grid):
    """Yield (grid_name, world, cur, budget, scenario, horizon, arms)."""
    if grid in ("primary", "both"):
        for w in PRIMARY_WORLDS:
            for cur in PRIMARY_CURS:
                for b in PRIMARY_BUDGETS:
                    for scen in PRIMARY_SCEN:
                        for h in PRIMARY_HORIZONS:
                            yield "primary", w, cur, b, scen, h, tuple(ARMS)
                    yield "primary", w, cur, b, "forgetting_21", 21, tuple(ARMS)
    if grid in ("stress", "both"):
        for w in STRESS_WORLDS:
            for cur in STRESS_CURS:
                for b in STRESS_BUDGETS:
                    for scen in STRESS_SCEN:
                        yield "stress", w, cur, b, scen, "w7", STRESS_ARMS


_W7: dict = {}


def skip_reason(scen, cur, b, h):
    """Why a cell has no scenario (arms.get_scenario returns None), or None if it runs."""
    base = _w7_engine(cur)
    if get_scenario(scen, base, base.init_learner(), goal=goal_of(base), budget=b, horizon=h):
        return None
    return {
        "budget_drop": "budget_drop needs a lower allowed budget (B > 5)",
        "budget_crash": "budget_crash is defined only at B = 30 (30 -> 5)",
    }.get(scen, "scenario undefined for this budget")


def prewarm(cells):
    """Build each cell's own arm engines in the parent so forked workers inherit them."""
    for cur in {c[2] for c in cells if c[2].startswith("synth-")}:
        curriculum_paths(cur)
    for _, w, cur, *_r, arms in cells:
        _w7_engine(cur)
        for arm in arms:
            ARMS[arm][0](cur, w)


def _w7_engine(cur):
    """W7-default engine, used only to size the 'w7' horizon (same for every arm)."""
    if cur not in _W7:
        cp, ap = curriculum_paths(cur)
        _W7[cur] = Engine.from_files(
            cp, ap, config=DEFAULT_CONFIG, allow_unreviewed=cur.startswith("synth-")
        )
    return _W7[cur]


def _hist(attempts):
    h: dict = {}
    for p, y in attempts:
        s = h.setdefault(str(min(N_BINS - 1, int(p * N_BINS))), [0, 0, 0.0])
        s[0 if y else 1] += 1
        s[2] += p
    return h


def run_unit(u):
    """One chunk of seeds for one (cell, arm). Returns checkpoint records (one per seed).
    Optional 9th element: dict of product_engine overrides (E3, E5); the arm then runs adapt_dx
    unless the dict carries "mode". Its "profile" key (E5 O.3) picks the product_engine profile."""
    grid, w, cur, b, scen, h, arm, seeds, *extra = u
    base = _w7_engine(cur)
    sc = get_scenario(scen, base, base.init_learner(), goal=goal_of(base), budget=b, horizon=h)
    if sc is None:
        return []
    if extra:
        ov = dict(extra[0])
        mode = ov.pop("mode", "adapt_dx")
        e = product_engine(cur, **ov)
    else:
        factory, mode = ARMS[arm]
        e = factory(cur, w)
    sim_w, sim_kw = world_kw(w)
    prof = PROFILES["fast_forgetter" if scen == "forgetting_21" else "nominal"]
    out = []
    for s in seeds:
        r = run_episode(e, s, sc, mode, prof, world=sim_w, sim_kw=sim_kw)
        mastered = sum(1 for t in r["final_theta"].values() if t >= 0.70)
        row = {
            "goal": int(r["goal_mastered"]),
            "allreq": int(r["all_required_mastered"]),
            "ttm": r["minutes_to_goal_mastery"],
            "minutes": r["minutes_used"],
            "avail": r["minutes_available"],
            "util": r["minute_utilisation"],
            "dx": r["dx_minutes"],
            "dx_items": r["dx_items"],
            "ret": r["retention"],
            "believed": r["believed_mastered"],
            "fm": r["false_mastered"],
            "items": r["total_activities_completed"],
            "mastered": mastered,
            "exec_viol": r["executed_prereq_violations"],
            "plan_viol": r["plan_prereq_violations"],
            "budget_viol": r["budget_violations"],
            "sse": sum((p - float(y)) ** 2 for p, y in r["attempts"]),
            "n_att": len(r["attempts"]),
        }
        out.append(
            {
                "cell": cell_id(w, cur, b, scen, h),
                "arm": arm,
                "seed": s,
                "deadline": sc.deadline,
                "row": row,
                "hist": _hist(r["attempts"]),
            }
        )
    return out


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def _reliability(hist):
    """10 equal-width bins from the 100-bin histogram (bin k -> k // 10); same edges as
    stats.reliability_bins. mean_p is the bin-mean of the raw predictions."""
    agg = [[0, 0, 0.0] for _ in range(10)]
    for k, (pos, neg, sp) in hist.items():
        x = agg[int(k) * 10 // N_BINS]
        x[0] += pos
        x[1] += neg
        x[2] += sp
    return [
        {
            "lo": i / 10,
            "hi": (i + 1) / 10,
            "n": pos + neg,
            "mean_p": round(sp / (pos + neg), 4) if pos + neg else None,
            "freq": round(pos / (pos + neg), 4) if pos + neg else None,
        }
        for i, (pos, neg, sp) in enumerate(agg)
    ]


def summarise(recs, hist, curve=False):
    rows = [r["row"] for r in recs]
    times = [r["ttm"] if r["ttm"] is not None else r["minutes"] for r in rows]
    events = [r["ttm"] is not None for r in rows]
    believed = sum(r["believed"] for r in rows)
    mastered = sum(r["mastered"] for r in rows)
    pairs, n_att = [], sum(r["n_att"] for r in rows)
    for pos, neg, sp in hist.values():  # AUC on bin-mean predictions (1/100-wide bins)
        p = sp / (pos + neg)
        pairs += [(p, True)] * pos + [(p, False)] * neg
    out = {
        "n": len(rows),
        "goal_mastery_rate": _mean([r["goal"] for r in rows]),
        "all_required_rate": _mean([r["allreq"] for r in rows]),
        "false_mastery_rate": round(sum(r["fm"] for r in rows) / believed, 4) if believed else None,
        "minute_utilisation": _mean([r["util"] for r in rows]),
        "mean_dx_minutes": _mean([r["dx"] for r in rows]),
        "mean_dx_items": _mean([r.get("dx_items") for r in rows]),
        "items_per_mastered_concept": round(sum(r["items"] for r in rows) / mastered, 4)
        if mastered
        else None,
        "reach_rate": _mean([float(e) for e in events]),
        "km_median_minutes": km_median(times, events),
        "km_rmst_minutes": km_rmst(times, events, max(r["avail"] for r in rows)),
        "km_tau": max(r["avail"] for r in rows),
        "brier": round(sum(r["sse"] for r in rows) / n_att, 4) if n_att else None,
        "auc": roc_auc(pairs) if pairs else None,
        "n_attempts": n_att,
        "executed_prereq_violations": sum(r["exec_viol"] for r in rows),
        "plan_prereq_violations": sum(r["plan_viol"] for r in rows),
        "budget_violations": sum(r["budget_viol"] for r in rows),
        "reliability": _reliability(hist),
    }
    if curve:  # same times/events as the RMST above
        out["km_curve"] = [[t, round(sv, 4)] for t, sv in kaplan_meier(times, events)]
    return out


def _paired(recs_a, recs_b, key):
    b = {r["seed"]: r["row"][key] for r in recs_b}
    d = [float(r["row"][key] - b[r["seed"]]) for r in recs_a if r["seed"] in b]
    return {
        "diff": round(sum(d) / len(d), 4) if d else 0.0,
        "ci95": list(paired_bootstrap_ci(d, n_boot=2000, seed=20260)),
        "n": len(d),
    }


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", choices=("primary", "stress", "both"), default="primary")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--processes", type=int, default=None)
    a = ap.parse_args(argv)
    t0 = time.time()
    prov = stamp()
    hashes = (prov["code_hash"], prov["experiment_hash"])
    out_dir = a.out_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(out_dir, exist_ok=True)
    name = "grid_smoke" if a.smoke else "grid"
    ckpt = os.path.join(out_dir, f"{name}.ckpt.jsonl")

    cells = list(grid_cells("primary" if a.smoke else a.grid))
    if a.smoke:
        keep = (("S1", "4node_x10", 15, "calm", 14), ("S1", "4node_x10", 15, "missed_day", 7))
        cells = [c for c in cells if c[1:6] in keep]
    prewarm(cells)

    units, meta_cells, skipped_cells = [], {}, {}
    for grid, w, cur, b, scen, h, arms in cells:
        why = skip_reason(scen, cur, b, h)
        if why:
            skipped_cells[cell_id(w, cur, b, scen, h)] = why
            continue
        seeds = HEADLINE_SEEDS if (w, cur, b, scen, h) == HEADLINE else REPORT_SEEDS
        seeds = seeds[:20] if a.smoke else seeds
        meta_cells[cell_id(w, cur, b, scen, h)] = grid
        for arm in arms:
            for i in range(0, len(seeds), CHUNK):
                units.append((grid, w, cur, b, scen, h, arm, seeds[i : i + CHUNK]))

    done: dict = {}  # (cell, arm, seed) -> slim record (no hist)
    hists: dict = defaultdict(dict)  # (cell, arm) -> bin -> [pos, neg, sum_p]
    skipped = other_hash = 0

    def add(rec):
        key = (rec["cell"], rec["arm"], rec["seed"])
        if key in done:
            return False
        agg = hists[(rec["cell"], rec["arm"])]
        for k, (pos, neg, sp) in rec.pop("hist").items():
            x = agg.setdefault(k, [0, 0, 0.0])
            x[0] += pos
            x[1] += neg
            x[2] += sp
        done[key] = rec
        return True

    if a.resume and os.path.exists(ckpt):
        with open(ckpt) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:  # truncated line from a killed run
                    skipped += 1
                    continue
                if (rec.get("code_hash"), rec.get("experiment_hash")) == hashes:
                    add(rec)
                else:  # written by other code: never mixed into this run
                    other_hash += 1
    elif os.path.exists(ckpt):
        os.remove(ckpt)

    def todo_seeds(u):
        grid, w, cur, b, scen, h, arm, seeds = u
        cid = cell_id(w, cur, b, scen, h)
        return [s for s in seeds if (cid, arm, s) not in done]

    todo = []
    for u in units:
        left = todo_seeds(u)
        if left:
            todo.append((*u[:7], left))
    executed = 0
    batch = max(8, 4 * (a.processes or os.cpu_count() or 1))
    with open(ckpt, "a+") as ck:
        ck.seek(0, 2)
        if ck.tell():  # a killed run may leave a half line; start new records on a fresh line
            ck.seek(ck.tell() - 1)
            if ck.read(1) != "\n":
                ck.write("\n")
        for i in range(0, len(todo), batch):
            gc.freeze()  # keep parent objects out of GC so forked workers share their pages
            for recs in run_parallel(run_unit, todo[i : i + batch], a.processes):
                for rec in recs:
                    rec["code_hash"], rec["experiment_hash"] = hashes
                    ck.write(json.dumps(rec) + "\n")
                    add(rec)
                    executed += 1
            ck.flush()
            print(
                f"  {min(i + batch, len(todo))}/{len(todo)} units, {time.time() - t0:.0f}s",
                flush=True,
            )

    print(f"  summarising {len(meta_cells)} cells (paired bootstrap), {time.time() - t0:.0f}s",
          flush=True)  # fmt: skip
    by_cell: dict = defaultdict(lambda: defaultdict(list))
    for (cid, arm, _s), rec in done.items():
        if cid in meta_cells:
            by_cell[cid][arm].append(rec)
    out_cells = {}
    for cid in sorted(by_cell):
        arms = {k: sorted(v, key=lambda r: r["seed"]) for k, v in by_cell[cid].items()}
        cell = {
            "grid": meta_cells[cid],
            "deadline": next(iter(arms.values()))[0]["deadline"],
            "arms": {
                k: summarise(v, hists[(cid, k)], curve=cid == cell_id(*HEADLINE))
                for k, v in arms.items()
            },
            "paired_vs_static_loop": {},
            "paired_vs_product": {},
        }
        if "product" in arms:
            for k, v in arms.items():
                if k in ABLATION_ARMS:
                    cell["paired_vs_product"][k] = {
                        "goal_mastery": _paired(v, arms["product"], "goal"),
                        "all_required": _paired(v, arms["product"], "allreq"),
                    }
        if "static_loop" in arms:
            for k, v in arms.items():
                if k != "static_loop":
                    cell["paired_vs_static_loop"][k] = {
                        "goal_mastery": _paired(v, arms["static_loop"], "goal"),
                        "all_required": _paired(v, arms["static_loop"], "allreq"),
                    }
        out_cells[cid] = cell
    payload = {
        "meta": {
            "grid": "primary" if a.smoke else a.grid,
            "smoke": a.smoke,
            "headline_cell": cell_id(*HEADLINE),
            "arms": list(ARMS),
            "curricula": [c for c in CURRICULA if c != "synth-50-x10"],
            "episodes_executed": executed,
            "checkpoint_lines_skipped": skipped,
            "checkpoint_lines_other_hash": other_hash,
            "skipped_cells": skipped_cells,
            "items_per_mastered_concept": "sum over seeds of executed planned activities "
            "(lessons + exercises, diagnostic items excluded) / sum over seeds of required "
            "concepts (goal + ancestors) with true theta >= 0.70 at episode end; concepts "
            "already mastered at day 0 count in the denominator",
            "km_censoring": "episodes without goal mastery are censored at minutes used "
            "(informative censoring, FINAL_A5 convention); RMST tau = max minutes available",
            "calibration_method": "Brier exact (SSE/n over in-loop attempts); AUC Mann-Whitney "
            "on per-seed 100-bin histograms, bin-mean predictions (approximate)",
            "runtime_s": round(time.time() - t0, 1),
        },
        "cells": out_cells,
    }
    write_result(name, payload, out_dir)
    print(f"  wrote {name}.json, {time.time() - t0:.0f}s", flush=True)
    return payload


if __name__ == "__main__":
    main()
