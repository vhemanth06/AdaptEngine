"""Unit tests for matched-budget diagnostic evaluation and tuning (Step 5)."""

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import pytest  # noqa: E402
from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.learner.state import ConceptStatus, LearnerConcept, LearnerState  # noqa: E402
from experiments.diag_eval import (  # noqa: E402
    compute_diagnostic_errors,
    evaluate_diagnostic_learner,
    run_diagnostic_tuning,
    run_fixed_diagnostic,
    run_random_diagnostic,
)
from experiments.sim import PROFILES  # noqa: E402


@pytest.fixture
def engine():
    return Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        config=DEFAULT_CONFIG,
    )


def test_compute_diagnostic_errors_hand_checkable():
    """Verify calculation of mae_all, mae_assessed, and unassessed_fraction on known values."""
    all_concepts = ["C1", "C2"]
    true_theta = {"C1": 0.80, "C2": 0.40}

    # Case 1: Both concepts assessed
    c1 = LearnerConcept(concept_id="C1", p=0.60, responses=2, status=ConceptStatus.ASSESSED)
    c2 = LearnerConcept(concept_id="C2", p=0.20, responses=1, status=ConceptStatus.ASSESSED)
    state1 = LearnerState(concepts={"C1": c1, "C2": c2})

    err1 = compute_diagnostic_errors(state1, true_theta, all_concepts)
    assert abs(err1["mae_all"] - 0.20) < 1e-4
    assert abs(err1["mae_assessed"] - 0.20) < 1e-4
    assert err1["unassessed_fraction"] == 0.0

    # Case 2: Only C1 assessed, C2 unassessed
    c2_un = LearnerConcept(concept_id="C2", p=0.20, responses=0, status=ConceptStatus.UNASSESSED)
    state2 = LearnerState(concepts={"C1": c1, "C2": c2_un})

    err2 = compute_diagnostic_errors(state2, true_theta, all_concepts)
    # mae_all = (|0.6 - 0.8| + |0.2 - 0.4|) / 2 = 0.20
    assert abs(err2["mae_all"] - 0.20) < 1e-4
    # mae_assessed = |0.6 - 0.8| = 0.20
    assert abs(err2["mae_assessed"] - 0.20) < 1e-4
    # unassessed_fraction = 1 / 2 = 0.50
    assert abs(err2["unassessed_fraction"] - 0.50) < 1e-4


def test_matched_budget_item_counts(engine):
    """Fixed and random arms respect requested item_cap."""
    profile = PROFILES["nominal"]
    for cap in (2, 4, 8):
        _, used_fixed = run_fixed_diagnostic(engine, seed=55, profile=profile, item_cap=cap)
        assert used_fixed == cap

        _, used_rand = run_random_diagnostic(engine, seed=55, profile=profile, item_cap=cap)
        assert used_rand == cap


def test_diagnostic_learner_determinism(engine):
    """Evaluating the same learner twice produces identical metrics."""
    profile = PROFILES["nominal"]
    res1 = evaluate_diagnostic_learner(engine, seed=101, profile=profile)
    res2 = evaluate_diagnostic_learner(engine, seed=101, profile=profile)

    assert res1 == res2


def test_tuning_grid_execution():
    """Verify run_diagnostic_tuning executes grid search and evaluates winner on held-out."""
    tuning_seeds = [100, 102]
    heldout_seeds = [101, 103]
    res = run_diagnostic_tuning(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        tuning_seeds=tuning_seeds,
        heldout_seeds=heldout_seeds,
    )
    assert "winner" in res
    assert "heldout_comparison" in res
    assert res["winner"]["avg_items"] <= 4.0


def test_binary_truth_scoring_t3_1():
    """W7 T3.1: reproduces the R§2.6 re-scoring on the 50 held-out learners (odd seeds 101-199):
    adaptive Brier 0.2425 vs prior-only 0.2080 against 1[theta >= 0.70]."""
    from adaptengine.core.config import EngineConfig
    from experiments.diag_eval import W6_DIAGNOSTIC, evaluate_diagnostic_binary

    e = Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        config=EngineConfig(**W6_DIAGNOSTIC),
    )
    r = evaluate_diagnostic_binary(e, [s for s in range(100, 200) if s % 2], PROFILES["nominal"])
    arms = r["arms"]
    assert arms["adaptive"]["brier"] == 0.2425
    assert arms["prior_only"]["brier"] == 0.208
    assert arms["prior_only"]["auc"] == 0.5
    lo, hi = arms["fixed@n"]["paired_brier_vs_adaptive"]["ci95"]
    assert hi < 0  # fixed@n is significantly better calibrated than the shipped adaptive arm
    assert sum(b["n"] for b in arms["adaptive"]["reliability"]) == 50 * 4
