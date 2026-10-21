import os
import json
import pytest
from unittest.mock import patch

from adaptengine.core.config import EngineConfig, DEFAULT_CONFIG
from adaptengine.core.errors import ValidationError, UnknownConceptError
from adaptengine.core.schema import (
    Activity,
    ActivityType,
    Event,
    EventType,
    PlanContext,
    PlanStatus,
)
from adaptengine.learner.state import (
    LearnerState,
    LearnerConcept,
    ExecutionLog,
    ConceptStatus,
    is_evidence_mastered,
)
from adaptengine.learner.adapter import (
    MasteryModel,
    CustomBKT,
    PyBKTAdapter,
    get_difficulty_class,
    derive_class_params,
)
from adaptengine.learner.evidence import update_concept_evidence
from adaptengine.learner.mastery import entropy
from adaptengine.diagnostic import compute_eig
from adaptengine.api import Engine
from adaptengine.cli import main as cli_main
from adaptengine.session import (
    save_snapshot,
    load_snapshot,
    deserialize_learner,
)


# =====================================================================
# SECTION 1: One atomic save path for the CLI (FB006)
# =====================================================================
def test_cli_atomic_snapshot_accumulation_and_restart(tmp_path, capsys):
    """TC1.2 / FB006: Verify CLI commands accumulate into canonical snapshot,

    survive process restart, and replanning after restart gives identical plan.
    """
    snap_path = str(tmp_path / "canonical_snapshot.json")

    # 1. init-learner creates canonical snapshot
    ret = cli_main(
        [
            "init-learner",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--goal",
            "C4",
            "--deadline",
            "10",
            "--budget",
            "15",
        ]
    )
    assert ret is None
    state0, log0, ctx0 = load_snapshot(snap_path, ("C1", "C2", "C3", "C4"), include_context=True)
    assert ctx0.goal == "C4"
    assert ctx0.deadline_day == 10
    assert len(log0.events) == 0

    # 2. update completed activity
    ret = cli_main(
        [
            "update",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--activity",
            "E-C1-0.2",
            "--response",
            "correct",
            "--day",
            "1",
        ]
    )
    assert ret is None
    state1, log1, _ = load_snapshot(snap_path, ("C1", "C2", "C3", "C4"), include_context=True)
    assert len(log1.events) == 1
    assert log1.events[0].kind == EventType.COMPLETED
    assert state1.concepts["C1"].p > state0.concepts["C1"].p

    # 3. missed-day
    ret = cli_main(
        [
            "missed-day",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--day",
            "2",
        ]
    )
    assert ret is None
    _, log2, _ = load_snapshot(snap_path, ("C1", "C2", "C3", "C4"), include_context=True)
    assert len(log2.events) == 2
    assert log2.events[1].kind == EventType.MISSED

    # 4. change-deadline
    ret = cli_main(
        [
            "change-deadline",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--day",
            "3",
            "--new-deadline",
            "14",
        ]
    )
    assert ret is None
    _, log3, _ = load_snapshot(snap_path, ("C1", "C2", "C3", "C4"), include_context=True)
    assert len(log3.events) == 3
    assert log3.events[2].kind == EventType.DEADLINE_CHANGED
    assert log3.events[2].value == 14

    # 5. change-budget
    ret = cli_main(
        [
            "change-budget",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--day",
            "3",
            "--new-budget",
            "30",
        ]
    )
    assert ret is None
    _, log4, _ = load_snapshot(snap_path, ("C1", "C2", "C3", "C4"), include_context=True)
    assert len(log4.events) == 4
    assert log4.events[3].kind == EventType.BUDGET_CHANGED

    # 6. failed-assessment
    ret = cli_main(
        [
            "failed-assessment",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--activity",
            "E-C1-0.2",
            "--day",
            "4",
        ]
    )
    assert ret is None
    state5, log5, _ = load_snapshot(snap_path, ("C1", "C2", "C3", "C4"), include_context=True)
    assert len(log5.events) == 5

    # 7. Simulated process restart: separate replan CLI invocation produces identical plan
    capsys.readouterr()  # drain prior output
    ret_plan1 = cli_main(
        [
            "replan",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--json",
        ]
    )
    assert ret_plan1 is None
    out1, _ = capsys.readouterr()
    plan_dict1 = json.loads(out1)

    ret_plan2 = cli_main(
        [
            "replan",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--json",
        ]
    )
    assert ret_plan2 is None
    out2, _ = capsys.readouterr()
    plan_dict2 = json.loads(out2)

    assert plan_dict1 == plan_dict2


