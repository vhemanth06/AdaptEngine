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


def test_evaluation_reproducibility_tc8_1(tmp_path):
    canonical = os.path.join(repo_root, "experiments", "results", "evaluation_results.json")
    before = open(canonical, "rb").read() if os.path.exists(canonical) else None

    # First run in quick mode (W7 T1.3: tests write to tmp_path, never the canonical artifact)
    res1 = run_evaluation(
        num_seeds=5, seed_start=100, quick=True, out_path=str(tmp_path / "a.json")
    )
    json_str1 = json.dumps(res1, sort_keys=True)

    # Second run with identical seeds
    res2 = run_evaluation(
        num_seeds=5, seed_start=100, quick=True, out_path=str(tmp_path / "b.json")
    )
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
                record[arm]["plan_prereq_violations"] == 0
            ), f"Plan prerequisite violation in {arm} for seed {record['seed']}"

        assert (
            record["static"]["budget_violations"] == 0
        ), f"Budget violation in static for seed {record['seed']}"
        # Non-vacuous audit check (W7 T1.2): records are missed_day runs; static keeps its fixed
        # sequence after the missed day, so the plan-level audit must flag it.
        assert record["static"]["plan_prereq_violations"] > 0

        # W7 T2.2: the closed loop never starts work on a concept whose prerequisite lacks evidence
        assert record["adapt"]["executed_prereq_violations"] == 0
        assert record["no_review"]["executed_prereq_violations"] == 0

        # Explanation coverage is exactly 1.0 for adaptive arms
        assert record["adapt"]["plan_trace_coverage"] == 1.0
        assert record["no_review"]["plan_trace_coverage"] == 1.0

    # W7 T1.3: running the evaluation from tests leaves the canonical artifact byte-identical
    after = open(canonical, "rb").read() if os.path.exists(canonical) else None
    assert before == after
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
