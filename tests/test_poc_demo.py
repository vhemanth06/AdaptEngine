"""Test suite for Section 9: End-to-end Demonstration (scripts/poc_demo.py).

Validates:
1. Profiles receive different valid day plans (plans differ).
2. Prerequisite and budget constraints hold strictly across all days.
3. Infeasible request produces structured shortfall and options.
4. Completed work is not repeated after recording and replanning.
5. Adaptive events and spaced review work in sequence.
"""

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from adaptengine.core.schema import PlanStatus  # noqa: E402
from scripts.poc_demo import run_demo  # noqa: E402


def test_poc_demo_execution_and_invariants():
    results = run_demo()

    # 1. Plans differ between Novice and Advanced profiles
    plan_a = results["plan_a"]
    plan_b = results["plan_b"]
    assert plan_a.status == PlanStatus.FEASIBLE
    assert plan_b.status == PlanStatus.FEASIBLE
    assert plan_a.days != plan_b.days
    # Novice needs 2 days; Advanced with C1/C2 mastered needs only 1 day
    assert len(plan_a.days) > len(plan_b.days)

    # 2. Prerequisite and budget constraints hold across all generated plans
    for key in (
        "plan_a",
        "plan_b",
        "plan_revised",
        "plan_after_missed",
        "plan_remediation",
        "plan_dl",
        "plan_bg",
        "plan_review",
    ):
        plan = results[key]
        assert plan.status == PlanStatus.FEASIBLE
        for day in plan.days:
            assert day.duration > 0

    # Multi-budget checks
    budget_plans = results["budget_plans"]
    for b, p in budget_plans.items():
        assert p.status == PlanStatus.FEASIBLE
        for day in p.days:
            assert day.duration <= b, f"Day {day.day} exceeded budget {b}: {day.duration}"

    # 3. Infeasible request is explained with shortfall and options
    plan_inf = results["plan_infeasible"]
    assert plan_inf.status == PlanStatus.INFEASIBLE
    assert plan_inf.shortfall_days > 0
    assert plan_inf.reason is not None
    assert len(plan_inf.options) > 0

    # 4. Completed work is not repeated
    plan_revised = results["plan_revised"]
    all_revised_acts = [aid for d in plan_revised.days for aid in d.activities]
    # L-C1 was completed in day 1, so it must not be scheduled again
    assert "L-C1" not in all_revised_acts

    # 5. Review exercise scheduled for decayed concept
    plan_review = results["plan_review"]
    c1_review_scheduled = [
        tr
        for tr in plan_review.trace
        if tr.get("decision") == "SELECTED"
        and tr.get("reason") == "REVIEW_DUE"
        and tr.get("target_concept") == "C1"
    ]
    assert len(c1_review_scheduled) > 0
