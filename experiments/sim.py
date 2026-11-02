"""Closed-loop key-seeded learner simulator (W6 Step 3).

Provides key-seeded deterministic response sampling, 2PL IRT response dynamics,
power-law memory decay, and activity learning gains across four simulated profiles.
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

    def __init__(self, seed: int, concepts: Iterable[str], profile: SimProfile):
        self.seed = seed
        self.profile = profile
        r = random.Random(f"{seed}|truth")
        self.theta: dict[str, float] = {
            c: round(r.uniform(0.10, 0.90), 4) for c in sorted(concepts)
        }
        self.initial: dict[str, float] = dict(self.theta)
        self.last_day: dict[str, int] = {c: 1 for c in concepts}
        self._n: dict[tuple[str, str, str], int] = {}

    def _retention(self, dt: int | float) -> float:
        h = self.profile.forget_half_life
        # Power law: deliberately a different family from the planner's 2**(-dt/h)
        return 1.0 if h is None else 1.0 / (1.0 + max(0.0, float(dt)) / h)

    def settle(self, day: int) -> None:
        """Settle memory decay across all concepts up to the specified calendar day."""
        for c in self.theta:
            self.theta[c] *= self._retention(day - self.last_day[c])
            self.last_day[c] = day

    def respond(self, concept: str, activity_id: str, difficulty: float, tag: str = "run") -> bool:
        """Sample a deterministic binary response to an item based on true theta and difficulty."""
        k = (concept, activity_id, tag)
        n = self._n.get(k, 0)
        self._n[k] = n + 1
        logit = max(-10.0, min(10.0, self.profile.a * (self.theta[concept] - difficulty)))
        p_success = 1.0 / (1.0 + math.exp(-logit))
        correct = keyed_uniform(self.seed, tag, activity_id, n) < p_success
        if (
            correct
            and self.profile.slip > 0.0
            and keyed_uniform(self.seed, "slip", activity_id, n) < self.profile.slip
        ):
            correct = False
        return correct

    def apply_activity(self, concept: str, is_lesson: bool, day: int) -> None:
        """Update hidden theta after participating in an activity."""
        self.theta[concept] *= self._retention(day - self.last_day[concept])
        g = self.profile.lesson_gain if is_lesson else self.profile.exercise_gain
        self.theta[concept] = min(0.98, self.theta[concept] + g * (1.0 - self.theta[concept]))
        self.last_day[concept] = day
