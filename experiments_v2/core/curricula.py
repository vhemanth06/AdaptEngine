"""Curricula: the reviewed ones through the engine's review gate, and the synthetic ones.

`8node_x10` is reviewed (D93) and loads like 4-node and 8-node, with no allow_unreviewed.
Synthetic curricula (seed 2026) are generated once into experiments_v2/data/synthetic/ and load
with allow_unreviewed=True because they are synthetic and not in the review manifest.
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import replace

from adaptengine.api import Engine
from adaptengine.core.config import DEFAULT_CONFIG, EngineConfig, config_hash

from .provenance import REPO_ROOT, V2_ROOT

REVIEWED = {
    "4-node": ("curriculum_4node.json", "activities_4node.json"),
    "8-node": ("curriculum_8node.json", "activities_8node.json"),
    "8node_x10": ("curriculum_8node_x10.json", "activities_8node_x10.json"),
}
SYNTH_DIR = os.path.join(V2_ROOT, "data", "synthetic")
SYNTH_SEED = 2026
# exercises per concept -> (difficulties, durations); 10 = the 3 easy / 4 medium / 3 hard spread
EXERCISE_SPECS = {
    4: ([0.20, 0.40, 0.60, 0.80], [1, 2, 2, 3]),
    10: (
        [0.10, 0.20, 0.30, 0.40, 0.45, 0.55, 0.60, 0.70, 0.80, 0.90],
        [1, 1, 1, 2, 2, 2, 2, 2, 2, 2],
    ),
}


def content_review(name: str) -> str:
    if name == "8node_x10":
        return "reviewed (D93)"
    return "reviewed" if name in REVIEWED else "synthetic, unreviewed"


def parse_synth(name: str) -> tuple[int, int]:
    """'synth-20' -> (20, 4); 'synth-50-x10' -> (50, 10)."""
    m = re.fullmatch(r"synth-(\d+)(?:-x(\d+))?", name)
    if not m or int(m.group(2) or 4) not in EXERCISE_SPECS:
        raise ValueError(f"unknown curriculum {name!r}")
    return int(m.group(1)), int(m.group(2) or 4)


def generate_synthetic(n: int, per: int = 4, seed: int = SYNTH_SEED) -> tuple[dict, dict]:
    """Layered DAG: 2-3 roots, layers of 2-4, one goal concept last; 1-2 prerequisites each from
    the previous layer. One 4-minute lesson and `per` exercises per concept."""
    rng = random.Random(seed)
    ids = [f"C{i}" for i in range(1, n + 1)]
    if n <= 8:
        sizes = [2, 3, 2, 1] if n == 8 else [n]
    else:
        remaining = n - 1
        first = min(remaining, rng.randint(2, 3))
        sizes, remaining = [first], remaining - first
        while remaining > 0:
            sz = remaining if remaining <= 4 else rng.randint(2, 4)
            sizes.append(sz)
            remaining -= sz
        sizes.append(1)
    layers, i = [], 0
    for sz in sizes:
        layers.append(ids[i : i + sz])
        i += sz
    concepts = []
    for li, layer in enumerate(layers):
        for cid in layer:
            pre = []
            if li:
                prev = layers[li - 1]
                pre = sorted(rng.sample(prev, min(len(prev), rng.randint(1, 2))))
            concepts.append(
                {"concept_id": cid, "description": f"Synthetic Concept {cid}", "prerequisites": pre}
            )
    diffs, durs = EXERCISE_SPECS[per]
    acts = []
    for cid in ids:
        acts.append(
            {
                "activity_id": f"L-{cid}",
                "type": "LESSON",
                "target_concept": cid,
                "duration": 4,
                "text": f"Lesson for {cid}",
                "_note": "synthetic unreviewed",
            }
        )
        for k, (d, t) in enumerate(zip(diffs, durs), start=1):
            acts.append(
                {
                    "activity_id": f"E-{cid}-{k}",
                    "type": "EXERCISE",
                    "target_concept": cid,
                    "duration": t,
                    "difficulty": d,
                    "text": f"Exercise {k} for {cid}",
                    "_note": "synthetic unreviewed",
                }
            )
    return {"schema_version": 1, "concepts": concepts}, {"schema_version": 1, "activities": acts}


def paths(name: str) -> tuple[str, str]:
    """Absolute (curriculum, activities) paths; synthetic files are written once if missing."""
    if name in REVIEWED:
        cp, ap = REVIEWED[name]
        base = os.path.join(REPO_ROOT, "data", "curriculum")
        return os.path.join(base, cp), os.path.join(base, ap)
    n, per = parse_synth(name)
    tag = f"synth_{n}" + ("" if per == 4 else f"_x{per}")
    cp = os.path.join(SYNTH_DIR, f"curriculum_{tag}.json")
    ap = os.path.join(SYNTH_DIR, f"activities_{tag}.json")
    if not (os.path.exists(cp) and os.path.exists(ap)):
        os.makedirs(SYNTH_DIR, exist_ok=True)
        cur, act = generate_synthetic(n, per)
        for p, obj in ((cp, cur), (ap, act)):
            with open(p, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2)
    return cp, ap


_ENGINES: dict = {}


def engine(name: str, cfg: EngineConfig = DEFAULT_CONFIG) -> Engine:
    """Cached Engine for a curriculum and config (per process)."""
    key = (name, config_hash(cfg))
    if key not in _ENGINES:
        cp, ap = paths(name)
        _ENGINES[key] = Engine.from_files(cp, ap, config=cfg, allow_unreviewed=name not in REVIEWED)
    return _ENGINES[key]


def engine_with(name: str, **overrides) -> Engine:
    return engine(name, replace(DEFAULT_CONFIG, **overrides))


def goal_of(e: Engine) -> str:
    """The concept with the most ancestors (ties: largest id)."""
    return max(e.graph.concepts(), key=lambda c: (len(e.graph.ancestors(c)), c))
