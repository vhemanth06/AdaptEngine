import pytest
import json
from adaptengine.api import Engine
from adaptengine.core.config import config_hash
from adaptengine.core.schema import (
    Event,
    EventType,
    PlanContext,
    PlanStatus,
    ActivityType,
)
from adaptengine.learner.state import (
    LearnerConcept,
    LearnerState,
    ExecutionLog,
    ConceptStatus,
)
from adaptengine.planner.plan import serialize_plan


# =====================================================================
# TC5.1: Mastered concept omitted from new learning; trace cites evidence
# =====================================================================
def test_tc5_1_mastered_concept_omitted_from_new_learning():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    # C1 is evidence-mastered (p >= 0.85, responses >= 2)
    c1 = LearnerConcept(
        concept_id="C1",
        p=0.90,
        responses=3,
        correct_responses=3,
        status=ConceptStatus.ASSESSED,
        last_practice_day=1,
    )
    state = LearnerState(
        concepts={
            "C1": c1,
            "C2": LearnerConcept("C2"),
            "C3": LearnerConcept("C3"),
            "C4": LearnerConcept("C4"),
        }
    )

    ctx = PlanContext(goal="C4", deadline_day=10, budget=10)
    p = engine.plan(state, ctx)

    assert p.status == PlanStatus.FEASIBLE

    # 1. No new learning activity for C1 scheduled in plan days
    all_scheduled = [aid for d in p.days for aid in d.activities]
    c1_acts = [aid for aid in all_scheduled if engine.activities[aid].target_concept == "C1"]
    assert len(c1_acts) == 0

    # 2. Trace cites omission with p and responses
    omitted_c1 = [
        t for t in p.trace if t.get("decision") == "OMITTED" and t.get("concept_id") == "C1"
    ]
    assert len(omitted_c1) == 1
    om_rec = omitted_c1[0]
    assert om_rec["reason"] in ("ALREADY_EVIDENCE_MASTERED", "EVIDENCE_MASTERED")
    assert om_rec["p"] == pytest.approx(0.90)
    assert om_rec["responses"] == 3


# =====================================================================
# TC5.2: Failed exercise leaves p < 0.40: remediation lesson inserted
# =====================================================================
def test_tc5_2_failed_exercise_remediation_flag_and_lesson():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    # Start after first lesson where p=0.36
    c1 = LearnerConcept(
        concept_id="C1",
        p=0.36,
        lessons_done=1,
        responses=0,
        last_practice_day=1,
    )
    state = LearnerState(
        concepts={
            "C1": c1,
            "C2": LearnerConcept("C2"),
            "C3": LearnerConcept("C3"),
            "C4": LearnerConcept("C4"),
        }
    )
    log = ExecutionLog(
        (
            Event(
                day=1,
                kind=EventType.COMPLETED,
                activity_id="L-C1",
                minutes_elapsed=4,
            ),
        )
    )

    # Wrong answer on E-C1-0.2 (d=0.2): posterior drops to ~0.116 (< 0.40)
    event_fail = Event(
        day=2,
        kind=EventType.COMPLETED,
        activity_id="E-C1-0.2",
        minutes_elapsed=1,
        correct=False,
    )
    state_after_fail, log_after_fail = engine.record(state, log, event_fail)

    # State updated: p < 0.40 and needs_remediation is True
    assert state_after_fail.concepts["C1"].p < 0.40
    assert state_after_fail.concepts["C1"].needs_remediation is True

    # Plan towards C1 (or C4): remediation lesson L-C1 inserted first
    ctx = PlanContext(goal="C1", deadline_day=5, budget=10, current_day=3)
    done_ids = log_after_fail.completed_ids()
    p = engine.plan(state_after_fail, ctx, done_ids=done_ids)

    assert p.status == PlanStatus.FEASIBLE
    assert len(p.days) > 0
    # First activity scheduled is the repeat remediation lesson L-C1
    first_act_id = p.days[0].activities[0]
    assert first_act_id == "L-C1"

    # Trace logs remediation insertion
    rem_traces = [t for t in p.trace if t.get("reason") == "REMEDIATION_INSERTED"]
    assert len(rem_traces) > 0

    # Simulate completing the remediation lesson L-C1
    event_rem_done = Event(
        day=3,
        kind=EventType.COMPLETED,
        activity_id="L-C1",
        minutes_elapsed=4,
    )
    state_after_rem, _ = engine.record(state_after_fail, log_after_fail, event_rem_done)
    # needs_remediation flag must be cleared
    assert state_after_rem.concepts["C1"].needs_remediation is False


