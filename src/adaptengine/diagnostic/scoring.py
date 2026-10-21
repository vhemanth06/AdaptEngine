from typing import Optional
from ..core.schema import Activity
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..learner.mastery import entropy
from ..learner.adapter import MasteryModel, CustomBKT


def compute_eig(
    p: float,
    activity: Activity,
    cfg: EngineConfig = DEFAULT_CONFIG,
    model: Optional[MasteryModel] = None,
) -> float:
    """Compute Expected Information Gain (EIG) entirely through the MasteryModel protocol.

    P_c    = model.predict_correct(p, d)
    EIG(a) = H(p) - [ P_c * H(p'_correct) + (1 - P_c) * H(p'_wrong) ]
    where p'_correct = model.update(p, d, True, 0.0) and p'_wrong = model.update(p, d, False, 0.0).
    """
    if model is None:
        model = CustomBKT(cfg)

    d = activity.difficulty
    p_c = model.predict_correct(p, d)
    p_correct = model.update(p, d, True, 0.0)
    p_wrong = model.update(p, d, False, 0.0)

    h_prior = entropy(p)
    h_expected_posterior = p_c * entropy(p_correct) + (1.0 - p_c) * entropy(p_wrong)
    eig = h_prior - h_expected_posterior

    # Numerical safeguard: EIG is mathematically non-negative
    return max(0.0, eig)


def candidate_sort_key(eig: float, difficulty: float, activity_id: str) -> tuple[float, float, str]:
    """Deterministic selection sort key (D10):
    1. Maximize EIG (rounded to 9 decimals for stable float comparison)
    2. Minimize |d - 0.5|
    3. Lexicographic activity_id
    """
    return (-round(eig, 9), round(abs(difficulty - 0.5), 9), activity_id)
