"""Planner arms, scenarios, and closed-loop episode execution harness (W6 Step 4).

Supports four comparison arms:
- adapt: Full engine planning and replanning on events with spaced review and remediation.
- no_review: Full replanning, but review urgency set to 0.0 (review disabled).
- no_replan: Initial plan only; missed days or events are not recovered.
- static: State-agnostic topological sequence packed next-fit into daily budgets.

W8 (WP-A):
- static_loop: static's topological order (lessons, then exercises), then keeps cycling the
  required exercises until the deadline; ignores learner state (A.1).
- random_eligible: uniform (keyed RNG) among required-path activities whose direct prerequisites
  are evidence-mastered in the recorded state and that fit the day's remaining budget (A.1).
- adapt_dx: the engine's diagnostic first (item minutes charged to day 1, spilling over if they
  exceed the budget), then the adapt closed loop from the diagnosed state (A.4).
- Scenarios take a policy-independent horizon (7/14/21 days) or "w7" (A.2).

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
from experiments.sim import SimProfile, TRUE_MASTERY_CUTOFF, keyed_uniform, make_sim


# Arms that use the engine's closed loop (Engine.next_activities, T2.2)
CLOSED_LOOP_ARMS = ("adapt", "no_review", "adapt_dx")
# W8 A.1 baselines executed day by day without the planner
SEQUENCE_ARMS = ("static_loop", "random_eligible")
HORIZONS = ("w7", 7, 14, 21)  # W8 A.2


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


def static_loop_sequence(engine, goal: str) -> tuple[list[Any], list[Any]]:
    """(one pass, cycled exercises) for static_loop: every required lesson in topological concept
    order, then every required exercise in topological order; the exercises then repeat."""
    order = [
        c for c in engine.graph.topological_order() if c in {goal} | engine.graph.ancestors(goal)
    ]
    acts = sorted(engine.activities.values(), key=lambda a: a.activity_id)
    lessons = [
        a for c in order for a in acts if a.target_concept == c and a.type == ActivityType.LESSON
    ]
    exs = [
        a for c in order for a in acts if a.target_concept == c and a.type == ActivityType.EXERCISE
    ]
    return lessons + exs, exs


def get_scenario(
    name: str, engine, start_state, goal: str, budget: int, horizon: Any = "w7"
) -> Optional[Scenario]:
    """Construct a standardized scenario (calm, missed_day, budget_drop, deadline_cut, ...).

    horizon (W8 A.2): an int fixes the deadline (policy-independent); "w7" keeps the W7 rule
    (the given engine's uncapped plan length + 2), kept for continuity only.
    """
    if horizon == "w7":
        uncapped_ctx = PlanContext(goal=goal, deadline_day=60, budget=budget, current_day=1)
        uncapped_plan = engine.plan(start_state, uncapped_ctx)
        # Size the horizon on new-content days only; maintenance review days (D43) are excluded.
        last_new = max(
            (
                t["day"]
                for t in uncapped_plan.trace
                if t.get("decision") == "SELECTED"
                and t.get("reason") not in ("REVIEW_DUE", "CONSOLIDATION")
            ),
            default=0,
        )
        deadline = max(3, sum(1 for d in uncapped_plan.days if d.day <= last_new) + 2)
    elif isinstance(horizon, int) and not isinstance(horizon, bool) and horizon >= 3:
        deadline = horizon
    else:
        raise ValueError(f"horizon must be 'w7' or an int >= 3, got {horizon!r}")

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
    next_fn: Optional[Any] = None,
    on_execute: Optional[Any] = None,
) -> dict[str, Any]:
    """Execute a single closed-loop episode day-by-day under the specified arm and scenario.

    world selects the simulator variant (S0-S4, T4.2); sim_kw is passed to the SimLearner.
    W8: next_fn(state, log, ctx, review_urgency=...) replaces Engine.next_activities in the closed
    loop (A3 orchestrator); on_execute(activity, correct, day) is called after every executed
    activity (bandit reward feedback).
    """
    sim = make_sim(engine, seed, profile, world=world, **(sim_kw or {}))
    start_state = engine.init_learner()

    dx_minutes = 0
    if arm == "adapt_dx":
        # A.4: diagnostic answers are sampled with their own tag and never change true theta
        dx = engine.diagnose(
            start_state,
            response_provider=lambda a: sim.respond(
                a.target_concept, a.activity_id, a.difficulty, tag="diag"
            ),
            goal_concepts=[scenario.goal]
            if engine.config.diagnostic_scope == "goal_path"
            else None,
            session_id=f"dx{seed}",
        )
        start_state = dx.state
        dx_minutes = sum(engine.activities[i.activity_id].duration for i in dx.item_log)

    review_urgency: Optional[Mapping[str, float]] = None
    if arm == "no_review":
        review_urgency = {c: 0.0 for c in engine.graph.concepts()}

    trace_coverage = 1.0
    plan_days: Sequence[PlanDay] = ()
    if arm == "static":
        plan_days = static_days(engine, scenario.goal, scenario.budget)
        trace_coverage = 0.0  # Static baseline does not use engine planner
    elif arm in SEQUENCE_ARMS:
        trace_coverage = 0.0  # W8 baselines do not use the engine planner
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
    activity_log: list[
        list[Any]
    ] = []  # [concept, activity_id, is_lesson, difficulty, correct, day]
    executed_activities_by_day: dict[int, list[str]] = {}
    effective_budget = scenario.budget
    effective_deadline = scenario.deadline
    budget_in_force_per_day: dict[int, int] = {}
    idle_days_unmastered = 0  # W7 `idle_days`: no work while the goal is believed unmastered
    idle_days_total = 0  # F.2: any study day (not missed) with 0 minutes
    study_days_budget = 0  # minutes available on non-missed days (utilisation denominator)
    closed_loop = arm in CLOSED_LOOP_ARMS
    goal = scenario.goal
    minutes_so_far = dx_minutes
    dx_left = dx_minutes  # diagnostic minutes still to charge (day 1, spilling over)
    goal_traj: list[list[float]] = [[0, round(sim.theta[goal], 4)]]
    minutes_to_goal_mastery: Optional[int] = 0 if sim.theta[goal] >= TRUE_MASTERY_CUTOFF else None
    if dx_minutes:
        goal_traj.append([dx_minutes, round(sim.theta[goal], 4)])
    loop_pass, loop_cycle = static_loop_sequence(engine, goal) if arm == "static_loop" else ([], [])
    loop_ptr = 0
    need_sorted = sorted({goal} | engine.graph.ancestors(goal))
    req_acts = sorted(
        (a for a in engine.activities.values() if a.target_concept in need_sorted),
        key=lambda a: a.activity_id,
    )

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
        activity_log.append([c, aid, a.type == ActivityType.LESSON, a.difficulty, correct, day])
        sim.apply_activity(c, is_lesson=a.type == ActivityType.LESSON, day=day)
        for concept_id in sim.theta:
            peak_theta[concept_id] = max(peak_theta[concept_id], sim.theta[concept_id])
        minutes_so_far += a.duration
        goal_traj.append([minutes_so_far, round(sim.theta[goal], 4)])
        if minutes_to_goal_mastery is None and sim.theta[goal] >= TRUE_MASTERY_CUTOFF:
            minutes_to_goal_mastery = minutes_so_far
        if on_execute is not None:
            on_execute(a, correct, day)
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

        study_days_budget += effective_budget
        day_done_acts: list[str] = []
        charged = min(dx_left, effective_budget)  # A.4: diagnostic minutes use today's budget
        dx_left -= charged
        if closed_loop:
            # T2.2: rolling horizon. Replan from the real state at the start of the day and after
            # every wrong answer; execute only today's slice.
            used = charged
            while used < effective_budget:
                ctx = PlanContext(
                    goal=scenario.goal,
                    deadline_day=effective_deadline,
                    budget=effective_budget,
                    current_day=day,
                )
                today, plan = (next_fn or engine.next_activities)(
                    state, log, ctx, review_urgency=review_urgency
                )
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
        elif arm == "static_loop":
            used = 0
            while loop_pass:
                if loop_ptr < len(loop_pass):
                    a = loop_pass[loop_ptr]
                elif loop_cycle:
                    a = loop_cycle[(loop_ptr - len(loop_pass)) % len(loop_cycle)]
                else:
                    break
                if used + a.duration > effective_budget:
                    break  # next-fit, like static
                execute(a.activity_id, day)
                used += a.duration
                loop_ptr += 1
                day_done_acts.append(a.activity_id)
        elif arm == "random_eligible":
            used, slot = 0, 0
            while True:
                elig = [
                    a
                    for a in req_acts
                    if used + a.duration <= effective_budget
                    and all(
                        is_evidence_mastered(state.concepts[q], engine.config)
                        for q in engine.graph.prerequisites(a.target_concept)
                    )
                ]
                if not elig:
                    break
                a = elig[int(keyed_uniform(seed, "random_eligible", day, slot) * len(elig))]
                execute(a.activity_id, day)
                used += a.duration
                slot += 1
                day_done_acts.append(a.activity_id)
        else:
            # no_replan / static: fixed initial schedule, never replanned (W6 baselines)
            current_day_plan = next((d for d in plan_days if d.day == day), None)
            for aid in current_day_plan.activities if current_day_plan else ():
                execute(aid, day)
                day_done_acts.append(aid)

        if not day_done_acts and not charged:
            idle_days_total += 1
            if not is_evidence_mastered(state.concepts[scenario.goal], engine.config):
                idle_days_unmastered += 1

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

    # A.3: believed evidence-mastered at the end but true theta < cutoff, over required concepts
    believed = [c for c in need_concepts if is_evidence_mastered(state.concepts[c], engine.config)]
    false_mastered = [c for c in believed if sim.theta[c] < TRUE_MASTERY_CUTOFF]
    minutes_used = dx_minutes + sum(
        engine.activities[a].duration for acts in executed_activities_by_day.values() for a in acts
    )

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
        "final_p": {c: round(state.concepts[c].p, 4) for c in sorted(need_concepts)},
        "final_theta": {c: round(sim.theta[c], 4) for c in sorted(need_concepts)},
        "exercise_log": exercise_log,
        "activity_log": activity_log,
        "plan_trace_coverage": trace_coverage,
        "idle_days_unmastered": idle_days_unmastered,
        "idle_days_total": idle_days_total,
        "believed_mastered": len(believed),
        "false_mastered": len(false_mastered),
        "false_mastery_rate": round(len(false_mastered) / len(believed), 4) if believed else 0.0,
        "dx_minutes": dx_minutes,
        "minutes_available": study_days_budget,
        "minute_utilisation": round(minutes_used / study_days_budget, 4)
        if study_days_budget
        else 0.0,
        "minutes_used": minutes_used,
        "total_activities_completed": sum(
            len(acts) for acts in executed_activities_by_day.values()
        ),
    }
