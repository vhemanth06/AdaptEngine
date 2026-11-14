from dataclasses import replace
import pytest
from adaptengine.core.config import DEFAULT_CONFIG, EngineConfig
from adaptengine.core.errors import ValidationError
from adaptengine.diagnostic import diagnostic_budget
from adaptengine.api import Engine

PRODUCT_DIAG = dict(n_max=25, diag_budget_min=12, diag_budget_per_concept=1.0)

@pytest.mark.parametrize("n,expected", [(4, 12), (8, 12), (12, 12), (20, 20), (25, 25), (50, 25)])
def test_budget_table(n, expected):
    assert diagnostic_budget(replace(DEFAULT_CONFIG, **PRODUCT_DIAG), n) == expected

def test_budget_default_is_n_max():
    assert diagnostic_budget(DEFAULT_CONFIG, 50) == DEFAULT_CONFIG.n_max == 6

def test_budget_n_max_override_truncates():
    assert diagnostic_budget(replace(DEFAULT_CONFIG, **{**PRODUCT_DIAG, "n_max": 3}), 50) == 3

@pytest.mark.parametrize("kw", [dict(known_threshold=0.30), dict(known_threshold=1.0),
                                dict(diag_budget_min=0), dict(diag_budget_per_concept=-0.1),
                                dict(selection_scope="nope")])
def test_new_fields_validated(kw):
    with pytest.raises(ValidationError):
        EngineConfig(**kw)

def test_goal_search_scope_accepted():
    assert EngineConfig(selection_scope="goal_search").selection_scope == "goal_search"

def test_sweep_uses_scaled_budget():
    cfg = replace(DEFAULT_CONFIG, **PRODUCT_DIAG)
    e = Engine.from_files("data/curriculum/curriculum_8node.json",
                          "data/curriculum/activities_8node.json", config=cfg)
    res = e.diagnose(e.init_learner(), lambda a: True)
    assert 6 < res.total_items <= 12

def test_budget_uses_round_not_ceil():
    cfg = replace(DEFAULT_CONFIG, n_max=100, diag_budget_min=1, diag_budget_per_concept=0.5)
    assert diagnostic_budget(cfg, 5) == 2  # round(2.5) == 2


from adaptengine.core.profiles import load_profile
from adaptengine.core.schema import Activity, ActivityType, Concept
from adaptengine.diagnostic import StopReason

GS = dict(selection_scope="goal_search", concept_cap=4, **PRODUCT_DIAG)

def chain_engine(cfg, n=8, no_exercises=()):
    concepts = tuple(Concept(f"K{i}", (f"K{i-1}",) if i > 1 else ()) for i in range(1, n + 1))
    acts = []
    for i in range(1, n + 1):
        acts.append(Activity(f"L-K{i}", ActivityType.LESSON, f"K{i}", 4))
        if f"K{i}" not in no_exercises:
            acts += [Activity(f"E-K{i}-{d}", ActivityType.EXERCISE, f"K{i}", 1, d)
                     for d in (0.2, 0.4, 0.6, 0.8)]
    return Engine(concepts, tuple(acts), cfg)

S1_GS = lambda **kw: load_profile("fitted_S1", **{**GS, **kw})
knows = lambda known: (lambda a: a.target_concept in known)

def test_goal_search_first_question_is_chain_middle():
    e = chain_engine(S1_GS())
    res = e.diagnose(e.init_learner(), lambda a: True)
    assert res.item_log[0].concept_id == "K4"

def test_goal_search_advanced_learner_finds_gap():
    e = chain_engine(S1_GS())
    res = e.diagnose(e.init_learner(), knows({"K1", "K2", "K3", "K4", "K5"}))
    r = res.concept_results
    assert {c for c in r if r[c].stop_reason == StopReason.INFERRED} == {"K1", "K2", "K3"}
    assert all(r[c].inferred_from == "K4" for c in ("K1", "K2", "K3"))
    assert r["K6"].p < 0.40
    assert {r["K7"].stop_reason, r["K8"].stop_reason} == {StopReason.SKIPPED_ANCESTOR_UNMASTERED}
    assert r["K4"].p == pytest.approx(0.77, abs=0.01) and r["K5"].p == pytest.approx(0.77, abs=0.01)
    assert res.total_items <= 12

