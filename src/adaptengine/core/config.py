import json
import hashlib
import math
from dataclasses import dataclass, asdict
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
    # concept_cap=3, n_max=8, other flags as below.
    min_items_per_concept: int = 1  # responses required before an entropy stop
    pruning_mode: str = "hard"  # "hard" skip | "soft" cap descendants' prior | "none"
    selection_scope: str = "concept_sweep"  # "concept_sweep" | "frontier" (global EIG) | "goal_search"
    known_threshold: float = 0.70
    diag_budget_min: int = 6
    diag_budget_per_concept: float = 0.0  # 0 -> budget is plain n_max
    prior_mode: str = "population"  # "flat" (state p) | "population" (population_p0)
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
    # ---- W8 settings. Every default reproduces W7 behaviour (plan §0.1 rule 4).
    # B.1 named profile: per-difficulty-class (class, guess, slip) triples replace the D6
    # g(d)/s(d) heuristics when set; O.3 BKT forgets in the exercise transition
    profile: str = "w7_default"
    class_params: Optional[tuple[tuple[str, float, float], ...]] = None
    forget: float = 0.0
    # C.1 (D49) consolidation tier: verification practice once all required work is done
    consolidation: bool = False
    # C.2 (D50) one hard item before unlocking dependents when > probe_easy_share of a
    # prerequisite's exercise evidence came from easy items
    verification_probe: bool = False
    probe_easy_share: float = 0.5
    # C.3 (D51) horizon-aware strictness: when slack > strict_slack, use the two-part criterion
    # (two_threshold) with k = strict_k and H <= strict_max_entropy
    horizon_aware_mastery: bool = False
    strict_slack: float = 0.5
    strict_k: int = 3
    strict_max_entropy: float = 0.35
    # D.1 review cap (share of the daily budget for reviews while new content is pending;
    # 1.0 = no cap) and goal-path relevance
    review_cap_fraction: float = 1.0
    review_goal_path_only: bool = False
    # E.1 diagnostic scope: "all" concepts or "goal_path" (goal + ancestors not yet mastered)
    diagnostic_scope: str = "all"
    # F.1 attach an expected-projection deadline warning to plans (does not change schedules)
    feasibility_warning: bool = False
    # J.4 new-content ranking policy (deterministic = W7 scheduler, no hook)
    ranking_policy: str = "deterministic"
    policy_top_k: int = 5
    policy_seed: int = 0
    # O.1 measurement model, O.2 half-life model (HLR-lite weights: bias, correct, wrong)
    mastery_model: str = "bkt"
    elo_k: float = 0.4
    elo_a: float = 1.7
    half_life_model: str = "fixed"
    hlr_weights: tuple[float, float, float] = (4.0, 0.5, -0.5)
    # O.4 scheduler back-end ("cpsat" needs the optional [solver] extra)
    scheduler: str = "greedy"

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
        if not (self.skip_threshold < self.known_threshold < 1.0):
            raise ValidationError(
                f"need skip_threshold < known_threshold < 1, got {self.skip_threshold}, "
                f"{self.known_threshold}"
            )
        check_positive_int(self.diag_budget_min, "diag_budget_min")
        if not math.isfinite(self.diag_budget_per_concept) or self.diag_budget_per_concept < 0:
            raise ValidationError(
                f"diag_budget_per_concept must be finite and >= 0, got {self.diag_budget_per_concept}"
            )
        for name, val, allowed in (
            ("pruning_mode", self.pruning_mode, ("hard", "soft", "none")),
            ("selection_scope", self.selection_scope, ("concept_sweep", "frontier", "goal_search")),
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
        if not (0.0 < self.half_life_growth <= 10.0) or not math.isfinite(self.half_life_growth):
            raise ValidationError(
                f"half_life_growth must be finite in (0, 10], got {self.half_life_growth}"
            )
        self._validate_w8()

    def _validate_w8(self) -> None:
        if not isinstance(self.profile, str) or not self.profile:
            raise ValidationError("profile must be a non-empty string")
        if self.class_params is not None:
            names = [c[0] for c in self.class_params]
            if sorted(names) != ["easy", "hard", "medium"]:
                raise ValidationError(f"class_params needs easy/medium/hard, got {names}")
            for name, g, s in self.class_params:
                for label, v in (("guess", g), ("slip", s)):
                    if not _finite_in(v, 0.0, 1.0):
                        raise ValidationError(f"{name} {label} must be in (0, 1), got {v}")
                if g + s >= 1.0:
                    raise ValidationError(f"{name}: guess + slip must be < 1, got {g} + {s}")
        if not (_finite_in(self.forget, 0.0, 1.0) or self.forget == 0.0):
            raise ValidationError(f"forget must be in [0, 1), got {self.forget}")
        for name in (
            "consolidation",
            "verification_probe",
            "horizon_aware_mastery",
            "review_goal_path_only",
            "feasibility_warning",
        ):
            check_bool(getattr(self, name), name)
        for name in ("probe_easy_share", "strict_slack"):
            if not _finite_in(getattr(self, name), 0.0, 1.0):
                raise ValidationError(f"{name} must be in (0, 1), got {getattr(self, name)}")
        if not _finite_in(self.strict_max_entropy, 0.0, 1.0):
            raise ValidationError(
                f"strict_max_entropy must be in (0, 1), got {self.strict_max_entropy}"
            )
        check_positive_int(self.strict_k, "strict_k")
        check_positive_int(self.policy_top_k, "policy_top_k")
        if not isinstance(self.policy_seed, int) or isinstance(self.policy_seed, bool):
            raise ValidationError("policy_seed must be an int")
        if not (_finite_in(self.review_cap_fraction, 0.0, 1.0) or self.review_cap_fraction == 1.0):
            raise ValidationError(
                f"review_cap_fraction must be in (0, 1], got {self.review_cap_fraction}"
            )
        for name, val, allowed in (
            ("diagnostic_scope", self.diagnostic_scope, ("all", "goal_path")),
            (
                "ranking_policy",
                self.ranking_policy,
                ("deterministic", "bandit_frozen", "bandit_updating", "random", "agent"),
            ),
            ("mastery_model", self.mastery_model, ("bkt", "elo")),
            ("half_life_model", self.half_life_model, ("fixed", "hlr")),
            ("scheduler", self.scheduler, ("greedy", "cpsat")),
        ):
            if val not in allowed:
                raise ValidationError(f"{name} must be one of {allowed}, got {val!r}")
        for name in ("elo_k", "elo_a"):
            v = getattr(self, name)
            if not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise ValidationError(f"{name} must be finite > 0, got {v}")
        if len(self.hlr_weights) != 3 or not all(
            isinstance(w, (int, float)) and math.isfinite(w) for w in self.hlr_weights
        ):
            raise ValidationError(f"hlr_weights must be 3 finite numbers, got {self.hlr_weights}")


def _finite_in(v, lo: float, hi: float) -> bool:
    """v is a finite real strictly inside (lo, hi)."""
    return (
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo < v < hi
    )


DEFAULT_CONFIG = EngineConfig()


def config_hash(cfg: EngineConfig) -> str:
    cfg_json = json.dumps(asdict(cfg), sort_keys=True)
    return hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
