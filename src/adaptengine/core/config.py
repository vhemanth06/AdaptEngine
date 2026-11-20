import json
import hashlib
import math
import os
from dataclasses import asdict, dataclass, fields, replace
from typing import Optional
from . import constants
from .errors import ValidationError
from .validators import check_bool, check_positive_int


@dataclass(frozen=True)
class EngineConfig:
    p0: float = constants.P0
    theta: float = constants.THETA
    t_diag: float = constants.T_DIAG
    t_exercise: float = constants.T_EXERCISE
    t_lesson: float = constants.T_LESSON
    guess_coef: float = constants.GUESS_COEF
    slip_base: float = constants.SLIP_BASE
    slip_coef: float = constants.SLIP_COEF
    d_min: float = constants.D_MIN
    d_max: float = constants.D_MAX
    # M2 Diagnostic settings
    n_max: int = 6  # W7 T3.3 pre-registered selection (W6: 8)
    concept_cap: int = 2  # W7 T3.3 pre-registered selection (W6: 3)
    h_stop: float = 0.50
    k_responses: int = 2
    skip_threshold: float = 0.40
    # W7 T3.2 diagnostic options; defaults set by the pre-registered T3.3 rule
    # (experiments/results/w7_diag_selection.json). W6 behaviour: prior_mode="flat",
    # concept_cap=3, n_max=8, other flags as below. D59: default prior_mode is "flat"
    # (sweep prior = p0 = 0.20); population_prior_config() restores the population prior 0.24.
    min_items_per_concept: int = 1  # responses required before an entropy stop
    pruning_mode: str = "hard"  # "hard" skip | "soft" cap descendants' prior | "none"
    selection_scope: str = "concept_sweep"  # "concept_sweep" | "frontier" (global EIG)
    prior_mode: str = "flat"  # "flat" (state p, D59) | "population" (population_p0)
    population_p0: float = 0.24  # S0 tuning-cohort base rate of 1[theta >= 0.70]
    # M3/M4 Planner settings
    target_success: float = 0.75
    w_review: float = 1.0
    w_unlock: float = 1.0
    w_fit: float = 1.0
    allowed_budgets: tuple[int, ...] = (5, 10, 15, 30)
    oracle_node_limit: int = 1000
    # W7 WP2 planner settings
    allow_exercise_repeats: bool = True  # D41: least-recently-seen repeats in new learning
    projection_mode: str = "optimistic"  # T2.5: "optimistic" | "expected"
    maintenance_reviews: bool = True  # D43: keep scheduling due reviews until deadline_day
    # M5/M6 Review & Remediation settings
    recall_threshold: float = 0.80
    remediation_threshold: float = 0.40
    half_life_growth: float = 1.0
    half_life_days: float = 30.0  # D43: planner's initial memory half-life (days)
    # T5.4 mastery criterion: "bkt_threshold" (p >= theta and responses >= k; D4),
    # "n_consecutive" (last n_consecutive responses correct), "two_threshold"
    # (bkt_threshold and H(p) <= certainty_max_entropy: knowledge level and certainty)
    mastery_criterion: str = "bkt_threshold"
    n_consecutive: int = 3
    certainty_max_entropy: float = 0.5
    # F2 item model (Plan 2, D60): "heuristic" (D6 g(d), s(d)) or a path to config/fitted_*.json
    # (class guess/slip; the profile's prior is never used). use_profile_learn takes t_exercise
    # from the profile as well.
    model_profile: str = "heuristic"
    use_profile_learn: bool = False
    # F1 (Plan 3, D49-D57): bisection diagnostic over prerequisite-closed knowledge states and the
    # planner's confirmation path. Defaults keep the sweep and D4 unchanged.
    diagnostic_method: str = "sweep"  # "sweep" | "bisection" (D49)
    bisection_prior: str = "uniform_states"  # "uniform_states" (D51) | "independent_p0" (arm)
    bisection_scope: str = "goal_ancestors"  # "goal_ancestors" | "all" (D54)
    bisection_exact_state_limit: int = 5000  # exact enumeration up to this many states (D53)
    bisection_samples: int = 4000  # weighted sample states in sampling mode
    bisection_seed: int = 0
    bisection_stop_confidence: float = 0.80  # top-state posterior that ends the run (D55)
    bisection_n_min: int = 6  # budget floor (D56)
    bisection_n_ceiling: int = 40  # budget ceiling (D56)
    bisection_alpha: Optional[float] = None  # questions-per-bit override (D56); None = from model
    bisection_concept_cap: int = 3
    confirm_diag_confident: bool = False  # planner confirmation path (D57)
    confirm_epsilon: float = 0.02  # acceptable false-confirm rate: confirm at 1 - epsilon
    confirm_max_checks: int = 3
    confirm_min_direct: int = 1

    def __post_init__(self):
        if not (0.0 < self.d_min < self.d_max < 1.0):
            raise ValidationError(
                f"Invalid difficulty bounds: 0 < d_min < d_max < 1 required, got {self.d_min}, {self.d_max}"
            )
        if not (0.0 <= self.p0 <= 1.0) or not math.isfinite(self.p0):
            raise ValidationError(f"Invalid p0: {self.p0}")
        if not (0.0 < self.theta <= 1.0) or not math.isfinite(self.theta):
            raise ValidationError(f"Invalid theta: {self.theta}")
        for name, t in [
            ("t_diag", self.t_diag),
            ("t_exercise", self.t_exercise),
            ("t_lesson", self.t_lesson),
        ]:
            if not (0.0 <= t <= 1.0) or not math.isfinite(t):
                raise ValidationError(f"Invalid {name}: {t}")

        for d in (self.d_min, self.d_max):
            g = self.guess_coef * (1.0 - d)
            s = self.slip_base + self.slip_coef * d
            if not (0.0 < g < 1.0):
                raise ValidationError(f"guess({d}) = {g} not in (0, 1)")
            if not (0.0 < s < 1.0):
                raise ValidationError(f"slip({d}) = {s} not in (0, 1)")

        check_positive_int(self.n_max, "n_max")
        check_positive_int(self.concept_cap, "concept_cap")
        if not (0.0 <= self.h_stop <= 1.0) or not math.isfinite(self.h_stop):
            raise ValidationError(f"h_stop must be in [0, 1], got {self.h_stop}")
        check_positive_int(self.k_responses, "k_responses")
        if not (0.0 <= self.skip_threshold <= 1.0) or not math.isfinite(self.skip_threshold):
            raise ValidationError(f"skip_threshold must be in [0, 1], got {self.skip_threshold}")
        check_positive_int(self.min_items_per_concept, "min_items_per_concept")
        for name, val, allowed in (
            ("pruning_mode", self.pruning_mode, ("hard", "soft", "none")),
            ("selection_scope", self.selection_scope, ("concept_sweep", "frontier")),
            ("prior_mode", self.prior_mode, ("flat", "population")),
        ):
            if val not in allowed:
                raise ValidationError(f"{name} must be one of {allowed}, got {val!r}")
        if not (0.0 < self.population_p0 < 1.0) or not math.isfinite(self.population_p0):
            raise ValidationError(f"population_p0 must be in (0, 1), got {self.population_p0}")

        if not (0.0 < self.target_success < 1.0) or not math.isfinite(self.target_success):
            raise ValidationError(f"target_success must be in (0, 1), got {self.target_success}")
        for w_name, w_val in [
            ("w_review", self.w_review),
            ("w_unlock", self.w_unlock),
            ("w_fit", self.w_fit),
        ]:
            if (
                not isinstance(w_val, (int, float))
                or isinstance(w_val, bool)
                or not math.isfinite(w_val)
                or w_val < 0.0
            ):
                raise ValidationError(f"{w_name} must be finite non-negative float, got {w_val}")

        if not isinstance(self.allowed_budgets, (tuple, list)) or not self.allowed_budgets:
            raise ValidationError(
                f"allowed_budgets must be a non-empty sequence, got {self.allowed_budgets}"
            )
        for b in self.allowed_budgets:
            check_positive_int(b, "allowed_budgets element")

        check_positive_int(self.oracle_node_limit, "oracle_node_limit")
        check_bool(self.allow_exercise_repeats, "allow_exercise_repeats")
        check_bool(self.maintenance_reviews, "maintenance_reviews")
        if self.mastery_criterion not in ("bkt_threshold", "n_consecutive", "two_threshold"):
            raise ValidationError(f"Unknown mastery_criterion {self.mastery_criterion!r}")
        check_positive_int(self.n_consecutive, "n_consecutive")
        if not (0.0 < self.certainty_max_entropy <= 1.0):
            raise ValidationError(
                f"certainty_max_entropy must be in (0, 1], got {self.certainty_max_entropy}"
            )
        if self.projection_mode not in ("optimistic", "expected"):
            raise ValidationError(
                f"projection_mode must be 'optimistic' or 'expected', got {self.projection_mode!r}"
            )
        if (
            not isinstance(self.half_life_days, (int, float))
            or isinstance(self.half_life_days, bool)
            or not math.isfinite(self.half_life_days)
            or self.half_life_days <= 0.0
        ):
            raise ValidationError(f"half_life_days must be finite > 0, got {self.half_life_days}")

        if not (0.0 < self.recall_threshold <= 1.0) or not math.isfinite(self.recall_threshold):
            raise ValidationError(
                f"recall_threshold must be in (0, 1], got {self.recall_threshold}"
            )
        if not (0.0 < self.remediation_threshold <= 1.0) or not math.isfinite(
            self.remediation_threshold
        ):
            raise ValidationError(
                f"remediation_threshold must be in (0, 1], got {self.remediation_threshold}"
            )
        for name, val, allowed in (
            ("diagnostic_method", self.diagnostic_method, ("sweep", "bisection")),
            ("bisection_prior", self.bisection_prior, ("uniform_states", "independent_p0")),
            ("bisection_scope", self.bisection_scope, ("goal_ancestors", "all")),
        ):
            if val not in allowed:
                raise ValidationError(f"{name} must be one of {allowed}, got {val!r}")
        for name in (
            "bisection_exact_state_limit",
            "bisection_samples",
            "bisection_n_min",
            "bisection_n_ceiling",
            "bisection_concept_cap",
            "confirm_max_checks",
            "confirm_min_direct",
        ):
            check_positive_int(getattr(self, name), name)
        if isinstance(self.bisection_seed, bool) or not isinstance(self.bisection_seed, int):
            raise ValidationError(f"bisection_seed must be an int, got {self.bisection_seed!r}")
        if self.bisection_n_min > self.bisection_n_ceiling:
            raise ValidationError("bisection_n_min must not exceed bisection_n_ceiling")
        for name in ("bisection_stop_confidence", "confirm_epsilon"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.0 < v < 1.0:
                raise ValidationError(f"{name} must be in (0, 1), got {v!r}")
        a = self.bisection_alpha
        if a is not None and (
            isinstance(a, bool) or not isinstance(a, (int, float)) or not math.isfinite(a) or a <= 0
        ):
            raise ValidationError(f"bisection_alpha must be None or a finite number > 0, got {a!r}")
        check_bool(self.confirm_diag_confident, "confirm_diag_confident")
        if not isinstance(self.model_profile, str) or not self.model_profile:
            raise ValidationError(
                f"model_profile must be a non-empty string, got {self.model_profile!r}"
            )
        if self.model_profile != "heuristic":
            resolve_profile_path(self.model_profile)
        check_bool(self.use_profile_learn, "use_profile_learn")
        if self.use_profile_learn and self.model_profile == "heuristic":
            raise ValidationError("use_profile_learn needs a fitted model_profile")
        if not (0.0 < self.half_life_growth <= 10.0) or not math.isfinite(self.half_life_growth):
            raise ValidationError(
                f"half_life_growth must be finite in (0, 10], got {self.half_life_growth}"
            )


_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def bisection_config(**overrides) -> EngineConfig:
    """F1 preset (Plan 3): bisection diagnostic with the planner confirmation path on."""
    return replace(
        EngineConfig(diagnostic_method="bisection", confirm_diag_confident=True), **overrides
    )


def resolve_profile_path(path: str) -> str:
    """Absolute path of a model_profile file: as given (cwd-relative), else from the repo root."""
    for candidate in (path, os.path.join(_REPO_ROOT, path)):
        if os.path.isfile(candidate) and os.access(candidate, os.R_OK):
            return os.path.abspath(candidate)
    raise ValidationError(f"model_profile file not found or not readable: {path!r}")


DEFAULT_CONFIG = EngineConfig()


def population_prior_config() -> EngineConfig:
    """Defaults with the population sweep prior: population_p0 = 0.24 (the D44 default before D59)."""
    return EngineConfig(prior_mode="population", population_p0=0.24)


def config_from_file(path: str, base: EngineConfig = DEFAULT_CONFIG) -> EngineConfig:
    """base with the EngineConfig field overrides in a JSON object file (Plan 2.5, D89).

    Unknown keys are rejected; every value is validated by EngineConfig.__post_init__. JSON lists
    become tuples for tuple fields (e.g. allowed_budgets).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise ValidationError(f"Cannot read config file {path}: {e}")
    except json.JSONDecodeError as e:
        raise ValidationError(f"Config file {path}: invalid JSON: {e}")
    if not isinstance(data, dict):
        raise ValidationError(f"Config file {path}: must hold a JSON object of EngineConfig fields")
    names = {f.name: f for f in fields(EngineConfig)}
    unknown = sorted(set(data) - set(names))
    if unknown:
        raise ValidationError(
            f"Config file {path}: unknown keys {unknown}; allowed keys: {sorted(names)}"
        )
    overrides = {
        k: tuple(v) if isinstance(v, list) and isinstance(getattr(base, k), tuple) else v
        for k, v in data.items()
    }
    return replace(base, **overrides)


def config_hash(cfg: EngineConfig) -> str:
    cfg_json = json.dumps(asdict(cfg), sort_keys=True)
    return hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
