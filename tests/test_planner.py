import json
import pytest
from adaptengine.api import Engine
from adaptengine.core.config import EngineConfig, DEFAULT_CONFIG
from adaptengine.core.schema import (
    Activity,
    ActivityType,
    PlanContext,
    PlanStatus,
    PlanDay,
    Plan,
)
from adaptengine.core.errors import ValidationError, UnknownConceptError
from adaptengine.learner.state import LearnerConcept, LearnerState
from adaptengine.learner.adapter import CustomBKT
from adaptengine.planner.difficulty import select_exercise
from adaptengine.planner.workload import compute_workload
from adaptengine.planner.oracle import solve_oracle, OracleActivity
from adaptengine.planner.plan import plan
from adaptengine.cli import main as cli_main


@pytest.fixture
def engine():
    return Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        manifest_path="data/review_manifest.json",
    )


# =====================================================================
# TC4.2: Next exercise nearest target success probability with D10 tie-break
# =====================================================================
def test_difficulty_policy_tc42():
    cfg = DEFAULT_CONFIG
    model = CustomBKT(cfg)

    # 1. Closed form verification:
    # Pc = 0.95p + 0.30(1-p) - d(0.25p + 0.30(1-p))
    p = 0.36
    exercises = [
        Activity("E1", ActivityType.EXERCISE, "C1", duration=1, difficulty=0.2),
        Activity("E2", ActivityType.EXERCISE, "C1", duration=1, difficulty=0.4),
        Activity("E3", ActivityType.EXERCISE, "C1", duration=2, difficulty=0.6),
        Activity("E4", ActivityType.EXERCISE, "C1", duration=2, difficulty=0.8),
    ]

    for ex in exercises:
        expected_pc = 0.95 * p + 0.30 * (1 - p) - ex.difficulty * (0.25 * p + 0.30 * (1 - p))
        actual_pc = model.predict_correct(p, ex.difficulty)
        assert abs(actual_pc - expected_pc) < 1e-9

    # 2. Unreachable target case (at p=0.36, max Pc is 0.4776 for d=0.2, target=0.75):
    # E1 (d=0.2) is nearest to target 0.75
    chosen = select_exercise(exercises, p=0.36, target_success=0.75, model=model, cfg=cfg)
    assert chosen.activity_id == "E1"
    assert chosen.difficulty == 0.2

    # 3. Target reachable case:
    # At p=0.80:
    # Pc(0.2) = 0.95(0.8) + 0.3(0.2) - 0.2(0.25*0.8 + 0.3*0.2) = 0.82 - 0.2(0.26) = 0.768
    # Pc(0.4) = 0.82 - 0.4(0.26) = 0.716
    # Pc(0.6) = 0.82 - 0.6(0.26) = 0.664
    # |0.768 - 0.75| = 0.018, |0.716 - 0.75| = 0.034 => E1 is still nearest
    chosen_high = select_exercise(exercises, p=0.80, target_success=0.75, model=model, cfg=cfg)
    assert chosen_high.activity_id == "E1"

    # 4. Tie-breaking rule (D10):
    # Construct two items with equal distance to target
    # If target is 0.70, suppose item A has Pc = 0.65 (dist 0.05), item B has Pc = 0.75 (dist 0.05)
    # Item closer to d=0.50 wins; if tied, smaller activity_id wins
    class MockModel:
        def predict_correct(self, p, d):
            return 0.70  # exact match for both

    ex_tie1 = Activity("B_ACT", ActivityType.EXERCISE, "C1", duration=1, difficulty=0.4)
    ex_tie2 = Activity("A_ACT", ActivityType.EXERCISE, "C1", duration=1, difficulty=0.6)
    # Both |0.4 - 0.5| and |0.6 - 0.5| == 0.10. Tie-breaker by activity_id: "A_ACT" < "B_ACT"
    res_tie = select_exercise([ex_tie1, ex_tie2], p=0.5, target_success=0.70, model=MockModel())
    assert res_tie.activity_id == "A_ACT"

    # Now test |d - 0.5| preference: d=0.5 vs d=0.3
    ex_mid = Activity("Z_ACT", ActivityType.EXERCISE, "C1", duration=1, difficulty=0.5)
    ex_off = Activity("A_ACT", ActivityType.EXERCISE, "C1", duration=1, difficulty=0.3)
    res_mid = select_exercise([ex_mid, ex_off], p=0.5, target_success=0.70, model=MockModel())
    assert res_mid.activity_id == "Z_ACT"  # |0.5 - 0.5| == 0 < |0.3 - 0.5| == 0.2


