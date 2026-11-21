"""One simulated learner through one scenario under one arm.

closed: Engine.next_activities at the start of each day and after every wrong answer; only today's
slice is executed. no_replan: the first plan, never replanned. static: goal and its ancestors in
topological order, lessons then exercises by id, next-fit packed into the daily budget.
Every plan the engine produces (first plan and each replan) is checked by audit.plan_violations.
"""

from __future__ import annotations

from typing import Any, Optional

from adaptengine.core.schema import ActivityType, Event, EventType, Plan, PlanContext, PlanDay
from adaptengine.learner.state import ExecutionLog, is_evidence_mastered

from .arms import Arm
from .audit import executed_violations, plan_violations
from .scenarios import Scenario
from .simulator import TRUE_MASTERY, make_learner

REVIEW_REASONS = ("REVIEW_DUE", "REVIEW_SCHEDULED")


def static_days(engine, goal: str, budget: int) -> tuple[PlanDay, ...]:
    need = {goal} | engine.graph.ancestors(goal)
    seq = []
    for c in engine.graph.topological_order():
        if c in need:
            seq += sorted(
                (a for a in engine.activities.values() if a.target_concept == c),
                key=lambda a: (a.type != ActivityType.LESSON, a.activity_id),
            )
    days, cur, used = [], [], 0
    for a in seq:
        if used + a.duration > budget:  # an activity longer than the budget gets an empty day first
            days.append(PlanDay(len(days) + 1, tuple(x.activity_id for x in cur), used))
            cur, used = [], 0
        cur.append(a)
        used += a.duration
    if cur:
        days.append(PlanDay(len(days) + 1, tuple(x.activity_id for x in cur), used))
    return tuple(days)


def first_plan(engine, state, sc: Scenario, review_urgency=None) -> Plan:
    ctx = PlanContext(goal=sc.goal, deadline_day=sc.deadline, budget=sc.budget, current_day=1)
    return engine.plan(state, ctx, review_urgency=review_urgency)


def verdict(plan: Plan) -> str:
    """FEASIBLE / GREEDY_FEASIBLE / INFEASIBLE / UNKNOWN (greedy's own plan met the deadline)."""
    if plan.status.value == "FEASIBLE" and plan.reason == "GREEDY_FEASIBLE":
        return "GREEDY_FEASIBLE"
    return plan.status.value


def plan_summary(plan: Plan) -> dict:
    return {
        "verdict": verdict(plan),
        "status": plan.status.value,
        "reason": plan.reason,
        "projected_finish_day": plan.days[-1].day if plan.days else None,
        "shortfall_days": plan.shortfall_days,
        "reviews": sum(
            1
            for t in plan.trace
            if t.get("decision") == "SELECTED" and t.get("reason") in REVIEW_REASONS
        ),
    }


def theta_at(traj, minutes: float) -> float:
    """Goal theta after the last activity that ended at or before `minutes`."""
    v = traj[0][1]
    for m, th in traj:
        if m > minutes:
            break
        v = th
    return v


