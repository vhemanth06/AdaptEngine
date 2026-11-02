"""Planner arms, scenarios, and closed-loop episode execution harness (W6 Step 4).

Supports four comparison arms:
- adapt: Full engine planning and replanning on events with spaced review and remediation.
- no_review: Full replanning, but review urgency set to 0.0 (review disabled).
- no_replan: Initial plan only; missed days or events are not recovered.
- static: State-agnostic topological sequence packed next-fit into daily budgets.

Never imported from src/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from adaptengine.core.schema import ActivityType, Event, EventType, Plan, PlanContext, PlanDay
from experiments.checks import count_budget_violations, count_prerequisite_violations
from experiments.sim import SimLearner, SimProfile, TRUE_MASTERY_CUTOFF


@dataclass(frozen=True)
class Scenario:
    name: str
    budget: int
    deadline: int
    goal: str
    events: tuple[tuple[int, EventType, Any], ...] = ()


def static_days(engine, goal: str, budget: int) -> tuple[PlanDay, ...]:
    """Fixed topological sequence, lessons then exercises sorted by activity_id, next-fit packed."""
    need = {goal} | engine.graph.ancestors(goal)
    seq = []
    for c in engine.graph.topological_order():
        if c in need:
            seq += sorted(
                (a for a in engine.activities.values() if a.target_concept == c),
                key=lambda a: (a.type != ActivityType.LESSON, a.activity_id),
            )
    days: list[PlanDay] = []
    cur: list[Any] = []
    used = 0
    d = 1
    for a in seq:
        if used + a.duration > budget:
            days.append(PlanDay(day=d, activities=tuple(x.activity_id for x in cur), duration=used))
            d += 1
            cur = []
            used = 0
        cur.append(a)
        used += a.duration
    if cur:
        days.append(PlanDay(day=d, activities=tuple(x.activity_id for x in cur), duration=used))
    return tuple(days)


def get_scenario(name: str, engine, start_state, goal: str, budget: int) -> Optional[Scenario]:
    """Construct a standardized scenario (calm, missed_day, budget_drop, deadline_cut)."""
    uncapped_ctx = PlanContext(goal=goal, deadline_day=60, budget=budget, current_day=1)
    uncapped_plan = engine.plan(start_state, uncapped_ctx)
    deadline = max(3, len(uncapped_plan.days) + 2)

    if name == "calm":
        return Scenario("calm", budget=budget, deadline=deadline, goal=goal, events=())
    elif name == "missed_day":
        return Scenario(
            "missed_day",
            budget=budget,
            deadline=deadline,
            goal=goal,
            events=((2, EventType.MISSED, None),),
        )
    elif name == "budget_drop":
        if budget <= 5:
            return None
        allowed = sorted(engine.config.allowed_budgets)
        idx = allowed.index(budget)
        lower_b = allowed[idx - 1]
        return Scenario(
            "budget_drop",
            budget=budget,
            deadline=deadline,
            goal=goal,
            events=((2, EventType.BUDGET_CHANGED, lower_b),),
        )
    elif name == "deadline_cut":
        return Scenario(
            "deadline_cut",
            budget=budget,
            deadline=deadline,
            goal=goal,
            events=((2, EventType.DEADLINE_CHANGED, deadline - 1),),
        )
    else:
        raise ValueError(f"Unknown scenario name: {name}")


def compute_plan_trace_coverage(plan: Plan) -> float:
    """Compute explanation coverage of a plan's trace across all scheduled activities."""
    if not plan.days:
        return 1.0
    total_acts = sum(len(d.activities) for d in plan.days)
    if total_acts == 0:
        return 1.0

    selected_in_trace: set[tuple[int, str]] = set()
    for tr in plan.trace:
        dec = tr.get("decision")
        if dec == "SELECTED":
            aid = tr.get("activity_id")
            reason = tr.get("reason")
            day = tr.get("day")
            if aid and reason and day is not None:
                if reason == "ORACLE_ASSIGNED" or tr.get("score_components") is not None:
                    selected_in_trace.add((day, aid))

    covered = 0
    for d in plan.days:
        for aid in d.activities:
            if (d.day, aid) in selected_in_trace:
                covered += 1
    return covered / total_acts


