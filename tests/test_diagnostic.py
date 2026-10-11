import pytest
from adaptengine.api import Engine
from adaptengine.diagnostic import (
    StopReason,
    candidate_sort_key,
)
from adaptengine.learner.state import LearnerConcept, ConceptStatus


@pytest.fixture
def engine():
    return Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )


# TC2.1: Diagnostic stops at threshold or cap, never exceeds N_max
def test_adversarial_learner_bounded_by_n_max(engine):
    """Adversarial learner (always wrong) never exceeds N_max."""
    init_state = engine.init_learner()
    # Always wrong
    res = engine.diagnose(init_state, lambda act: False)
    assert res.total_items <= engine.config.n_max
    assert res.total_items <= 8
    assert len(res.item_log) == res.total_items


def test_alternating_learner_bounded_by_n_max(engine):
    """Alternating correct/incorrect learner never exceeds N_max."""
    init_state = engine.init_learner()
    turn = [True]

    def alternating_provider(act):
        ans = turn[0]
        turn[0] = not turn[0]
        return ans

    res = engine.diagnose(init_state, alternating_provider)
    assert res.total_items <= engine.config.n_max


def test_entropy_stopping_rule(engine):
    """A consistent learner stops before the caps once H(p) <= H_stop."""
    init_state = engine.init_learner()
    # Consistent learner: always correct
    res = engine.diagnose(init_state, lambda act: True)
    assert res.total_items <= engine.config.n_max

    # Check concepts that were diagnosed
    for cid, cr in res.concept_results.items():
        if cr.n_items > 0:
            if cr.stop_reason == StopReason.ENTROPY:
                assert cr.h <= engine.config.h_stop


# TC2.2: Concepts with no prior observations keep prior state and UNASSESSED
def test_cold_start_unassessed_preserved(engine):
    """Untouched concepts keep existing state and UNASSESSED status."""
    init_state = engine.init_learner()
    # Run diagnostic for C1 only
    res = engine.diagnose(init_state, lambda act: True, goal_concepts=("C1",))

    # C1 should be assessed
    assert res.concept_results["C1"].status == ConceptStatus.ASSESSED
    assert res.concept_results["C1"].n_items > 0

    # C2, C3, C4 were not in goal concepts so their state is untouched
    for cid in ("C2", "C3", "C4"):
        c = res.state.concepts[cid]
        assert c.p == engine.config.p0
        assert c.status == ConceptStatus.UNASSESSED
        assert not c.assessed
        assert c.responses == 0


def test_surprise_response_and_cap(engine):
    """p=0.9, d=0.5, incorrect raises entropy and cap bounds run."""
    # Create learner state where C1 starts at p=0.9
    concepts = dict(engine.init_learner().concepts)
    concepts["C1"] = LearnerConcept(concept_id="C1", p=0.9, status=ConceptStatus.UNASSESSED)
    from adaptengine.learner.state import LearnerState

    state = LearnerState(concepts=concepts)
    h_before = state.concepts["C1"].uncertainty
    assert h_before == pytest.approx(0.4690, abs=1e-4)

    # First answer is incorrect -> entropy jumps
    res = engine.diagnose(state, lambda act: False, goal_concepts=("C1",))
    assert res.total_items <= engine.config.concept_cap
    assert len(res.item_log) >= 1
    first_item = res.item_log[0]
    assert first_item.p_before == 0.9
    assert first_item.p_after < 0.9


def test_descendant_skipping_on_low_mastery(engine):
    """Descendants are skipped when ancestor ends with p < skip_threshold (D8: 0.40)."""
    init_state = engine.init_learner()
    # Always wrong on C1 ensures C1 ends with p < 0.40
    res = engine.diagnose(init_state, lambda act: False)

    c1_res = res.concept_results["C1"]
    assert c1_res.p < engine.config.skip_threshold

    # In 4-node curriculum, C1 is prerequisite for C2, C3, C4
    # All descendants of C1 should have stop_reason SKIPPED_ANCESTOR_UNMASTERED
    descendants = engine.graph.descendants("C1")
    for desc in descendants:
        assert desc in res.concept_results
        desc_res = res.concept_results[desc]
        assert desc_res.stop_reason == StopReason.SKIPPED_ANCESTOR_UNMASTERED
        assert desc_res.n_items == 0
        assert res.state.concepts[desc].status == ConceptStatus.UNASSESSED


def test_no_activity_asked_twice(engine):
    """Diagnostic never asks any activity twice."""
    init_state = engine.init_learner()
    res = engine.diagnose(init_state, lambda act: False)
    asked_aids = [item.activity_id for item in res.item_log]
    assert len(asked_aids) == len(set(asked_aids))


def test_input_state_not_mutated(engine):
    """Running diagnostic does not mutate input state."""
    init_state = engine.init_learner()
    p_c1_before = init_state.concepts["C1"].p
    res = engine.diagnose(init_state, lambda act: True)
    assert init_state.concepts["C1"].p == p_c1_before
    assert res.state is not init_state


def test_deterministic_identical_runs(engine):
    """Two diagnostic runs with identical inputs produce byte-identical logs."""
    init_state = engine.init_learner()
    res1 = engine.diagnose(init_state, lambda act: True)
    res2 = engine.diagnose(init_state, lambda act: True)

    assert res1.total_items == res2.total_items
    assert len(res1.item_log) == len(res2.item_log)
    for it1, it2 in zip(res1.item_log, res2.item_log):
        assert it1.activity_id == it2.activity_id
        assert it1.p_before == it2.p_before
        assert it1.p_after == it2.p_after
        assert it1.eig == it2.eig


def test_tie_breaking_d10():
    """Tie-break: smaller |d - 0.5|, then lexicographic activity_id (D10)."""
    # Two activities with identical EIG and difficulties 0.4 and 0.6
    # |0.4 - 0.5| = 0.1, |0.6 - 0.5| = 0.1
    # Ties broken by activity_id
    k1 = candidate_sort_key(0.5, 0.4, "ACT-B")
    k2 = candidate_sort_key(0.5, 0.6, "ACT-A")
    assert k2 < k1  # ACT-A wins on lexicographic ID

    # Difficulty closer to 0.5 wins over further
    k_close = candidate_sort_key(0.5, 0.5, "ACT-Z")
    k_far = candidate_sort_key(0.5, 0.2, "ACT-A")
    assert k_close < k_far  # |0.5 - 0.5| = 0 wins over |0.2 - 0.5| = 0.3
