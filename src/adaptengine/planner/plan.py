from typing import Mapping, Sequence, Optional
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.errors import ValidationError, UnknownConceptError
from ..core.schema import Activity, PlanContext, Plan, PlanDay, PlanStatus
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerState
from ..learner.adapter import MasteryModel, CustomBKT
from .workload import compute_workload, ContentInsufficientError
from .feasibility import check_feasibility_bounds
from .schedule import run_greedy_schedule
from .oracle import solve_oracle


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

    if ctx.budget not in cfg.allowed_budgets:
        raise ValidationError(
            f"PlanContext budget {ctx.budget} not in allowed_budgets {cfg.allowed_budgets}"
        )

    if ctx.goal not in graph.concepts():
        raise UnknownConceptError(f"Goal concept '{ctx.goal}' not in graph")

    if model is None:
        model = CustomBKT(cfg)

    # 1. Compute workload
    try:
        workload, init_trace, initial_projected_p = compute_workload(
            graph, activities, state, ctx.goal, done_ids=done_ids, model=model, cfg=cfg
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
        graph, workload, initial_projected_p, ctx, model=model, cfg=cfg
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
    # Build complete precedence graph between activities
    act_preds: dict[str, list[str]] = {a.activity_id: [] for a in all_activities}

    # Concept order dependencies
    concept_last_act: dict[str, str] = {}
    concept_first_act: dict[str, str] = {}
    for c, acts in workload.items():
        if acts:
            concept_first_act[c] = acts[0].activity_id
            concept_last_act[c] = acts[-1].activity_id
            # Within concept: sequential dependency
            for i in range(len(acts) - 1):
                act_preds[acts[i + 1].activity_id].append(acts[i].activity_id)

    # Across concepts: prerequisites' final activities precede concept's first activity
    for c in workload:
        first_act = concept_first_act.get(c)
        if first_act:
            for pred_c in graph.prerequisites(c):
                last_act = concept_last_act.get(pred_c)
                if last_act and last_act not in act_preds[first_act]:
                    act_preds[first_act].append(last_act)

    num_days = ctx.deadline_day - ctx.current_day + 1
    oracle_status, assignment, nodes_explored = solve_oracle(
        all_activities, act_preds, ctx.budget, num_days, node_limit=cfg.oracle_node_limit
    )

    if oracle_status == PlanStatus.FEASIBLE and assignment is not None:
        oracle_days: list[PlanDay] = []
        for d_idx, day_aids in enumerate(assignment):
            day_num = ctx.current_day + d_idx
            dur = sum(activities[aid].duration for aid in day_aids)
            oracle_days.append(PlanDay(day=day_num, activities=tuple(day_aids), duration=dur))

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
