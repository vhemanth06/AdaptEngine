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


# ---------------- W7 T3.2: diagnostic flags ----------------
def _diag(**kw):
    from adaptengine.core.config import EngineConfig

    return Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        config=EngineConfig(**kw),
    )


def _run(engine, answer):
    return engine.diagnose(engine.init_learner(), response_provider=answer, session_id="t")


def test_min_items_before_entropy_stop_t3_2():
    r1 = _run(_diag(), lambda a: False)
    assert any(
        cr.stop_reason == StopReason.ENTROPY and cr.n_items == 1
        for cr in r1.concept_results.values()
    )
    r2 = _run(_diag(min_items_per_concept=2, pruning_mode="none"), lambda a: False)
    for cr in r2.concept_results.values():
        if cr.stop_reason == StopReason.ENTROPY:
            assert cr.n_items >= 2


def test_pruning_modes_t3_2():
    hard = _run(_diag(prior_mode="flat"), lambda a: False)
    assert any(
        cr.stop_reason == StopReason.SKIPPED_ANCESTOR_UNMASTERED
        for cr in hard.concept_results.values()
    )
    for mode in ("soft", "none"):
        r = _run(_diag(pruning_mode=mode, n_max=12, prior_mode="flat"), lambda a: False)
        assert all(
            cr.stop_reason != StopReason.SKIPPED_ANCESTOR_UNMASTERED
            for cr in r.concept_results.values()
        )
        first_c4 = next(x for x in r.item_log if x.concept_id == "C4")
        c3_final = r.concept_results["C3"].p
        if mode == "soft":
            assert first_c4.p_before <= c3_final + 1e-12  # prior capped at the ancestor's p
        else:
            assert first_c4.p_before == 0.20


def test_frontier_scope_respects_dag_and_caps_t3_2():
    eng = _diag(selection_scope="frontier", pruning_mode="none", n_max=6)
    r = _run(eng, lambda a: a.difficulty < 0.5)
    assert r.total_items <= 6 and len(r.item_log) == r.total_items
    seen = []
    for it in r.item_log:
        for q in eng.graph.prerequisites(it.concept_id):
            # a concept is only probed after its prerequisites' diagnoses ended
            assert q in seen or all(x.concept_id != q for x in r.item_log)
        if it.concept_id not in seen:
            seen.append(it.concept_id)
    r2 = _run(eng, lambda a: a.difficulty < 0.5)
    assert r == r2  # deterministic
    with pytest.raises(TypeError):
        r.concept_results["C1"] = None  # read-only mapping


def test_population_prior_t3_2():
    r = _run(_diag(prior_mode="population", population_p0=0.3, n_max=1), lambda a: True)
    unprobed = [c for c, cr in r.concept_results.items() if cr.n_items == 0]
    assert unprobed and all(r.state.concepts[c].p == 0.3 for c in unprobed)


def test_diagnostic_flag_validation_t3_2():
    from adaptengine.core.config import EngineConfig

    for kw in (
        {"pruning_mode": "x"},
        {"selection_scope": "x"},
        {"prior_mode": "x"},
        {"min_items_per_concept": 0},
        {"population_p0": 1.0},
    ):
        with pytest.raises(Exception):
            EngineConfig(**kw)


def test_state_space_diagnostic_t3_6():
    from adaptengine.diagnostic.state_space import StateSpaceDiagnostic, consistent_patterns

    eng = _diag()
    pats = consistent_patterns(eng.graph, eng.graph.concepts())
    # 4-node DAG C1, C2 -> C3 -> C4: {}, {1}, {2}, {1,2}, {1,2,3}, {1,2,3,4}
    assert len(pats) == 6
    assert all(all(q in s for c in s for q in eng.graph.prerequisites(c)) for s in pats)
    ssd = StateSpaceDiagnostic(eng.graph, eng.activities, eng.config)
    r = ssd.run(eng.init_learner(), lambda a: False)
    p = {c: r.state.concepts[c].p for c in eng.graph.concepts()}
    # marginals respect the DAG: a dependant is never more likely mastered than its prerequisite
    assert p["C3"] <= min(p["C1"], p["C2"]) + 1e-12 and p["C4"] <= p["C3"] + 1e-12
    assert 1 <= r.total_items <= eng.config.n_max
    assert r == ssd.run(eng.init_learner(), lambda a: False)
    right = ssd.run(eng.init_learner(), lambda a: True)
    assert right.state.concepts["C1"].p > p["C1"]
    e8 = Engine.from_files(
        "data/curriculum/curriculum_8node.json", "data/curriculum/activities_8node.json"
    )
    assert len(consistent_patterns(e8.graph, e8.graph.concepts())) <= 256
