from dataclasses import replace
from typing import Optional, TYPE_CHECKING
from ..core.validators import check_bool, check_non_negative_int
from ..core.config import EngineConfig, DEFAULT_CONFIG
from .state import LearnerConcept, ConceptStatus

if TYPE_CHECKING:
    from .adapter import MasteryModel


def update_concept_evidence(
    concept: LearnerConcept,
    difficulty: float,
    correct: bool,
    *,
    transition: float,
    model: "MasteryModel",
    cfg: EngineConfig = DEFAULT_CONFIG,
    day: Optional[int] = None,
    attempt_id: Optional[str] = None,
) -> tuple[LearnerConcept, bool]:
    """Single canonical rebuild site for concept evidence updates.

    Adheres to D4, D5, D20, D22:
    - Idempotent: duplicate attempt_id in seen_attempt_ids returns (concept, False).
    - Uses dataclasses.replace so needs_remediation, half_life_days, and other fields survive.
    - Updates p, responses, correct_responses, status=ASSESSED, seen_attempt_ids.
    - If day is provided, updates last_practice_day; otherwise preserves it.
    - Returns (updated_concept, changed: bool).
    """
    check_bool(correct, "correct")

    # Idempotency check: duplicate attempt_id is a no-op
    if attempt_id is not None and attempt_id in concept.seen_attempt_ids:
        return concept, False

    new_p = model.update(concept.p, difficulty, correct, transition)

    new_responses = concept.responses + 1
    new_correct = concept.correct_responses + (1 if correct else 0)
    new_seen = concept.seen_attempt_ids | ({attempt_id} if attempt_id else frozenset())

    if day is not None:
        check_non_negative_int(day, "day")
        new_day = max(concept.last_practice_day or 0, day)
    else:
        new_day = concept.last_practice_day

    new_concept = replace(
        concept,
        p=new_p,
        responses=new_responses,
        correct_responses=new_correct,
        status=ConceptStatus.ASSESSED,
        seen_attempt_ids=new_seen,
        last_practice_day=new_day,
        n_reviews=concept.n_reviews + 1,
    )
    return new_concept, True