# =====================================================================
# TC5.3: High urgency with spare capacity: review before lower-urgency new content
# =====================================================================
def test_tc5_3_high_urgency_review_scheduled_before_new_content():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    # C1 was mastered on day 1 with a short half life (h=2.0)
    # Planning from current_day=5: dt = 4 = 2h -> r = 0.25 (< 0.80) -> review due!
    c1 = LearnerConcept(
        concept_id="C1",
        p=0.90,
        responses=2,
        correct_responses=2,
        status=ConceptStatus.ASSESSED,
        last_practice_day=1,
        half_life_days=2.0,
    )
    # C2 has not been started
    state = LearnerState(
        concepts={
            "C1": c1,
            "C2": LearnerConcept("C2"),
            "C3": LearnerConcept("C3"),
            "C4": LearnerConcept("C4"),
        }
    )

    ctx = PlanContext(goal="C2", deadline_day=10, budget=15, current_day=5)
    p = engine.plan(state, ctx)

    assert p.status == PlanStatus.FEASIBLE
    assert len(p.days) > 0
    day5 = p.days[0]

    # C1 review exercise must be scheduled on day 5 BEFORE C2 new lesson
    assert len(day5.activities) >= 2
    first_act = day5.activities[0]
    assert engine.activities[first_act].target_concept == "C1"
    assert engine.activities[first_act].type == ActivityType.EXERCISE

    # Trace includes REVIEW_DUE for C1
    rev_due_traces = [
        t for t in p.trace if t.get("decision") == "REVIEW_DUE" and t.get("concept_id") == "C1"
    ]
    assert len(rev_due_traces) > 0
    assert rev_due_traces[0]["r"] == pytest.approx(0.25)


# =====================================================================
# TC6.1: Missed day triggers valid replan without lost or duplicated work
# =====================================================================
def test_tc6_1_missed_day_replan_no_loss_or_duplication():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    log = ExecutionLog()
    initial_ctx = PlanContext(goal="C4", deadline_day=15, budget=10, current_day=1)

    # Day 1: Learner completes lesson L-C1 and exercise E-C1-0.2
    ev1 = Event(day=1, kind=EventType.COMPLETED, activity_id="L-C1", minutes_elapsed=4)
    state, log = engine.record(state, log, ev1)
    ev2 = Event(
        day=1, kind=EventType.COMPLETED, activity_id="E-C1-0.2", minutes_elapsed=1, correct=True
    )
    state, log = engine.record(state, log, ev2)

    # Day 2: Missed day
    ev_missed = Event(day=2, kind=EventType.MISSED)
    state, log = engine.record(state, log, ev_missed)

    assert len(log.events) == 3
    assert log.events[2].kind == EventType.MISSED

    # Replan after missed day
    revised_plan = engine.replan(state, log, initial_ctx)
    assert revised_plan.status == PlanStatus.FEASIBLE

    # Revised plan starts from Day 3 (next day after missed day)
    assert revised_plan.days[0].day >= 3

    # Completed work L-C1 and E-C1-0.2 must NEVER appear in the revised plan schedule
    revised_acts = [aid for d in revised_plan.days for aid in d.activities]
    assert "L-C1" not in revised_acts
    assert "E-C1-0.2" not in revised_acts

    # Replan trace cites completed activities preserved
    preserved = [t for t in revised_plan.trace if t.get("reason") == "REPLAN_PRESERVED_COMPLETED"]
    assert len(preserved) == 2


# =====================================================================
# TC6.2: Failed assessment updates state and triggers valid replan with remediation
# =====================================================================
def test_tc6_2_failed_assessment_replan_with_remediation():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    log = ExecutionLog()
    initial_ctx = PlanContext(goal="C1", deadline_day=10, budget=10, current_day=1)

    # Learner takes assessment item on Day 1 and fails
    ev_fail = Event(day=1, kind=EventType.FAILED_ASSESSMENT, activity_id="E-C1-0.2")
    state, log = engine.record(state, log, ev_fail)

    # State updated: p < 0.40 and needs_remediation is True
    assert state.concepts["C1"].p < 0.40
    assert state.concepts["C1"].needs_remediation is True
    assert log.events[-1].kind == EventType.FAILED_ASSESSMENT

    # Replan incorporates remediation lesson L-C1
    revised_plan = engine.replan(state, log, initial_ctx)
    assert revised_plan.status == PlanStatus.FEASIBLE
    first_act = revised_plan.days[0].activities[0]
    assert first_act == "L-C1"

    # Trace cites REMEDIATION_INSERTED
    assert any(t.get("reason") == "REMEDIATION_INSERTED" for t in revised_plan.trace)