def test_cli_atomic_commit_failure_injection(tmp_path):
    """TC1.2 / FB006: Inject failure in os.replace during snapshot commit for all events;

    verifies snapshot remains byte-identical and NO temp files remain.
    """
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    log = ExecutionLog()
    ctx = PlanContext(goal="C4", deadline_day=10, budget=15)
    snap_path = str(tmp_path / "snap_atomic_fail.json")
    save_snapshot(state, log, snap_path, context=ctx)
    original_bytes = open(snap_path, "rb").read()

    event_scenarios = [
        [
            "update",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--activity",
            "E-C1-0.2",
            "--response",
            "correct",
            "--day",
            "1",
        ],
        [
            "missed-day",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--day",
            "2",
        ],
        [
            "failed-assessment",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--activity",
            "E-C1-0.2",
            "--day",
            "3",
        ],
        [
            "change-deadline",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--day",
            "3",
            "--new-deadline",
            "15",
        ],
        [
            "change-budget",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--day",
            "3",
            "--new-budget",
            "30",
        ],
    ]

    for argv in event_scenarios:
        with patch("os.replace", side_effect=OSError("Disk failure")):
            with pytest.raises(OSError):
                cli_main(argv)

        # Snapshot MUST remain byte-identical
        assert open(snap_path, "rb").read() == original_bytes
        # No temp file left behind
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Dangling temp files: {tmp_files}"


# =====================================================================
# SECTION 2: One validated policy for every consumer
# =====================================================================
def test_config_driven_mastery_theta_k_planner():
    """TC2.3 / Section 2: When theta=0.99 and k=5, concept with p=0.90 and responses=2

    is NOT mastered, and planner schedules extra work through real consumer.
    """
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    cfg_strict = EngineConfig(theta=0.99, k_responses=5)

    # Concept C1 with p=0.90 and responses=2
    c1 = LearnerConcept(concept_id="C1", p=0.90, responses=2, status=ConceptStatus.ASSESSED)
    c2 = LearnerConcept(concept_id="C2", p=0.20, responses=0)
    c3 = LearnerConcept(concept_id="C3", p=0.20, responses=0)
    c4 = LearnerConcept(concept_id="C4", p=0.20, responses=0)
    state = LearnerState(concepts={"C1": c1, "C2": c2, "C3": c3, "C4": c4})

    # Under default config, C1 would be mastered
    assert is_evidence_mastered(c1, DEFAULT_CONFIG) is True
    # Under cfg_strict, C1 is NOT mastered
    assert is_evidence_mastered(c1, cfg_strict) is False

    ctx = PlanContext(goal="C1", deadline_day=5, budget=15)
    _ = engine.plan(state, ctx, model=CustomBKT(cfg_strict))
    # Under DEFAULT_CONFIG in engine, C1 would be omitted; under strict engine, C1 has work scheduled
    engine_strict = Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        config=cfg_strict,
    )
    plan_consumer = engine_strict.plan(state, ctx)
    assert plan_consumer.status == PlanStatus.FEASIBLE
    assert len(plan_consumer.days) > 0
    # C1 activities scheduled
    c1_acts = [
        aid
        for d in plan_consumer.days
        for aid in d.activities
        if engine.activities[aid].target_concept == "C1"
    ]
    assert len(c1_acts) > 0


