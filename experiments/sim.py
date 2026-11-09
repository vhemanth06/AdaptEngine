"""Closed-loop key-seeded learner simulator (W6 Step 3, W7 T4.2 worlds).

Provides key-seeded deterministic response sampling, 2PL IRT response dynamics,
power-law memory decay, and activity learning gains across four simulated profiles.

Worlds (W7 T4.2, pre-registered in docs/EVALUATION_PROTOCOL.md §W7):
  S0  independent abilities U(0.1, 0.9), unconditional gains, no forgetting unless the profile
      has it (W6 baseline, the default: byte-identical to W6).
  S1  S0 + gains x readiness, readiness = min over direct prerequisites of
      sigmoid(READINESS_K * (theta_pre - READINESS_MID)).
  S2  correlated abilities: g ~ U(0.2, 0.8), theta_c = clip(g + N(0, 0.10), 0.05, 0.95).
  S3  S0 + forgetting for every profile, per-learner half-life ~ U(5, 30) days (unless the
      profile sets its own).
  S4  BKT-generated responses: binary latent mastery (initial P = S4_P0), P(correct) =
      1 - s(d) if mastered else g(d) with the engine's g/s heuristics, learning transitions
      T_lesson / T_ex. theta is 1.0 (mastered) or 0.0, so TRUE_MASTERY_CUTOFF still applies.
      Optional bkt_params override; `s4_fitted_params(profile)` gives the S4-fitted world
      (class guess/slip, prior and learn from a fitted profile such as fitted_assist09, T7.5;
      lessons keep T_lesson = 0.20 because the fits have no lesson events).
Never imported from src/.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

TRUE_MASTERY_CUTOFF = (
    0.70  # Synthetic heuristic definition of "really knows it"; documented as such
)
WORLDS = ("S0", "S1", "S2", "S3", "S4")
READINESS_K = 10.0  # synthetic assumption (T4.3)
READINESS_MID = 0.70  # = TRUE_MASTERY_CUTOFF
S3_HALF_LIFE_RANGE = (5.0, 30.0)  # days; synthetic assumption (T4.3)
S4_P0 = 0.20  # = engine p0: the well-specified world
# Engine heuristics (core/constants.py): g(d) = 0.30 (1 - d), s(d) = 0.05 + 0.25 d
S4_DEFAULT_BKT = {
    "guess_coef": 0.30,
    "slip_base": 0.05,
    "slip_coef": 0.25,
    "t_lesson": 0.20,
    "t_ex": 0.05,
}


def keyed_uniform(*key: object) -> float:
    """Generate a deterministic uniform float in [0, 1) derived strictly from key values."""
    return random.Random("|".join(str(k) for k in key)).random()


@dataclass(frozen=True)
class SimProfile:
    name: str
    a: float = 3.0  # 2PL discrimination parameter
    slip: float = 0.0  # P(wrong | would have been right)
    lesson_gain: float = 0.18
    exercise_gain: float = 0.05
    forget_half_life: Optional[float] = None  # Days; None = no forgetting


PROFILES: Mapping[str, SimProfile] = {
    "nominal": SimProfile("nominal"),
    "high_slip": SimProfile("high_slip", slip=0.15),
    "fast_forgetter": SimProfile("fast_forgetter", forget_half_life=7.0),
    "rapid_learner": SimProfile("rapid_learner", lesson_gain=0.30, exercise_gain=0.10),
}


class SimLearner:
    """Simulated learner with hidden true latent mastery theta for each concept."""

    def __init__(
        self,
        seed: int,
        concepts: Iterable[str],
        profile: SimProfile,
        world: str = "S0",
        prereqs: Optional[Mapping[str, Iterable[str]]] = None,
        bkt_params: Optional[Mapping[str, object]] = None,
    ):
        if world not in WORLDS:
            raise ValueError(f"Unknown world {world!r}; expected one of {WORLDS}")
        if world == "S1" and prereqs is None:
            raise ValueError("World S1 needs the curriculum prerequisites")
        self.seed = seed
        self.profile = profile
        self.world = world
        self.prereqs = {c: tuple(v) for c, v in (prereqs or {}).items()}
        self.bkt = dict(S4_DEFAULT_BKT, **(bkt_params or {}))
        r = random.Random(f"{seed}|truth")
        self.theta: dict[str, float] = {
            c: round(r.uniform(0.10, 0.90), 4) for c in sorted(concepts)
        }
        if world == "S2":
            r2 = random.Random(f"{seed}|S2")
            g = r2.uniform(0.2, 0.8)
            self.theta = {
                c: round(min(0.95, max(0.05, g + r2.gauss(0.0, 0.10))), 4) for c in sorted(concepts)
            }
        elif world == "S4":
            self.theta = {
                c: 1.0
                if keyed_uniform(seed, "S4init", c) < float(self.bkt.get("p0", S4_P0))
                else 0.0
                for c in sorted(concepts)
            }
        self.half_life = profile.forget_half_life
        if world == "S3" and self.half_life is None:
            self.half_life = round(random.Random(f"{seed}|S3h").uniform(*S3_HALF_LIFE_RANGE), 3)
        self.initial: dict[str, float] = dict(self.theta)
        self.last_day: dict[str, int] = {c: 1 for c in concepts}
        self._n: dict[tuple[str, str, str], int] = {}
        self._learn_n: dict[str, int] = {}

    def _retention(self, dt: int | float) -> float:
        h = self.half_life
        # Power law: deliberately a different family from the planner's 2**(-dt/h)
        return 1.0 if h is None or self.world == "S4" else 1.0 / (1.0 + max(0.0, float(dt)) / h)

    def settle(self, day: int) -> None:
        """Settle memory decay across all concepts up to the specified calendar day."""
        for c in self.theta:
            self.theta[c] *= self._retention(day - self.last_day[c])
            self.last_day[c] = day

    def p_correct(self, concept: str, difficulty: float) -> float:
        """True probability of a correct answer (before the high-slip profile's extra slips)."""
        if self.world == "S4":
            b = self.bkt
            if "class_params" in b:  # S4-fitted (T7.5): guess/slip per engine D6 class
                cp = b["class_params"][_d6_class(difficulty)]
                return 1.0 - cp["slip"] if self.theta[concept] >= 1.0 else cp["guess"]
            if self.theta[concept] >= 1.0:
                return 1.0 - (b["slip_base"] + b["slip_coef"] * difficulty)
            return b["guess_coef"] * (1.0 - difficulty)
        logit = max(-10.0, min(10.0, self.profile.a * (self.theta[concept] - difficulty)))
        return 1.0 / (1.0 + math.exp(-logit))

    def respond(self, concept: str, activity_id: str, difficulty: float, tag: str = "run") -> bool:
        """Sample a deterministic binary response to an item based on true theta and difficulty."""
        k = (concept, activity_id, tag)
        n = self._n.get(k, 0)
        self._n[k] = n + 1
        correct = keyed_uniform(self.seed, tag, activity_id, n) < self.p_correct(
            concept, difficulty
        )
        if (
            correct
            and self.profile.slip > 0.0
            and keyed_uniform(self.seed, "slip", activity_id, n) < self.profile.slip
        ):
            correct = False
        return correct

    def readiness(self, concept: str) -> float:
        """S1: min over direct prerequisites of sigmoid(K (theta_pre - MID)); 1.0 elsewhere."""
        if self.world != "S1":
            return 1.0
        pre = self.prereqs.get(concept, ())
        return min(
            (1.0 / (1.0 + math.exp(-READINESS_K * (self.theta[q] - READINESS_MID))) for q in pre),
            default=1.0,
        )

    def apply_activity(self, concept: str, is_lesson: bool, day: int) -> None:
        """Update hidden theta after participating in an activity."""
        if self.world == "S4":
            n = self._learn_n.get(concept, 0)
            self._learn_n[concept] = n + 1
            t = self.bkt["t_lesson"] if is_lesson else self.bkt["t_ex"]
            if self.theta[concept] < 1.0 and keyed_uniform(self.seed, "S4learn", concept, n) < t:
                self.theta[concept] = 1.0
            self.last_day[concept] = day
            return
        self.theta[concept] *= self._retention(day - self.last_day[concept])
        g = self.profile.lesson_gain if is_lesson else self.profile.exercise_gain
        g *= self.readiness(concept)
        self.theta[concept] = min(0.98, self.theta[concept] + g * (1.0 - self.theta[concept]))
        self.last_day[concept] = day


def _d6_class(d: float) -> str:
    """Engine D6 difficulty classes (learner/adapter.get_difficulty_class boundaries)."""
    return "easy" if d < 0.35 else "medium" if d < 0.65 else "hard"


def s4_fitted_params(profile_path: str) -> dict:
    """bkt_params for an S4 world driven by a fitted config profile (e.g. fitted_assist09)."""
    import json

    prof = json.load(open(profile_path, encoding="utf-8"))
    return {
        "p0": prof["p0"],
        "t_ex": prof["t_exercise"],
        "class_params": prof["class_params"],
    }


def make_sim(engine, seed: int, profile: SimProfile, world: str = "S0", **kw) -> SimLearner:
    """SimLearner for an engine's curriculum (passes prerequisites for S1)."""
    g = engine.graph
    prereqs = {c: g.prerequisites(c) for c in g.concepts()}
    return SimLearner(seed, g.concepts(), profile, world=world, prereqs=prereqs, **kw)
