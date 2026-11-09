#!/usr/bin/env python3
"""W7 T3.5 (simulated part): fit BKT guess/slip per difficulty class plus prior/learn on the
*tuning* cohort's simulated answers, then compare fitted vs the D6 heuristic on *held-out* learners.

Data: exercise answers from closed-loop `adapt` episodes (4-node, B=15, calm), tuning = even seeds
100-198, held-out = odd seeds 101-199, in world S0 (the profile written to config/fitted_sim.json)
and S4 (BKT world: a recovery check). Fitting uses experiments/fit_bkt.py (fast_em, best of 5).
Writes experiments/results/bkt_fit_sim.json and config/fitted_sim.json (code_hash, no git).
"""

from __future__ import annotations

import json
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

import pandas as pd  # noqa: E402

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core import constants as C  # noqa: E402
from adaptengine.learner.adapter import DEFAULT_CLASS_PARAMS  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.fit_bkt import (  # noqa: E402
    CLASSES,
    class_seqs,
    classify,
    fit_classes,
    metrics,
    predict,
    write_profile,
)
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402

TUNING, HELDOUT = range(100, 200, 2), range(101, 200, 2)


def answers(engine, world, seeds) -> pd.DataFrame:
    sc = get_scenario("calm", engine, engine.init_learner(), goal="C4", budget=15)
    rows = []
    for s in seeds:
        r = run_episode(engine, s, sc, "adapt", PROFILES["nominal"], world=world)
        rows += [
            {"user": s, "skill": c, "correct": int(y), "d": d} for c, _, d, y in r["exercise_log"]
        ]
    return pd.DataFrame(rows)


def heuristic_fit():
    return {
        "prior": C.P0,
        "learn": C.T_EXERCISE,
        "guess": [DEFAULT_CLASS_PARAMS[k]["guess"] for k in CLASSES[:3]] + [0.15],
        "slip": [DEFAULT_CLASS_PARAMS[k]["slip"] for k in CLASSES[:3]] + [0.175],
    }


def as_arrays(f):
    return {**f, "guess": [f["guess"][k] for k in CLASSES], "slip": [f["slip"][k] for k in CLASSES]}


def run_world(engine, world):
    tune, held = answers(engine, world, TUNING), answers(engine, world, HELDOUT)
    fit = fit_classes(tune, classify(tune.d))
    S = class_seqs(held, classify(held.d))
    y = held.correct.to_numpy()
    res = {
        "n_answers": {"tuning": len(tune), "heldout": len(held)},
        "fit": {k: fit[k] for k in ("prior", "learn", "guess", "slip", "flags")},
        "heldout": {
            "fitted_class": metrics(y, predict(S, as_arrays(fit), len(held))),
            "heuristic_D6": metrics(y, predict(S, heuristic_fit(), len(held))),
        },
    }
    return res, fit


def main():
    e = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    out = {"metadata": {**stamp(), "tuning": "even 100-198", "heldout": "odd 101-199"}}
    for world in ("S0", "S4"):
        out[world], fit = run_world(e, world)
        if world == "S0":
            prof = write_profile(
                os.path.join(repo_root, "config", "fitted_sim.json"),
                fit,
                {
                    "name": "fitted_sim",
                    "source": "simulated S0 tuning cohort, adapt episodes, 4-node, B=15, calm",
                    **out["metadata"],
                },
            )
            out["profile_written"] = "config/fitted_sim.json"
            out["profile_class_params"] = prof.get("class_params")
    path = os.path.join(repo_root, "experiments", "results", "bkt_fit_sim.json")
    json.dump(out, open(path, "w"), indent=2, sort_keys=True, default=float)
    for w in ("S0", "S4"):
        print(
            w,
            out[w]["n_answers"],
            "fit prior/learn",
            out[w]["fit"]["prior"],
            out[w]["fit"]["learn"],
        )
        print("  guess", out[w]["fit"]["guess"], "slip", out[w]["fit"]["slip"])
        for k, v in out[w]["heldout"].items():
            print(
                f"  {k}: rmse {v['rmse']:.4f} brier {v['brier']:.4f} logloss {v['logloss']:.4f}"
                f" auc {v['auc']:.4f} ece {v['ece']:.4f}"
            )


if __name__ == "__main__":
    main()