def run_episode(
    engine,
    seed: int,
    sc: Scenario,
    arm: Arm,
    world: str = "S0",
    profile: str = "nominal",
    first: Optional[Plan] = None,
) -> dict[str, Any]:
    """Run one episode. `first` may pass a precomputed first plan (identical for every learner
    when no diagnostic runs); it is recomputed when the diagnostic changes the start state."""
    sim = make_learner(engine, seed, world, profile)
    state = engine.init_learner()
    out: dict[str, Any] = {"seed": seed}
    if arm.diagnose:
        res = engine.diagnose(
            state,
            lambda a: sim.respond(a.target_concept, a.activity_id, a.difficulty, tag="diag"),
            goal_concepts=sorted({sc.goal} | set(engine.graph.ancestors(sc.goal))),
            session_id=str(seed),
        )
        state = res.state
        confirmed = [c for c, x in state.concepts.items() if x.confirmed]
        out.update(
            diag_items=res.total_items,
            diag_minutes=sum(engine.activities[x.activity_id].duration for x in res.item_log),
            confirmed_at_diag=len(confirmed),
            false_confirm_at_diag=sum(sim.initial[c] < TRUE_MASTERY for c in confirmed),
        )
        first = None
    # theta at each confirmation event (diagnostic or planner check), before any later forgetting
    conf_theta = [sim.initial[c] for c, x in state.concepts.items() if x.confirmed]
    start = state
    urgency = {c: 0.0 for c in engine.graph.concepts()} if arm.no_review else None
    plan_checks = {"plans": 0, "prereq": 0, "budget": 0, "deadline": 0}

    def audit(plan, s, budget, deadline, day, used, days=None):
        v = plan_violations(engine, s, plan, budget, deadline, day, used, days)
        plan_checks["plans"] += 1
        for k in v:
            plan_checks[k] += v[k]

    if arm.mode == "static":
        plan_days = static_days(engine, sc.goal, sc.budget)
    else:
        if first is None:
            first = first_plan(engine, start, sc, urgency)
        out["first_plan"] = plan_summary(first)
        plan_days = first.days if first.status.value == "FEASIBLE" else first.best_effort_days
        if arm.mode == "no_replan":
            audit(first, start, sc.budget, sc.deadline, 1, 0, plan_days)

    log = ExecutionLog()
    peak = dict(sim.theta)
    attempts: list = []
    done_by_day: dict[int, list[str]] = {}
    budget, deadline = sc.budget, sc.deadline
    budget_on: dict[int, int] = {}
    idle = minutes = 0
    goal = sc.goal
    traj = [[0, round(sim.theta[goal], 4)]]
    to_mastery: Optional[int] = 0 if sim.theta[goal] >= TRUE_MASTERY else None

    def execute(aid: str, day: int) -> Optional[bool]:
        nonlocal state, log, minutes, to_mastery
        a = engine.activities[aid]
        c = a.target_concept
        correct = None
        if a.type == ActivityType.EXERCISE:
            pred = float(engine.model.predict_correct(state.concepts[c].p, a.difficulty))
            correct = sim.respond(c, aid, a.difficulty, tag="run")
            attempts.append((round(pred, 4), bool(correct)))
        ev = Event(
            day=day,
            kind=EventType.COMPLETED,
            activity_id=aid,
            minutes_elapsed=a.duration,
            correct=correct,
        )
        was = state.concepts[c].confirmed
        state, log = engine.record(state, log, ev)
        if state.concepts[c].confirmed and not was:
            conf_theta.append(sim.theta[c])  # the answer was drawn at this theta
        sim.learn(c, a.type == ActivityType.LESSON, day)
        for k, v in sim.theta.items():
            peak[k] = max(peak[k], v)
        minutes += a.duration
        traj.append([minutes, round(sim.theta[goal], 4)])
        if to_mastery is None and sim.theta[goal] >= TRUE_MASTERY:
            to_mastery = minutes
        return correct

    for day in range(1, deadline + 1):
        budget_on[day] = budget
        skip = False
        for _, kind, val in (e for e in sc.events if e[0] == day):
            if kind == EventType.MISSED:
                state, log = engine.record(state, log, Event(day=day, kind=EventType.MISSED))
                skip = True
            elif kind == EventType.BUDGET_CHANGED:
                budget = budget_on[day] = val
                state, log = engine.record(state, log, Event(day=day, kind=kind, value=val))
            elif kind == EventType.DEADLINE_CHANGED:
                deadline = val
                state, log = engine.record(state, log, Event(day=day, kind=kind, value=val))
        if day > deadline:
            break
        if skip:
            continue
        today_done: list[str] = []
        if arm.mode == "closed":
            used = 0
            while True:
                ctx = PlanContext(goal=goal, deadline_day=deadline, budget=budget, current_day=day)
                today, plan = engine.next_activities(state, log, ctx, review_urgency=urgency)
                audit(plan, state, budget, deadline, day, used)
                if today is None:
                    break
                surprised = False
                for aid in today.activities:
                    if used + engine.activities[aid].duration > budget:
                        break  # defensive; the engine already respects minutes used today
                    correct = execute(aid, day)
                    used += engine.activities[aid].duration
                    today_done.append(aid)
                    if correct is False:
                        surprised = True
                        break
                if not surprised:
                    break
        else:
            pd = next((d for d in plan_days if d.day == day), None)
            for aid in pd.activities if pd else ():
                execute(aid, day)
                today_done.append(aid)
        if not today_done and not is_evidence_mastered(state.concepts[goal], engine.config):
            idle += 1
        if today_done:
            done_by_day[day] = today_done

    sim.settle(deadline)
    for k, v in sim.theta.items():
        peak[k] = max(peak[k], v)
    need = {goal} | engine.graph.ancestors(goal)
    reached = [c for c in need if peak[c] >= TRUE_MASTERY]
    reviewed = {c for c in reached if state.concepts[c].n_reviews > 0}

    def ret(cs):
        return round(sum(sim.theta[c] / peak[c] for c in cs) / len(cs), 4) if cs else None

    day_minutes = {
        d: sum(engine.activities[a].duration for a in acts) for d, acts in done_by_day.items()
    }
    out.update(
        goal_mastered=sim.theta[goal] >= TRUE_MASTERY,
        goal_theta=round(sim.theta[goal], 4),
        all_required=all(sim.theta[c] >= TRUE_MASTERY for c in need),
        minutes=minutes,
        minutes_to_mastery=to_mastery,
        exec_viol=executed_violations(engine, start, log),
        exec_budget_viol=sum(1 for d, m in day_minutes.items() if m > budget_on.get(d, sc.budget)),
        exec_deadline_viol=sum(1 for d in done_by_day if d > deadline),
        idle_days=idle,
        ret_reviewed=ret(reviewed),
        ret_not_reviewed=ret(set(reached) - reviewed),
        attempts=attempts,
        traj=traj,
        effective_deadline=deadline,
    )
    if arm.mode != "static":
        out["plan_checks"] = plan_checks
    if arm.diagnose:
        conf_end = [c for c, x in state.concepts.items() if x.confirmed]
        out.update(
            confirmed_at_end=len(conf_end),
            false_confirm_at_end=sum(sim.theta[c] < TRUE_MASTERY for c in conf_end),
            confirmations=len(conf_theta),
            false_confirmations=sum(t < TRUE_MASTERY for t in conf_theta),
        )
    return out
