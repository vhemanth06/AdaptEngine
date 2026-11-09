#!/usr/bin/env python3
"""W7 T3.3: apply the pre-registered diagnostic selection rule
(docs/preregistration/W7_T3.3_2026-11-08.md) and report the winner on the held-out cohort.

Writes experiments/results/w7_diag_selection.json (code_hash + timestamp, no git).
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from experiments.diag_eval import W6_DIAGNOSTIC, binary_score, run_adaptive_diagnostic  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES, TRUE_MASTERY_CUTOFF, make_sim  # noqa: E402
from experiments.stats import log_loss, paired_summary, roc_auc  # noqa: E402

CUR, ACT = "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
GRID = {
    "min_items_per_concept": (1, 2),
    "pruning_mode": ("hard", "soft", "none"),
    "selection_scope": ("concept_sweep", "frontier"),
    "prior_mode": ("flat", "population"),
    "h_stop": (0.20, 0.35, 0.50),
    "concept_cap": (2, 3, 4),
    "n_max": (4, 6, 8),
}
TUNING = list(range(100, 200, 2))
HELDOUT = list(range(101, 200, 2))


def settings_rank(cfg: dict) -> tuple:
    """Rule step 3 tie-break: position of each value in the registered value lists."""
    return tuple(GRID[k].index(cfg[k]) for k in GRID)


def score(engine, seeds, world="S0", full=False):
    prof = PROFILES["nominal"]
    rows, items = [], []
    for s in seeds:
        st, n = run_adaptive_diagnostic(engine, s, prof, world)
        if full:
            rows.append(binary_score(engine, st, s, prof, world))
        else:
            truth = make_sim(engine, s, prof, world).initial
            rows.append(
                {
                    "brier": sum(
                        (st.concepts[c].p - (truth[c] >= TRUE_MASTERY_CUTOFF)) ** 2 for c in truth
                    )
                    / len(truth)
                }
            )
        items.append(n)
    return rows, items


def summary(rows, items):
    out = {
        "brier": round(sum(r["brier"] for r in rows) / len(rows), 4),
        "items": round(sum(items) / len(items), 3),
    }
    if "pairs" in rows[0]:
        pairs = [x for r in rows for x in r["pairs"]]
        out.update(
            log_loss=log_loss(pairs),
            auc=roc_auc(pairs),
            next_response_brier=round(sum(r["next_brier"] for r in rows) / len(rows), 4),
        )
    return out


def engine_for(**kw):
    return Engine.from_files(CUR, ACT, config=dataclasses.replace(DEFAULT_CONFIG, **kw))


def main(out_path: str) -> dict:
    prof = PROFILES["nominal"]
    e0 = engine_for(**W6_DIAGNOSTIC)  # the diagnostic shipped when the rule was registered
    base = [
        v >= TRUE_MASTERY_CUTOFF for s in TUNING for v in make_sim(e0, s, prof).initial.values()
    ]
    pop_p0 = round(sum(base) / len(base), 2)

    grid = []
    for values in itertools.product(*GRID.values()):
        cfg = dict(zip(GRID, values))
        rows, items = score(engine_for(population_p0=pop_p0, **cfg), TUNING)
        grid.append({**cfg, **summary(rows, items)})

    eligible = [g for g in grid if g["items"] <= 8]
    eligible.sort(key=lambda g: (g["brier"], g["items"], settings_rank(g)))
    winner = eligible[0]
    win_cfg = {k: winner[k] for k in GRID}

    held = {}
    for name, eng in (
        ("winner", engine_for(population_p0=pop_p0, **win_cfg)),
        ("shipped", e0),
    ):
        held[name] = score(eng, HELDOUT, full=True)
    prior_rows = [binary_score(e0, e0.init_learner(), s, prof, "S0") for s in HELDOUT]
    held["prior_only"] = (prior_rows, [0] * len(HELDOUT))

    def b(name):
        return [r["brier"] for r in held[name][0]]

    winner_better = summary(*held["winner"])["brier"] < summary(*held["shipped"])["brier"]
    result = {
        "metadata": {
            **stamp(),
            "preregistration": "docs/preregistration/W7_T3.3_2026-11-08.md",
            "tuning_seeds": [TUNING[0], TUNING[-1], "even"],
            "heldout_seeds": [HELDOUT[0], HELDOUT[-1], "odd"],
            "population_p0": pop_p0,
            "n_configs": len(grid),
            "n_eligible": len(eligible),
        },
        "winner": winner,
        "top10_tuning": eligible[:10],
        "heldout": {k: summary(*v) for k, v in held.items()},
        "heldout_paired": {
            "winner_minus_shipped": paired_summary(b("winner"), b("shipped")),
            "winner_minus_prior_only": paired_summary(b("winner"), b("prior_only")),
            "shipped_minus_prior_only": paired_summary(b("shipped"), b("prior_only")),
        },
        "adopt_winner_as_default": winner_better,
        "grid": grid,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out", default=os.path.join(repo_root, "experiments/results/w7_diag_selection.json")
    )
    r = main(ap.parse_args().out)
    print(json.dumps({k: r[k] for k in ("winner", "heldout", "heldout_paired")}, indent=1))
    print("adopt winner as default:", r["adopt_winner_as_default"])
