from dataclasses import dataclass
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

    def __init__(
        self,
        concept_id: str = "",
        p: Optional[float] = None,
        lessons_done: int = 0,
        responses: int = 0,
        correct_responses: int = 0,
        status: ConceptStatus = ConceptStatus.UNASSESSED,
        seen_attempt_ids: Any = frozenset(),
        half_life_days: float = 30.0,
        last_practice_day: Optional[int] = None,
        n_reviews: int = 0,
        mastery: Optional[float] = None,
        uncertainty: Optional[float] = None,
        assessed: Optional[bool] = None,
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
        """evidence_mastered := p >= theta and responses >= k (D4: k=2, theta=0.85)."""
        return self.p >= 0.85 and self.responses >= 2


@dataclass(frozen=True)
class ExecutionLog:
    events: tuple[Event, ...] = ()

    def append(self, event: Event) -> "ExecutionLog":
        return ExecutionLog(events=self.events + (event,))

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
            half_life_days=30.0,
        )
        for cid in sorted(concept_ids)
    }
    return LearnerState(concepts=concepts)
