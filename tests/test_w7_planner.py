"""W7 WP2 planner behaviour: exercise repeats (T2.3), expected projection (T2.5),
best-effort plans (T2.4) and the closed-loop entry point (T2.2)."""

import pytest

from adaptengine.api import Engine
from adaptengine.core.config import EngineConfig
from adaptengine.core.schema import ActivityType, Event, EventType, PlanContext, PlanStatus
from adaptengine.learner.state import ExecutionLog

CUR, ACT = "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"


def make_engine(**kw):
    return Engine.from_files(CUR, ACT, config=EngineConfig(**kw))


def fail_c1(engine, n_wrong=3, n_right=1):
    """Lesson on C1, then n_wrong wrong and n_right right answers on distinct C1 exercises."""
    state, log = engine.init_learner(), ExecutionLog()
    lesson = next(
        a
        for a in engine.activities.values()
        if a.target_concept == "C1" and a.type == ActivityType.LESSON
    )
    state, log = engine.record(state, log, Event(1, EventType.COMPLETED, lesson.activity_id, 4))
    exs = sorted(
        a.activity_id
        for a in engine.activities.values()
        if a.target_concept == "C1" and a.type == ActivityType.EXERCISE
    )
    assert len(exs) == n_wrong + n_right
    for i, aid in enumerate(exs):
        dur = engine.activities[aid].duration
        ev = Event(1, EventType.COMPLETED, aid, dur, correct=i >= n_wrong)
        state, log = engine.record(state, log, ev)
    return state, log


def test_repeats_keep_plan_feasible_after_failing_c1_t2_3():
    ctx = PlanContext(goal="C4", deadline_day=20, budget=15)
    rep = make_engine()
    state, log = fail_c1(rep)
    p = rep.replan(state, log, ctx)
    assert p.status == PlanStatus.FEASIBLE
    c1_ex = [
        a
        for d in p.days
        for a in d.activities
        if rep.activities[a].target_concept == "C1"
        and rep.activities[a].type == ActivityType.EXERCISE
    ]
    assert c1_ex  # C1 is re-practised with repeated (already-seen) exercises
    # W6 behaviour (ablation): the bank is exhausted, so the planner gives up
    norep = make_engine(allow_exercise_repeats=False)
    state, log = fail_c1(norep)
    p2 = norep.replan(state, log, ctx)
    assert p2.status == PlanStatus.INFEASIBLE and p2.reason == "CONTENT_INSUFFICIENT"


def test_repeats_prefer_least_recently_seen_t2_3():
    e = make_engine()
    state, log = fail_c1(e)
    p = e.replan(state, log, PlanContext(goal="C1", deadline_day=20, budget=30))
    first = next(
        a for d in p.days for a in d.activities if e.activities[a].type == ActivityType.EXERCISE
    )
    done = [x for x in log.completed_ids() if e.activities[x].type == ActivityType.EXERCISE]
    assert first == done[0]  # oldest attempt comes back first


@pytest.mark.parametrize("budget", [5, 10, 15, 30])
def test_expected_projection_never_fewer_items_t2_5(budget):
    ctx = PlanContext(goal="C4", deadline_day=60, budget=budget)

    def n_new(engine):
        p = engine.plan(engine.init_learner(), ctx)
        return sum(
            1
            for t in p.trace
            if t.get("decision") == "SELECTED" and t.get("reason") != "REVIEW_DUE"
        )

    opt, exp = n_new(make_engine()), n_new(make_engine(projection_mode="expected"))
    assert exp >= opt
    assert exp > opt  # from p0=0.20 P(correct) < 1, so the expectation adds items


def test_projection_mode_validated():
    with pytest.raises(Exception):
        EngineConfig(projection_mode="pessimistic")


def test_wrong_answer_changes_rest_of_day_t2_2():
    """T2.2: after a wrong answer the closed loop's slice for the rest of the day differs from the
    slice computed at the start of the day (fresh state), and stays within the day's budget."""
    e = make_engine()
    state, log = e.init_learner(), ExecutionLog()
    ctx = PlanContext(goal="C4", deadline_day=10, budget=15)
    today, _ = e.next_activities(state, log, ctx)
    first_ex = next(a for a in today.activities if e.activities[a].type == ActivityType.EXERCISE)
    used = 0
    for aid in today.activities:
        a = e.activities[aid]
        correct = None if a.type == ActivityType.LESSON else False
        state, log = e.record(state, log, Event(1, EventType.COMPLETED, aid, a.duration, correct))
        used += a.duration
        if aid == first_ex:
            break
    rest_before = list(today.activities[today.activities.index(first_ex) + 1 :])
    rest_after, plan = e.next_activities(state, log, ctx)
    assert plan.status == PlanStatus.FEASIBLE
    after = list(rest_after.activities) if rest_after else []
    assert after != rest_before
    assert used + sum(e.activities[a].duration for a in after) <= 15