def run_episode(
    engine,
    seed: int,
    scenario: Scenario,
    arm: str,
    profile: SimProfile,
) -> dict[str, Any]:
    """Execute a single closed-loop episode day-by-day under the specified arm and scenario."""
    sim = SimLearner(seed=seed, concepts=engine.graph.concepts(), profile=profile)
    start_state = engine.init_learner()

    review_urgency: Optional[Mapping[str, float]] = None
    if arm == "no_review":
        review_urgency = {c: 0.0 for c in engine.graph.concepts()}

    trace_coverage = 1.0
    if arm == "static":
        plan_days: Sequence[PlanDay] = static_days(engine, scenario.goal, scenario.budget)
        trace_coverage = 0.0  # Static baseline does not use engine planner
    else:
        initial_ctx = PlanContext(
            goal=scenario.goal,
            deadline_day=scenario.deadline,
            budget=scenario.budget,
            current_day=1,
        )
        plan = engine.plan(start_state, initial_ctx, review_urgency=review_urgency)
        plan_days = plan.days
        trace_coverage = compute_plan_trace_coverage(plan)

    state = start_state
    log = engine.init_learner_session().log if hasattr(engine, "init_learner_session") else None
    from adaptengine.learner.state import ExecutionLog

    log = ExecutionLog()

    peak_theta = dict(sim.theta)
    attempts: list[list[Any]] = []
    executed_activities_by_day: dict[int, list[str]] = {}
    effective_budget = scenario.budget
    effective_deadline = scenario.deadline
    budget_in_force_per_day: dict[int, int] = {}
    dirty = False

    for day in range(1, effective_deadline + 1):
        budget_in_force_per_day[day] = effective_budget

        # Apply scenario events for this day
        day_events = [e for e in scenario.events if e[0] == day]
        skip_day_execution = False

        for _, kind, val in day_events:
            if kind == EventType.MISSED:
                state, log = engine.record(state, log, Event(day=day, kind=EventType.MISSED))
                dirty = True
                skip_day_execution = True
            elif kind == EventType.BUDGET_CHANGED:
                effective_budget = val
                budget_in_force_per_day[day] = effective_budget
                state, log = engine.record(
                    state, log, Event(day=day, kind=EventType.BUDGET_CHANGED, value=val)
                )
                dirty = True
            elif kind == EventType.DEADLINE_CHANGED:
                effective_deadline = val
                state, log = engine.record(
                    state, log, Event(day=day, kind=EventType.DEADLINE_CHANGED, value=val)
                )
                dirty = True

        if day > effective_deadline:
            break

        if dirty and arm in ("adapt", "no_review"):
            replan_ctx = PlanContext(
                goal=scenario.goal,
                deadline_day=effective_deadline,
                budget=effective_budget,
                current_day=day,
            )
            plan = engine.replan(state, log, replan_ctx, review_urgency=review_urgency)
            plan_days = plan.days
            trace_coverage = min(trace_coverage, compute_plan_trace_coverage(plan))
            dirty = False

        if skip_day_execution:
            continue

        # Look up activities scheduled for current day
        current_day_plan = next((d for d in plan_days if d.day == day), None)
        if current_day_plan is None:
            continue

        day_done_acts: list[str] = []
        for aid in current_day_plan.activities:
            a = engine.activities[aid]
            c = a.target_concept

            if a.type == ActivityType.LESSON:
                state, log = engine.record(
                    state,
                    log,
                    Event(
                        day=day,
                        kind=EventType.COMPLETED,
                        activity_id=aid,
                        minutes_elapsed=a.duration,
                        correct=None,
                    ),
                )
                sim.apply_activity(c, is_lesson=True, day=day)
            else:
                p_before = state.concepts[c].p
                pred = float(engine.model.predict_correct(p_before, a.difficulty))
                correct = sim.respond(c, a.activity_id, a.difficulty, tag="run")
                attempts.append([round(pred, 4), bool(correct)])

                state_before = state
                state, log = engine.record(
                    state,
                    log,
                    Event(
                        day=day,
                        kind=EventType.COMPLETED,
                        activity_id=aid,
                        minutes_elapsed=a.duration,
                        correct=correct,
                    ),
                )
                sim.apply_activity(c, is_lesson=False, day=day)

                if (
                    not state_before.concepts[c].needs_remediation
                    and state.concepts[c].needs_remediation
                ):
                    dirty = True

            for concept_id in sim.theta:
                peak_theta[concept_id] = max(peak_theta[concept_id], sim.theta[concept_id])
            day_done_acts.append(aid)

        if day_done_acts:
            executed_activities_by_day[day] = day_done_acts

    # Settle simulated memory decay to final effective deadline
    sim.settle(effective_deadline)
    for c in sim.theta:
        peak_theta[c] = max(peak_theta[c], sim.theta[c])

    # Convert executed activity dictionary to PlanDay sequence for audit
    executed_plan_days = tuple(
        PlanDay(
            day=d,
            activities=tuple(acts),
            duration=sum(engine.activities[a].duration for a in acts),
        )
        for d, acts in sorted(executed_activities_by_day.items())
    )

    prereq_violations = count_prerequisite_violations(engine, start_state, executed_plan_days)
    budget_violations = count_budget_violations(
        engine, executed_plan_days, lambda d: budget_in_force_per_day.get(d, scenario.budget)
    )

    goal_true_mastery = round(sim.theta[scenario.goal], 4)
    goal_mastered = goal_true_mastery >= TRUE_MASTERY_CUTOFF
    need_concepts = {scenario.goal} | engine.graph.ancestors(scenario.goal)
    mean_true_mastery = round(sum(sim.theta[c] for c in need_concepts) / len(need_concepts), 4)

    reached = [c for c in need_concepts if peak_theta[c] >= TRUE_MASTERY_CUTOFF]
    retention = (
        round(sum(sim.theta[c] / peak_theta[c] for c in reached) / len(reached), 4)
        if reached
        else 1.0
    )

    return {
        "arm": arm,
        "scenario": scenario.name,
        "seed": seed,
        "goal_true_mastery": goal_true_mastery,
        "goal_mastered": goal_mastered,
        "mean_true_mastery_goal_and_ancestors": mean_true_mastery,
        "retention": retention,
        "days_used": len(executed_activities_by_day),
        "executed_minutes_per_day": {
            d: sum(engine.activities[a].duration for a in acts)
            for d, acts in executed_activities_by_day.items()
        },
        "prerequisite_violations": prereq_violations,
        "budget_violations": budget_violations,
        "attempts": attempts,
        "plan_trace_coverage": trace_coverage,
        "total_activities_completed": sum(
            len(acts) for acts in executed_activities_by_day.values()
        ),
    }
