import math
from ..core.errors import ValidationError
from ..core.config import DEFAULT_CONFIG, EngineConfig
from ..core.validators import check_probability, check_transition, check_bool


def guess(d: float, cfg: EngineConfig = DEFAULT_CONFIG) -> float:
    """Calculate probability of guessing correctly given item difficulty d.

    g(d) = guess_coef * (1 - d)
    """
    if not isinstance(d, (int, float)) or isinstance(d, bool) or not math.isfinite(d):
        raise ValidationError(f"Invalid d: {d}")
    if not (cfg.d_min <= d <= cfg.d_max):
        raise ValidationError(f"Difficulty {d} outside [{cfg.d_min}, {cfg.d_max}]")
    return cfg.guess_coef * (1.0 - d)


def slip(d: float, cfg: EngineConfig = DEFAULT_CONFIG) -> float:
    """Calculate probability of slipping given item difficulty d.

    s(d) = slip_base + slip_coef * d
    """
    if not isinstance(d, (int, float)) or isinstance(d, bool) or not math.isfinite(d):
        raise ValidationError(f"Invalid d: {d}")
    if not (cfg.d_min <= d <= cfg.d_max):
        raise ValidationError(f"Difficulty {d} outside [{cfg.d_min}, {cfg.d_max}]")
    return cfg.slip_base + cfg.slip_coef * d


def bayes_update(p: float, d: float, correct: bool, cfg: EngineConfig = DEFAULT_CONFIG) -> float:
    """Bayesian update of prior mastery probability p after observing response on item of difficulty d.

    P_c = p*(1 - s) + (1 - p)*g
    If correct: p' = p*(1 - s) / P_c
    If wrong:   p' = p*s / (1 - P_c)
    """
    check_bool(correct, "correct")
    p_val = check_probability(p, "p")
    g = guess(d, cfg)
    s = slip(d, cfg)
    if correct:
        num = p_val * (1.0 - s)
        den = num + (1.0 - p_val) * g
    else:
        num = p_val * s
        den = num + (1.0 - p_val) * (1.0 - g)
    return num / den if den > 0 else 0.0


def learn(p: float, T: float) -> float:
    """Apply transition learning probability T to prior mastery p.

    p'' = p' + (1 - p') * T
    Requires T in [0.0, 1.0].
    """
    p_val = check_probability(p, "p")
    t_val = check_transition(T, "T")
    return p_val + (1.0 - p_val) * t_val


def update_mastery(
    p: float, d: float, correct: bool, T: float, cfg: EngineConfig = DEFAULT_CONFIG
) -> float:
    """Full BKT step: Bayesian observation update followed by learning transition."""
    p_bayes = bayes_update(p, d, correct, cfg)
    return learn(p_bayes, T)


def entropy(p: float) -> float:
    """Binary Shannon entropy H(p) = -p log2(p) - (1-p) log2(1-p).

    Note on Entropy Interpretation:
    H(p) measures uncertainty about a *binary latent mastery state* (whether the learner
    is currently in the mastered state or unmastered state). It is NOT confidence in a
    parameter estimate, and it does NOT monotonically shrink merely because evidence accumulates.
    In fact, entropy can rise after a surprising response (e.g. p=0.9, d=0.5, incorrect
    leads to p'=0.6495, causing H to jump from ~0.469 to ~0.935).
    """
    p_val = check_probability(p, "p")
    if p_val == 0.0 or p_val == 1.0:
        return 0.0
    return -(p_val * math.log2(p_val) + (1.0 - p_val) * math.log2(1.0 - p_val))
