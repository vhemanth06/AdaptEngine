"""Elo / per-concept 1PL IRT measurement model (W8 O.1, D59) behind the MasteryModel interface.

The engine state keeps a number p in (0, 1) per concept; here p = sigmoid(ability) on the logit
scale, so thresholds such as theta = 0.85 keep their meaning as "P(correct) on an item of
difficulty 0.5 is high". Item difficulty d maps to b = logit(d).

  P(correct | p, d) = sigmoid(a * (logit(p) - logit(d)))
  update: ability += K * (y - P(correct)), then the usual learning transition p + (1 - p) T.

Deterministic, standard library only.
"""

import math

from ..core.config import DEFAULT_CONFIG, EngineConfig
from ..core.validators import check_bool, check_probability, check_transition
from .mastery import learn

_EPS = 1e-4


def _logit(x: float) -> float:
    x = min(1.0 - _EPS, max(_EPS, x))
    return math.log(x / (1.0 - x))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


class EloModel:
    def __init__(self, cfg: EngineConfig = DEFAULT_CONFIG):
        self.cfg = cfg

    def predict_correct(self, p: float, d: float) -> float:
        check_probability(p, "p")
        return _sigmoid(self.cfg.elo_a * (_logit(p) - _logit(d)))

    def update(self, p: float, d: float, correct: bool, transition: float) -> float:
        check_probability(p, "p")
        check_bool(correct, "correct")
        check_transition(transition, "transition")
        pc = self.predict_correct(p, d)
        ability = _logit(p) + self.cfg.elo_k * ((1.0 if correct else 0.0) - pc)
        return learn(min(1.0 - _EPS, max(_EPS, _sigmoid(ability))), transition)