# =====================================================================
# T3: Workload calculation and projected workload numbers
# =====================================================================
def test_cold_start_workload_numbers(engine):
    state = engine.init_learner()
    workload, trace, _ = compute_workload(
        engine.graph, engine.activities, state, goal="C4", cfg=engine.config
    )

    # Required concept workloads: C1=6 min, C2=6 min, C3=7 min, C4=7 min
    assert sum(a.duration for a in workload["C1"]) == 6
    assert sum(a.duration for a in workload["C2"]) == 6
    assert sum(a.duration for a in workload["C3"]) == 7
    assert sum(a.duration for a in workload["C4"]) == 7

    total_workload = sum(a.duration for acts in workload.values() for a in acts)
    assert total_workload == 26

    # Verify lessons precede exercises in each queue (D16)
    for c, acts in workload.items():
        assert acts[0].type == ActivityType.LESSON
        assert all(a.type == ActivityType.EXERCISE for a in acts[1:])


# =====================================================================
# TC3.1: Prerequisite safety (locked concept never scheduled before prereqs)
# =====================================================================
@pytest.mark.parametrize("budget", [5, 10, 15, 30])
def test_prerequisite_safety_tc31(engine, budget):
    state = engine.init_learner()
    ctx = PlanContext(goal="C4", deadline_day=30, budget=budget)
    p = engine.plan(state, ctx)
    assert p.status == PlanStatus.FEASIBLE

    # Map each scheduled activity to (day, sequence_index_within_day)
    schedule_pos = {}
    for d in p.days:
        for idx, aid in enumerate(d.activities):
            schedule_pos[aid] = (d.day, idx)

    # For every concept in graph, all activities of prerequisite concepts
    # must appear strictly before any activity of dependent concept
    for aid, pos in schedule_pos.items():
        act = engine.activities[aid]
        c = act.target_concept
        for pred_c in engine.graph.prerequisites(c):
            # Find all activities of pred_c that were scheduled
            pred_acts = [
                pred_aid
                for pred_aid, pred_p in schedule_pos.items()
                if engine.activities[pred_aid].target_concept == pred_c
            ]
            for pred_aid in pred_acts:
                pred_pos = schedule_pos[pred_aid]
                assert pred_pos < pos, (
                    f"Safety violation: prerequisite activity {pred_aid} at {pred_pos} "
                    f"not before dependent activity {aid} at {pos}"
                )


# =====================================================================
# TC3.2: Daily budget adherence (no day exceeds B, for 5, 10, 15, 30)
# =====================================================================
@pytest.mark.parametrize("budget", [5, 10, 15, 30])
def test_daily_budget_adherence_tc32(engine, budget):
    state = engine.init_learner()
    ctx = PlanContext(goal="C4", deadline_day=30, budget=budget)
    p = engine.plan(state, ctx)
    assert p.status == PlanStatus.FEASIBLE

    for d in p.days:
        act_durations = [engine.activities[aid].duration for aid in d.activities]
        total_day_dur = sum(act_durations)
        assert d.duration == total_day_dur
        assert d.duration <= budget, f"Day {d.day} exceeded budget {budget}: {d.duration}"