def test_next_activities_matches_replan_first_day_t2_2():
    e = make_engine()
    s, log = e.init_learner(), ExecutionLog()
    ctx = PlanContext(goal="C4", deadline_day=10, budget=15)
    today, plan = e.next_activities(s, log, ctx)
    assert plan.days[0] == today and plan == e.replan(s, log, ctx)


def test_best_effort_plan_on_infeasible_t2_4():
    """T2.4 / D42: an infeasible deadline keeps INFEASIBLE + shortfall + options and adds a
    best-effort schedule (prerequisite-ordered, within budget and deadline)."""
    e = make_engine()
    p = e.plan(e.init_learner(), PlanContext(goal="C4", deadline_day=2, budget=5))
    assert p.status == PlanStatus.INFEASIBLE and p.shortfall_days > 0 and p.options
    assert p.days == () and p.best_effort_days
    assert all(d.day <= 2 and d.duration <= 5 for d in p.best_effort_days)
    assert any(t.get("decision") == "BEST_EFFORT" for t in p.trace)
    today, _ = e.next_activities(
        e.init_learner(), ExecutionLog(), PlanContext(goal="C4", deadline_day=2, budget=5)
    )
    assert today is not None and today.day == 1


def test_deadline_cut_episode_never_idle_t2_4():
    import sys

    sys.path.insert(0, ".")
    from experiments.arms import get_scenario, run_episode
    from experiments.sim import PROFILES

    e = make_engine()
    sc = get_scenario("deadline_cut", e, e.init_learner(), "C4", 5)
    for seed in range(100, 120):
        r = run_episode(e, seed, sc, "adapt", PROFILES["nominal"])
        assert r["idle_days"] == 0 and r["executed_prereq_violations"] == 0


def test_allowed_budgets_from_config_t5_1():
    """T5.1: the schema no longer hard-codes (5, 10, 15, 30); EngineConfig decides."""
    e = make_engine(allowed_budgets=(5, 10, 15, 20, 30))
    p = e.plan(e.init_learner(), PlanContext(goal="C4", deadline_day=20, budget=20))
    assert p.status == PlanStatus.FEASIBLE and all(d.duration <= 20 for d in p.days)
    with pytest.raises(Exception, match="budget must be one of"):
        make_engine().plan(make_engine().init_learner(), PlanContext("C4", 20, 20))


def test_reviews_wait_for_prerequisite_relearning_t4_4_fix():
    """Defect found by the pre-registered T4.4 audit: a due review of C3 was scheduled while its
    prerequisite C1 (lost evidence after a wrong review answer) still had queued work."""
    from adaptengine.learner.state import LearnerConcept

    e = make_engine(half_life_days=1.0)
    concepts = dict(e.init_learner().concepts)
    concepts["C1"] = LearnerConcept(
        "C1", p=0.30, responses=3, correct_responses=1, last_practice_day=1, half_life_days=1.0
    )
    for c in ("C2", "C3"):
        concepts[c] = LearnerConcept(
            c,
            p=0.95,
            responses=3,
            correct_responses=3,
            correct_streak=3,
            last_practice_day=1,
            half_life_days=1.0,
        )
    from adaptengine.learner.state import LearnerState as LS

    state = LS(concepts=concepts)
    p = e.plan(state, PlanContext(goal="C3", deadline_day=20, budget=15, current_day=10))
    sel = [t for t in p.trace if t.get("decision") == "SELECTED"]
    order = [(t["day"], i, t["target_concept"]) for i, t in enumerate(sel)]
    last_c1 = max(o for o in order if o[2] == "C1" and sel[o[1]]["reason"] != "REVIEW_DUE")
    first_c3 = min(o for o in order if o[2] == "C3")
    assert first_c3 > last_c1


def test_reviews_wait_for_unmastered_prerequisite_outside_workload_t4_4_fix():
    """Second Defect-7 path: in a best-effort schedule toward C1, prerequisite C2 of C3 is not in
    the workload and not evidence-mastered, so a due review of C3 must not be scheduled."""
    from adaptengine.learner.state import LearnerConcept, LearnerState
    from adaptengine.planner.schedule import run_greedy_schedule
    from adaptengine.planner.workload import compute_workload

    e = make_engine(half_life_days=1.0)
    cs = dict(e.init_learner().concepts)
    cs["C2"] = LearnerConcept("C2", p=0.2, responses=3, correct_responses=0, last_practice_day=1)
    cs["C3"] = LearnerConcept(
        "C3",
        p=0.95,
        responses=3,
        correct_responses=3,
        correct_streak=3,
        last_practice_day=1,
        half_life_days=1.0,
    )
    state = LearnerState(concepts=cs)
    ctx = PlanContext(goal="C1", deadline_day=12, budget=15, current_day=10)
    wl, _, p0 = compute_workload(e.graph, e.activities, state, "C1", cfg=e.config)
    days, trace = run_greedy_schedule(
        e.graph, wl, p0, ctx, cfg=e.config, state=state, activities=e.activities
    )
    assert not any(e.activities[a].target_concept == "C3" for d in days for a in d.activities)
    assert any(t.get("concept_id") == "C3" and t["decision"] == "REVIEW_DUE" for t in trace)
