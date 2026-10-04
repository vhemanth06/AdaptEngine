import math
from ..core.errors import ValidationError
from ..core.config import DEFAULT_CONFIG
from ..core.constants import D_MIN, D_MAX

def guess(d, cfg=DEFAULT_CONFIG) -> float:
    if not (D_MIN <= d <= D_MAX):
        raise ValidationError(f"Invalid d: {d}")
    return cfg.guess_coef * (1 - d)

def slip(d, cfg=DEFAULT_CONFIG) -> float:
    if not (D_MIN <= d <= D_MAX):
        raise ValidationError(f"Invalid d: {d}")
    return cfg.slip_base + cfg.slip_coef * d

def bayes_update(p, d, correct, cfg=DEFAULT_CONFIG) -> float:
    if not (0.0 <= p <= 1.0):
        raise ValidationError(f"Invalid p: {p}")
    g = guess(d, cfg)
    s = slip(d, cfg)
    if correct:
        num = p * (1 - s)
        den = num + (1 - p) * g
    else:
        num = p * s
        den = num + (1 - p) * (1 - g)
    return num / den if den > 0 else 0.0

def learn(p, T) -> float:
    if not (0.0 <= p <= 1.0):
        raise ValidationError(f"Invalid p: {p}")
    if T < 0.0:
        raise ValidationError(f"Invalid T: {T}")
    return p + (1 - p) * T

def update_mastery(p, d, correct, T, cfg=DEFAULT_CONFIG) -> float:
    p_bayes = bayes_update(p, d, correct, cfg)
    return learn(p_bayes, T)

def entropy(p) -> float:
    if not (0.0 <= p <= 1.0):
        raise ValidationError(f"Invalid p: {p}")
    if p == 0.0 or p == 1.0:
        return 0.0
    return - (p * math.log2(p) + (1 - p) * math.log2(1 - p))