# =====================================================================
# TC3.3: 5 min vs 30 min daily budgets produce materially different pacing
# =====================================================================
def test_pacing_variation_by_budget_tc33(engine):
    state = engine.init_learner()
    ctx_5 = PlanContext(goal="C4", deadline_day=30, budget=5)
    ctx_30 = PlanContext(goal="C4", deadline_day=30, budget=30)

    p_5 = engine.plan(state, ctx_5)
    p_30 = engine.plan(state, ctx_30)

    assert p_5.status == PlanStatus.FEASIBLE
    assert p_30.status == PlanStatus.FEASIBLE

    # B=30 finishes in exactly 1 day (total workload 26 min <= 30)
    assert len(p_30.days) == 1
    assert p_30.days[0].duration == 26

    # B=5 takes clearly more days (7 days)
    assert len(p_5.days) >= 6
    assert len(p_5.days) > len(p_30.days)


# =====================================================================
# TC3.4: Infeasible goal/deadline returns INFEASIBLE with shortfall and options
# =====================================================================
def test_infeasible_short_deadline_tc34(engine):
    state = engine.init_learner()
    # Goal C4 requires 26 minutes total, critical path 20 min.
    # At B=5, deadline 1 day is impossible.
    ctx = PlanContext(goal="C4", deadline_day=1, budget=5, current_day=1)
    p = engine.plan(state, ctx)

    assert p.status == PlanStatus.INFEASIBLE
    assert p.reason in ("INSUFFICIENT_TIME_BUDGET", "CRITICAL_PATH_EXCEEDS_DEADLINE")
    assert p.shortfall_days >= 3
    assert len(p.options) > 0
    # Options must mention budget increase and deadline extension
    assert any("budget" in opt.lower() for opt in p.options)
    assert any("deadline" in opt.lower() for opt in p.options)


# =====================================================================
# TC3.5: 8 + 8 + 4 at B=10 fixture: bounds pass, exact oracle INFEASIBLE over 2 days, FEASIBLE over 3
# =====================================================================
def test_exact_oracle_tc35():
    activities = [
        OracleActivity("A1", duration=8),
        OracleActivity("A2", duration=8),
        OracleActivity("A3", duration=4),
    ]
    # Linear prerequisite chain: A1 -> A2 -> A3
    predecessors = {"A2": ["A1"], "A3": ["A2"]}

    # Over 2 days, budget 10:
    # Total minutes = 20 <= 2 * 10 = 20 (simple bounds pass!)
    # But bin packing into 2 bins of 10 cannot fit (8, 8, 4).
    status_2d, assignment_2d, _ = solve_oracle(
        activities, predecessors, budget=10, num_days=2, node_limit=1000
    )
    assert status_2d == PlanStatus.INFEASIBLE
    assert assignment_2d is None

    # Over 3 days, budget 10:
    # Day 1: A1 (8), Day 2: A2 (8), Day 3: A3 (4) -> FEASIBLE!
    status_3d, assignment_3d, _ = solve_oracle(
        activities, predecessors, budget=10, num_days=3, node_limit=1000
    )
    assert status_3d == PlanStatus.FEASIBLE
    assert assignment_3d == [["A1"], ["A2"], ["A3"]]


# =====================================================================
# TC3.6: Oracle node limit returns UNKNOWN, never a false infeasible
# =====================================================================
def test_exact_oracle_node_limit_tc36():
    activities = [
        OracleActivity("A1", duration=8),
        OracleActivity("A2", duration=8),
        OracleActivity("A3", duration=4),
    ]
    predecessors = {"A2": ["A1"], "A3": ["A2"]}

    # Node limit = 1 triggers immediate search termination
    status, assignment, nodes = solve_oracle(
        activities, predecessors, budget=10, num_days=2, node_limit=1
    )
    assert status == PlanStatus.UNKNOWN
    assert assignment is None
    assert nodes >= 1