# =====================================================================
# TC6.3: Deadline change triggers valid replan or INFEASIBLE proof
# =====================================================================
def test_tc6_3_deadline_change_replan():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    log = ExecutionLog()
    initial_ctx = PlanContext(goal="C4", deadline_day=10, budget=5, current_day=1)

    # Tighten deadline to day 1 (impossible for budget 5 min to complete 26 min workload)
    ev_tight = Event(day=1, kind=EventType.DEADLINE_CHANGED, value=1)
    state, log = engine.record(state, log, ev_tight)

    # Replan returns INFEASIBLE proof with shortfall and options
    revised_infeas = engine.replan(state, log, initial_ctx)
    assert revised_infeas.status == PlanStatus.INFEASIBLE
    assert revised_infeas.shortfall_days > 0
    assert len(revised_infeas.options) > 0

    # Extend deadline to day 20
    ev_extend = Event(day=1, kind=EventType.DEADLINE_CHANGED, value=20)
    state, log = engine.record(state, log, ev_extend)
    revised_feas = engine.replan(state, log, initial_ctx)
    assert revised_feas.status == PlanStatus.FEASIBLE
    assert len(revised_feas.days) > 0


# =====================================================================
# TC6.4: Daily budget change triggers valid replan
# =====================================================================
def test_tc6_4_budget_change_replan():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    log = ExecutionLog()
    initial_ctx = PlanContext(goal="C4", deadline_day=10, budget=5, current_day=1)

    # Budget changed to 30 min on day 1
    ev_b = Event(day=1, kind=EventType.BUDGET_CHANGED, value=30)
    state, log = engine.record(state, log, ev_b)

    revised_plan = engine.replan(state, log, initial_ctx)
    assert revised_plan.status == PlanStatus.FEASIBLE
    # 26 min total workload finishes in 1 day with 30 min budget
    assert len(revised_plan.days) == 1
    assert revised_plan.days[0].duration <= 30


# =====================================================================
# TC7.1: Every decision traceable to state, constraints, and score components
# =====================================================================
def test_tc7_1_comprehensive_traceability_and_serialization():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    # Setup state with evidence-mastered C1 and short half-life for review
    c1 = LearnerConcept(
        concept_id="C1",
        p=0.90,
        responses=2,
        correct_responses=2,
        status=ConceptStatus.ASSESSED,
        last_practice_day=1,
        half_life_days=2.0,
    )
    state = LearnerState(
        concepts={
            "C1": c1,
            "C2": LearnerConcept("C2"),
            "C3": LearnerConcept("C3"),
            "C4": LearnerConcept("C4"),
        }
    )
    ctx = PlanContext(goal="C4", deadline_day=15, budget=10, current_day=5)
    plan_res = engine.plan(state, ctx)

    assert plan_res.status == PlanStatus.FEASIBLE
    assert len(plan_res.trace) > 0

    valid_reasons = {
        "RANKED_TOP",
        "REVIEW_DUE",
        "REMEDIATION_INSERTED",
        "DOES_NOT_FIT_REMAINING_TIME",
        "ALREADY_EVIDENCE_MASTERED",
        "EVIDENCE_MASTERED",
        "REPLAN_PRESERVED_COMPLETED",
    }

    # Verify every trace record conforms to contract
    for t in plan_res.trace:
        decision = t.get("decision")
        if decision == "SELECTED":
            assert t.get("reason") in valid_reasons
            assert "activity_id" in t
            assert "target_concept" in t
            assert "day" in t
            assert "duration" in t
            assert "remaining_budget" in t
            assert "projected_p" in t
            assert "score" in t
            assert "score_components" in t
            components = t["score_components"]
            assert "review" in components
            assert "unlock" in components
            assert "fit" in components
        elif decision == "DEFERRED":
            assert t.get("reason") in valid_reasons
            assert "activity_id" in t
            assert "remaining_budget" in t
        elif decision == "OMITTED":
            assert t.get("reason") in valid_reasons
            if t.get("reason") in ("ALREADY_EVIDENCE_MASTERED", "EVIDENCE_MASTERED"):
                assert "p" in t
                assert "responses" in t
        elif decision == "REVIEW_DUE":
            assert "concept_id" in t
            assert "r" in t
            assert "threshold" in t
            assert "urgency" in t

    # Test pure serialize_plan
    serialized = serialize_plan(plan_res, engine.config)
    assert "config_hash" in serialized
    assert serialized["config_hash"] == config_hash(engine.config)
    assert serialized["status"] == "FEASIBLE"
    assert isinstance(serialized["days"], list)
    assert isinstance(serialized["trace"], list)

    # Pure JSON roundtrip
    json_str = json.dumps(serialized)
    data = json.loads(json_str)
    assert data["config_hash"] == serialized["config_hash"]


