import math
from typing import Any
from .errors import ValidationError


def check_bool(value: Any, name: str) -> bool:
    """Strict boolean check. Rejects 'false', 'true', 0, 1, etc."""
    if type(value) is not bool:
        raise ValidationError(f"{name} must be a boolean, got {type(value).__name__}: {value!r}")
    return value


def check_probability(value: Any, name: str) -> float:
    """Check that value is a finite float in [0.0, 1.0]."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(
            f"{name} must be a numeric probability, got {type(value).__name__}: {value!r}"
        )
    val_float = float(value)
    if not math.isfinite(val_float) or not (0.0 <= val_float <= 1.0):
        raise ValidationError(f"{name} must be a finite probability in [0, 1], got {value}")
    return val_float


def check_transition(value: Any, name: str) -> float:
    """Check transition rate T in [0.0, 1.0]."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(
            f"{name} must be a numeric transition rate, got {type(value).__name__}: {value!r}"
        )
    val_float = float(value)
    if not math.isfinite(val_float) or not (0.0 <= val_float <= 1.0):
        raise ValidationError(f"{name} must be in [0, 1], got {value}")
    return val_float


def check_difficulty(value: Any, d_min: float, d_max: float, name: str = "difficulty") -> float:
    """Check difficulty d in [d_min, d_max]."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(
            f"{name} must be a numeric difficulty, got {type(value).__name__}: {value!r}"
        )
    val_float = float(value)
    if not math.isfinite(val_float) or not (d_min <= val_float <= d_max):
        raise ValidationError(f"{name} must be in [{d_min}, {d_max}], got {value}")
    return val_float


def check_non_negative_int(value: Any, name: str) -> int:
    """Check integer >= 0."""
    if type(value) is not int or value < 0:
        raise ValidationError(f"{name} must be a non-negative integer, got {value!r}")
    return value


def check_positive_int(value: Any, name: str) -> int:
    """Check integer >= 1."""
    if type(value) is not int or value < 1:
        raise ValidationError(f"{name} must be a positive integer >= 1, got {value!r}")
    return value


def check_finite_positive_float(value: Any, name: str) -> float:
    """Check finite float > 0."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(
            f"{name} must be a numeric value, got {type(value).__name__}: {value!r}"
        )
    val_float = float(value)
    if not math.isfinite(val_float) or val_float <= 0.0:
        raise ValidationError(f"{name} must be a finite float > 0, got {value}")
    return val_float


def check_valid_id(value: Any, name: str) -> str:
    """Check non-empty string without whitespace."""
    if not isinstance(value, str) or not value.strip() or any(c.isspace() for c in value):
        raise ValidationError(f"{name} must be a non-empty string without spaces, got {value!r}")
    return value