# =====================================================================
# TC2.3: Two learners, same goal/budget produce different individually valid plans
# =====================================================================
def test_two_learners_different_valid_plans_tc23(engine):
    # Learner A: cold start novice
    state_a = engine.init_learner()

    # Learner B: has already evidence-mastered C1 and C2 (p=0.90, responses=2)
    state_b = LearnerState(
        concepts={
            "C1": LearnerConcept(concept_id="C1", p=0.90, responses=2, correct_responses=2),
            "C2": LearnerConcept(concept_id="C2", p=0.90, responses=2, correct_responses=2),
            "C3": LearnerConcept(concept_id="C3", p=0.20, responses=0),
            "C4": LearnerConcept(concept_id="C4", p=0.20, responses=0),
        }
    )

    ctx = PlanContext(goal="C4", deadline_day=10, budget=10)
    plan_a = engine.plan(state_a, ctx)
    plan_b = engine.plan(state_b, ctx)

    assert plan_a.status == PlanStatus.FEASIBLE
    assert plan_b.status == PlanStatus.FEASIBLE

    # Learner A requires C1, C2, C3, C4
    all_acts_a = [aid for d in plan_a.days for aid in d.activities]
    target_concepts_a = {engine.activities[aid].target_concept for aid in all_acts_a}
    assert target_concepts_a == {"C1", "C2", "C3", "C4"}

    # Learner B requires only C3, C4 (C1 and C2 omitted)
    all_acts_b = [aid for d in plan_b.days for aid in d.activities]
    target_concepts_b = {engine.activities[aid].target_concept for aid in all_acts_b}
    assert target_concepts_b == {"C3", "C4"}

    # Trace for Learner B must document omission of C1 and C2
    omitted_c1 = any(
        t.get("decision") == "OMITTED"
        and t.get("concept_id") == "C1"
        and t.get("reason") in ("ALREADY_EVIDENCE_MASTERED", "EVIDENCE_MASTERED")
        for t in plan_b.trace
    )
    omitted_c2 = any(
        t.get("decision") == "OMITTED"
        and t.get("concept_id") == "C2"
        and t.get("reason") in ("ALREADY_EVIDENCE_MASTERED", "EVIDENCE_MASTERED")
        for t in plan_b.trace
    )
    assert omitted_c1
    assert omitted_c2

    # Different, individually valid plans
    assert len(plan_b.days) < len(plan_a.days)
    assert sum(d.duration for d in plan_b.days) < sum(d.duration for d in plan_a.days)


# =====================================================================
# Determinism and Repeatability
# =====================================================================
def test_plan_determinism(engine):
    state = engine.init_learner()
    ctx = PlanContext(goal="C4", deadline_day=10, budget=10)

    p1 = engine.plan(state, ctx)
    p2 = engine.plan(state, ctx)

    assert p1.status == p2.status
    assert p1.days == p2.days
    assert p1.trace == p2.trace


# =====================================================================
# CLI Plan Subcommand
# =====================================================================
def test_cli_plan_text_output(capsys):
    ret = cli_main(
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
            "10",
            "--budget",
            "10",
        ]
    )
    assert ret is None or ret == 0
    captured = capsys.readouterr()
    assert "Status: FEASIBLE" in captured.out
    assert "Schedule (3 days):" in captured.out


def test_cli_plan_json_output(capsys):
    ret = cli_main(
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
            "10",
            "--budget",
            "10",
            "--json",
        ]
    )
    assert ret is None or ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "FEASIBLE"
    assert len(data["days"]) == 3
    assert len(data["trace"]) > 0


