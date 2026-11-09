from dataclasses import replace
from typing import Mapping, Sequence, Optional
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.errors import ValidationError, UnknownConceptError
from ..core.validators import check_budget
from ..core.schema import Activity, PlanContext, Plan, PlanDay, PlanStatus
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerState
from ..learner.adapter import MasteryModel, CustomBKT
from .workload import compute_workload, ContentInsufficientError, WorkloadCache
from .feasibility import check_feasibility_bounds
from .schedule import run_greedy_schedule
from .oracle import OracleActivity, solve_oracle


def plan(
    graph: CurriculumGraph,
    activities: Mapping[str, Activity],
    state: LearnerState,
    ctx: PlanContext,
    *,
    done_ids: Sequence[str] = (),
    review_urgency: Optional[Mapping[str, float]] = None,
    model: Optional[MasteryModel] = None,
    cfg: EngineConfig = DEFAULT_CONFIG,
    workload_cache: Optional[WorkloadCache] = None,
) -> Plan:
    """Plan toward ctx.goal (see _plan_goal). If the goal can't be planned (INFEASIBLE/UNKNOWN),
    the verdict, shortfall and options are kept and best_effort_days is added (D42)."""
    kw = dict(
        done_ids=done_ids,
        review_urgency=review_urgency,
        model=model,
        cfg=cfg,
        workload_cache=workload_cache,
    )
    result = _plan_goal(graph, activities, state, ctx, **kw)
    if result.status == PlanStatus.FEASIBLE:
        return result
    days, trace = _best_effort(graph, activities, state, ctx, **kw)
    return replace(result, best_effort_days=days, trace=result.trace + tuple(trace))


def _best_effort(
    graph, activities, state, ctx, *, done_ids, review_urgency, model, cfg, workload_cache
):
    """D42: the deepest concept on the goal's path whose workload can be built is planned with the
    greedy scheduler and truncated at the deadline, so the learner keeps progressing."""
    need = {ctx.goal} | graph.ancestors(ctx.goal)
    for target in sorted(need, key=lambda c: (-graph.depth(c), c)):
        try:
            workload, _, init_p = compute_workload(
                graph,
                activities,
                state,
                target,
                done_ids=done_ids,
                model=model if model is not None else CustomBKT(cfg),
                cfg=cfg,
                cache=workload_cache,
            )
        except ContentInsufficientError:
            continue
        if not any(workload.values()):
            continue
        days, trace = run_greedy_schedule(
            graph,
            workload,
            init_p,
            replace(ctx, goal=target),
            model=model,
            cfg=cfg,
            state=state,
            activities=activities,
            review_urgency_override=review_urgency,
        )
        days = tuple(d for d in days if d.day <= ctx.deadline_day)
        if not days:
            continue
        kept = [
            {**t, "best_effort": True}
            for t in trace
            if t.get("day") is None or t["day"] <= ctx.deadline_day
        ]
        head = {"decision": "BEST_EFFORT", "target_concept": target, "reason": "DEEPEST_REACHABLE"}
        return days, [head] + kept
    return (), []


