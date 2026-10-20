from typing import Any, Mapping, Optional, Sequence
from ..core.schema import PlanStatus


class OracleActivity:
    """Lightweight representation of an activity for oracle bin packing."""

    def __init__(self, activity_id: str, duration: int):
        self.activity_id = activity_id
        self.duration = duration


def solve_oracle(
    activities: Sequence[Any],
    predecessors: Mapping[str, Sequence[str]],
    budget: int,
    num_days: int,
    node_limit: int = 1000,
) -> tuple[PlanStatus, Optional[list[list[str]]], int]:
    """Exact branch-and-bound bin packing oracle with precedence constraints (T6).

    Assigns activities to days 0..(num_days - 1) such that:
    1. Daily capacity: sum(duration) <= budget for each day.
    2. Precedence: for every p in predecessors(a), day(p) <= day(a).
       If day(p) == day(a), p must be placed before a.
    3. Pruned by remaining total capacity.
    4. Bounded by node_limit: stops with PlanStatus.UNKNOWN if reached (never false INFEASIBLE).

    Returns:
        (status, assignment, nodes_explored)
        where assignment is a list of lists of activity_ids per day if FEASIBLE, else None.
    """
    if num_days <= 0:
        return PlanStatus.INFEASIBLE, None, 0

    if not activities:
        return PlanStatus.FEASIBLE, [[] for _ in range(num_days)], 0

    # Ensure topological ordering of activities according to predecessors
    act_map = {a.activity_id: a for a in activities}
    in_degree = {a.activity_id: 0 for a in activities}
    adj: dict[str, list[str]] = {a.activity_id: [] for a in activities}

    for aid, preds in predecessors.items():
        if aid in in_degree:
            for p in preds:
                if p in in_degree:
                    adj[p].append(aid)
                    in_degree[aid] += 1

    # Deterministic Kahn's algorithm
    ready = sorted([aid for aid, deg in in_degree.items() if deg == 0])
    ordered_ids: list[str] = []
    while ready:
        curr = ready.pop(0)
        ordered_ids.append(curr)
        for nxt in sorted(adj[curr]):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                ready.append(nxt)
                ready.sort()

    if len(ordered_ids) < len(activities):
        # Fallback if circular or partial dependencies
        ordered_ids = [a.activity_id for a in activities]

    ordered_acts = [act_map[aid] for aid in ordered_ids]
    n = len(ordered_acts)

    # Precompute suffix duration sums for quick pruning
    suffix_durations = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_durations[i] = suffix_durations[i + 1] + ordered_acts[i].duration

    day_durations = [0] * num_days
    day_assignments: list[list[str]] = [[] for _ in range(num_days)]
    activity_day: dict[str, int] = {}
    nodes_explored = 0

    def backtrack(index: int) -> tuple[PlanStatus, Optional[list[list[str]]]]:
        nonlocal nodes_explored
        nodes_explored += 1

        if nodes_explored >= node_limit:
            return PlanStatus.UNKNOWN, None

        if index == n:
            # All activities successfully assigned
            return PlanStatus.FEASIBLE, [list(d) for d in day_assignments]

        curr_act = ordered_acts[index]
        curr_dur = curr_act.duration

        # Capacity lower bound pruning
        rem_dur = suffix_durations[index]
        total_rem_cap = sum(budget - day_durations[d] for d in range(num_days))
        if rem_dur > total_rem_cap:
            return PlanStatus.INFEASIBLE, None

        # Determine earliest allowed day from predecessors
        earliest_day = 0
        for p in predecessors.get(curr_act.activity_id, ()):
            if p in activity_day:
                earliest_day = max(earliest_day, activity_day[p])

        hit_empty_day = False
        for d in range(earliest_day, num_days):
            if day_durations[d] + curr_dur <= budget:
                is_empty = day_durations[d] == 0
                if is_empty:
                    if hit_empty_day:
                        # Symmetric to previous empty day already explored
                        continue
                    hit_empty_day = True

                # Try assigning curr_act to day d
                day_durations[d] += curr_dur
                day_assignments[d].append(curr_act.activity_id)
                activity_day[curr_act.activity_id] = d

                status, res = backtrack(index + 1)
                if status in (PlanStatus.FEASIBLE, PlanStatus.UNKNOWN):
                    return status, res

                # Undo assignment
                day_durations[d] -= curr_dur
                day_assignments[d].pop()
                del activity_day[curr_act.activity_id]

        return PlanStatus.INFEASIBLE, None

    status, assignment = backtrack(0)
    return status, assignment, nodes_explored
