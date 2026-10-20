import pytest
from adaptengine.learner.state import LearnerConcept, LearnerState
from adaptengine.core.config import EngineConfig
from adaptengine.core.schema import Concept
from adaptengine.curriculum.graph import CurriculumGraph
from adaptengine.review.forgetting import (
    recall,
    is_review_due,
    review_urgency,
    compute_review_urgencies,
)


def test_recall_known_values():
    # dt = 0 gives 1.0
    c_day5 = LearnerConcept(concept_id="C1", p=0.85, last_practice_day=5, half_life_days=10.0)
    assert recall(c_day5, 5) == pytest.approx(1.0)

    # dt = h gives 0.5
    assert recall(c_day5, 15) == pytest.approx(0.5)

    # dt = 2h gives 0.25
    assert recall(c_day5, 25) == pytest.approx(0.25)

    # None practice day gives None
    c_none = LearnerConcept(concept_id="C2", p=0.85, last_practice_day=None, half_life_days=10.0)
    assert recall(c_none, 10) is None


def test_is_review_due():
    cfg = EngineConfig(recall_threshold=0.80)

    # Never practiced -> False
    c_none = LearnerConcept(concept_id="C1", p=0.85, last_practice_day=None, half_life_days=10.0)
    assert not is_review_due(c_none, 10, cfg)

    # r = 1.0 (>= 0.80) -> False
    c_recent = LearnerConcept(concept_id="C1", p=0.85, last_practice_day=10, half_life_days=10.0)
    assert not is_review_due(c_recent, 10, cfg)

    # At day 14 (dt = 4, h = 10): r = 2^(-0.4) ≈ 0.7579 (< 0.80) -> True
    assert is_review_due(c_recent, 14, cfg)


def test_review_urgency_formula_d25():
    cfg = EngineConfig(recall_threshold=0.80)

    # Concept with last_practice_day=0, h=10, day=10 -> r = 0.5
    # Descendant count = 3 -> urgency = (1 - 0.5) * (1 + 3) = 0.5 * 4 = 2.0
    c1 = LearnerConcept(concept_id="C1", p=0.85, last_practice_day=0, half_life_days=10.0)
    urg = review_urgency(c1, day=10, descendant_count=3, cfg=cfg)
    assert urg == pytest.approx(2.0)

    # Leaf concept (descendant_count = 0) stays above zero: 0.5 * 1 = 0.5
    urg_leaf = review_urgency(c1, day=10, descendant_count=0, cfg=cfg)
    assert urg_leaf == pytest.approx(0.5)

    # Not due (r = 1.0 >= 0.80) -> urgency = 0.0
    urg_not_due = review_urgency(c1, day=0, descendant_count=3, cfg=cfg)
    assert urg_not_due == 0.0


def test_compute_review_urgencies():
    graph = CurriculumGraph.from_concepts((Concept("C1"), Concept("C2", prerequisites=("C1",))))
    # C1 has descendant C2 (descendant_count=1)
    # C2 is a leaf (descendant_count=0)
    c1 = LearnerConcept(concept_id="C1", p=0.85, last_practice_day=0, half_life_days=5.0)
    c2 = LearnerConcept(concept_id="C2", p=0.85, last_practice_day=None, half_life_days=5.0)
    state = LearnerState(concepts={"C1": c1, "C2": c2})

    # At day 5, C1 has dt=5=h -> r=0.5 < 0.80 -> due! Urgency = (1 - 0.5) * (1 + 1) = 1.0
    # C2 was never practiced -> not due
    urgs = compute_review_urgencies(graph, state, day=5)
    assert "C1" in urgs
    assert urgs["C1"] == pytest.approx(1.0)
    assert "C2" not in urgs
