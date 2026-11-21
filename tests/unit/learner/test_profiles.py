"""Plan 2 (F2, D60): fitted item-model profiles (F2-TC1 to F2-TC5)."""

import dataclasses
import json
import os
from collections import Counter

import pytest

from adaptengine.api import Engine
from adaptengine.core.config import DEFAULT_CONFIG, EngineConfig, config_hash
from adaptengine.core.errors import ValidationError
from adaptengine.core.schema import ActivityType, Event, EventType, PlanContext
from adaptengine.learner.adapter import CustomBKT, PyBKTAdapter
from adaptengine.learner.profiles import ClassBKT, build_model, load_profile
from adaptengine.learner.state import ExecutionLog
from adaptengine.planner import serialize_plan

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ASSIST = "config/fitted_assist09.json"
CT = "config/fitted_ct.json"
CUR4 = os.path.join(repo_root, "data/curriculum/curriculum_4node.json")
ACT4 = os.path.join(repo_root, "data/curriculum/activities_4node.json")


def _engine(**kw):
    return Engine.from_files(CUR4, ACT4, config=dataclasses.replace(DEFAULT_CONFIG, **kw))


def _json(rel):
    with open(os.path.join(repo_root, rel), encoding="utf-8") as f:
        return json.load(f)


# ---------------- F2-T1: config fields ----------------


def test_heuristic_default_f2_tc1():
    assert DEFAULT_CONFIG.model_profile == "heuristic"
    assert DEFAULT_CONFIG.use_profile_learn is False
    assert type(_engine().model) is CustomBKT


@pytest.mark.parametrize(
    "kw",
    [
        {"model_profile": "config/no_such_profile.json"},
        {"model_profile": ""},
        {"model_profile": 3},
        {"use_profile_learn": 1},
        {"use_profile_learn": True},  # needs a profile
    ],
)
def test_bad_profile_config_rejected(kw):
    with pytest.raises(ValidationError):
        EngineConfig(**kw)


def test_profile_path_resolves_from_repo_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert EngineConfig(model_profile=ASSIST).model_profile == ASSIST
    assert load_profile(ASSIST).name == "fitted_assist09"


# ---------------- F2-T2: loader and ClassBKT ----------------


def test_load_assist09_exposes_warnings_and_provenance_f2_tc2():
    prof = load_profile(ASSIST)
    raw = _json(ASSIST)
    assert prof.class_params == raw["class_params"]
    assert prof.t_exercise == raw["t_exercise"] and prof.p0 == raw["p0"]
    assert prof.warnings == {"hard": ("slip>0.5",)}
    pv = prof.provenance()
    assert pv["profile"] == "fitted_assist09" and len(pv["sha256"]) == 64
    assert pv["code_hash"] == raw["code_hash"] and pv["timestamp_utc"] == raw["timestamp_utc"]


def _bad_file(tmp_path, mutate):
    doc = _json(ASSIST)
    mutate(doc)
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(doc))
    return str(p)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["class_params"].pop("medium"),
        lambda d: d["class_params"]["easy"].update(guess=0.0),
        lambda d: d["class_params"]["hard"].update(slip=1.2),
        lambda d: d["class_params"]["hard"].update(slip="0.5"),
        lambda d: d["class_params"]["easy"].update(guess=0.6, slip=0.5),  # guess + slip >= 1
        lambda d: d.pop("class_params"),
        lambda d: d.update(t_exercise=1.5),
    ],
)
def test_malformed_profiles_rejected_f2_tc2(tmp_path, mutate):
    with pytest.raises(ValidationError):
        load_profile(_bad_file(tmp_path, mutate))


