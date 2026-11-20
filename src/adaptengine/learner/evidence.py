from dataclasses import replace
from typing import Optional, TYPE_CHECKING
from ..core.validators import check_bool, check_non_negative_int
from ..core.config import EngineConfig, DEFAULT_CONFIG
from .state import LearnerConcept, ConceptStatus, is_evidence_mastered

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

    # n_reviews counts review attempts only (W7 T2.6): responses on an already evidence-mastered
    # concept. A correct review stretches the half-life by half_life_growth (1.0 = unchanged).
    is_review = is_evidence_mastered(concept, cfg)
    new_half_life = concept.half_life_days * (
        cfg.half_life_growth if is_review and correct else 1.0
    )

    flags = {}
    if cfg.confirm_diag_confident and concept.diag_confident:
        flags = confirmation_flags(concept.p, difficulty, correct, new_responses, model, cfg)

    new_concept = replace(
        concept,
        p=new_p,
        responses=new_responses,
        correct_responses=new_correct,
        status=ConceptStatus.ASSESSED,
        seen_attempt_ids=new_seen,
        last_practice_day=new_day,
        n_reviews=concept.n_reviews + (1 if is_review else 0),
        correct_streak=concept.correct_streak + 1 if correct else 0,
        half_life_days=new_half_life,
        **flags,
    )
    return new_concept, True


def checks_to_confirm(p: float, d: float, model: "MasteryModel", cfg: EngineConfig) -> int:
    """Correct answers on items of difficulty d that lift the observation-only posterior from p to
    1 - confirm_epsilon (D57); confirm_max_checks + 1 when it takes more than that."""
    n = 0
    while p < 1.0 - cfg.confirm_epsilon and n <= cfg.confirm_max_checks:
        p = model.update(p, d, True, 0.0)
        n += 1
    return n


def confirmation_flags(
    p: float, d: float, correct: bool, responses: int, model: "MasteryModel", cfg: EngineConfig
) -> dict:
    """Epsilon test after a direct answer on a diag_confident concept (F1.4.3).

    Confirmed when the observation-only posterior (transition 0) reaches 1 - epsilon with at least
    confirm_min_direct direct answers. A wrong answer that leaves confirmation out of reach within
    confirm_max_checks clears diag_confident, so the concept returns to normal study.
    """
    p_obs = model.update(p, d, correct, 0.0)
    if p_obs >= 1.0 - cfg.confirm_epsilon and responses >= cfg.confirm_min_direct:
        return {"confirmed": True, "diag_confident": False}
    if not correct and checks_to_confirm(p_obs, d, model, cfg) > cfg.confirm_max_checks:
        return {"diag_confident": False}
    return {}
