"""The eight scenarios and the horizon rule (Plan V2 §V2.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from adaptengine.core.schema import EventType, PlanContext

SCENARIOS = (
    "calm",
    "missed_day",
    "budget_drop",
    "deadline_cut",
    "missed_2days",
    "budget_crash",
    "deadline_halved",
    "forgetting_21",
)
BUDGETS = (5, 10, 15, 30)


@dataclass(frozen=True)
class Scenario:
    name: str
    budget: int
    deadline: int
    goal: str
    events: tuple[tuple[int, EventType, Any], ...] = ()


def applies(name: str, budget: int) -> bool:
    """budget_drop needs a lower allowed budget (not at 5); budget_crash runs only at 30."""
    if name == "budget_drop":
        return budget != 5
    if name == "budget_crash":
        return budget == 30
    return True


def horizon(engine, goal: str, budget: int) -> int:
    """New-content days of an uncapped plan (deadline 60, maintenance-review days excluded) + 2,
    minimum 3."""
    plan = engine.plan(
        engine.init_learner(), PlanContext(goal=goal, deadline_day=60, budget=budget)
    )
    last_new = max(
        (
            t["day"]
            for t in plan.trace
            if t.get("decision") == "SELECTED" and t.get("reason") != "REVIEW_DUE"
        ),
        default=0,
    )
    return max(3, sum(1 for d in plan.days if d.day <= last_new) + 2)


def make_scenario(
    name: str, engine, goal: str, budget: int, deadline: Optional[int] = None
) -> Optional[Scenario]:
    """The scenario, or None where it does not apply. `deadline` overrides the horizon (E6 fixes
    every configuration's horizon from DEFAULT_CONFIG)."""
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}")
    if not applies(name, budget):
        return None
    dl = deadline if deadline is not None else horizon(engine, goal, budget)
    ev: tuple = ()
    if name == "missed_day":
        ev = ((2, EventType.MISSED, None),)
    elif name == "budget_drop":
        allowed = sorted(engine.config.allowed_budgets)
        ev = ((2, EventType.BUDGET_CHANGED, allowed[allowed.index(budget) - 1]),)
    elif name == "deadline_cut":
        ev = ((2, EventType.DEADLINE_CHANGED, dl - 1),)
    elif name == "missed_2days":
        ev = ((2, EventType.MISSED, None), (3, EventType.MISSED, None))
    elif name == "budget_crash":
        ev = ((2, EventType.BUDGET_CHANGED, 5),)
    elif name == "deadline_halved":
        ev = ((2, EventType.DEADLINE_CHANGED, max(2, dl // 2)),)
    elif name == "forgetting_21":
        dl = 21
    return Scenario(name, budget, dl, goal, ev)


def profile_for(name: str) -> str:
    """forgetting_21 cells use fast-forgetting learners (half-life 7 days); all others nominal."""
    return "fast_forgetter" if name == "forgetting_21" else "nominal"
