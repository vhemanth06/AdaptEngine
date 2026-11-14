"""Named learner-model profiles (W8 B.1, D48): JSON files in config/ loaded into EngineConfig.

A profile sets p0, t_exercise, optionally t_lesson and forget, and guess/slip per D6 difficulty
class. "w7_default" is the built-in W7 configuration (the D6 heuristics), so loading it gives
bit-identical plans. Extra keyword overrides (e.g. theta, k_responses, W8 flags) are applied on
top. Validation: guess + slip < 1 per class, 0 < T < 1, all values finite (EngineConfig checks
the rest).
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import replace
from typing import Any

from .config import DEFAULT_CONFIG, EngineConfig
from .errors import ValidationError

DEFAULT_PROFILE = "w7_default"
CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "config"))


def profile_path(name: str, config_dir: str = CONFIG_DIR) -> str:
    if name.endswith(".json") or os.sep in name:
        return name
    return os.path.join(config_dir, f"{name}.json")


def _transition(v: Any, name: str) -> float:
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
        raise ValidationError(f"profile {name} must be a finite number, got {v!r}")
    if not 0.0 < v < 1.0:
        raise ValidationError(f"profile {name} must be in (0, 1), got {v}")
    return float(v)


def profile_config(data: dict, base: EngineConfig = DEFAULT_CONFIG, **overrides) -> EngineConfig:
    """EngineConfig from a profile dict (the JSON content)."""
    try:
        cp = data["class_params"]
        class_params = tuple(
            (k, float(cp[k]["guess"]), float(cp[k]["slip"])) for k in ("easy", "medium", "hard")
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ValidationError(f"profile needs class_params easy/medium/hard guess/slip: {e}")
    fields: dict[str, Any] = {
        "profile": str(data.get("name", "custom")),
        "class_params": class_params,
        "p0": _transition(data["p0"], "p0") if "p0" in data else base.p0,
        "t_exercise": _transition(data["t_exercise"], "t_exercise"),
    }
    if "t_lesson" in data:
        fields["t_lesson"] = _transition(data["t_lesson"], "t_lesson")
    if data.get("forget"):
        fields["forget"] = _transition(data["forget"], "forget")
    return replace(base, **{**fields, **overrides})  # EngineConfig re-validates


def load_profile(name: str = DEFAULT_PROFILE, config_dir: str = CONFIG_DIR, **overrides):
    """EngineConfig for a named profile (config/<name>.json) or a path; overrides on top."""
    if name == DEFAULT_PROFILE:
        return replace(DEFAULT_CONFIG, **overrides) if overrides else DEFAULT_CONFIG
    path = profile_path(name, config_dir)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise ValidationError(f"unknown profile {name!r}: {e}")
    data.setdefault("name", os.path.splitext(os.path.basename(path))[0])
    return profile_config(data, **overrides)


def list_profiles(config_dir: str = CONFIG_DIR) -> list[str]:
    names = [DEFAULT_PROFILE]
    if os.path.isdir(config_dir):
        names += sorted(
            f[:-5]
            for f in os.listdir(config_dir)
            if f.endswith(".json") and not f.startswith("policy_")
        )
    return names


STRICT_MASTERY = {"theta": 0.95, "k_responses": 1, "horizon_aware_mastery": False}
GOAL_SEARCH_DIAGNOSTIC = {
    "selection_scope": "goal_search",
    "concept_cap": 4,
    "n_max": 25,
    "diag_budget_min": 12,
    "diag_budget_per_concept": 1.0,
}
PRODUCT_OVERRIDES = {
    **STRICT_MASTERY,
    **GOAL_SEARCH_DIAGNOSTIC,
    "consolidation": True,
    "verification_probe": True,
    "feasibility_warning": True,
    "diagnostic_scope": "goal_path",  # only the goal and its prerequisites are worth asking about
}
PRODUCT_PROFILE = "fitted_S1"


def product_config(profile: str = PRODUCT_PROFILE) -> EngineConfig:
    """The product preset: strict mastery + goal-search diagnostic on any learner profile."""
    return load_profile(profile, **PRODUCT_OVERRIDES)
