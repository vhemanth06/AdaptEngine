"""Ranking-policy interface (W8 J.1).

choose(candidates, context) -> (activity_id, propensity, info)

`candidates` are the engine's deterministic top-K new-content candidates (dicts, best first; see
planner/schedule._policy_pick); `context` holds the day, deadline, budget and keyed-RNG seed. The
scheduler re-checks the returned id and falls back to the deterministic choice on any failure.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RankingPolicy(Protocol):
    name: str
    version: str

    def choose(self, candidates: list[dict], context: dict) -> tuple[str, float, dict]: ...


def keyed_uniform(*key: Any) -> float:
    """Deterministic uniform [0, 1) from a key (SHA-256; no global RNG state)."""
    h = hashlib.sha256("|".join(str(k) for k in key).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / 2.0**64


class DeterministicPolicy:
    """Wraps the W7 ranking: always the deterministic top candidate (plans are bit-identical)."""

    name = "deterministic"
    version = "w7"

    def choose(self, candidates: list[dict], context: dict) -> tuple[str, float, dict]:
        return candidates[0]["activity_id"], 1.0, {}
