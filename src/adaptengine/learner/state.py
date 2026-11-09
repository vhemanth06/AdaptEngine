import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Mapping, Any
from types import MappingProxyType
import math
from ..core.errors import ValidationError
from .mastery import entropy
from ..core.config import DEFAULT_CONFIG, EngineConfig
from ..core.schema import Event, EventType
from ..core.validators import (
    check_probability,
    check_non_negative_int,
    check_finite_positive_float,
    check_valid_id,
    check_bool,
)


class ConceptStatus(str, Enum):
    UNASSESSED = "UNASSESSED"
    ASSESSED = "ASSESSED"


@dataclass(frozen=True, init=False)
class LearnerConcept:
    concept_id: str
    p: float
    lessons_done: int
    responses: int
    correct_responses: int
    status: ConceptStatus
    seen_attempt_ids: frozenset[str]
    half_life_days: float
    last_practice_day: Optional[int]
    n_reviews: int
    needs_remediation: bool = False
    correct_streak: int = 0  # consecutive correct responses (T5.4)

    def __init__(
        self,
        concept_id: str = "",
        p: Optional[float] = None,
        lessons_done: int = 0,
        responses: int = 0,
        correct_responses: int = 0,
        status: ConceptStatus = ConceptStatus.UNASSESSED,
        seen_attempt_ids: Any = frozenset(),
        half_life_days: float = DEFAULT_CONFIG.half_life_days,
        last_practice_day: Optional[int] = None,
        n_reviews: int = 0,
        mastery: Optional[float] = None,
        uncertainty: Optional[float] = None,
        assessed: Optional[bool] = None,
        needs_remediation: bool = False,
        correct_streak: int = 0,
    ):
        if p is None and mastery is not None:
            p = mastery
        elif p is None:
            p = 0.20

        if uncertainty is not None:
            if not isinstance(uncertainty, (int, float)) or isinstance(uncertainty, bool):
                raise ValidationError(
                    f"uncertainty must be numeric, got {type(uncertainty).__name__}"
                )
            if not math.isfinite(uncertainty) or uncertainty < 0.0:
                raise ValidationError(f"uncertainty must be >= 0, got {uncertainty}")

        if assessed is not None:
            check_bool(assessed, "assessed")
            if assessed and status == ConceptStatus.UNASSESSED:
                status = ConceptStatus.ASSESSED
            elif not assessed:
                status = ConceptStatus.UNASSESSED

        if concept_id:
            check_valid_id(concept_id, "concept_id")

        p_val = check_probability(p, "p")
        check_non_negative_int(lessons_done, "lessons_done")
        check_non_negative_int(responses, "responses")
        check_non_negative_int(correct_responses, "correct_responses")

        if correct_responses > responses:
            raise ValidationError(
                f"correct_responses ({correct_responses}) cannot exceed responses ({responses})"
            )

        if not isinstance(status, ConceptStatus):
            raise ValidationError(f"status must be ConceptStatus, got {status!r}")

        if not isinstance(seen_attempt_ids, (frozenset, set)):
            raise ValidationError("seen_attempt_ids must be a frozenset or set")
        frozen_attempts = frozenset(str(x) for x in seen_attempt_ids)

        check_finite_positive_float(half_life_days, "half_life_days")

        if last_practice_day is not None:
            check_non_negative_int(last_practice_day, "last_practice_day")

        check_non_negative_int(n_reviews, "n_reviews")
        check_bool(needs_remediation, "needs_remediation")
        check_non_negative_int(correct_streak, "correct_streak")
        if correct_streak > correct_responses:
            raise ValidationError("correct_streak cannot exceed correct_responses")

        object.__setattr__(self, "concept_id", concept_id)
        object.__setattr__(self, "p", p_val)
        object.__setattr__(self, "lessons_done", lessons_done)
        object.__setattr__(self, "responses", responses)
        object.__setattr__(self, "correct_responses", correct_responses)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "seen_attempt_ids", frozen_attempts)
        object.__setattr__(self, "half_life_days", float(half_life_days))
        object.__setattr__(self, "last_practice_day", last_practice_day)
        object.__setattr__(self, "n_reviews", n_reviews)
        object.__setattr__(self, "needs_remediation", bool(needs_remediation))
        object.__setattr__(self, "correct_streak", correct_streak)

    @property
    def mastery(self) -> float:
        return self.p

    @property
    def uncertainty(self) -> float:
        return entropy(self.p)

    @property
    def assessed(self) -> bool:
        return self.status == ConceptStatus.ASSESSED

    @property
    def evidence_mastered(self) -> bool:
        """Deprecated (W7 T2.7): always uses DEFAULT_CONFIG, so it is wrong under any other theta/k.
        Use is_evidence_mastered(concept, cfg)."""
        warnings.warn(
            "LearnerConcept.evidence_mastered ignores the engine config; "
            "use is_evidence_mastered(concept, cfg)",
            DeprecationWarning,
            stacklevel=2,
        )
        return is_evidence_mastered(self, DEFAULT_CONFIG)


