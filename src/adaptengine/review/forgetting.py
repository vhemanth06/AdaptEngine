from typing import Optional
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerConcept, LearnerState


def recall(concept: LearnerConcept, day: int) -> Optional[float]:
    """Calculate exponential forgetting recall probability r(t) = 2^(-dt / h) (D23).

    Returns None if concept was never practiced (last_practice_day is None, D22).
    dt uses integer day differences: max(0, day - last_practice_day).
    """
    if concept.last_practice_day is None:
        return None

    dt = max(0, day - concept.last_practice_day)
    h = concept.half_life_days
    if h <= 0.0:
        return 0.0
    return 2.0 ** (-float(dt) / float(h))


def is_review_due(concept: LearnerConcept, day: int, cfg: EngineConfig = DEFAULT_CONFIG) -> bool:
    """Return True if recall is defined and drops below recall_threshold (D24)."""
    r = recall(concept, day)
    if r is None:
        return False
    return r < cfg.recall_threshold


def review_urgency(
    concept: LearnerConcept,
    day: int,
    descendant_count: int,
    cfg: EngineConfig = DEFAULT_CONFIG,
) -> float:
    """Calculate spaced review urgency: (1 - r) * (1 + descendant_count) (D25).

    Returns 0.0 if concept is not due for review or was never practiced.
    """
    r = recall(concept, day)
    if r is None or r >= cfg.recall_threshold:
        return 0.0
    return (1.0 - r) * (1.0 + float(descendant_count))


def compute_review_urgencies(
    graph: CurriculumGraph,
    state: LearnerState,
    day: int,
    cfg: EngineConfig = DEFAULT_CONFIG,
) -> dict[str, float]:
    """Compute review urgency mapping for all concepts due for review on a given day."""
    urgencies: dict[str, float] = {}
    for cid, concept in state.concepts.items():
        desc_count = graph.descendant_count(cid)
        urg = review_urgency(concept, day, desc_count, cfg)
        if urg > 0.0:
            urgencies[cid] = urg
    return urgencies