def _plan_goal(
    graph: CurriculumGraph,
    activities: Mapping[str, Activity],
    state: LearnerState,
    ctx: PlanContext,
    *,
    done_ids: Sequence[str] = (),
    review_urgency: Optional[Mapping[str, float]] = None,
    model: Optional[MasteryModel] = None,
    cfg: EngineConfig = DEFAULT_CONFIG,
    workload_cache: Optional[WorkloadCache] = None,
) -> Plan:
    """Deterministic, time-budgeted path planner with feasibility oracle (M3).

    Pipeline:
    1. Validation of inputs and bounds.
    2. Workload projection to mastery (T3).
    3. Mathematical feasibility bounds check (T5).
    4. Deterministic day-by-day greedy packing (T4).
    5. If greedy exceeds deadline, exact branch-and-bound oracle (T6).

    Returns:
        Plan(status, days, reason, shortfall_days, options, trace)
    """
    if not isinstance(ctx, PlanContext):
        raise ValidationError(f"ctx must be a PlanContext instance, got {type(ctx).__name__}")

    check_budget(ctx.budget, cfg.allowed_budgets)  # T5.1: allowed budgets come from config

    if ctx.goal not in graph.concepts():
        raise UnknownConceptError(f"Goal concept '{ctx.goal}' not in graph")

    if model is None:
        model = CustomBKT(cfg)

    # 1. Compute workload
    try:
        workload, init_trace, initial_projected_p = compute_workload(
            graph,
            activities,
            state,
            ctx.goal,
            done_ids=done_ids,
            model=model,
            cfg=cfg,
            cache=workload_cache,
        )
    except ContentInsufficientError as e:
        return Plan(
            status=PlanStatus.INFEASIBLE,
            reason="CONTENT_INSUFFICIENT",
            shortfall_days=0,
            options=("Add additional exercises for required concepts",),
            trace=({"decision": "INFEASIBLE", "reason": str(e)},),
        )

    all_activities = [a for acts in workload.values() for a in acts]
    if not all_activities:
        # All required concepts are already evidence-mastered
        return Plan(
            status=PlanStatus.FEASIBLE,
            days=(),
            reason="GOAL_ALREADY_MASTERED",
            shortfall_days=0,
            options=(),
            trace=tuple(init_trace),
        )

    # 2. Check initial mathematical feasibility bounds (before greedy)
    bound_res = check_feasibility_bounds(graph, workload, ctx, cfg=cfg)
    if not bound_res.is_feasible:
        return Plan(
            status=PlanStatus.INFEASIBLE,
            days=(),
            reason=bound_res.reason,
            shortfall_days=bound_res.shortfall_days,
            options=bound_res.options,
            trace=tuple(init_trace),
        )

    # 3. Run greedy day packing
    greedy_days, greedy_trace = run_greedy_schedule(
        graph,
        workload,
        initial_projected_p,
        ctx,
        model=model,
        cfg=cfg,
        state=state,
        activities=activities,
        review_urgency_override=review_urgency,
    )
    full_trace = list(init_trace) + list(greedy_trace)

    last_day = greedy_days[-1].day if greedy_days else ctx.current_day
    greedy_days_count = len(greedy_days)

    if last_day <= ctx.deadline_day:
        # Greedy schedule successfully meets the deadline
        return Plan(
            status=PlanStatus.FEASIBLE,
            days=greedy_days,
            reason="GREEDY_FEASIBLE",
            shortfall_days=0,
            options=(),
            trace=tuple(full_trace),
        )

    # 4. Greedy exceeded deadline: run exact branch-and-bound oracle (T6)
    # Build complete precedence graph between activity occurrences. With exercise repeats (D41)
    # an activity id can occur more than once, so the oracle works on unique occurrence tokens.
    token_aid: dict[str, str] = {}
    concept_tokens: dict[str, list[str]] = {}
    for c, acts in workload.items():
        for i, a in enumerate(acts):
            tok = f"{a.activity_id}#{c}#{i}"
            token_aid[tok] = a.activity_id
            concept_tokens.setdefault(c, []).append(tok)
    oracle_acts = [OracleActivity(t, activities[aid].duration) for t, aid in token_aid.items()]
    act_preds: dict[str, list[str]] = {t: [] for t in token_aid}
    for toks in concept_tokens.values():
        # Within concept: sequential dependency
        for i in range(len(toks) - 1):
            act_preds[toks[i + 1]].append(toks[i])
    # Across concepts: prerequisites' final occurrences precede the concept's first occurrence
    for c, toks in concept_tokens.items():
        for pred_c in graph.prerequisites(c):
            if concept_tokens.get(pred_c):
                act_preds[toks[0]].append(concept_tokens[pred_c][-1])

    num_days = ctx.deadline_day - ctx.current_day + 1
    oracle_status, assignment, nodes_explored = solve_oracle(
        oracle_acts,
        act_preds,
        ctx.budget,
        num_days,
        node_limit=cfg.oracle_node_limit,
        used_first_day=ctx.minutes_used_today,
    )

    if oracle_status == PlanStatus.FEASIBLE and assignment is not None:
        # T1.4 / TC7.1: the greedy schedule is abandoned, so its per-activity records are
        # re-tagged as superseded attempts; only ORACLE_ASSIGNED records explain the final plan.
        full_trace = list(init_trace) + _supersede(greedy_trace)
        oracle_days: list[PlanDay] = []
        for d_idx, day_tokens in enumerate(assignment):
            day_aids = [token_aid[t] for t in day_tokens]
            day_num = ctx.current_day + d_idx
            dur = sum(activities[aid].duration for aid in day_aids)
            oracle_days.append(PlanDay(day=day_num, activities=tuple(day_aids), duration=dur))
            for aid in day_aids:
                act = activities[aid]
                full_trace.append(
                    {
                        "decision": "SELECTED",
                        "activity_id": aid,
                        "target_concept": act.target_concept,
                        "day": day_num,
                        "duration": act.duration,
                        "reason": "ORACLE_ASSIGNED",
                    }
                )

        full_trace.append(
            {
                "decision": "ORACLE_ASSIGNMENT",
                "reason": "GREEDY_EXCEEDED_DEADLINE_ORACLE_FOUND_PACKING",
                "nodes_explored": nodes_explored,
            }
        )

        return Plan(
            status=PlanStatus.FEASIBLE,
            days=tuple(oracle_days),
            reason="ORACLE_ASSIGNMENT",
            shortfall_days=0,
            options=(),
            trace=tuple(full_trace),
        )

    # The greedy schedule overshot the deadline and is not the answer: mark its records superseded
    full_trace = list(init_trace) + _supersede(greedy_trace)

    # Calculate shortfall and options using greedy result as upper bound
    shortfall = last_day - ctx.deadline_day
    feas_opts = check_feasibility_bounds(
        graph, workload, ctx, greedy_days_estimate=greedy_days_count, cfg=cfg
    ).options

    if oracle_status == PlanStatus.UNKNOWN:
        full_trace.append(
            {
                "decision": "ORACLE_LIMIT_EXCEEDED",
                "reason": "NODE_LIMIT_REACHED",
                "nodes_explored": nodes_explored,
                "node_limit": cfg.oracle_node_limit,
            }
        )
        return Plan(
            status=PlanStatus.UNKNOWN,
            days=(),
            reason="ORACLE_LIMIT_EXCEEDED",
            shortfall_days=shortfall,
            options=feas_opts,
            trace=tuple(full_trace),
        )

    # oracle_status == PlanStatus.INFEASIBLE
    full_trace.append(
        {
            "decision": "ORACLE_INFEASIBLE",
            "reason": "NO_VALID_PACKING_WITHIN_DEADLINE",
            "nodes_explored": nodes_explored,
        }
    )
    return Plan(
        status=PlanStatus.INFEASIBLE,
        days=(),
        reason="ORACLE_INFEASIBLE",
        shortfall_days=shortfall,
        options=feas_opts,
        trace=tuple(full_trace),
    )


def _supersede(greedy_trace) -> list:
    """Re-tag an abandoned greedy schedule's SELECTED/DEFERRED records (T1.4 / TC7.1)."""
    return [
        (
            {**r, "decision": "GREEDY_ATTEMPT", "superseded": True, "greedy_decision": d}
            if (d := r.get("decision")) in ("SELECTED", "DEFERRED")
            else r
        )
        for r in greedy_trace
    ]


def serialize_plan(plan: Plan, cfg: EngineConfig = DEFAULT_CONFIG) -> dict:
    """Serialize a Plan into pure primitives including the configuration hash (T7)."""
    from ..core.config import config_hash

    return {
        "config_hash": config_hash(cfg),
        "status": plan.status.value,
        "reason": plan.reason,
        "shortfall_days": plan.shortfall_days,
        "options": list(plan.options),
        "days": [
            {
                "day": d.day,
                "activities": list(d.activities),
                "duration": d.duration,
            }
            for d in plan.days
        ],
        "best_effort_days": [
            {"day": d.day, "activities": list(d.activities), "duration": d.duration}
            for d in plan.best_effort_days
        ],
        "trace": list(plan.trace),
    }
