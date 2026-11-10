"""Unit tests for statistical metrics and bootstrap intervals (Step 6)."""

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from adaptengine.core.schema import Plan, PlanDay, PlanStatus  # noqa: E402
from experiments.stats import (  # noqa: E402
    audit_plan_trace_coverage,
    brier_score,
    paired_bootstrap_ci,
    roc_auc,
)


def test_brier_score_known_cases():
    assert brier_score([]) is None
    # Perfect predictions: Brier = 0.0
    assert brier_score([(1.0, True), (0.0, False)]) == 0.0
    # Completely wrong: Brier = 1.0
    assert brier_score([(0.0, True), (1.0, False)]) == 1.0
    # 0.5 coin flip: (0.25 + 0.25) / 2 = 0.25
    assert brier_score([(0.5, True), (0.5, False)]) == 0.25


def test_roc_auc_known_cases():
    # Empty or single-class
    assert roc_auc([]) is None
    assert roc_auc([(0.8, True), (0.9, True)]) is None
    assert roc_auc([(0.2, False), (0.3, False)]) is None

    # Perfect ranking: AUC = 1.0
    assert roc_auc([(0.9, True), (0.1, False)]) == 1.0
    # Ties: AUC = 0.5
    assert roc_auc([(0.5, True), (0.5, False)]) == 0.5
    # Inverted ranking: AUC = 0.0
    assert roc_auc([(0.1, True), (0.9, False)]) == 0.0


def test_bootstrap_ci_properties():
    # Symmetric sample around mean 5.0
    diffs = [4.0, 4.5, 5.0, 5.5, 6.0] * 20
    ci_low, ci_high = paired_bootstrap_ci(diffs, n_boot=2000, seed=42)
    assert ci_low <= 5.0 <= ci_high
    assert ci_low < ci_high

    # Determinism: same seed gives identical CI
    ci_low2, ci_high2 = paired_bootstrap_ci(diffs, n_boot=2000, seed=42)
    assert (ci_low, ci_high) == (ci_low2, ci_high2)


def test_audit_plan_trace_coverage():
    # Valid plan with SELECTED and score_components
    plan_valid = Plan(
        status=PlanStatus.FEASIBLE,
        days=(PlanDay(day=1, activities=("act_1",), duration=4),),
        reason="GOAL_FEASIBLE",
        shortfall_days=0,
        options=(),
        trace=(
            {
                "decision": "SELECTED",
                "activity_id": "act_1",
                "day": 1,
                "reason": "RANKED_TOP",
                "score_components": {"review": 0.0, "unlock": 1.0, "fit": 0.9},
            },
        ),
    )
    assert audit_plan_trace_coverage(plan_valid) == 1.0

    # Plan missing score_components for greedy SELECTED
    plan_missing_components = Plan(
        status=PlanStatus.FEASIBLE,
        days=(PlanDay(day=1, activities=("act_1",), duration=4),),
        reason="GOAL_FEASIBLE",
        shortfall_days=0,
        options=(),
        trace=(
            {
                "decision": "SELECTED",
                "activity_id": "act_1",
                "day": 1,
                "reason": "RANKED_TOP",
            },
        ),
    )
    assert audit_plan_trace_coverage(plan_missing_components) == 0.0

    # Oracle assigned activity does not require score_components
    plan_oracle = Plan(
        status=PlanStatus.FEASIBLE,
        days=(PlanDay(day=1, activities=("act_oracle",), duration=4),),
        reason="GOAL_FEASIBLE",
        shortfall_days=0,
        options=(),
        trace=(
            {
                "decision": "SELECTED",
                "activity_id": "act_oracle",
                "day": 1,
                "reason": "ORACLE_ASSIGNED",
            },
        ),
    )
    assert audit_plan_trace_coverage(plan_oracle) == 1.0


def test_kaplan_meier_hand_computed():
    from experiments.stats import kaplan_meier, km_median, km_rmst

    t, e = [2, 3, 3, 5, 7], [True, True, False, True, False]
    curve = kaplan_meier(t, e)
    assert [(x, round(s, 6)) for x, s in curve] == [(0.0, 1.0), (2.0, 0.8), (3.0, 0.6), (5.0, 0.3)]
    assert km_median(t, e) == 5.0
    assert km_rmst(t, e, tau=6) == 4.3  # 2*1 + 1*0.8 + 2*0.6 + 1*0.3
    assert km_median([4, 9], [False, False]) is None  # all censored: no median
    assert km_rmst([4, 9], [False, False], tau=10) == 10.0