def test_goal_search_novice_stops_fast():
    e = chain_engine(S1_GS())
    res = e.diagnose(e.init_learner(), lambda a: False)
    assert res.total_items <= 6
    assert all(x.p < 0.40 for x in res.state.concepts.values())

def test_goal_search_floors_ancestors_without_settling():
    e = chain_engine(S1_GS())
    res = e.diagnose(e.init_learner(), lambda a: a.difficulty != 0.2)  # misses every easy item
    r = res.concept_results
    assert r["K4"].p < 0.70
    assert all(res.state.concepts[a].p >= r["K4"].p - 1e-12 for a in ("K1", "K2", "K3"))
    assert r["K2"].stop_reason != StopReason.INFERRED

def test_goal_search_deterministic():
    e = chain_engine(S1_GS())
    run = lambda: e.diagnose(e.init_learner(), knows({"K1", "K2"})).item_log
    assert run() == run()

def test_goal_search_prefix_override_stops_at_n_max():
    e = chain_engine(S1_GS(n_max=3))
    assert e.diagnose(e.init_learner(), lambda a: True).total_items == 3

def test_goal_search_branching_dag_terminates():
    cfg = load_profile("fitted_S1", **GS)
    e = Engine.from_files("data/curriculum/curriculum_8node.json",
                          "data/curriculum/activities_8node.json", config=cfg)
    res = e.diagnose(e.init_learner(), lambda a: a.target_concept in {"C1", "C2", "C3", "C6"})
    assert set(res.concept_results) == set(e.graph.concepts())
    assert res.total_items <= 12

def test_goal_search_concept_without_exercises():
    e = chain_engine(S1_GS(), no_exercises=("K4",))
    res = e.diagnose(e.init_learner(), lambda a: True)
    assert res.concept_results["K4"].stop_reason == StopReason.NO_ITEMS
    assert set(res.concept_results) == {f"K{i}" for i in range(1, 9)}

def test_goal_search_leaves_out_of_set_concepts_untouched():
    e = chain_engine(S1_GS())
    init = e.init_learner()
    res = e.diagnose(init, lambda a: True, goal_concepts=["K5", "K6", "K7", "K8"])
    assert all(res.state.concepts[c] == init.concepts[c] for c in ("K1", "K2", "K3", "K4"))


def test_goal_search_budget_cut_concept_does_not_propagate():
    e = chain_engine(S1_GS(n_max=2))
    res = e.diagnose(e.init_learner(), lambda a: True)
    assert res.concept_results["K4"].stop_reason == StopReason.GLOBAL_CAP
    assert all(res.state.concepts[a].p == pytest.approx(0.24) for a in ("K1", "K2", "K3"))


def test_goal_search_prefix_replay_matches_full_run():
    answers = knows({"K1", "K2", "K3", "K4", "K5"})
    full = chain_engine(S1_GS()).diagnose(chain_engine(S1_GS()).init_learner(), answers)
    log = full.item_log
    for k in range(1, len(log) + 1):
        e = chain_engine(S1_GS(n_max=k))
        pre = e.diagnose(e.init_learner(), answers)
        assert pre.item_log == log[:k]
        # live state after k items: asked concepts at their last p_after; K1-K3 inferred only
        # once K4's block is complete (4 items); everything else still at the prior
        expected = {c: 0.24 for c in pre.state.concepts}
        if k >= 4:
            expected.update(K1=log[3].p_after, K2=log[3].p_after, K3=log[3].p_after)
        for x in log[:k]:
            expected[x.concept_id] = x.p_after
        assert {c: s.p for c, s in pre.state.concepts.items()} == pytest.approx(expected)
