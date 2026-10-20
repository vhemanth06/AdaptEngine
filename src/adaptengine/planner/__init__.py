"""Planner package: deterministic path planning, difficulty policy, and feasibility oracle."""

from .difficulty import select_exercise
from .workload import compute_workload, ContentInsufficientError
from .feasibility import check_feasibility_bounds, FeasibilityCheckResult
from .schedule import run_greedy_schedule
from .oracle import solve_oracle, OracleActivity
from .plan import plan, serialize_plan

__all__ = [
    "select_exercise",
    "compute_workload",
    "ContentInsufficientError",
    "check_feasibility_bounds",
    "FeasibilityCheckResult",
    "run_greedy_schedule",
    "solve_oracle",
    "OracleActivity",
    "plan",
    "serialize_plan",
]
