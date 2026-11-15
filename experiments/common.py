"""Shared base for the E1-E6 runners: product engine, seeds, curricula, results, parallel map.
Never imported from src/."""

from __future__ import annotations

import atexit
import dataclasses
import json
import multiprocessing as mp
import os
import re
import shutil
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (REPO_ROOT, os.path.join(REPO_ROOT, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.profiles import product_config  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import s4_fitted_params  # noqa: E402
from experiments.synth_curriculum import X10_DIFFICULTIES, write_synthetic_curriculum  # noqa: E402

# FINAL_A5 §1 seed sets. Reporting uses odd seeds only; tuning and fitting never touch them.
FIT_SEEDS = tuple(range(2000, 2400, 2))
TRAIN_SEEDS = tuple(range(6000, 6400, 2))
HLR_SEEDS = tuple(range(8000, 8400, 2))
REPORT_SEEDS = tuple(range(2001, 2401, 2))
HEADLINE_SEEDS = tuple(range(2001, 4001, 2))

CURRICULA = ("4node_x10", "8node_x10", "synth-20-x10", "synth-50-x10")
_SYNTH: dict = {}
_ENGINES: dict = {}


def curriculum_paths(cur: str, root: str = REPO_ROOT) -> tuple[str, str]:
    m = re.fullmatch(r"synth-(\d+)-x10", cur)
    if m:
        if cur not in _SYNTH:
            tmp = tempfile.mkdtemp(prefix="adaptengine-synth-")
            pid = os.getpid()  # forked workers inherit the hook; only the creator deletes
            atexit.register(lambda: os.getpid() == pid and shutil.rmtree(tmp, ignore_errors=True))
            _SYNTH[cur] = write_synthetic_curriculum(
                tmp, int(m[1]), seed=2026, difficulties=X10_DIFFICULTIES
            )
        return _SYNTH[cur]
    if cur not in CURRICULA:
        raise ValueError(f"unknown curriculum {cur!r}")
    paths = tuple(
        os.path.join(root, "data", "curriculum", f"{k}_{cur}.json")
        for k in ("curriculum", "activities")
    )
    for p in paths:
        if not os.path.isfile(p):
            raise FileNotFoundError(p)  # never fall back to the 4-exercise curriculum
    return paths


def product_engine(cur: str, profile: str = "fitted_S1", policy=None, **overrides) -> Engine:
    """Product-config engine. Engine is immutable after __init__ (state lives in LearnerState),
    so it is cached; a stateful policy gets a fresh instance."""
    key = (cur, profile, tuple(sorted(overrides.items())))
    if policy is None and key in _ENGINES:
        return _ENGINES[key]
    cp, ap = curriculum_paths(cur)
    cfg = dataclasses.replace(product_config(profile), **overrides)
    e = Engine.from_files(
        cp, ap, config=cfg, allow_unreviewed=cur.startswith("synth-"), policy=policy
    )
    if policy is None:
        _ENGINES[key] = e
    return e


def goal_of(e: Engine) -> str:
    return max(e.graph.concepts(), key=lambda c: (len(e.graph.ancestors(c)), c))


def world_kw(world: str) -> tuple[str, dict]:
    if world == "S4F":
        return "S4", {
            "bkt_params": s4_fitted_params(os.path.join(REPO_ROOT, "config/fitted_assist09.json"))
        }
    return world, {}


def write_result(name: str, payload: dict, out_dir: str | None = None) -> str:
    out_dir = out_dir or os.path.join(REPO_ROOT, "experiments", "results")
    os.makedirs(out_dir, exist_ok=True)
    payload["meta"] = {**payload.get("meta", {}), **stamp(), "engine": "product"}
    path = os.path.join(out_dir, f"{name}.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


def run_parallel(fn, units, processes: int | None = None) -> list:
    with mp.Pool(processes) as pool:
        return pool.map(fn, units)  # map preserves input order
