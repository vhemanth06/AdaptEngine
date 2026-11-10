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


# ---------------------------------------------------------------- W8 B.2 / O.3


def _w8_episodes(args):
    from experiments.w8_common import engine, goal_of

    world, cur, arm, scen, horizon, seeds = args
    e = engine(cur)
    sc = get_scenario(scen, e, e.init_learner(), goal=goal_of(e), budget=15, horizon=horizon)
    prof = PROFILES["fast_forgetter" if scen == "forgetting_21" else "nominal"]
    return [
        {"activity_log": run_episode(e, s, sc, arm, prof, world=world)["activity_log"]}
        for s in seeds
    ]


def main_w8():
    """B.2 (pre-registered, FINAL_A5 §2 + Amendment 1): per-world profiles with T_lesson;
    O.3: S3 profile with forgets. Writes config/fitted_S{0,1,4}.json, config/fitted_S3*.json and
    experiments/results/w8_fits.json."""
    from multiprocessing import Pool

    from experiments.bkt_lessons import fit, flags, sequences_from_episodes
    from experiments.w8_common import FIT_SEEDS

    jobs = {}
    for world in ("S0", "S1", "S4"):
        jobs[world] = [
            (world, cur, arm, "calm", 14, FIT_SEEDS)
            for cur in ("4-node", "8-node")
            for arm in ("static_loop", "random_eligible")
        ]
    jobs["S3"] = [
        (("S3", cur, arm, "forgetting_21", 21, FIT_SEEDS))
        for cur in ("4-node", "8-node")
        for arm in ("static_loop", "random_eligible")
    ]
    meta = {
        **stamp(),
        "fit_seeds": "even 2000-2398",
        "preregistration": "docs/preregistration/FINAL_A5_2026-11-10.md",
    }
    out = {"metadata": meta, "fits": {}}
    with Pool(min(12, os.cpu_count() or 2)) as pool:
        episodes = {
            w: [ep for r in pool.map(_w8_episodes, js) for ep in r] for w, js in jobs.items()
        }
    variants = [("S0", False), ("S1", False), ("S4", False), ("S3", False), ("S3", True)]
    for world, forgets in variants:
        seqs = sequences_from_episodes(episodes[world])
        f = fit(seqs, forgets=forgets)
        fl = flags(f)
        name = f"fitted_{world}" + ("_forget" if forgets else "")
        valid = not any("guess+slip>=1" in v for v in fl.values())
        out["fits"][name] = {**f, "flags": fl, "valid": valid}
        if not valid:
            continue
        prof = {
            "name": name,
            "source": f"simulated {world} fit cohort: static_loop + random_eligible, 4-node + 8-node, "
            + ("forgetting_21 (fast_forgetter)" if world == "S3" else "B=15, calm, 14 days"),
            **meta,
            "p0": f["prior"],
            "t_lesson": f["t_lesson"],
            "t_exercise": f["t_exercise"],
            "class_params": {
                c: {"guess": f["guess"][c], "slip": f["slip"][c]}
                for c in ("easy", "medium", "hard")
            },
            "constraint_warnings": fl,
            "loglik": f["loglik"],
        }
        if forgets:
            prof["forget"] = f["forget"]
        with open(os.path.join(repo_root, "config", f"{name}.json"), "w") as fh:
            json.dump(prof, fh, indent=2)
            fh.write("\n")
    path = os.path.join(repo_root, "experiments", "results", "w8_fits.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    for name, f in out["fits"].items():
        print(
            name,
            "valid" if f["valid"] else "INVALID",
            "p0 %.3f T_les %.3f T_ex %.3f F %.3f"
            % (f["prior"], f["t_lesson"], f["t_exercise"], f["forget"]),
            "g",
            {k: round(v, 3) for k, v in f["guess"].items()},
            "s",
            {k: round(v, 3) for k, v in f["slip"].items()},
            f["flags"],
        )


if __name__ == "__main__":
    if sys.argv[1:] == ["w8"]:
        main_w8()
    else:
        main()