def mastered_by(p: float, responses: int, streak: int, cfg: EngineConfig = DEFAULT_CONFIG) -> bool:
    """The configured mastery criterion on raw evidence (also used by the planner's projection).

    bkt_threshold (D4, default): p >= theta and responses >= k_responses.
    n_consecutive (T5.4): the last n_consecutive responses were correct.
    two_threshold (T5.4): bkt_threshold and H(p) <= certainty_max_entropy.
    """
    if cfg.mastery_criterion == "n_consecutive":
        return streak >= cfg.n_consecutive
    ok = p >= cfg.theta and responses >= cfg.k_responses
    if cfg.mastery_criterion == "two_threshold":
        return ok and entropy(p) <= cfg.certainty_max_entropy
    return ok


def is_evidence_mastered(concept: LearnerConcept, cfg: EngineConfig = DEFAULT_CONFIG) -> bool:
    """evidence_mastered under cfg.mastery_criterion (default D4: p >= theta and responses >= k)."""
    return mastered_by(concept.p, concept.responses, concept.correct_streak, cfg)


@dataclass(frozen=True)
class ExecutionLog:
    events: tuple[Event, ...] = ()
    # Index of attempt IDs for O(1) duplicate checks in Engine.record (T9.1); derived, so it is
    # excluded from equality and repr.
    attempt_ids: Optional[frozenset[str]] = field(default=None, compare=False, repr=False)

    def __post_init__(self):
        if self.attempt_ids is None:
            ids = frozenset(e.attempt_id for e in self.events if e.attempt_id is not None)
            object.__setattr__(self, "attempt_ids", ids)

    def append(self, event: Event) -> "ExecutionLog":
        extra = frozenset((event.attempt_id,)) if event.attempt_id is not None else frozenset()
        return ExecutionLog(events=self.events + (event,), attempt_ids=self.attempt_ids | extra)

    def completed_ids(self) -> tuple[str, ...]:
        return tuple(
            e.activity_id
            for e in self.events
            if e.activity_id is not None and e.kind == EventType.COMPLETED
        )


@dataclass(frozen=True)
class LearnerState:
    concepts: Mapping[str, LearnerConcept]

    def __post_init__(self):
        sorted_copy = {k: self.concepts[k] for k in sorted(self.concepts.keys())}
        object.__setattr__(self, "concepts", MappingProxyType(sorted_copy))


def initial_state(concept_ids: tuple[str, ...], cfg: EngineConfig = DEFAULT_CONFIG) -> LearnerState:
    p0 = cfg.p0
    concepts = {
        cid: LearnerConcept(
            concept_id=cid,
            p=p0,
            status=ConceptStatus.UNASSESSED,
            half_life_days=cfg.half_life_days,
        )
        for cid in sorted(concept_ids)
    }
    return LearnerState(concepts=concepts)
