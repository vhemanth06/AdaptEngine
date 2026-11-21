"""Plan 3 (F1-T1, F1-T3): bisection diagnostic (F1-TC1, TC2, TC4, TC6)."""

import dataclasses
import math
import os

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG, EngineConfig, bisection_config  # noqa: E402
from adaptengine.core.errors import UnknownConceptError, ValidationError  # noqa: E402
from adaptengine.core.schema import Activity, ActivityType, Concept  # noqa: E402
from adaptengine.diagnostic import DIAGNOSTICS, AdaptiveDiagnostic, StopReason  # noqa: E402
from adaptengine.diagnostic.bisection import BisectionDiagnostic, item_information  # noqa: E402
from experiments.core.curricula import paths as synth_paths  # noqa: E402
from experiments.core.simulator import make_learner  # noqa: E402

CUR = os.path.join(repo_root, "data", "curriculum")
ALL8 = {f"C{i}" for i in range(1, 9)}


def _eng(name="8node", **kw):
    return Engine.from_files(
        f"{CUR}/curriculum_{name}.json",
        f"{CUR}/activities_{name}.json",
        config=dataclasses.replace(bisection_config(), **kw),
        allow_unreviewed=name.endswith("x10"),
    )


# ---------------- F1-T1: config and registry ----------------


@pytest.mark.parametrize(
    "kw",
    [
        {"diagnostic_method": "binary"},
        {"bisection_prior": "flat"},
        {"bisection_scope": "goal"},
        {"bisection_samples": 0},
        {"bisection_stop_confidence": 1.0},
        {"bisection_n_min": 50},
        {"bisection_alpha": 0},
        {"confirm_epsilon": 0.0},
        {"confirm_max_checks": 0},
        {"confirm_diag_confident": 1},
        {"bisection_seed": 1.5},
    ],
)
def test_invalid_f1_config_rejected(kw):
    with pytest.raises(ValidationError):
        EngineConfig(**kw)


def test_defaults_and_registry_f1_tc1():
    assert DEFAULT_CONFIG.diagnostic_method == "sweep" and not DEFAULT_CONFIG.confirm_diag_confident
    assert DIAGNOSTICS == {"sweep": AdaptiveDiagnostic, "bisection": BisectionDiagnostic}
    e = Engine.from_files(f"{CUR}/curriculum_8node.json", f"{CUR}/activities_8node.json")
    r = e.diagnose(e.init_learner(), lambda a: True, session_id="t")
    assert dict(r.info) == {}  # the sweep's result shape is unchanged
    assert bisection_config().diagnostic_method == "bisection"
    assert bisection_config().confirm_diag_confident is True


# ---------------- F1-T3: the diagnostic ----------------


class Noiseless:
    def predict_correct(self, p, d):
        return p

    def update(self, p, d, correct, transition):
        return (1.0 if p > 0 else 0.0) if correct else (0.0 if p < 1 else 1.0)


def _chain_engine(n, model=None):
    concepts = tuple(Concept(f"K{i}", (f"K{i - 1}",) if i else ()) for i in range(n))
    acts = tuple(
        Activity(f"E-K{i}-{j}", ActivityType.EXERCISE, f"K{i}", 1, difficulty=0.5)
        for i in range(n)
        for j in range(3)
    )
    return Engine(concepts, acts, bisection_config(), model=model)


@pytest.mark.parametrize("cut", range(8))
def test_noiseless_chain_is_binary_search_f1_tc4(cut):
    e = _chain_engine(7, Noiseless())
    r = e.diagnose(e.init_learner(), lambda a: int(a.target_concept[1:]) < cut, session_id="t")
    assert r.total_items <= math.ceil(math.log2(8))
    assert set(r.info["top_state"]) == {f"K{i}" for i in range(cut)}
    assert r.info["top_state_p"] == 1.0


def _sim_run(e, seed, world="S0", **kw):
    sim = make_learner(e, seed, world, "nominal")
    return e.diagnose(
        e.init_learner(),
        lambda a: sim.respond(a.target_concept, a.activity_id, a.difficulty, "diag"),
        session_id=str(seed),
        **kw,
    )


@pytest.mark.parametrize("name", ["4node", "8node", "8node_x10"])
def test_budget_repeats_mutation_determinism_f1_tc2(name):
    e = _eng(name)
    for seed in range(101, 121, 2):
        state = e.init_learner()
        before = state
        r = _sim_run(e, seed)
        assert r.total_items == len(r.item_log) <= r.info["n_max"]
        ids = [x.activity_id for x in r.item_log]
        assert len(ids) == len(set(ids))
        assert state == before
        assert r == _sim_run(e, seed)
        for c, cr in r.concept_results.items():
            assert cr.n_items <= e.config.bisection_concept_cap
            asked = sum(x.concept_id == c for x in r.item_log)
            assert r.state.concepts[c].responses == asked
            assert (cr.stop_reason == StopReason.INFERRED) == (asked == 0)


