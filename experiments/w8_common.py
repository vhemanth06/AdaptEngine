"""Shared helpers for the W8 runners: curricula, goals, seed sets, profile-backed engines.
Never imported from src/."""

from __future__ import annotations

import dataclasses
import os
import sys
import tempfile

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.core.profiles import load_profile  # noqa: E402
from experiments.synth_curriculum import write_synthetic_curriculum  # noqa: E402

# Pre-registered seed sets (docs/preregistration/FINAL_A5_2026-11-10.md §1)
FIT_SEEDS = tuple(range(2000, 2400, 2))
SELECT_SEEDS = tuple(range(4000, 4400, 2))
TRAIN_SEEDS = tuple(range(6000, 6400, 2))
HLR_SEEDS = tuple(range(8000, 8400, 2))
REPORT_SEEDS = tuple(range(2001, 2401, 2))
HEADLINE_SEEDS = tuple(range(2001, 4001, 2))
FINAL_FLAGS = {"consolidation": True, "verification_probe": True}

_SYNTH: dict = {}
_ENGINES: dict = {}


def curriculum_paths(cur: str):
    if cur in ("4-node", "8-node"):
        n = cur.split("-")[0]
        return (
            f"data/curriculum/curriculum_{n}node.json",
            f"data/curriculum/activities_{n}node.json",
        )
    if cur.startswith("synth-"):
        if cur not in _SYNTH:
            _SYNTH[cur] = write_synthetic_curriculum(tempfile.mkdtemp(), int(cur[6:]), seed=2026)
        return _SYNTH[cur]
    return (f"data/curriculum/curriculum_{cur}.json", f"data/curriculum/activities_{cur}.json")


def goal_of(e: Engine) -> str:
    return max(e.graph.concepts(), key=lambda c: (len(e.graph.ancestors(c)), c))


def config_for(profile: str = "w7_default", **overrides):
    if profile == "w7_default":
        return dataclasses.replace(DEFAULT_CONFIG, **overrides) if overrides else DEFAULT_CONFIG
    return load_profile(profile, **overrides)


def engine(cur: str, profile: str = "w7_default", policy=None, **overrides) -> Engine:
    """Cached engine (no policy) or a fresh one (with a stateful policy)."""
    key = (cur, profile, tuple(sorted(overrides.items())))
    if policy is None and key in _ENGINES:
        return _ENGINES[key]
    cp, ap = curriculum_paths(cur)
    e = Engine.from_files(
        os.path.join(repo_root, cp) if not os.path.isabs(cp) else cp,
        os.path.join(repo_root, ap) if not os.path.isabs(ap) else ap,
        config=config_for(profile, **overrides),
        allow_unreviewed=cur.startswith("synth-"),
        policy=policy,
    )
    if policy is None:
        _ENGINES[key] = e
    return e
