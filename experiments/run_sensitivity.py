#!/usr/bin/env python3
"""E3: sensitivity around the shipped product config. A measurement, not a selection.

  python experiments/run_sensitivity.py --smoke   # 2 cells, 8 report seeds -> sensitivity_smoke.json
  python experiments/run_sensitivity.py           # -> experiments/results/sensitivity.json
Options: --out-dir, --processes.
One-at-a-time scans of SCANS plus a theta x k_responses factorial; each config is
product_engine(cur, **changes), arm adapt_dx, on REPORT_SEEDS. The product config appears in every
scan but runs once per cell; static_loop runs once per cell as reference. Combinations the config
validation rejects are logged under meta.skipped, never raised.
"""

from __future__ import annotations

import argparse
import itertools
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from adaptengine.core.profiles import product_config  # noqa: E402
from experiments.common import (  # noqa: E402
    REPORT_SEEDS,
    curriculum_paths,
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

SCANS = {
    "theta": (0.85, 0.90, 0.95, 0.98),
    "k_responses": (1, 2, 3),
    "mastery_criterion": ("bkt_threshold", "two_threshold", "n_consecutive"),
    "horizon_aware_mastery": (False, True),
    "consolidation": (False, True),
    "concept_cap": (2, 4, 6),
    "n_max": (12, 25, 40),
    "diag_budget_per_concept": (0.0, 0.5, 1.0, 2.0),
    "known_threshold": (0.60, 0.70, 0.80),
    "skip_threshold": (0.30, 0.40, 0.50),
    "selection_scope": ("concept_sweep", "frontier", "goal_search"),
    "pruning_mode": ("hard", "soft", "none"),
}
FACTORIAL = ("theta", "k_responses")
WORLDS = ("S0", "S1", "S4")
CURS = ("4node_x10", "8node_x10")
BUDGET, SCEN, HORIZON = 15, "calm", 14


def label(changes: dict) -> str:
    return ",".join(f"{k}={v}" for k, v in sorted(changes.items())) or "product"


def build_configs(scans=SCANS, factorial=FACTORIAL, cur="4node_x10"):
    """-> (configs {label: changes}, index {scan: [(value, label | None)]}, skipped {label: reason}).
    A change equal to the product value is dropped, so that config dedupes to "product"."""
    prod = product_config()
    configs: dict = {"product": {}}
    skipped: dict = {}

    def add(changes):
        eff = {k: v for k, v in changes.items() if v != getattr(prod, k)}
        lab = label(eff)
        if lab not in configs and lab not in skipped:
            try:
                product_engine(cur, **eff)
                configs[lab] = eff
            except Exception as ex:  # ValidationError etc.: invalid combination, record it
                skipped[lab] = f"{type(ex).__name__}: {ex}"
        return lab if lab in configs else None

    index = {k: [(v, add({k: v})) for v in vals] for k, vals in scans.items()}
    for combo in itertools.product(*(scans[k] for k in factorial)):
        add(dict(zip(factorial, combo)))
    return configs, index, skipped


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--processes", type=int, default=None)
    a = ap.parse_args(argv)
    t0 = time.time()
    cells = [(w, c) for w in WORLDS for c in CURS]
    seeds = REPORT_SEEDS
    if a.smoke:
        cells, seeds = [("S1", "4node_x10"), ("S0", "4node_x10")], REPORT_SEEDS[:8]
    configs, index, skipped = build_configs()
    for _w, cur in cells:  # pre-warm so forked workers inherit curricula and engines
        curriculum_paths(cur)
        _w7_engine(cur)
        for ch in configs.values():
            product_engine(cur, **ch)

    units = []
    for w, cur in cells:
        for lab, ch in {"static_loop": None, **configs}.items():
            for i in range(0, len(seeds), CHUNK):
                s = seeds[i : i + CHUNK]
                base = ("sens", w, cur, BUDGET, SCEN, HORIZON, lab, s)
                units.append(base if ch is None else (*base, ch))
    # static_loop goes through the grid's own arm table (no overrides element)
    recs = [r for out in run_parallel(run_unit, units, a.processes) for r in out]

    by: dict = defaultdict(lambda: defaultdict(list))
    hists: dict = defaultdict(dict)
    for r in recs:
        by[r["cell"]][r["arm"]].append(r)
        agg = hists.setdefault((r["cell"], r["arm"]), {})
        for k, (pos, neg, sp) in r.pop("hist").items():
            x = agg.setdefault(k, [0, 0, 0.0])
            x[0] += pos
            x[1] += neg
            x[2] += sp
    out_cells = {}
    for cid in sorted(by):
        arms = {k: sorted(v, key=lambda r: r["seed"]) for k, v in by[cid].items()}
        cell = {"configs": {}, "paired_vs_static_loop": {}, "paired_vs_product": {}}
        for lab, v in arms.items():
            cell["configs"][lab] = {
                **summarise(v, hists[(cid, lab)]),
                "mean_dx_items": _mean([r["row"]["dx_items"] for r in v]),
            }
            for ref, dst in (
                ("static_loop", "paired_vs_static_loop"),
                ("product", "paired_vs_product"),
            ):
                if lab != ref:
                    cell[dst][lab] = {
                        "goal_mastery": _paired(v, arms[ref], "goal"),
                        "all_required": _paired(v, arms[ref], "allreq"),
                    }
        out_cells[cid] = cell
    payload = {
        "meta": {
            "smoke": a.smoke,
            "arm": "adapt_dx",
            "reference": "static_loop",
            "cells": [cell_id(w, c, BUDGET, SCEN, HORIZON) for w, c in cells],
            "n_seeds": len(seeds),
            "scans": {k: list(v) for k, v in SCANS.items()},
            "factorial": list(FACTORIAL),
            "scan_index": {k: [[v, lab] for v, lab in vs] for k, vs in index.items()},
            "configs": configs,
            "skipped": skipped,
            "episodes_executed": len(recs),
            "runtime_s": round(time.time() - t0, 1),
        },
        "cells": out_cells,
    }
    write_result("sensitivity_smoke" if a.smoke else "sensitivity", payload, a.out_dir)
    return payload


if __name__ == "__main__":
    main()
