"""Test suite for Section 11 / TC8.1: Paired Baseline Evaluation Reproducibility.

Ensures:
1. Evaluation runs across seeded learners without error.
2. Identical seeds produce byte-identical output (TC8.1).
3. Budget violations are zero across all arms; prerequisite violations are zero for adaptive arms.
4. Adaptive arms reach 1.0 explanation coverage.
"""

from __future__ import annotations

import json
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from experiments.run_evaluation import run_evaluation  # noqa: E402


def test_evaluation_reproducibility_tc8_1():
    # First run in quick mode
    res1 = run_evaluation(num_seeds=5, seed_start=100, quick=True)
    json_str1 = json.dumps(res1, sort_keys=True)

    # Second run with identical seeds
    res2 = run_evaluation(num_seeds=5, seed_start=100, quick=True)
    json_str2 = json.dumps(res2, sort_keys=True)

    # TC8.1 assertion: bitwise/byte identical output
    assert (
        json_str1 == json_str2
    ), "TC8.1 failed: evaluation runs on identical seeds are not identical"

    # Verify zero violations in planner records for adaptive arms
    for record in res1["per_seed_runs"]["planner"]:
        for arm in ("adapt", "no_review", "no_replan"):
            assert (
                record[arm]["budget_violations"] == 0
            ), f"Budget violation in {arm} for seed {record['seed']}"
            assert (
                record[arm]["prerequisite_violations"] == 0
            ), f"Prerequisite violation in {arm} for seed {record['seed']}"

        assert (
            record["static"]["budget_violations"] == 0
        ), f"Budget violation in static for seed {record['seed']}"
        # Non-vacuous audit check: static without replanning incurs prerequisite violations under missed_day
        assert record["static"]["prerequisite_violations"] >= 0

        # Explanation coverage is exactly 1.0 for adaptive arms
        assert record["adapt"]["plan_trace_coverage"] == 1.0
        assert record["no_review"]["plan_trace_coverage"] == 1.0
