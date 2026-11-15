#!/usr/bin/env python3
"""E5: four extension experiments on the shipped product engine (FINAL_A5 §7).

  python experiments/run_extensions.py review_cap|elo|hlr|forgets|all [--smoke]
Each subcommand writes its key into <out-dir>/extensions.json (extensions_smoke.json for --smoke),
keeping the other keys. `hlr` also writes hlr_fit.json. Smoke = 2 seeds.
  review_cap (D.1): product_nodx vs +review cap vs product_norev, synth-20-x10 forgetting cells.
  elo (O.1): mastery_model elo vs bkt.   forgets (O.3): fitted_S3 vs fitted_S3_forget.
  hlr (O.2): HLR-lite weights fitted on HLR_SEEDS product episodes (S3), evaluated on REPORT_SEEDS.
Arms run through run_grid.run_unit with an overrides dict ("mode" picks the run mode).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.common import (  # noqa: E402
    HLR_SEEDS,
    REPORT_SEEDS,
    curriculum_paths,
    goal_of,
    product_engine,
    run_parallel,
    write_result,
)
from experiments.run_grid import (  # noqa: E402
    CHUNK,
    _mean,
    _paired,
    _w7_engine,
    cell_id,
    run_unit,
    summarise,
)
from experiments.sim import PROFILES  # noqa: E402

KEYS = ("review_cap", "elo", "hlr", "forgets")
CURS2 = ("4node_x10", "8node_x10")


def _cells(key, hlr_w=None):
    """-> list of (name, ref_arm, (world, cur, B, scenario, horizon), {arm: overrides})."""
    out = []
    if key == "review_cap":
        arms = {
            "product_nodx": {"mode": "adapt"},
            "capped": {"mode": "adapt", "review_cap_fraction": 0.25, "review_goal_path_only": True},
            "product_norev": {"mode": "no_review"},
        }
        for w in ("S0", "S1"):
            for b in (10, 15):
                out.append(
                    (
                        f"{w}|B{b}",
                        "product_norev",
                        (w, "synth-20-x10", b, "forgetting_21", 21),
                        arms,
                    )
                )
    elif key == "elo":
        arms = {"bkt": {}, "elo": {"mastery_model": "elo"}}
        for w in ("S0", "S1", "S4"):
            out.append((w, "bkt", (w, "4node_x10", 15, "calm", 14), arms))
    elif key == "hlr":
        arms = {
            "fixed": {"mode": "adapt"},
            "hlr": {"mode": "adapt", "half_life_model": "hlr", "hlr_weights": hlr_w},
            "product_norev": {"mode": "no_review"},
        }
        for w in ("S0", "S3"):
            for cur in CURS2:
                out.append((f"{w}|{cur}", "product_norev", (w, cur, 15, "forgetting_21", 21), arms))
    else:  # forgets
        arms = {
            "fitted_S3": {"profile": "fitted_S3"},
            "fitted_S3_forget": {"profile": "fitted_S3_forget"},
        }
        out.append(("S3", "fitted_S3", ("S3", "4node_x10", 15, "forgetting_21", 21), arms))
    return out


def fit_units(seeds=HLR_SEEDS):
    return [(cur, seeds[i : i + CHUNK]) for cur in CURS2 for i in range(0, len(seeds), CHUNK)]


def _fit_unit(u):
    """Product (adapt_dx, fixed half-life) episodes in S3 / forgetting_21 -> (gap, n_ok, n_wrong, y)."""
    cur, seeds = u
    e = product_engine(cur)
    sc = get_scenario("forgetting_21", e, e.init_learner(), goal=goal_of(e), budget=15, horizon=21)
    rows = []
    for s in seeds:
        log = run_episode(e, s, sc, "adapt_dx", PROFILES["fast_forgetter"], world="S3")[
            "activity_log"
        ]
        last, nc, nw = {}, {}, {}
        for c, _, is_lesson, _d, y, day in log:
            if not is_lesson:
                if c in last and day - last[c] >= 1:  # first exercise after a gap >= 1 day
                    rows.append((day - last[c], nc.get(c, 0), nw.get(c, 0), int(y)))
                nc[c] = nc.get(c, 0) + int(y)
                nw[c] = nw.get(c, 0) + (1 - int(y))
            last[c] = day
    return rows


def fit_hlr(seeds, out_dir, smoke, processes=None):
    """p(recall) = 2^(-gap/h), h = 2^(w . [1, sqrt(1+ok), sqrt(1+wrong)]); least squares by grid
    search (same grid as the pre-rewrite fit)."""
    units = fit_units(seeds)
    for cur, _ in units:
        product_engine(cur)
    rows = [r for out in run_parallel(_fit_unit, units, processes) for r in out]
    if not rows:
        raise RuntimeError("HLR fit: no recall-after-gap observations")
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
    fit = {
        "weights": list(best[1]),
        "brier": round(best[0], 5),
        "baseline_brier_mean": round(float(np.mean((y - y.mean()) ** 2)), 5),
        "n_observations": len(rows),
        "n_seeds": len(seeds),
        "worlds": "S3",
        "scenario": "forgetting_21",
        "curricula": list(CURS2),
        "episodes": len(seeds) * len(CURS2),
    }
    write_result("hlr_fit_smoke" if smoke else "hlr_fit", dict(fit), out_dir)
    return fit


def run_key(key, seeds, out_dir, smoke, processes, hlr_w=None):
    cells = _cells(key, hlr_w)
    for _n, _r, (_w, cur, *_x), arms in cells:  # pre-warm so forked workers inherit engines
        curriculum_paths(cur)
        _w7_engine(cur)
        for ov in arms.values():
            product_engine(cur, **{k: v for k, v in ov.items() if k != "mode"})
    units = []
    for name, _ref, (w, cur, b, scen, h), arms in cells:
        for arm, ov in arms.items():
            for i in range(0, len(seeds), CHUNK):
                units.append((key, w, cur, b, scen, h, arm, seeds[i : i + CHUNK], ov))
    recs = [r for out in run_parallel(run_unit, units, processes) for r in out]
    by, hists = defaultdict(lambda: defaultdict(list)), {}
    for r in recs:
        by[r["cell"]][r["arm"]].append(r)
        agg = hists.setdefault((r["cell"], r["arm"]), {})
        for k, (pos, neg, sp) in r.pop("hist").items():
            x = agg.setdefault(k, [0, 0, 0.0])
            x[0] += pos
            x[1] += neg
            x[2] += sp
    out_cells = {}
    for name, ref, (w, cur, b, scen, h), arms in cells:
        cid = cell_id(w, cur, b, scen, h)
        a = {k: sorted(v, key=lambda r: r["seed"]) for k, v in by[cid].items()}
        cell = {"name": name, "arms": {}, f"paired_vs_{ref}": {}}
        for lab, v in a.items():
            cell["arms"][lab] = {
                **summarise(v, hists[(cid, lab)]),
                "mean_retention": _mean([r["row"]["ret"] for r in v]),
            }
            if lab != ref:
                cell[f"paired_vs_{ref}"][lab] = {
                    "goal_mastery": _paired(v, a[ref], "goal"),
                    "all_required": _paired(v, a[ref], "allreq"),
                }
        if key == "review_cap":
            ci = cell["paired_vs_product_norev"]["capped"]["goal_mastery"]
            cell["capped_vs_no_review"] = ci
            _lo, hi = ci["ci95"]
            cell["pass"] = bool(hi >= 0)  # "CI includes or exceeds 0": fails only if hi < 0
        out_cells[cid] = cell
    return {
        "meta": {
            "smoke": smoke,
            "n_seeds": len(seeds),
            "episodes_executed": len(recs),
            **({"hlr_weights": list(hlr_w)} if hlr_w else {}),
        },
        "cells": out_cells,
    }


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=(*KEYS, "all"))
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--processes", type=int, default=None)
    a = ap.parse_args(argv)
    seeds = REPORT_SEEDS[:2] if a.smoke else REPORT_SEEDS
    name = "extensions_smoke" if a.smoke else "extensions"
    out_dir = a.out_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    path = os.path.join(out_dir, f"{name}.json")
    for key in KEYS if a.cmd == "all" else (a.cmd,):
        t0, hlr_w = time.time(), None
        if key == "hlr":
            fit = fit_hlr(HLR_SEEDS[:2] if a.smoke else HLR_SEEDS, out_dir, a.smoke, a.processes)
            hlr_w = tuple(fit["weights"])
        sub = run_key(key, seeds, out_dir, a.smoke, a.processes, hlr_w)
        sub["meta"]["runtime_s"] = round(time.time() - t0, 1)
        data = json.load(open(path)) if os.path.exists(path) else {}
        data[key] = sub
        write_result(name, data, out_dir)
        print(f"{key}: {sub['meta']['episodes_executed']} episodes, {sub['meta']['runtime_s']}s")
    return json.load(open(path))


if __name__ == "__main__":
    main()
