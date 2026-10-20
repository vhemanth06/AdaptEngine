from typing import Mapping, Optional
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.schema import (
    Activity,
    Plan,
    PlanContext,
    PlanStatus,
    EventType,
)
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerState, ExecutionLog
from ..learner.adapter import MasteryModel
from ..planner import plan


def compute_effective_context(
    initial_ctx: PlanContext, log: ExecutionLog
) -> tuple[Optional[PlanContext], int, int]:
    """Fold DEADLINE_CHANGED and BUDGET_CHANGED events over initial_ctx (D29, D30).

    Returns (effective_context, target_current_day, effective_deadline).
    If target_current_day > effective_deadline, effective_context is None.
    """
    deadline = initial_ctx.deadline_day
    budget = initial_ctx.budget
    current_day = initial_ctx.current_day

    minutes_per_day: dict[int, int] = {}
    for e in log.events:
        if e.kind == EventType.DEADLINE_CHANGED and e.value is not None:
            deadline = e.value
        elif e.kind == EventType.BUDGET_CHANGED and e.value is not None:
            budget = e.value
        elif e.kind == EventType.MISSED:
            # D30: replan from next day; missed day contributes zero minutes
            current_day = max(current_day, e.day + 1)
        elif e.kind in (EventType.COMPLETED, EventType.FAILED_ASSESSMENT):
            minutes_per_day[e.day] = minutes_per_day.get(e.day, 0) + e.minutes_elapsed
            if minutes_per_day[e.day] >= budget:
                # Daily budget reached or exceeded for this day; advance start day to next day
                current_day = max(current_day, e.day + 1)
            else:
                current_day = max(current_day, e.day)

    if current_day > deadline:
        return None, current_day, deadline

    return (
        PlanContext(
            goal=initial_ctx.goal,
            deadline_day=deadline,
            budget=budget,
            current_day=current_day,
        ),
        current_day,
        deadline,
    )


def replan(
    graph: CurriculumGraph,
    activities: Mapping[str, Activity],
    state: LearnerState,
    log: ExecutionLog,
    ctx: PlanContext,
    *,
    review_urgency=None,
    model: Optional[MasteryModel] = None,
    cfg: EngineConfig = DEFAULT_CONFIG,
) -> Plan:
    """Pure replanning from state, execution log, and initial context (M6).

    Rules:
    - Derive effective context from log events (D29).
    - Exclude completed activities from new plan (TC6.1, REPLAN_PRESERVED_COMPLETED).
    - If deadline tightened past start day, return INFEASIBLE proof with options.
    - If revised plan feasible, return new valid schedule without duplication.
    """
    eff_ctx, start_day, deadline = compute_effective_context(ctx, log)
    done_ids = log.completed_ids()

    # Build omission trace for completed activities (T7)
    replan_trace: list[dict] = [
        {
            "decision": "OMITTED",
            "activity_id": aid,
            "reason": "REPLAN_PRESERVED_COMPLETED",
        }
        for aid in done_ids
    ]

    if eff_ctx is None:
        shortfall = start_day - deadline
        return Plan(
            status=PlanStatus.INFEASIBLE,
            days=(),
            reason="DEADLINE_EXCEEDED",
            shortfall_days=shortfall,
            options=(
                f"Extend deadline to at least day {start_day}",
                f"Increase daily budget from {ctx.budget} minutes",
            ),
            trace=tuple(replan_trace),
        )

    # Pure invocation of planner
    revised_plan = plan(
        graph,
        activities,
        state,
        eff_ctx,
        done_ids=done_ids,
        review_urgency=review_urgency,
        model=model,
        cfg=cfg,
    )

    combined_trace = tuple(replan_trace) + revised_plan.trace
    return Plan(
        status=revised_plan.status,
        days=revised_plan.days,
        reason=revised_plan.reason,
        shortfall_days=revised_plan.shortfall_days,
        options=revised_plan.options,
        trace=combined_trace,
    )
