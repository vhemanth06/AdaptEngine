import json
import hashlib
import math
from dataclasses import dataclass, asdict
from . import constants
from .errors import ValidationError
from .validators import check_positive_int


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
    n_max: int = 8
    concept_cap: int = 3
    h_stop: float = 0.50
    k_responses: int = 2
    skip_threshold: float = 0.40
    # M3/M4 Planner settings
    target_success: float = 0.75
    w_review: float = 1.0
    w_unlock: float = 1.0
    w_fit: float = 1.0
    allowed_budgets: tuple[int, ...] = (5, 10, 15, 30)
    oracle_node_limit: int = 1000
    # M5/M6 Review & Remediation settings
    recall_threshold: float = 0.80
    remediation_threshold: float = 0.40
    half_life_growth: float = 1.0

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
        if not (0.0 < self.half_life_growth <= 10.0) or not math.isfinite(self.half_life_growth):
            raise ValidationError(
                f"half_life_growth must be finite in (0, 10], got {self.half_life_growth}"
            )


DEFAULT_CONFIG = EngineConfig()


def config_hash(cfg: EngineConfig) -> str:
    cfg_json = json.dumps(asdict(cfg), sort_keys=True)
    return hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
