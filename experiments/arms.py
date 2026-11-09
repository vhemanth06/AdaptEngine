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
from experiments.checks import (
    count_budget_violations,
    count_executed_prereq_violations,
    count_plan_prereq_violations,
)
from adaptengine.learner.state import ExecutionLog, is_evidence_mastered
from experiments.stats import selected_coverage
from experiments.sim import SimProfile, TRUE_MASTERY_CUTOFF, make_sim


# Arms that use the engine's closed loop (Engine.next_activities, T2.2)
CLOSED_LOOP_ARMS = ("adapt", "no_review")


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
    # Size the horizon on new-content days only; maintenance review days (D43) are excluded.
    last_new = max(
        (
            t["day"]
            for t in uncapped_plan.trace
            if t.get("decision") == "SELECTED" and t.get("reason") != "REVIEW_DUE"
        ),
        default=0,
    )
    deadline = max(3, sum(1 for d in uncapped_plan.days if d.day <= last_new) + 2)

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
    # W7 T4.1 stress cases
    elif name == "missed_2days":
        return Scenario(
            "missed_2days",
            budget=budget,
            deadline=deadline,
            goal=goal,
            events=((2, EventType.MISSED, None), (3, EventType.MISSED, None)),
        )
    elif name == "budget_crash":
        if budget != 30:
            return None
        return Scenario(
            "budget_crash",
            budget=budget,
            deadline=deadline,
            goal=goal,
            events=((2, EventType.BUDGET_CHANGED, 5),),
        )
    elif name == "deadline_halved":
        return Scenario(
            "deadline_halved",
            budget=budget,
            deadline=deadline,
            goal=goal,
            events=((2, EventType.DEADLINE_CHANGED, max(2, deadline // 2)),),
        )
    elif name == "forgetting_21":
        return Scenario("forgetting_21", budget=budget, deadline=21, goal=goal, events=())
    else:
        raise ValueError(f"Unknown scenario name: {name}")


def compute_plan_trace_coverage(plan: Plan) -> float:
    """Explanation coverage: exactly one SELECTED record per planned (day, activity) (T1.4)."""
    return selected_coverage(plan)


def run_episode(
    engine,
    seed: int,
    scenario: Scenario,
    arm: str,
    profile: SimProfile,
    world: str = "S0",
    sim_kw: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Execute a single closed-loop episode day-by-day under the specified arm and scenario.

    world selects the simulator variant (S0-S4, T4.2); sim_kw is passed to the SimLearner.
    """
    sim = make_sim(engine, seed, profile, world=world, **(sim_kw or {}))
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
    log = ExecutionLog()

    peak_theta = dict(sim.theta)
    attempts: list[list[Any]] = []
    exercise_log: list[list[Any]] = []  # [concept, activity_id, difficulty, correct] (T3.5)
    executed_activities_by_day: dict[int, list[str]] = {}
    effective_budget = scenario.budget
    effective_deadline = scenario.deadline
    budget_in_force_per_day: dict[int, int] = {}
    idle_days = 0
    closed_loop = arm in CLOSED_LOOP_ARMS
    goal = scenario.goal
    minutes_so_far = 0
    goal_traj: list[list[float]] = [[0, round(sim.theta[goal], 4)]]
    minutes_to_goal_mastery: Optional[int] = 0 if sim.theta[goal] >= TRUE_MASTERY_CUTOFF else None

    def execute(aid: str, day: int) -> Optional[bool]:
        """Run one activity on the simulated learner and record it; returns correctness."""
        nonlocal state, log, minutes_so_far, minutes_to_goal_mastery
        a = engine.activities[aid]
        c = a.target_concept
        correct: Optional[bool] = None
        if a.type == ActivityType.EXERCISE:
            pred = float(engine.model.predict_correct(state.concepts[c].p, a.difficulty))
            correct = sim.respond(c, a.activity_id, a.difficulty, tag="run")
            attempts.append([round(pred, 4), bool(correct)])
            exercise_log.append([c, a.activity_id, a.difficulty, bool(correct)])
        ev = Event(
            day=day,
            kind=EventType.COMPLETED,
            activity_id=aid,
            minutes_elapsed=a.duration,
            correct=correct,
        )
        state, log = engine.record(state, log, ev)
        sim.apply_activity(c, is_lesson=a.type == ActivityType.LESSON, day=day)
        for concept_id in sim.theta:
            peak_theta[concept_id] = max(peak_theta[concept_id], sim.theta[concept_id])
        minutes_so_far += a.duration
        goal_traj.append([minutes_so_far, round(sim.theta[goal], 4)])
        if minutes_to_goal_mastery is None and sim.theta[goal] >= TRUE_MASTERY_CUTOFF:
            minutes_to_goal_mastery = minutes_so_far
        return correct

    for day in range(1, effective_deadline + 1):
        budget_in_force_per_day[day] = effective_budget

        # Apply scenario events for this day
        day_events = [e for e in scenario.events if e[0] == day]
        skip_day_execution = False

        for _, kind, val in day_events:
            if kind == EventType.MISSED:
                state, log = engine.record(state, log, Event(day=day, kind=EventType.MISSED))
                skip_day_execution = True
            elif kind == EventType.BUDGET_CHANGED:
                effective_budget = val
                budget_in_force_per_day[day] = effective_budget
                state, log = engine.record(
                    state, log, Event(day=day, kind=EventType.BUDGET_CHANGED, value=val)
                )
            elif kind == EventType.DEADLINE_CHANGED:
                effective_deadline = val
                state, log = engine.record(
                    state, log, Event(day=day, kind=EventType.DEADLINE_CHANGED, value=val)
                )

        if day > effective_deadline:
            break
        if skip_day_execution:
            continue

        day_done_acts: list[str] = []
        if closed_loop:
            # T2.2: rolling horizon. Replan from the real state at the start of the day and after
            # every wrong answer; execute only today's slice.
            used = 0
            while True:
                ctx = PlanContext(
                    goal=scenario.goal,
                    deadline_day=effective_deadline,
                    budget=effective_budget,
                    current_day=day,
                )
                today, plan = engine.next_activities(state, log, ctx, review_urgency=review_urgency)
                trace_coverage = min(trace_coverage, compute_plan_trace_coverage(plan))
                if today is None:
                    break
                surprised = False
                for aid in today.activities:
                    if used + engine.activities[aid].duration > effective_budget:
                        break  # defensive; the engine already respects minutes_used_today
                    correct = execute(aid, day)
                    used += engine.activities[aid].duration
                    day_done_acts.append(aid)
                    if correct is False:
                        surprised = True
                        break
                if not surprised:
                    break
        else:
            # no_replan / static: fixed initial schedule, never replanned (W6 baselines)
            current_day_plan = next((d for d in plan_days if d.day == day), None)
            for aid in current_day_plan.activities if current_day_plan else ():
                execute(aid, day)
                day_done_acts.append(aid)

        if not day_done_acts and not is_evidence_mastered(
            state.concepts[scenario.goal], engine.config
        ):
            idle_days += 1

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

    plan_prereq_violations = count_plan_prereq_violations(engine, start_state, executed_plan_days)
    executed_prereq_violations = count_executed_prereq_violations(engine, start_state, log)
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

    all_required_mastered = all(sim.theta[c] >= TRUE_MASTERY_CUTOFF for c in need_concepts)
    reviewed = {c for c in reached if state.concepts[c].n_reviews > 0}

    def mean_ret(cs):
        return round(sum(sim.theta[c] / peak_theta[c] for c in cs) / len(cs), 4) if cs else None

    return {
        "world": sim.world,
        "all_required_mastered": all_required_mastered,
        "minutes_to_goal_mastery": minutes_to_goal_mastery,
        "goal_theta_by_minutes": goal_traj,
        "deadline_violations": sum(1 for d in executed_activities_by_day if d > effective_deadline),
        "retention_reviewed": mean_ret(reviewed),
        "retention_not_reviewed": mean_ret(set(reached) - reviewed),
        "goal_evidence_mastered": is_evidence_mastered(state.concepts[goal], engine.config),
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
        "plan_prereq_violations": plan_prereq_violations,
        "executed_prereq_violations": executed_prereq_violations,
        "budget_violations": budget_violations,
        "attempts": attempts,
        "exercise_log": exercise_log,
        "plan_trace_coverage": trace_coverage,
        "idle_days": idle_days,
        "minutes_used": sum(
            engine.activities[a].duration
            for acts in executed_activities_by_day.values()
            for a in acts
        ),
        "total_activities_completed": sum(
            len(acts) for acts in executed_activities_by_day.values()
        ),
    }
