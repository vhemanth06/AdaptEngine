#!/usr/bin/env python3
"""E2: diagnostic-accuracy matrix. How well each opening diagnostic estimates which concepts a
simulated learner has mastered (truth 1[theta >= 0.70], day 0), vs cheaper/alternative
diagnostics on a matched item budget.

  python experiments/run_diag.py --smoke        # 2 cells, 10 report seeds -> diag_matrix_smoke.json
  python experiments/run_diag.py                # -> experiments/results/diag_matrix.json
Options: --out-dir, --processes.
Arms: prior_only; product (AdaptiveDiagnostic on the product engine, diagnostic_scope="all",
every concept scored); product_goalpath (shipped scope, goal + ancestors scored);
concept_sweep_w7 (DEFAULT_CONFIG diagnostic fields on fitted_S1); frontier; state_space
(<= 12 concepts); fixed@n / random@n / irt_cat@n with n = the product item count for that
same learner. Output is deterministic for fixed seeds (wall-clock only in meta).
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.diagnostic.engine import StopReason  # noqa: E402
from adaptengine.diagnostic.state_space import MAX_CONCEPTS, StateSpaceDiagnostic  # noqa: E402
from experiments.common import (  # noqa: E402
    CURRICULA,
    REPORT_SEEDS,
    curriculum_paths,
    goal_of,
    product_engine,
    run_parallel,
    write_result,
)
from experiments.diag_baselines import fixed_order, irt_cat, prior_p, random_order  # noqa: E402
from experiments.sim import PROFILES, TRUE_MASTERY_CUTOFF, make_sim  # noqa: E402
from experiments.stats import brier_score, roc_auc  # noqa: E402

WORLDS = ("S0", "S1", "S2", "S4")
CHUNK = 10
# The W7 shipped diagnostic = DEFAULT_CONFIG's diagnostic fields, applied on the product engine.
_W7_FIELDS = (
    "selection_scope",
    "concept_cap",
    "n_max",
    "h_stop",
    "min_items_per_concept",
    "pruning_mode",
    "prior_mode",
    "diag_budget_min",
    "diag_budget_per_concept",
)
W7_DIAG = {f: getattr(DEFAULT_CONFIG, f) for f in _W7_FIELDS}
ARMS = (
    "prior_only",
    "product",
    "product_goalpath",
    "concept_sweep_w7",
    "frontier",
    "state_space",
    "fixed@n",
    "random@n",
    "irt_cat@n",
)


def _engines(cur):
    return {
        "product": product_engine(cur, diagnostic_scope="all"),
        "goalpath": product_engine(cur),
        "w7": product_engine(cur, diagnostic_scope="all", **W7_DIAG),
        "frontier": product_engine(cur, diagnostic_scope="all", selection_scope="frontier"),
    }


class _Counting:
    """Learner proxy that counts the items a baseline actually asked."""

    def __init__(self, sim):
        self.sim, self.items = sim, 0

    def respond(self, *a, **kw):
        self.items += 1
        return self.sim.respond(*a, **kw)


def _provider(sim):
    return lambda a: sim.respond(a.target_concept, a.activity_id, a.difficulty or 0.5, tag="diag")


def _record(p, scored, theta, items, result=None):
    """Per-learner record for one arm: (p, truth) over the scored concepts, plus INFERRED info."""
    rec = {
        "p": [p[c] for c in scored],
        "y": [theta[c] >= TRUE_MASTERY_CUTOFF for c in scored],
        "err": [abs(p[c] - theta[c]) for c in scored],
        "items": items,
        "stops": {},
        "inferred": [0, 0],
    }
    if result is not None:
        scope = set(scored)
        res = [(c, r) for c, r in result.concept_results.items() if c in scope]
        rec["stops"] = dict(Counter(r.stop_reason.value for _, r in res))
        inf = [c for c, r in res if r.stop_reason is StopReason.INFERRED]
        rec["inferred"] = [len(inf), sum(theta[c] >= TRUE_MASTERY_CUTOFF for c in inf)]
    return rec


def learner_arms(cur: str, world: str, seed: int) -> dict[str, dict]:
    """Every arm's record for one learner (same seed, cell). Learners are day-0 nominal sims."""
    es = _engines(cur)
    prof = PROFILES["nominal"]
    base = es["product"]
    concepts = list(base.graph.concepts())
    theta = make_sim(base, seed, prof, world).initial
    out = {"prior_only": _record(dict.fromkeys(concepts, prior_p(base)), concepts, theta, 0)}

    def sim():
        return make_sim(base, seed, prof, world)

    def diag(eng, goals=None):
        return eng.diagnose(
            eng.init_learner(), _provider(sim()), goal_concepts=goals, session_id=str(seed)
        )

    def from_result(r):
        return {c: r.state.concepts[c].p for c in concepts}

    r = diag(es["product"])
    out["product"] = _record(from_result(r), concepts, theta, r.total_items, r)
    n = r.total_items
    goal = goal_of(base)
    path = sorted({goal} | base.graph.ancestors(goal))
    r = diag(es["goalpath"], [goal])
    out["product_goalpath"] = _record(from_result(r), path, theta, r.total_items, r)
    for arm, key in (("concept_sweep_w7", "w7"), ("frontier", "frontier")):
        r = diag(es[key])
        out[arm] = _record(from_result(r), concepts, theta, r.total_items, r)
    if len(concepts) <= MAX_CONCEPTS:
        ssd = StateSpaceDiagnostic(base.graph, base.activities, base.config)
        r = ssd.run(base.init_learner(), _provider(sim()), session_id=str(seed))
        out["state_space"] = _record(from_result(r), concepts, theta, r.total_items, r)
    for arm, fn in (
        ("fixed@n", lambda L: fixed_order(base, L, n)),
        ("random@n", lambda L: random_order(base, L, n, seed)),
        ("irt_cat@n", lambda L: irt_cat(base, L, n)),
    ):
        L = _Counting(sim())
        p = fn(L)
        out[arm] = _record(p, concepts, theta, L.items)
    return out


