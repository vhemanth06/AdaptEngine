"""W8 WP-M A1 plan proposer: engine validation rules and fallback, offline (stub). TC3.1-TC3.2, TC7.1."""

import json
import os
import sys

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from adaptengine.agents.plan_proposer import propose_plan  # noqa: E402
from adaptengine.api import Engine  # noqa: E402
from adaptengine.authoring.providers import StubProvider  # noqa: E402
from adaptengine.core.schema import PlanContext, PlanStatus  # noqa: E402
from adaptengine.learner.state import ExecutionLog  # noqa: E402

C4 = ("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
CTX = PlanContext(goal="C4", deadline_day=10, budget=15, current_day=1)


@pytest.fixture
def e():
    return Engine.from_files(*C4)


def run(e, mutate, ctx=CTX, log=None):
    def responder(payload):
        days = json.loads(json.dumps(payload["reference_days"]))
        out = mutate(days)
        return out if isinstance(out, str) else json.dumps({"days": out, "rationale": "r"})

    prov = StubProvider({"propose_plan": responder})
    return propose_plan(e, e.init_learner(), log or ExecutionLog(), ctx, prov)


def test_valid_proposal_accepted(e):
    plan, res = run(e, lambda d: d)
    assert (
        res["accepted"]
        and plan.reason == "AGENT_PROPOSAL_ACCEPTED"
        and plan.status == PlanStatus.FEASIBLE
    )
    assert sum(1 for t in plan.trace if t.get("decision") == "SELECTED") == sum(
        len(d.activities) for d in plan.days
    )


def _move_c3_before_c1(days):
    first = days[0]["activities"]
    first.insert(0, "L-C3")
    for d in days[1:]:
        if "L-C3" in d["activities"]:
            d["activities"].remove("L-C3")
    return days


CASES = {
    "UNKNOWN_ACTIVITY": lambda d: [{"day": 1, "activities": ["E-NOPE"] + d[0]["activities"]}]
    + d[1:],
    "DUPLICATE_ACTIVITY": lambda d: [
        {"day": d[0]["day"], "activities": d[0]["activities"] + ["L-C1"]}
    ]
    + d[1:],
    "OVER_BUDGET": lambda d: [{"day": 1, "activities": d[0]["activities"] + d[1]["activities"]}]
    + d[2:],
    "DEADLINE_EXCEEDED": lambda d: d + [{"day": 11, "activities": ["E-C4-0.2"]}],
    "PREREQUISITE_ORDER": _move_c3_before_c1,
    "GOAL_NOT_REACHED": lambda d: d[:1],
    "MALFORMED": lambda d: "this is not JSON",
}


@pytest.mark.parametrize("rule", sorted(CASES))
def test_each_rule_violation_rejected_with_reason(e, rule):
    plan, res = run(e, CASES[rule])
    assert not res["accepted"]
    assert rule in {v["rule"] for v in res["violations"]}
    ref = e.replan(e.init_learner(), ExecutionLog(), CTX)
    assert plan.days == ref.days  # deterministic fallback
    assert plan.trace[0]["decision"] == "PROPOSAL_REJECTED"


def test_day_before_start_outside_horizon(e):
    from adaptengine.core.schema import Event, EventType

    st, log = e.record(e.init_learner(), ExecutionLog(), Event(day=1, kind=EventType.MISSED))
    plan, res = run(e, lambda d: [{"day": 1, "activities": ["E-C1-0.2"]}] + d, log=log)
    assert "OUTSIDE_HORIZON" in {v["rule"] for v in res["violations"]}


def test_unordered_days_malformed(e):
    plan, res = run(e, lambda d: list(reversed(d)))
    assert [v["rule"] for v in res["violations"]] == ["MALFORMED"]
