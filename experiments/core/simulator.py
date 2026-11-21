"""Simulated learners (Plan V2 §V2.3). Behaviour is pinned: every rule and random key below is the
one the earlier harness used, so results stay comparable (checked once in V2-T4).

Worlds: S0 independent abilities; S1 gains x readiness; S2 correlated abilities; S3 forgetting for
everyone; S4 BKT learners; S4-assist09 = S4 driven by config/fitted_assist09.json.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

from .provenance import REPO_ROOT

TRUE_MASTERY = 0.70
WORLDS = ("S0", "S1", "S2", "S3", "S4")
ALL_WORLDS = (*WORLDS, "S4-assist09")
READINESS_K = 10.0
S3_HALF_LIFE = (5.0, 30.0)
S4_P0 = 0.20
# The engine's heuristic g(d) = 0.30 (1 - d), s(d) = 0.05 + 0.25 d; learning transitions
S4_BKT = {"guess_coef": 0.30, "slip_base": 0.05, "slip_coef": 0.25, "t_lesson": 0.20, "t_ex": 0.05}
ASSIST09 = "config/fitted_assist09.json"


def keyed_uniform(*key: object) -> float:
    """Uniform [0, 1) from Random("|".join(key)): the same key gives the same draw in every arm."""
    return random.Random("|".join(str(k) for k in key)).random()


@dataclass(frozen=True)
class Profile:
    name: str
    a: float = 3.0
    slip: float = 0.0
    lesson_gain: float = 0.18
    exercise_gain: float = 0.05
    half_life: Optional[float] = None


PROFILES: Mapping[str, Profile] = {
    "nominal": Profile("nominal"),
    "high_slip": Profile("high_slip", slip=0.15),
    "fast_forgetter": Profile("fast_forgetter", half_life=7.0),
    "rapid_learner": Profile("rapid_learner", lesson_gain=0.30, exercise_gain=0.10),
}


def d6_class(d: float) -> str:
    return "easy" if d < 0.35 else "medium" if d < 0.65 else "hard"


def assist09_bkt() -> dict:
    with open(f"{REPO_ROOT}/{ASSIST09}", encoding="utf-8") as f:
        prof = json.load(f)
    return {"p0": prof["p0"], "t_ex": prof["t_exercise"], "class_params": prof["class_params"]}


def world_spec(world: str) -> tuple[str, dict]:
    """(simulator world, SimLearner kwargs) for a world name, including S4-assist09."""
    if world == "S4-assist09":
        return "S4", {"bkt": assist09_bkt()}
    if world not in WORLDS:
        raise ValueError(f"unknown world {world!r}")
    return world, {}


class SimLearner:
    """A learner with hidden ability theta per concept."""

    def __init__(
        self,
        seed: int,
        concepts: Iterable[str],
        profile: Profile = PROFILES["nominal"],
        world: str = "S0",
        prereqs: Optional[Mapping[str, Iterable[str]]] = None,
        bkt: Optional[Mapping[str, object]] = None,
    ):
        if world not in WORLDS:
            raise ValueError(f"unknown world {world!r}")
        if world == "S1" and prereqs is None:
            raise ValueError("S1 needs the prerequisites")
        concepts = sorted(concepts)
        self.seed, self.profile, self.world = seed, profile, world
        self.prereqs = {c: tuple(v) for c, v in (prereqs or {}).items()}
        self.bkt = dict(S4_BKT, **(bkt or {}))
        r = random.Random(f"{seed}|truth")
        self.theta = {c: round(r.uniform(0.10, 0.90), 4) for c in concepts}
        if world == "S2":
            r2 = random.Random(f"{seed}|S2")
            g = r2.uniform(0.2, 0.8)
            self.theta = {
                c: round(min(0.95, max(0.05, g + r2.gauss(0.0, 0.10))), 4) for c in concepts
            }
        elif world == "S4":
            p0 = float(self.bkt.get("p0", S4_P0))
            self.theta = {
                c: 1.0 if keyed_uniform(seed, "S4init", c) < p0 else 0.0 for c in concepts
            }
        self.half_life = profile.half_life
        if world == "S3" and self.half_life is None:
            self.half_life = round(random.Random(f"{seed}|S3h").uniform(*S3_HALF_LIFE), 3)
        self.initial = dict(self.theta)
        self.last_day = {c: 1 for c in concepts}
        self._n: dict[tuple[str, str, str], int] = {}
        self._learn_n: dict[str, int] = {}

    def retention(self, dt: float) -> float:
        """Power law 1 / (1 + dt / h): deliberately a different family from the engine's."""
        h = self.half_life
        return 1.0 if h is None or self.world == "S4" else 1.0 / (1.0 + max(0.0, float(dt)) / h)

    def settle(self, day: int) -> None:
        for c in self.theta:
            self.theta[c] *= self.retention(day - self.last_day[c])
            self.last_day[c] = day

    def p_correct(self, concept: str, d: float) -> float:
        if self.world == "S4":
            b, known = self.bkt, self.theta[concept] >= 1.0
            if "class_params" in b:
                cp = b["class_params"][d6_class(d)]
                return 1.0 - cp["slip"] if known else cp["guess"]
            return (
                1.0 - (b["slip_base"] + b["slip_coef"] * d) if known else b["guess_coef"] * (1 - d)
            )
        logit = max(-10.0, min(10.0, self.profile.a * (self.theta[concept] - d)))
        return 1.0 / (1.0 + math.exp(-logit))

    def respond(self, concept: str, activity_id: str, d: float, tag: str = "run") -> bool:
        """Draw key (seed, tag, activity, n), n = earlier draws of (concept, activity, tag)."""
        k = (concept, activity_id, tag)
        n = self._n.get(k, 0)
        self._n[k] = n + 1
        correct = keyed_uniform(self.seed, tag, activity_id, n) < self.p_correct(concept, d)
        if correct and self.profile.slip > 0.0:
            correct = keyed_uniform(self.seed, "slip", activity_id, n) >= self.profile.slip
        return correct

    def readiness(self, concept: str) -> float:
        if self.world != "S1":
            return 1.0
        return min(
            (
                1.0 / (1.0 + math.exp(-READINESS_K * (self.theta[q] - TRUE_MASTERY)))
                for q in self.prereqs.get(concept, ())
            ),
            default=1.0,
        )

    def learn(self, concept: str, is_lesson: bool, day: int) -> None:
        if self.world == "S4":
            n = self._learn_n.get(concept, 0)
            self._learn_n[concept] = n + 1
            t = self.bkt["t_lesson"] if is_lesson else self.bkt["t_ex"]
            if self.theta[concept] < 1.0 and keyed_uniform(self.seed, "S4learn", concept, n) < t:
                self.theta[concept] = 1.0
            self.last_day[concept] = day
            return
        th = self.theta[concept] * self.retention(day - self.last_day[concept])
        g = (
            self.profile.lesson_gain if is_lesson else self.profile.exercise_gain
        ) * self.readiness(concept)
        self.theta[concept] = min(0.98, th + g * (1.0 - th))
        self.last_day[concept] = day


def make_learner(engine, seed: int, world: str = "S0", profile: str = "nominal") -> SimLearner:
    """A learner for an engine's curriculum; `world` may be S4-assist09."""
    sim_world, kw = world_spec(world)
    g = engine.graph
    prereqs = {c: g.prerequisites(c) for c in g.concepts()}
    return SimLearner(seed, g.concepts(), PROFILES[profile], sim_world, prereqs, **kw)
