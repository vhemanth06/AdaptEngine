"""V2-TC3: executed-violation audit and plan-level validity checks."""

from adaptengine.core.config import bisection_config
from adaptengine.core.schema import Event, EventType, Plan, PlanDay, PlanStatus
from adaptengine.learner.state import ExecutionLog

from experiments.core import curricula as C
from experiments.core.audit import executed_violations, plan_violations
from experiments.core.episode import first_plan
from experiments.core.scenarios import make_scenario


def _log(e, aids, correct=True):
    state, log = e.init_learner(), ExecutionLog()
    for i, aid in enumerate(aids):
        a = e.activities[aid]
        y = None if a.type.value == "LESSON" else correct
        ev = Event(day=1, kind=EventType.COMPLETED, activity_id=aid, correct=y, attempt_id=f"x{i}")
        state, log = e.record(state, log, ev)
    return log


def _by_concept(e, c, kind):
    return sorted(
        a.activity_id
        for a in e.activities.values()
        if a.target_concept == c and a.type.value == kind
    )


def test_executed_violation_counts():
    e = C.engine("4-node")
    order = list(e.graph.topological_order())
    dep = next(c for c in order if e.graph.prerequisites(c))
    assert (
        executed_violations(e, e.init_learner(), _log(e, [_by_concept(e, dep, "LESSON")[0]])) == 1
    )
    root = order[0]
    clean = _by_concept(e, root, "LESSON") + _by_concept(e, root, "EXERCISE")
    assert executed_violations(e, e.init_learner(), _log(e, clean)) == 0


def test_plan_checks_flag_each_kind_once():
    e = C.engine("4-node")
    g = C.goal_of(e)
    sc = make_scenario("calm", e, g, 15)
    plan = first_plan(e, e.init_learner(), sc)
    s0 = e.init_learner()
    assert plan_violations(e, s0, plan, 15, sc.deadline) == {
        "prereq": 0,
        "budget": 0,
        "deadline": 0,
    }
    order = list(e.graph.topological_order())
    dep = next(c for c in order if e.graph.prerequisites(c))
    bad = Plan(
        status=PlanStatus.FEASIBLE, days=(PlanDay(1, (_by_concept(e, dep, "LESSON")[0],), 4),)
    )
    assert plan_violations(e, s0, bad, 15, 5)["prereq"] == 1
    root = _by_concept(e, order[0], "LESSON") + _by_concept(e, order[0], "EXERCISE")
    over = sum(e.activities[a].duration for a in root)
    big = Plan(status=PlanStatus.FEASIBLE, days=(PlanDay(1, tuple(root), over),))
    assert plan_violations(e, s0, big, over - 1, 5) == {"prereq": 0, "budget": 1, "deadline": 0}
    late = Plan(status=PlanStatus.FEASIBLE, days=(PlanDay(6, (root[0],), 4),))
    assert plan_violations(e, s0, late, 15, 5) == {"prereq": 0, "budget": 0, "deadline": 1}
    used = Plan(status=PlanStatus.FEASIBLE, days=(PlanDay(2, (root[0],), 4),))
    assert plan_violations(e, s0, used, 15, 5, current_day=2, minutes_used_today=12)["budget"] == 1


def test_plan_with_confirmation_checks_is_valid():
    e = C.engine("8node_x10", bisection_config())
    g = C.goal_of(e)
    state = e.init_learner()
    concepts = dict(state.concepts)
    for c in e.graph.ancestors(g):  # every prerequisite inferred known by the diagnostic
        x = concepts[c]
        concepts[c] = type(x)(
            **{
                **{k: getattr(x, k) for k in x.__dataclass_fields__},
                "p": 0.97,
                "diag_confident": True,
            }
        )
    state = type(state)(concepts=concepts)
    sc = make_scenario("calm", C.engine("8node_x10"), g, 15)
    plan = first_plan(e, state, sc)
    assert any(t.get("decision") == "CONFIRMATION" for t in plan.trace)
    assert plan_violations(e, state, plan, 15, sc.deadline) == {
        "prereq": 0,
        "budget": 0,
        "deadline": 0,
    }
