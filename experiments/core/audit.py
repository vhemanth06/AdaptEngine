"""Safety audits.

- executed_violations (D46, primary): replay the real execution log through Engine.record and
  count activities done while a direct prerequisite was not evidence-mastered in the recorded state.
- plan_violations (M8 plan validity): check one plan the engine produced against prerequisite
  order (D4, with confirmation checks counted as the engine counts them), the daily budget in
  force, and the effective deadline.
"""

from __future__ import annotations

from typing import Iterable, Optional

from adaptengine.core.schema import ActivityType, EventType, Plan, PlanDay, PlanStatus
from adaptengine.learner.mastery import learn
from adaptengine.learner.state import ExecutionLog, is_evidence_mastered, mastered_by


def executed_violations(engine, start_state, log: ExecutionLog) -> int:
    cfg, graph = engine.config, engine.graph
    state, replay, bad = start_state, ExecutionLog(), 0
    for e in log.events:
        if e.kind in (EventType.COMPLETED, EventType.FAILED_ASSESSMENT) and e.activity_id:
            c = engine.activities[e.activity_id].target_concept
            if any(
                not is_evidence_mastered(state.concepts[q], cfg) for q in graph.prerequisites(c)
            ):
                bad += 1
        state, replay = engine.record(state, replay, e)
    return bad


def executed_days(plan: Plan) -> tuple[PlanDay, ...]:
    """The schedule a learner would follow: the plan, or its best effort when not FEASIBLE (D42)."""
    return plan.days if plan.status == PlanStatus.FEASIBLE else plan.best_effort_days


def plan_violations(
    engine,
    state,
    plan: Plan,
    budget: int,
    deadline: int,
    current_day: int = 1,
    minutes_used_today: int = 0,
    days: Optional[Iterable[PlanDay]] = None,
) -> dict:
    """{'prereq', 'budget', 'deadline'} counts for one plan made from `state`.

    prereq: per scheduled activity whose concept has a direct prerequisite not yet unlocked. A
    concept is unlocked if it is evidence-mastered in `state`, reaches D4 on the optimistic replay
    of the schedule (the planner's own projection), or is routed to confirmation checks and all of
    its checks are already scheduled (the engine confirms a concept by passing them, D57).
    budget: per day whose minutes (recomputed from the catalogue) exceed the budget in force
    (minus the minutes already used on current_day). deadline: per day after the deadline.
    """
    cfg, graph, acts, model = engine.config, engine.graph, engine.activities, engine.model
    days = tuple(executed_days(plan) if days is None else days)
    sc = state.concepts
    p = {c: x.p for c, x in sc.items()}
    n = {c: x.responses for c, x in sc.items()}
    streak = {c: x.correct_streak for c, x in sc.items()}
    unlocked = {c for c, x in sc.items() if is_evidence_mastered(x, cfg)}
    checks_left: dict[str, list[str]] = {}
    for t in plan.trace:
        if t.get("decision") == "CONFIRMATION" and not t.get("best_effort"):
            checks_left[t["concept_id"]] = list(t["activity_ids"])
    if plan.status != PlanStatus.FEASIBLE:  # best-effort confirmation records
        for t in plan.trace:
            if t.get("decision") == "CONFIRMATION" and t.get("best_effort"):
                checks_left[t["concept_id"]] = list(t["activity_ids"])
    out = {"prereq": 0, "budget": 0, "deadline": 0}
    for d in sorted(days, key=lambda d: d.day):
        cap = budget - (minutes_used_today if d.day == current_day else 0)
        if sum(acts[a].duration for a in d.activities) > cap:
            out["budget"] += 1
        if d.day > deadline:
            out["deadline"] += 1
        for aid in d.activities:
            a = acts[aid]
            c = a.target_concept
            if any(q not in unlocked for q in graph.prerequisites(c)):
                out["prereq"] += 1
            if a.type == ActivityType.LESSON:
                p[c] = learn(p[c], cfg.t_lesson)
            else:
                p[c] = model.update(p[c], a.difficulty, True, cfg.t_exercise)
                n[c] += 1
                streak[c] += 1
                if c in checks_left and aid in checks_left[c]:
                    checks_left[c].remove(aid)
                    if not checks_left[c]:
                        unlocked.add(c)
            if mastered_by(p[c], n[c], streak[c], cfg):
                unlocked.add(c)
    return out


def budget_violations(engine, days: Iterable[PlanDay], budget_for_day) -> int:
    return sum(
        1
        for d in days
        if sum(engine.activities[a].duration for a in d.activities) > budget_for_day(d.day)
    )
