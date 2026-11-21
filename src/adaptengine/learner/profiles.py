"""Fitted item-model profiles (Plan 2, F2, D60).

A profile file (config/fitted_*.json, written by the removed experiments/fit_bkt.py, D102) holds guess/slip per D6
difficulty class, plus the fitted prior and learn rate. The engine uses the class guess/slip
through ClassBKT. The profile's prior is never used (the learner prior comes from p0 /
population_p0), and its learn rate only when EngineConfig.use_profile_learn is on.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Mapping, Optional

from ..core.config import EngineConfig, resolve_profile_path
from ..core.errors import ValidationError
from ..core.validators import check_bool, check_probability, check_transition
from .adapter import CustomBKT, MasteryModel, get_difficulty_class

CLASSES = ("easy", "medium", "hard")


def _prob(value, what: str, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError(f"Profile {path}: {what} must be a number, got {value!r}")
    if not 0.0 < value < 1.0:
        raise ValidationError(f"Profile {path}: {what} must be in (0, 1), got {value}")
    return float(value)


@dataclass(frozen=True)
class Profile:
    name: str
    path: str
    sha256: str
    class_params: Mapping[str, Mapping[str, float]]
    t_exercise: Optional[float]
    p0: Optional[float]  # kept for the record only; never used by the engine (D60)
    warnings: Mapping[str, tuple]
    source: str
    code_hash: Optional[str]
    timestamp_utc: Optional[str]

    def provenance(self) -> dict:
        return {
            "profile": self.name,
            "sha256": self.sha256,
            "code_hash": self.code_hash,
            "timestamp_utc": self.timestamp_utc,
        }


def load_profile(path: str) -> Profile:
    """Read and validate a fitted profile file; raise ValidationError if it is malformed."""
    real = resolve_profile_path(path)
    with open(real, "rb") as f:
        raw = f.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Profile {path}: failed to parse json: {e}")
    cp = data.get("class_params") if isinstance(data, dict) else None
    if not isinstance(cp, dict) or any(not isinstance(cp.get(c), dict) for c in CLASSES):
        raise ValidationError(f"Profile {path}: class_params must hold {list(CLASSES)}")
    params = {}
    for c in CLASSES:
        g = _prob(cp[c].get("guess"), f"{c} guess", path)
        s = _prob(cp[c].get("slip"), f"{c} slip", path)
        if g + s >= 1.0:  # an item that knowing makes no likelier to answer right (as old fit_bkt)
            raise ValidationError(f"Profile {path}: {c} guess + slip >= 1")
        params[c] = {"guess": g, "slip": s}
    t = data.get("t_exercise")
    if t is not None and (
        isinstance(t, bool) or not isinstance(t, (int, float)) or not 0.0 <= t < 1.0
    ):
        raise ValidationError(f"Profile {path}: t_exercise must be in [0, 1), got {t!r}")
    return Profile(
        name=str(data.get("profile", path)),
        path=real,
        sha256=hashlib.sha256(raw).hexdigest(),
        class_params=params,
        t_exercise=t,
        p0=data.get("p0"),
        warnings={k: tuple(v) for k, v in data.get("constraint_warnings", {}).items()},
        source=str(data.get("source", "")),
        code_hash=data.get("code_hash"),
        timestamp_utc=data.get("timestamp_utc"),
    )


class ClassBKT:
    """BKT with guess/slip per D6 difficulty class (the maths of PyBKTAdapter, without pyBKT)."""

    def __init__(self, cfg: EngineConfig, class_params: Mapping[str, Mapping[str, float]]):
        self.cfg = cfg
        self.class_params = class_params

    def _gs(self, d: float) -> tuple[float, float]:
        c = self.class_params[get_difficulty_class(d, self.cfg)]
        return c["guess"], c["slip"]

    def predict_correct(self, p: float, d: float) -> float:
        check_probability(p, "p")
        g, s = self._gs(d)
        return p * (1.0 - s) + (1.0 - p) * g

    def update(self, p: float, d: float, correct: bool, transition: float) -> float:
        check_probability(p, "p")
        check_bool(correct, "correct")
        check_transition(transition, "transition")
        g, s = self._gs(d)
        if correct:
            num = p * (1.0 - s)
            den = num + (1.0 - p) * g
        else:
            num = p * s
            den = num + (1.0 - p) * (1.0 - g)
        p_bayes = num / den if den > 0 else 0.0
        return p_bayes + (1.0 - p_bayes) * transition


def profile_config(cfg: EngineConfig) -> EngineConfig:
    """cfg with t_exercise taken from the profile when use_profile_learn is on; else cfg itself."""
    if not cfg.use_profile_learn:
        return cfg
    t = load_profile(cfg.model_profile).t_exercise
    if t is None:
        raise ValidationError(f"Profile {cfg.model_profile} has no t_exercise")
    return dataclasses.replace(cfg, t_exercise=t)


def build_model(cfg: EngineConfig) -> MasteryModel:
    """The engine's one observation model (D33) for cfg.model_profile."""
    if cfg.model_profile == "heuristic":
        return CustomBKT(cfg)
    return ClassBKT(cfg, load_profile(cfg.model_profile).class_params)