def _mean(xs, nd=4):
    return round(sum(xs) / len(xs), nd) if xs else None


def _ratio(ok, n):
    return round(ok / n, 4) if n else None


def summarise(records, arms=ARMS) -> dict:
    out = {}
    for arm in arms:
        rs = [r[arm] for r in records if arm in r]
        if not rs:
            continue
        p = [x for r in rs for x in r["p"]]
        y = [x for r in rs for x in r["y"]]
        known = [t for q, t in zip(p, y) if q >= 0.70]
        unknown = [t for q, t in zip(p, y) if q < 0.40]
        items = sorted(r["items"] for r in rs)
        inf = [sum(r["inferred"][i] for r in rs) for i in (0, 1)]
        out[arm] = {
            "n_learners": len(rs),
            "brier": brier_score(list(zip(p, y))),
            "auc": roc_auc(list(zip(p, y))),
            "mae": _mean([e for r in rs for e in r["err"]]),
            "known_accuracy": _ratio(sum(known), len(known)),
            "n_known": len(known),
            "unknown_accuracy": _ratio(len(unknown) - sum(unknown), len(unknown)),
            "n_unknown": len(unknown),
            "inferred_precision": _ratio(inf[1], inf[0]),
            "n_inferred": inf[0],
            "items_mean": _mean(items, 3),
            "items_p90": items[max(0, math.ceil(0.9 * len(items)) - 1)],
            "stop_reasons": dict(sorted(sum((Counter(r["stops"]) for r in rs), Counter()).items())),
        }
    return out


def run_unit(u):
    cur, world, seeds = u
    return [learner_arms(cur, world, s) for s in seeds]


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--processes", type=int, default=None)
    a = ap.parse_args(argv)
    t0 = time.time()
    cells = [(w, c) for w in WORLDS for c in CURRICULA]
    seeds = REPORT_SEEDS
    if a.smoke:
        cells = [("S1", "4node_x10"), ("S4", "8node_x10")]
        seeds = seeds[:10]
    for _, cur in cells:  # pre-warm so forked workers inherit curricula and engines
        curriculum_paths(cur)
        _engines(cur)
    units = [(c, w, seeds[i : i + CHUNK]) for w, c in cells for i in range(0, len(seeds), CHUNK)]
    results = iter(run_parallel(run_unit, units, a.processes))
    out_cells = {}
    for w, cur in cells:
        recs = [r for _ in range(0, len(seeds), CHUNK) for r in next(results)]
        out_cells[f"{w}|{cur}"] = {"n": len(recs), "arms": summarise(recs)}
    payload = {
        "meta": {
            "smoke": a.smoke,
            "worlds": list(WORLDS),
            "curricula": list(CURRICULA),
            "arms": list(ARMS),
            "n_seeds": len(seeds),
            "truth": f"1[theta >= {TRUE_MASTERY_CUTOFF}] at day 0; labels Known p>=0.70, Unknown p<0.40",
            "concept_sweep_w7_fields": W7_DIAG,
            "matched_budget": "fixed@n, random@n, irt_cat@n use the product item count of the same learner",
            "irt_cat_note": "uses the simulator's true discrimination a=3 (advantage in 2PL worlds)",
            "runtime_s": round(time.time() - t0, 1),
        },
        "cells": out_cells,
    }
    write_result("diag_matrix_smoke" if a.smoke else "diag_matrix", payload, a.out_dir)
    return payload


if __name__ == "__main__":
    main()
