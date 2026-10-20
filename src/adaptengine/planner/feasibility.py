import math
from typing import Mapping, Sequence, Optional
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.schema import Activity, PlanContext
from ..curriculum.graph import CurriculumGraph


class FeasibilityCheckResult:
    def __init__(
        self,
        is_feasible: bool,
        reason: Optional[str] = None,
        shortfall_days: int = 0,
        options: Sequence[str] = (),
    ):
        self.is_feasible = is_feasible
        self.reason = reason
        self.shortfall_days = shortfall_days
        self.options = tuple(options)


def check_feasibility_bounds(
    graph: CurriculumGraph,
    workload: Mapping[str, Sequence[Activity]],
    ctx: PlanContext,
    greedy_days_estimate: Optional[int] = None,
    cfg: EngineConfig = DEFAULT_CONFIG,
) -> FeasibilityCheckResult:
    """Evaluate mathematical feasibility bounds (T5, TC3.4).

    Bounds checked:
    1. Activity duration bound: Any needed item longer than daily budget B.
    2. Total duration bound: ceil(total_minutes / B) > days_left.
    3. Critical path bound: ceil(critical_path_minutes / B) > days_left.

    Returns:
        FeasibilityCheckResult(is_feasible, reason, shortfall_days, options)
    """
    days_left = ctx.deadline_day - ctx.current_day + 1
    all_activities = [a for acts in workload.values() for a in acts]

    if not all_activities:
        # No work required
        return FeasibilityCheckResult(is_feasible=True)

    # 1. Activity duration bound
    oversized = [a for a in all_activities if a.duration > ctx.budget]
    if oversized:
        max_dur = max(a.duration for a in oversized)
        larger_budgets = [b for b in cfg.allowed_budgets if b >= max_dur]
        options = [
            f"Increase daily budget to {b} min to accommodate longest activity ({max_dur} min)"
            for b in larger_budgets
        ]
        return FeasibilityCheckResult(
            is_feasible=False,
            reason="ACTIVITY_EXCEEDS_BUDGET",
            shortfall_days=0,
            options=options,
        )

    # 2. Total duration bound
    total_minutes = sum(a.duration for a in all_activities)
    min_days_total = math.ceil(total_minutes / ctx.budget)

    # 3. Critical path bound
    concept_durations = {c: sum(a.duration for a in acts) for c, acts in workload.items()}
    cp: dict[str, int] = {}
    for c in graph.topological_order():
        dur = concept_durations.get(c, 0)
        preds = graph.prerequisites(c)
        if not preds:
            cp[c] = dur
        else:
            cp[c] = dur + max(cp.get(p, 0) for p in preds)

    critical_path_minutes = cp.get(ctx.goal, 0)
    min_days_critical = math.ceil(critical_path_minutes / ctx.budget)

    min_required_days = max(min_days_total, min_days_critical)

    if min_required_days > days_left:
        shortfall = min_required_days - days_left
        reason = (
            "CRITICAL_PATH_EXCEEDS_DEADLINE"
            if min_days_critical > min_days_total
            else "INSUFFICIENT_TIME_BUDGET"
        )

        options: list[str] = []
        # Option A: larger budgets from allowed_budgets
        for b in cfg.allowed_budgets:
            if b > ctx.budget:
                new_min_days = max(
                    math.ceil(total_minutes / b), math.ceil(critical_path_minutes / b)
                )
                if new_min_days <= days_left:
                    options.append(
                        f"Increase daily budget to {b} min (fits in {new_min_days} days)"
                    )
                else:
                    options.append(
                        f"Increase daily budget to {b} min (requires {new_min_days} days)"
                    )

        # Option B: longer deadline
        if greedy_days_estimate is not None and greedy_days_estimate > min_required_days:
            options.append(
                f"Extend deadline by at least {shortfall} days to day {ctx.current_day + min_required_days - 1} "
                f"(greedy upper bound: day {ctx.current_day + greedy_days_estimate - 1})"
            )
        else:
            options.append(
                f"Extend deadline by at least {shortfall} days to day {ctx.current_day + min_required_days - 1}"
            )

        return FeasibilityCheckResult(
            is_feasible=False,
            reason=reason,
            shortfall_days=shortfall,
            options=options,
        )

    return FeasibilityCheckResult(is_feasible=True)