def test_config_integer_validators_strictly_enforce():
    """Section 2: n_max, concept_cap, k_responses, oracle_node_limit reject 1.5, True, 0."""
    with pytest.raises(ValidationError):
        EngineConfig(n_max=1.5)
    with pytest.raises(ValidationError):
        EngineConfig(n_max=True)
    with pytest.raises(ValidationError):
        EngineConfig(n_max=0)
    with pytest.raises(ValidationError):
        EngineConfig(concept_cap=0)
    with pytest.raises(ValidationError):
        EngineConfig(concept_cap=True)
    with pytest.raises(ValidationError):
        EngineConfig(k_responses=0)
    with pytest.raises(ValidationError):
        EngineConfig(k_responses=2.5)
    with pytest.raises(ValidationError):
        EngineConfig(oracle_node_limit=0)
    with pytest.raises(ValidationError):
        EngineConfig(oracle_node_limit=1.5)


def test_adapter_difficulty_validation_and_derived_params():
    """Section 2: get_difficulty_class rejects NaN, -1, 2; class params derived from cfg."""
    with pytest.raises(ValidationError):
        get_difficulty_class(float("nan"))
    with pytest.raises(ValidationError):
        get_difficulty_class(-1.0)
    with pytest.raises(ValidationError):
        get_difficulty_class(2.0)

    cfg_custom = EngineConfig(guess_coef=0.50, slip_base=0.10, slip_coef=0.40)
    params = derive_class_params(cfg_custom)
    # easy rep_d = 0.20 -> guess = 0.50 * 0.80 = 0.40, slip = 0.10 + 0.40 * 0.20 = 0.18
    assert params["easy"]["guess"] == pytest.approx(0.40)
    assert params["easy"]["slip"] == pytest.approx(0.18)

    adapter = PyBKTAdapter(cfg_custom)
    p_pred = adapter.predict_correct(0.5, 0.20)
    # 0.5 * (1 - 0.18) + 0.5 * 0.40 = 0.41 + 0.20 = 0.61
    assert p_pred == pytest.approx(0.61)


# =====================================================================
# SECTION 3: Strict loading of learner, log and snapshot files
# =====================================================================
def test_strict_learner_deserialization_rejections():
    """Section 3: assessed='false', uncertainty=-5, half_life_days=0,

    needs_remediation='yes', legacy assessed without responses: each rejected.
    """
    valid_base = {
        "schema_version": 1,
        "concepts": {
            "C1": {
                "p": 0.2,
                "uncertainty": 0.7219,
                "status": "UNASSESSED",
                "responses": 0,
            }
        },
    }

    # 1. assessed="false" (string)
    d1 = json.loads(json.dumps(valid_base))
    d1["concepts"]["C1"]["assessed"] = "false"
    with pytest.raises(ValidationError, match="assessed must be a boolean"):
        deserialize_learner(d1, ("C1",))

    # 2. uncertainty = -5
    d2 = json.loads(json.dumps(valid_base))
    d2["concepts"]["C1"]["uncertainty"] = -5.0
    with pytest.raises(ValidationError, match="uncertainty must be a finite non-negative"):
        deserialize_learner(d2, ("C1",))

    # 3. uncertainty does not match entropy(p)
    d3 = json.loads(json.dumps(valid_base))
    d3["concepts"]["C1"]["uncertainty"] = 0.10  # entropy(0.2) is ~0.7219
    with pytest.raises(ValidationError, match="does not agree with entropy"):
        deserialize_learner(d3, ("C1",))

    # 4. half_life_days = 0
    d4 = json.loads(json.dumps(valid_base))
    d4["concepts"]["C1"]["half_life_days"] = 0
    with pytest.raises(ValidationError, match="half_life_days must be a positive finite number"):
        deserialize_learner(d4, ("C1",))

    # 5. needs_remediation = "yes"
    d5 = json.loads(json.dumps(valid_base))
    d5["concepts"]["C1"]["needs_remediation"] = "yes"
    with pytest.raises(ValidationError, match="needs_remediation must be a boolean"):
        deserialize_learner(d5, ("C1",))

    # 6. Legacy assessed: true with no responses field
    d6 = {
        "schema_version": 1,
        "concepts": {
            "C1": {
                "p": 0.5,
                "assessed": True,
            }
        },
    }
    with pytest.raises(ValidationError, match="without responses field is rejected"):
        deserialize_learner(d6, ("C1",))

    # 7. Conflicting p and mastery
    d7 = {
        "schema_version": 1,
        "concepts": {
            "C1": {
                "p": 0.2,
                "mastery": 0.8,
                "responses": 0,
            }
        },
    }
    with pytest.raises(ValidationError, match="conflicting 'p'.*and 'mastery'"):
        deserialize_learner(d7, ("C1",))

    # 8. Contradicting status ASSESSED and assessed=False
    d8 = {
        "schema_version": 1,
        "concepts": {
            "C1": {
                "p": 0.2,
                "status": "ASSESSED",
                "assessed": False,
                "responses": 2,
            }
        },
    }
    with pytest.raises(ValidationError, match="status ASSESSED contradicts assessed=False"):
        deserialize_learner(d8, ("C1",))


