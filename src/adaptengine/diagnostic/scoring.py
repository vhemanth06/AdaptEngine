from ..core.schema import Activity
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..learner.mastery import guess, slip, entropy


def compute_eig(p: float, activity: Activity, cfg: EngineConfig = DEFAULT_CONFIG) -> float:
    """Compute Expected Information Gain (EIG) without the learning transition.

    P_c    = p*(1 - s) + (1 - p)*g
    EIG(a) = H(p) - [ P_c * H(p'_correct) + (1 - P_c) * H(p'_wrong) ]
    """
    d = activity.difficulty
    g = guess(d, cfg)
    s = slip(d, cfg)

    p_c = p * (1.0 - s) + (1.0 - p) * g

    if p_c > 0.0:
        p_correct = (p * (1.0 - s)) / p_c
    else:
        p_correct = 0.0

    if p_c < 1.0:
        p_wrong = (p * s) / (1.0 - p_c)
    else:
        p_wrong = 0.0

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
