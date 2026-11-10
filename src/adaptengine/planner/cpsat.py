"""Exact CP-SAT scheduler (W8 O.4, D60; optional `[solver]` extra with OR-Tools).

Same problem as the branch-and-bound oracle (planner/oracle.py): assign activity occurrences to
days within capacity and precedence (day(p) <= day(a); same-day order follows the given token
order, which is topological), minimising the last used day. Used only when
EngineConfig.scheduler == "cpsat"; without OR-Tools, `available()` is False and the planner keeps
greedy + oracle. Plans are checked by the same audits as greedy/oracle plans.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ..core.schema import PlanStatus


def available() -> bool:
    try:
        from ortools.sat.python import cp_model  # noqa: F401
    except ImportError:
        return False
    return True


def solve_cpsat(
    activities: Sequence[Any],
    predecessors: Mapping[str, Sequence[str]],
    budget: int,
    num_days: int,
    used_first_day: int = 0,
    time_limit_s: float = 5.0,
) -> tuple[PlanStatus, Optional[list[list[str]]], dict]:
    from ortools.sat.python import cp_model

    if num_days <= 0:
        return PlanStatus.INFEASIBLE, None, {}
    toks = [a.activity_id for a in activities]
    dur = {a.activity_id: a.duration for a in activities}
    m = cp_model.CpModel()
    day = {t: m.NewIntVar(0, num_days - 1, f"d_{i}") for i, t in enumerate(toks)}
    x = {}
    for i, t in enumerate(toks):
        lits = []
        for d in range(num_days):
            x[t, d] = m.NewBoolVar(f"x_{i}_{d}")
            lits.append(x[t, d])
        m.AddExactlyOne(lits)
        m.Add(day[t] == sum(d * x[t, d] for d in range(num_days)))
    for d in range(num_days):
        cap = budget - (used_first_day if d == 0 else 0)
        m.Add(sum(dur[t] * x[t, d] for t in toks) <= cap)
    for t, preds in predecessors.items():
        for p in preds:
            m.Add(day[p] <= day[t])
    makespan = m.NewIntVar(0, num_days - 1, "makespan")
    for t in toks:
        m.Add(makespan >= day[t])
    m.Minimize(makespan)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 1  # deterministic
    solver.parameters.random_seed = 0
    st = solver.Solve(m)
    info = {"status": solver.StatusName(st), "wall_s": round(solver.WallTime(), 4)}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        out: list[list[str]] = [[] for _ in range(num_days)]
        for t in toks:  # token order is topological, so same-day precedence holds
            out[solver.Value(day[t])].append(t)
        last = max((i for i, ts in enumerate(out) if ts), default=-1)
        return PlanStatus.FEASIBLE, out[: last + 1], info
    if st == cp_model.INFEASIBLE:
        return PlanStatus.INFEASIBLE, None, info
    return PlanStatus.UNKNOWN, None, info