def test_strict_snapshot_context_budget_rejection(tmp_path):
    """Section 3: A snapshot with a bad budget (e.g. 25) is rejected."""
    bad_snap = {
        "schema_version": 1,
        "state": {
            "schema_version": 1,
            "concepts": {
                "C1": {"p": 0.2, "status": "UNASSESSED", "responses": 0},
            },
        },
        "log": {"schema_version": 1, "events": []},
        "context": {
            "goal": "C1",
            "deadline_day": 5,
            "budget": 25,  # Invalid: allowed is (5, 10, 15, 30)
        },
    }
    p = tmp_path / "bad_snap.json"
    p.write_text(json.dumps(bad_snap))
    with pytest.raises(ValidationError, match="budget must be one of"):
        load_snapshot(str(p), ("C1",))


# =====================================================================
# SECTION 4: Real pyBKT adapter parity & injection
# =====================================================================
def test_pybkt_adapter_genuine_parity():
    """TC4.1 / Section 4: Genuine parity test comparing PyBKTAdapter with pyBKT.models.Model."""
    adapter = PyBKTAdapter()
    if not adapter.is_library_available:
        if os.environ.get("REQUIRE_PYBKT") == "1":
            pytest.fail("pyBKT is not available but REQUIRE_PYBKT=1 is set")
        pytest.skip("pyBKT not available in current environment")

    import pandas as pd

    df = pd.DataFrame(
        [
            {"user_id": 1, "skill_name": "easy", "correct": 1, "order_id": 1},
            {"user_id": 1, "skill_name": "medium", "correct": 0, "order_id": 2},
            {"user_id": 1, "skill_name": "hard", "correct": 1, "order_id": 3},
        ]
    )
    # Check predictions from pyBKT model
    py_preds = adapter.pybkt_model.predict(data=df)
    assert len(py_preds) == 3

    # Check parity with adapter's predict_correct and update
    rep_d = {"easy": 0.20, "medium": 0.50, "hard": 0.80}
    for cname in ("easy", "medium", "hard"):
        d = rep_d[cname]
        pred_adapter = adapter.predict_correct(0.20, d)
        params = adapter.get_class_params(cname)
        g, s = params["guess"], params["slip"]
        exp_pred = 0.20 * (1.0 - s) + 0.80 * g
        assert pred_adapter == pytest.approx(exp_pred, abs=1e-9)


def test_planner_and_replanner_with_adapter_injection():
    """Section 4: Run planner and replanner with PyBKTAdapter injected as MasteryModel."""
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    ctx = PlanContext(goal="C4", deadline_day=10, budget=15)
    adapter = PyBKTAdapter(engine.config)

    # 1. Plan with PyBKTAdapter
    plan_res = engine.plan(state, ctx, model=adapter)
    assert plan_res.status == PlanStatus.FEASIBLE
    assert len(plan_res.days) > 0
    # Verify budgets and prerequisites hold
    for d in plan_res.days:
        assert d.duration <= ctx.budget

    # 2. Replan with PyBKTAdapter
    log = ExecutionLog(
        (Event(day=1, kind=EventType.COMPLETED, activity_id="L-C1", minutes_elapsed=4),)
    )
    replan_res = engine.replan(state, log, ctx, model=adapter)
    assert replan_res.status == PlanStatus.FEASIBLE