def test_out_of_scope_untouched_tc2_2():
    e = _eng()
    init = e.init_learner()
    r = e.diagnose(init, lambda a: True, goal_concepts=["C4"], session_id="t")
    assert set(r.concept_results) == {"C1", "C2", "C3", "C4"}
    for c in ("C5", "C6", "C7", "C8"):
        assert r.state.concepts[c] == init.concepts[c]
    with pytest.raises(UnknownConceptError):
        e.diagnose(init, lambda a: True, goal_concepts=["C99"])


def test_advanced_first_question_is_mid_dag():
    e = _eng()
    r = e.diagnose(e.init_learner(), lambda a: True, session_id="t")
    first = r.item_log[0].concept_id
    assert first not in e.graph.roots()
    assert [x.concept_id for x in r.item_log] == ["C5", "C4", "C7", "C8"]  # F1.4.6
    assert r.concept_results["C1"].stop_reason == StopReason.INFERRED
    assert r.concept_results["C8"].stop_reason == StopReason.CONFIDENT


@pytest.mark.parametrize("name", ["8node", "8node_x10"])
def test_item_limit_is_a_prefix(name):
    e = _eng(name)
    full = _sim_run(e, 105)
    for n in range(full.total_items + 1):
        part = _sim_run(e, 105, item_limit=n)
        assert part.item_log == full.item_log[:n]


def test_budget_formula_f1_tc6():
    e = _eng()
    d = BisectionDiagnostic(e.graph, e.activities, e.config, e.model)
    items = [a for a in e.activities.values() if a.type == ActivityType.EXERCISE]
    best = max(
        item_information(
            0.5, e.model.predict_correct(1, a.difficulty), e.model.predict_correct(0, a.difficulty)
        )
        for a in items
    )
    n_max, q_bit = d.budget(math.log2(18), items, e.model)
    assert q_bit == pytest.approx(1 / best) and 2.4 < q_bit < 2.9
    assert n_max == math.ceil(math.log2(18) * q_bit)  # 11
    assert d.budget(1.0, items, e.model)[0] == 6  # floor
    assert d.budget(100.0, items, e.model)[0] == 32  # all 32 items, under the ceiling 40
    assert d.budget(100.0, items * 2, e.model)[0] == 40  # ceiling
    fit = _eng(model_profile="config/fitted_assist09.json")
    fd = BisectionDiagnostic(fit.graph, fit.activities, fit.config, fit.model)
    n_fit, q_fit = fd.budget(math.log2(18), items, fit.model)
    assert q_fit > q_bit and n_fit > n_max  # less information per answer -> bigger budget
    alpha = BisectionDiagnostic(e.graph, e.activities, replace_cfg(e.config, bisection_alpha=2.0))
    assert alpha.budget(math.log2(18), items, e.model) == (math.ceil(2 * math.log2(18)), 2.0)


def replace_cfg(cfg, **kw):
    return dataclasses.replace(cfg, **kw)


def test_fitted_profile_and_heuristic_both_work():
    for kw in ({}, {"model_profile": "config/fitted_assist09.json"}):
        e = _eng(**kw)
        r = _sim_run(e, 107)
        assert r.total_items <= r.info["n_max"] and r.info["mode"] == "exact"


def test_earlier_evidence_is_folded_in():
    e = _eng()
    init = e.init_learner()
    known = dataclasses.replace(init.concepts["C3"], p=0.95, responses=2, correct_responses=2)
    r0 = e.diagnose(init, lambda a: True, item_limit=0)
    r1 = e.diagnose(
        dataclasses.replace(init, concepts={**init.concepts, "C3": known}),
        lambda a: True,
        item_limit=0,
    )
    assert r1.state.concepts["C3"].p > r0.state.concepts["C3"].p
    assert r1.state.concepts["C1"].p > r0.state.concepts["C1"].p  # prerequisites move with it


def test_independent_p0_prior_arm():
    e = _eng(bisection_prior="independent_p0")
    r = e.diagnose(e.init_learner(), lambda a: True, item_limit=0)
    p = {c: x.p for c, x in r.state.concepts.items()}
    assert p["C8"] < 0.01 and p["C1"] < 0.3  # chained 0.20 per concept (Appendix A.7)


def test_sampling_mode_on_wide_dag():
    cp, ap = synth_paths("synth-50-x10")  # same generator and seed as the removed synth_curriculum
    e = Engine.from_files(cp, ap, config=bisection_config(), allow_unreviewed=True)
    r = _sim_run(e, 109)
    assert r.info["mode"] == "sampling" and r.info["n_states"] is None
    assert r.total_items <= r.info["n_max"] <= 40
    assert r == _sim_run(e, 109)