# =====================================================================
# T8: 8-node curriculum fixture test
# =====================================================================
def test_planner_8node_fixture():
    engine_8node = Engine.from_files(
        "data/curriculum/curriculum_8node.json",
        "data/curriculum/activities_8node.json",
        manifest_path="data/review_manifest.json",
    )
    state = engine_8node.init_learner()
    ctx = PlanContext(goal="C8", deadline_day=30, budget=15)
    p = engine_8node.plan(state, ctx)
    assert p.status == PlanStatus.FEASIBLE
    assert len(p.days) > 0

    # Ensure all 8 concepts are represented in the path to C8
    all_acts = [aid for d in p.days for aid in d.activities]
    scheduled_concepts = {engine_8node.activities[aid].target_concept for aid in all_acts}
    # C8 depends on C7 which depends on C5 (from C3 <- C1, C2) and C6 (from C1).
    # All concepts C1, C2, C3, C5, C6, C7, C8 are ancestors of C8. (C4 is not on path to C8).
    expected_ancestors = {"C1", "C2", "C3", "C5", "C6", "C7", "C8"}
    assert scheduled_concepts == expected_ancestors

    # Check prerequisite safety on 8-node DAG
    schedule_pos = {}
    for d in p.days:
        for idx, aid in enumerate(d.activities):
            schedule_pos[aid] = (d.day, idx)

    for aid, pos in schedule_pos.items():
        c = engine_8node.activities[aid].target_concept
        for pred_c in engine_8node.graph.prerequisites(c):
            pred_acts = [
                pred_aid
                for pred_aid in schedule_pos
                if engine_8node.activities[pred_aid].target_concept == pred_c
            ]
            for pred_aid in pred_acts:
                assert schedule_pos[pred_aid] < pos


# =====================================================================
# Edge Cases & Branch Coverage
# =====================================================================
def test_plan_goal_already_mastered(engine):
    # If all required concepts are already evidence-mastered
    state = LearnerState(
        concepts={
            c: LearnerConcept(concept_id=c, p=0.95, responses=3, correct_responses=3)
            for c in engine.graph.concepts()
        }
    )
    ctx = PlanContext(goal="C4", deadline_day=10, budget=10)
    p = engine.plan(state, ctx)
    assert p.status == PlanStatus.FEASIBLE
    assert p.days == ()
    assert p.reason == "GOAL_ALREADY_MASTERED"


def test_plan_oracle_scenarios():
    from adaptengine.curriculum.graph import CurriculumGraph
    from adaptengine.core.schema import Concept

    # Scenario: 8, 8, 4 over 2 days at B=10
    # Bounds pass, greedy cannot fit into 2 days (takes 3 days), oracle runs and returns INFEASIBLE
    p_inf = plan(
        CurriculumGraph.from_concepts(
            (
                Concept("X1", ()),
                Concept("X2", ()),
                Concept("X3", ()),
                Concept("GoalX", ("X1", "X2", "X3")),
            )
        ),
        {
            "LX1": Activity("LX1", ActivityType.LESSON, "X1", duration=8),
            "LX2": Activity("LX2", ActivityType.LESSON, "X2", duration=8),
            "LX3": Activity("LX3", ActivityType.LESSON, "X3", duration=4),
        },
        LearnerState(
            concepts={
                "X1": LearnerConcept("X1", p=0.20, responses=1),
                "X2": LearnerConcept("X2", p=0.20, responses=1),
                "X3": LearnerConcept("X3", p=0.20, responses=1),
                "GoalX": LearnerConcept("GoalX", p=0.90, responses=2),
            }
        ),
        PlanContext(goal="GoalX", deadline_day=2, budget=10),
        cfg=EngineConfig(t_lesson=0.70, theta=0.75, k_responses=1, oracle_node_limit=1000),
    )
    assert p_inf.status == PlanStatus.INFEASIBLE
    assert p_inf.reason == "ORACLE_INFEASIBLE"
    assert p_inf.shortfall_days >= 1

    # Now test oracle node limit = 1 -> UNKNOWN
    p_unk = plan(
        CurriculumGraph.from_concepts(
            (
                Concept("X1", ()),
                Concept("X2", ()),
                Concept("X3", ()),
                Concept("GoalX", ("X1", "X2", "X3")),
            )
        ),
        {
            "LX1": Activity("LX1", ActivityType.LESSON, "X1", duration=8),
            "LX2": Activity("LX2", ActivityType.LESSON, "X2", duration=8),
            "LX3": Activity("LX3", ActivityType.LESSON, "X3", duration=4),
        },
        LearnerState(
            concepts={
                "X1": LearnerConcept("X1", p=0.20, responses=1),
                "X2": LearnerConcept("X2", p=0.20, responses=1),
                "X3": LearnerConcept("X3", p=0.20, responses=1),
                "GoalX": LearnerConcept("GoalX", p=0.90, responses=2),
            }
        ),
        PlanContext(goal="GoalX", deadline_day=2, budget=10),
        cfg=EngineConfig(t_lesson=0.70, theta=0.75, k_responses=1, oracle_node_limit=1),
    )
    assert p_unk.status == PlanStatus.UNKNOWN
    assert p_unk.reason == "ORACLE_LIMIT_EXCEEDED"


