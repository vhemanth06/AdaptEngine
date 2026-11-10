"""HLR-lite per-learner half-life (W8 O.2 / D.2; after Settles & Meeder 2016).

h = 2 ** (w0 + w1 * sqrt(1 + n_correct) + w2 * sqrt(1 + n_wrong)) days, from two counts on the
concept. Weights come from EngineConfig.hlr_weights (fitted on even seeds by
experiments/fit_hlr.py). Used only when EngineConfig.half_life_model == "hlr".
"""

import math

from ..core.config import DEFAULT_CONFIG, EngineConfig
from ..learner.state import LearnerConcept

H_MIN, H_MAX = 0.5, 365.0  # days; keeps 2**x finite and recall_at well defined


def hlr_half_life_counts(n_correct: int, n_wrong: int, weights) -> float:
    w0, w1, w2 = weights
    x = w0 + w1 * math.sqrt(1 + n_correct) + w2 * math.sqrt(1 + n_wrong)
    return min(H_MAX, max(H_MIN, 2.0 ** min(x, 20.0)))


def hlr_half_life(concept: LearnerConcept, cfg: EngineConfig = DEFAULT_CONFIG) -> float:
    wrong = concept.responses - concept.correct_responses
    return hlr_half_life_counts(concept.correct_responses, wrong, cfg.hlr_weights)
