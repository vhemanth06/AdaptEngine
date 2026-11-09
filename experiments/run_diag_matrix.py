#!/usr/bin/env python3
"""W7 T3.7: diagnostic comparison matrix across simulator worlds S0, S2, S4 (R§7.3).

Arms: prior only, W6 shipped, T3.3 default, single-flag variants (min-k, soft prune, frontier),
the R§7.4 recommendation, state-space (T3.6), fitted BKT parameters (T3.5, if
config/fitted_sim.json exists), fixed order at matched items, and the external IRT CAT baseline
(global and per-concept ability). Scored with T3.1 metrics; paired CIs vs prior-only and vs the
W6 shipped diagnostic. Writes experiments/results/w7_diag_matrix.json.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.diagnostic.state_space import StateSpaceDiagnostic  # noqa: E402
from experiments.cat_baseline import irt_cat  # noqa: E402
from experiments.diag_eval import (  # noqa: E402
    W6_DIAGNOSTIC,
    binary_score,
    run_fixed_diagnostic,
)
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES, make_sim  # noqa: E402
from experiments.stats import brier_decomposition, log_loss, paired_summary, roc_auc  # noqa: E402

CUR, ACT = "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
FITTED_SIM = os.path.join(repo_root, "config", "fitted_sim.json")
VARIANTS = {
    "w6_shipped": W6_DIAGNOSTIC,
    "default_t33": {},
    "min_k2": {**W6_DIAGNOSTIC, "min_items_per_concept": 2},
    "soft_prune": {**W6_DIAGNOSTIC, "pruning_mode": "soft"},
    "frontier": {**W6_DIAGNOSTIC, "selection_scope": "frontier"},
    "r74_recommended": {
        "min_items_per_concept": 2,
        "pruning_mode": "none",
        "selection_scope": "frontier",
        "concept_cap": 2,
        "n_max": 8,
    },
}


def engine_for(model=None, **kw):
    cfg = dataclasses.replace(DEFAULT_CONFIG, **kw)
    return Engine.from_files(CUR, ACT, config=cfg, model=model)


def fitted_model():
    if not os.path.exists(FITTED_SIM):
        return None
    from adaptengine.learner.adapter import PyBKTAdapter

    prof = json.load(open(FITTED_SIM, encoding="utf-8"))
    return PyBKTAdapter(class_params=prof["class_params"])


def run_world(world: str, seeds, prof) -> dict:
    engines = {k: engine_for(**v) for k, v in VARIANTS.items()}
    fm = fitted_model()
    if fm is not None:
        engines["fitted_bkt"] = engine_for(model=fm)
    base = engines["default_t33"]
    rows: dict[str, list] = {}
    items: dict[str, list] = {}

    def add(name, eng, st, n, s):
        rows.setdefault(name, []).append(binary_score(eng, st, s, prof, world))
        items.setdefault(name, []).append(n)

    def provider(sim):
        return lambda a: sim.respond(a.target_concept, a.activity_id, a.difficulty, tag="diag")

    for s in seeds:
        add("prior_only", base, base.init_learner(), 0, s)
        for name, eng in engines.items():
            r = eng.diagnose(
                eng.init_learner(), provider(make_sim(eng, s, prof, world)), None, session_id=str(s)
            )
            add(name, eng, r.state, r.total_items, s)
        ssd = StateSpaceDiagnostic(base.graph, base.activities, base.config)
        r = ssd.run(
            base.init_learner(), provider(make_sim(base, s, prof, world)), session_id=str(s)
        )
        add("state_space", base, r.state, r.total_items, s)
        n = items["default_t33"][-1]
        st, k = run_fixed_diagnostic(base, s, prof, n, world)
        add("fixed@n_default", base, st, k, s)
        for k_items in (n, 8):
            st, k = irt_cat(base, make_sim(base, s, prof, world), k_items, a=prof.a)
            add(f"irt_cat_global@{'n' if k_items == n else k_items}", base, st, k, s)
        st, k = irt_cat(base, make_sim(base, s, prof, world), 8, a=prof.a, per_concept=True)
        add("irt_cat_per_concept@8", base, st, k, s)

    def br(name):
        return [r["brier"] for r in rows[name]]

    out = {}
    for name, rs in rows.items():
        pairs = [x for r in rs for x in r["pairs"]]
        out[name] = {
            "brier": round(sum(br(name)) / len(rs), 4),
            "log_loss": log_loss(pairs),
            "auc": roc_auc(pairs),
            "next_response_brier": round(sum(r["next_brier"] for r in rs) / len(rs), 4),
            "items": round(sum(items[name]) / len(items[name]), 3),
            "decomposition": brier_decomposition(pairs),
            "vs_prior_only": paired_summary(br(name), br("prior_only")),
            "vs_w6_shipped": paired_summary(br(name), br("w6_shipped")),
        }
    return out


def main(out_path: str, n: int) -> dict:
    prof = PROFILES["nominal"]
    seeds = list(range(101, 101 + 2 * n, 2))  # held-out (odd) learners
    res = {
        "metadata": {
            **stamp(),
            "seeds": [seeds[0], seeds[-1], "odd"],
            "n_learners": len(seeds),
            "fitted_profile": FITTED_SIM if os.path.exists(FITTED_SIM) else None,
            "irt_cat_note": "IRT CAT uses the simulator's true discrimination a=3 (advantage in "
            "S0/S2, which are 2PL IRT worlds)",
        },
        "worlds": {w: run_world(w, seeds, prof) for w in ("S0", "S2", "S4")},
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, sort_keys=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out", default=os.path.join(repo_root, "experiments/results/w7_diag_matrix.json")
    )
    ap.add_argument("--n", type=int, default=250)
    a = ap.parse_args()
    r = main(a.out, a.n)
    for w, arms in r["worlds"].items():
        print(f"\n== {w} ==")
        for k, v in arms.items():
            print(
                f"  {k:24s} Brier={v['brier']:.4f} AUC={v['auc']} items={v['items']:.2f} "
                f"vs prior {v['vs_prior_only']['diff']:+.4f} {v['vs_prior_only']['ci95']} "
                f"vs W6 {v['vs_w6_shipped']['diff']:+.4f} {v['vs_w6_shipped']['ci95']}"
            )