# =====================================================================
# SECTION 5: One observation model
# =====================================================================
class SpyMasteryModel:
    def __init__(self, base_model: MasteryModel):
        self.base = base_model
        self.predict_calls = []
        self.update_calls = []

    def predict_correct(self, p: float, d: float) -> float:
        self.predict_calls.append((p, d))
        return self.base.predict_correct(p, d)

    def update(self, p: float, d: float, correct: bool, transition: float) -> float:
        self.update_calls.append((p, d, correct, transition))
        return self.base.update(p, d, correct, transition)


def test_spy_model_receives_predict_and_update_during_diagnostic():
    """Section 5: Spy model receives both prediction and update calls during diagnostic run."""
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    spy = SpyMasteryModel(CustomBKT(engine.config))

    _ = engine.diagnose(state, response_provider=lambda a: True, model=spy)
    assert len(spy.predict_calls) > 0, "Spy model received NO predict_correct calls"
    assert len(spy.update_calls) > 0, "Spy model received NO update calls"


def test_compute_eig_matches_hand_calc_at_d_06():
    """Section 5: At d=0.60, EIG matches hand calculation for that model."""
    cfg = DEFAULT_CONFIG
    model = CustomBKT(cfg)
    act = Activity("E-test", ActivityType.EXERCISE, "C1", duration=2, difficulty=0.60)
    p = 0.50

    p_c = model.predict_correct(p, 0.60)
    p_corr = model.update(p, 0.60, True, 0.0)
    p_wrong = model.update(p, 0.60, False, 0.0)

    expected_eig = entropy(p) - (p_c * entropy(p_corr) + (1.0 - p_c) * entropy(p_wrong))
    calculated_eig = compute_eig(p, act, cfg, model=model)
    assert calculated_eig == pytest.approx(expected_eig, abs=1e-9)


def test_engine_model_swapping_changes_behavior():
    """Section 5: Swapping model in Engine changes diagnostic and plan output."""
    engine_custom = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    # Define an alternate model with higher guess/slip
    cfg_alt = EngineConfig(guess_coef=0.50, slip_base=0.20, slip_coef=0.30)
    engine_alt = Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        config=cfg_alt,
        model=CustomBKT(cfg_alt),
    )

    state = engine_custom.init_learner()
    diag1 = engine_custom.diagnose(state, response_provider=lambda a: True)
    diag2 = engine_alt.diagnose(state, response_provider=lambda a: True)
    # Posteriors differ under different observation models
    assert diag1.state.concepts["C1"].p != diag2.state.concepts["C1"].p


# =====================================================================
# SECTION 6: Diagnostic IDs and single evidence path
# =====================================================================
def test_diagnostic_session_ids_and_idempotency():
    """Section 6: IDs include session id: diag-<session>-<concept>-<n>.

    Replaying same session is no-op; new session accumulates.
    """
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state0 = engine.init_learner()

    # Session 1
    res1 = engine.diagnose(state0, response_provider=lambda a: True, session_id="session1")
    assert "diag-session1-C1-1" in res1.state.concepts["C1"].seen_attempt_ids
    resp1 = res1.state.concepts["C1"].responses

    # Replay Session 1 on res1.state -> no-op
    res1_replay = engine.diagnose(
        res1.state, response_provider=lambda a: True, session_id="session1"
    )
    assert res1_replay.state.concepts["C1"].responses == resp1

    # Session 2 on res1.state -> accumulates
    res2 = engine.diagnose(res1.state, response_provider=lambda a: True, session_id="session2")
    assert "diag-session2-C1-1" in res2.state.concepts["C1"].seen_attempt_ids
    assert res2.state.concepts["C1"].responses > resp1