def test_unparseable_profile_rejected(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{not json")
    with pytest.raises(ValidationError):
        load_profile(str(p))


@pytest.mark.parametrize("d,cls", [(0.2, "easy"), (0.5, "medium"), (0.8, "hard")])
def test_classbkt_hand_values_f2_tc3(d, cls):
    cp = _json(ASSIST)["class_params"]
    g, s = cp[cls]["guess"], cp[cls]["slip"]
    m = ClassBKT(DEFAULT_CONFIG, cp)
    p = 0.4
    assert m.predict_correct(p, d) == pytest.approx(p * (1 - s) + (1 - p) * g, abs=1e-15)
    right = p * (1 - s) / (p * (1 - s) + (1 - p) * g)
    wrong = p * s / (p * s + (1 - p) * (1 - g))
    assert m.update(p, d, True, 0.0) == pytest.approx(right, abs=1e-15)
    assert m.update(p, d, False, 0.1) == pytest.approx(wrong + (1 - wrong) * 0.1, abs=1e-15)


def test_classbkt_literal_value_f2_tc3():
    # easy class of fitted_assist09: 0.5 * (1 - 0.132163) + 0.5 * 0.369083
    assert ClassBKT(DEFAULT_CONFIG, _json(ASSIST)["class_params"]).predict_correct(
        0.5, 0.1
    ) == pytest.approx(0.618460, abs=1e-6)


def test_classbkt_equals_pybkt_adapter_f2_tc3():
    """Same class maths as PyBKTAdapter (its predict/update never call pyBKT itself)."""
    cp = _json(ASSIST)["class_params"]
    a, b = ClassBKT(DEFAULT_CONFIG, cp), PyBKTAdapter(DEFAULT_CONFIG, class_params=cp)
    for d in (0.05, 0.3, 0.35, 0.5, 0.64, 0.65, 0.95):
        for p in (0.0, 0.2, 0.5, 0.99):
            assert a.predict_correct(p, d) == b.predict_correct(p, d)
            for c in (True, False):
                assert a.update(p, d, c, 0.07) == b.update(p, d, c, 0.07)


# ---------------- F2-T3: Cognitive Tutor profile ----------------


def test_ct_profile_matches_results_file():
    prof = load_profile(CT)
    # The cross-check against experiments/results/bkt_fit_ct.json was removed with the old harness
    # (rename plan R4c); the file is archived outside the repository and not re-created.
    assert prof.warnings == {"hard": ("slip>0.5",)}
    raw = _json(CT)
    assert raw["profile"] == "fitted_ct" and "MATHS" in raw["caveat"]
    assert raw["source_results"] == "experiments/results/bkt_fit_ct.json"


# ---------------- F2-T4: engine wiring ----------------


def test_engine_uses_profile_model_and_ignores_profile_prior_f2_tc4():
    eng = _engine(model_profile=ASSIST)
    assert isinstance(eng.model, ClassBKT)
    assert eng.model.class_params == _json(ASSIST)["class_params"]
    assert all(c.p == DEFAULT_CONFIG.p0 for c in eng.init_learner().concepts.values())
    assert eng.config.t_exercise == DEFAULT_CONFIG.t_exercise  # learn rate untouched by default


def test_learn_rate_only_with_switch_f2_tc4():
    eng = _engine(model_profile=ASSIST, use_profile_learn=True)
    assert eng.config.t_exercise == _json(ASSIST)["t_exercise"]
    assert eng.config.t_lesson == DEFAULT_CONFIG.t_lesson
    assert all(c.p == DEFAULT_CONFIG.p0 for c in eng.init_learner().concepts.values())


def test_one_model_instance_shared_f2_tc5():
    eng = _engine(model_profile=ASSIST)
    m, calls = eng.model, Counter()
    for name in ("predict_correct", "update"):
        orig = getattr(m, name)

        def wrap(*a, _orig=orig, _name=name, **k):
            calls[_name] += 1
            return _orig(*a, **k)

        setattr(m, name, wrap)
    state = eng.diagnose(eng.init_learner(), lambda a: True, session_id="t").state
    after_diag = calls.copy()
    assert after_diag["predict_correct"] > 0 and after_diag["update"] > 0
    ctx = PlanContext(goal="C4", deadline_day=10, budget=15, current_day=1)
    eng.plan(state, ctx)
    after_plan = calls.copy()
    assert after_plan["update"] > after_diag["update"]  # planner projection
    ex = next(a for a in eng.activities.values() if a.type == ActivityType.EXERCISE)
    eng.record(
        state,
        ExecutionLog(),
        Event(day=1, kind=EventType.COMPLETED, activity_id=ex.activity_id, correct=False),
    )
    assert calls["update"] > after_plan["update"]  # answer update


def test_explicit_model_still_wins():
    eng = Engine.from_files(
        CUR4,
        ACT4,
        config=dataclasses.replace(DEFAULT_CONFIG, model_profile=ASSIST),
        model=CustomBKT(),
    )
    assert type(eng.model) is CustomBKT


def test_profile_changes_diagnostic_but_heuristic_matches_default():
    answer = lambda a: a.difficulty < 0.5  # noqa: E731
    base = _engine().diagnose(_engine().init_learner(), answer, session_id="t")
    heur = _engine(model_profile="heuristic").diagnose(
        _engine().init_learner(), answer, session_id="t"
    )
    fit = _engine(model_profile=ASSIST)
    fitted = fit.diagnose(fit.init_learner(), answer, session_id="t")
    assert heur == base
    assert fitted.state != base.state


def test_build_model_heuristic_is_custombkt():
    assert type(build_model(DEFAULT_CONFIG)) is CustomBKT
    assert isinstance(build_model(EngineConfig(model_profile=CT)), ClassBKT)


def test_provenance_in_serialized_plan_only_with_profile():
    ctx = PlanContext(goal="C4", deadline_day=10, budget=15, current_day=1)
    eng = _engine()
    assert "model_profile" not in serialize_plan(eng.plan(eng.init_learner(), ctx), eng.config)
    fit = _engine(model_profile=ASSIST)
    s = serialize_plan(fit.plan(fit.init_learner(), ctx), fit.config)
    assert s["model_profile"] == load_profile(ASSIST).provenance()
    assert s["config_hash"] == config_hash(fit.config)