def test_plan_content_insufficient():
    # Concept with no exercises when exercises are needed
    from adaptengine.curriculum.graph import CurriculumGraph
    from adaptengine.core.schema import Concept

    graph = CurriculumGraph.from_concepts((Concept("C1", ()),))
    activities = {
        "L1": Activity("L1", ActivityType.LESSON, "C1", duration=4),
    }
    state = LearnerState(concepts={"C1": LearnerConcept("C1", p=0.20, responses=0)})
    ctx = PlanContext(goal="C1", deadline_day=5, budget=10)
    p = plan(graph, activities, state, ctx, cfg=EngineConfig(k_responses=2))
    assert p.status == PlanStatus.INFEASIBLE
    assert p.reason == "CONTENT_INSUFFICIENT"


def test_plan_validation_errors(engine):
    state = engine.init_learner()
    # Unknown goal
    with pytest.raises(UnknownConceptError):
        plan(engine.graph, engine.activities, state, PlanContext("UNKNOWN_GOAL", 10, 10))

    # Bad context type
    with pytest.raises(ValidationError):
        plan(engine.graph, engine.activities, state, "not-a-context")

    # Budget not in allowed_budgets
    with pytest.raises(ValidationError):
        plan(
            engine.graph,
            engine.activities,
            state,
            PlanContext("C1", 10, 10),
            cfg=EngineConfig(allowed_budgets=(5, 15, 30)),
        )


def test_schema_validations():
    with pytest.raises(ValidationError):
        PlanContext(goal="", deadline_day=1, budget=10)
    with pytest.raises(ValidationError):
        PlanContext(goal="C1", deadline_day=0, budget=10)
    with pytest.raises(ValidationError):
        PlanContext(goal="C1", deadline_day=1, budget=7)
    with pytest.raises(ValidationError):
        PlanContext(goal="C1", deadline_day=1, budget=10, current_day=2)

    with pytest.raises(ValidationError):
        PlanDay(day=0, activities=("A1",), duration=5)
    with pytest.raises(ValidationError):
        PlanDay(day=1, activities=("",), duration=5)
    with pytest.raises(ValidationError):
        PlanDay(day=1, activities="not-a-seq", duration=5)

    with pytest.raises(ValidationError):
        Plan(status="INVALID")
    with pytest.raises(ValidationError):
        Plan(status=PlanStatus.FEASIBLE, days=("not-a-plan-day",))


def test_is_evidence_mastered_custom():
    c = LearnerConcept("C1", p=0.86, responses=2)
    # Mastered under default (theta=0.85, k=2)
    assert c.evidence_mastered is True
    from adaptengine.learner import is_evidence_mastered

    assert is_evidence_mastered(c, DEFAULT_CONFIG) is True
    # Not mastered under stricter config (theta=0.90)
    cfg_strict = EngineConfig(theta=0.90)
    assert is_evidence_mastered(c, cfg_strict) is False