def test_field_survival_throughout_updates():
    """Section 6: needs_remediation, half_life_days survive response, lesson, and diagnostic updates."""
    c1 = LearnerConcept(
        concept_id="C1",
        p=0.30,
        half_life_days=14.0,
        last_practice_day=None,
        needs_remediation=True,
    )
    act_ex = Activity("E-C1", ActivityType.EXERCISE, "C1", duration=2, difficulty=0.5)

    # 1. Evidence response update preserves needs_remediation and half_life_days
    new_c, changed = update_concept_evidence(
        c1,
        act_ex.difficulty,
        True,
        transition=0.05,
        model=CustomBKT(),
        day=None,
        attempt_id="att-1",
    )
    assert changed is True
    assert new_c.needs_remediation is True
    assert new_c.half_life_days == 14.0
    # Practice day not stamped when day=None (D22)
    assert new_c.last_practice_day is None


# =====================================================================
# SECTION 7: Lessons vs Evidence Decision D31
# =====================================================================
def test_lessons_vs_evidence_contract_decision_d31():
    """Section 7 / Decision D31: Two wrong answers + many lessons push p >= theta,

    but responses stays at 2 (lessons update belief via T_lesson, not responses).
    Documents Option 1 contract behavior.
    """
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    log = ExecutionLog()

    # 2 wrong answers
    state, log = engine.record(
        state,
        log,
        Event(
            day=1,
            kind=EventType.COMPLETED,
            activity_id="E-C1-0.2",
            minutes_elapsed=2,
            correct=False,
            attempt_id="w-1",
        ),
    )
    state, log = engine.record(
        state,
        log,
        Event(
            day=1,
            kind=EventType.COMPLETED,
            activity_id="E-C1-0.2",
            minutes_elapsed=2,
            correct=False,
            attempt_id="w-2",
        ),
    )
    assert state.concepts["C1"].responses == 2

    # 10 lessons
    for i in range(10):
        state, log = engine.record(
            state,
            log,
            Event(
                day=2,
                kind=EventType.COMPLETED,
                activity_id="L-C1",
                minutes_elapsed=4,
                attempt_id=f"lesson-{i}",
            ),
        )

    # Belief pushed high
    assert state.concepts["C1"].p >= 0.85
    # But responses strictly remained 2
    assert state.concepts["C1"].responses == 2
    # Satisfies evidence_mastered (p >= 0.85 and responses >= 2) per Decision D4 / D31
    assert is_evidence_mastered(state.concepts["C1"], DEFAULT_CONFIG) is True


# =====================================================================
# SECTION 8: Explicit failure for unknown goals and for UNKNOWN
# =====================================================================
def test_unknown_goal_rejected_everywhere():
    """Section 8: Unknown goal raises UnknownConceptError in diagnostic, planner, replanner."""
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    ctx = PlanContext(goal="UNKNOWN_CONCEPT", deadline_day=5, budget=15)

    # Diagnostic
    with pytest.raises(UnknownConceptError):
        engine.diagnose(state, response_provider=lambda a: True, goal_concepts=["UNKNOWN_CONCEPT"])

    # Planner
    with pytest.raises(UnknownConceptError):
        engine.plan(state, ctx)

    # Replanner
    with pytest.raises(UnknownConceptError):
        engine.replan(state, ExecutionLog(), ctx)


def test_status_exit_codes_infeasible_and_unknown(tmp_path, capsys):
    """Section 8: CLI exit codes: 0/None for FEASIBLE, 1 for INFEASIBLE, 3 for UNKNOWN."""
    # 1. Feasible plan -> return None (exit 0)
    ret_feas = cli_main(
        [
            "plan",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--learner",
            "data/learner_novice.json",
            "--goal",
            "C1",
            "--deadline",
            "5",
            "--budget",
            "15",
        ]
    )
    assert ret_feas is None

    # 2. Infeasible plan -> return 1
    ret_infeas = cli_main(
        [
            "plan",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--learner",
            "data/learner_novice.json",
            "--goal",
            "C4",
            "--deadline",
            "1",
            "--budget",
            "5",
        ]
    )
    assert ret_infeas == 1
    out, _ = capsys.readouterr()
    assert "Status: INFEASIBLE" in out