# =====================================================================
# CLI Replan Test
# =====================================================================
def test_cli_replan_subcommand(capsys, tmp_path):
    from adaptengine.cli import main as cli_main
    from adaptengine.session import save_snapshot

    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    ctx = PlanContext(goal="C4", deadline_day=15, budget=10, current_day=1)
    log = ExecutionLog(
        (
            Event(day=1, kind=EventType.COMPLETED, activity_id="L-C1", minutes_elapsed=4),
            Event(day=2, kind=EventType.MISSED),
        )
    )

    snap_file = str(tmp_path / "snap.json")
    save_snapshot(state, log, snap_file, context=ctx)

    # Test CLI replan with snapshot
    ret = cli_main(
        [
            "replan",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_file,
        ]
    )
    assert ret is None or ret == 0
    captured = capsys.readouterr()
    assert "Status: FEASIBLE" in captured.out
    assert "Schedule (" in captured.out

    # Test CLI replan with --json
    ret_json = cli_main(
        [
            "replan",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_file,
            "--json",
        ]
    )
    assert ret_json is None or ret_json == 0
    captured_json = capsys.readouterr()
    data = json.loads(captured_json.out)
    assert data["status"] == "FEASIBLE"
    assert "config_hash" in data
    assert len(data["trace"]) > 0


# =====================================================================
# Working Ahead Scenario: User completes more than necessary today
# =====================================================================
def test_working_ahead_replan():
    """Verify that when a learner works ahead and exceeds/exhausts today's budget,

    the replanner advances execution to the next day and schedules remaining
    material in proper topological prerequisite order without duplication.
    """
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    log = ExecutionLog()
    ctx = PlanContext(goal="C4", deadline_day=10, budget=10, current_day=1)

    # Initial plan for novice is 3 days (Day 1: 10m, Day 2: 9m, Day 3: 7m)
    p_initial = engine.plan(state, ctx)
    assert len(p_initial.days) == 3

    # On Day 1, user completes all Day 1 activities (6 min) AND works ahead
    # into Day 2 activities (L-C2 4 min, E-C2-0.2 1 min) -> total 11 min on Day 1 (exceeds B=10)
    worked_ahead_ids = ["L-C1", "E-C1-0.2", "E-C1-0.4", "L-C2", "E-C2-0.2"]
    for aid in worked_ahead_ids:
        act = engine.activities[aid]
        dur = act.duration
        corr = True if act.type == ActivityType.EXERCISE else None
        ev = Event(
            day=1, kind=EventType.COMPLETED, activity_id=aid, minutes_elapsed=dur, correct=corr
        )
        state, log = engine.record(state, log, ev)

    # Replan after working ahead
    revised = engine.replan(state, log, ctx)
    assert revised.status == PlanStatus.FEASIBLE

    # 1. Day 1 is full, so revised plan begins on Day 2
    assert revised.days[0].day == 2

    # 2. Total remaining days needed to reach C4 drops from 3 to 2
    assert len(revised.days) == 2

    # 3. None of the 5 already-completed activities appear in the new schedule
    revised_acts = [aid for d in revised.days for aid in d.activities]
    for done_id in worked_ahead_ids:
        assert done_id not in revised_acts

    # 4. Remaining activities are in valid prerequisite order
    # Day 2 starts with remaining C2 exercise (E-C2-0.4) before C3 lesson/exercises
    assert revised.days[0].activities[0] == "E-C2-0.4"
    assert "L-C3" in revised.days[0].activities
    # Day 3 schedules C4
    assert revised.days[1].activities[0] == "L-C4"
