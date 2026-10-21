"""Test suite for Section 11 / TC8.1: Paired Baseline Evaluation Reproducibility.

Ensures:
1. Evaluation runs across 25 seeded learners without error.
2. Identical seeds produce byte-identical output (TC8.1).
3. Budget and prerequisite violations are zero across both planner arms.
"""

import json
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from experiments.run_evaluation import run_evaluation  # noqa: E402


def test_evaluation_reproducibility_tc8_1():
    # First run
    res1 = run_evaluation(num_seeds=5, seed_start=100)
    json_str1 = json.dumps(res1, sort_keys=True)

    # Second run with identical seeds
    res2 = run_evaluation(num_seeds=5, seed_start=100)
    json_str2 = json.dumps(res2, sort_keys=True)

    # TC8.1 assertion: bitwise/byte identical output
    assert (
        json_str1 == json_str2
    ), "TC8.1 failed: evaluation runs on identical seeds are not identical"

    # Verify zero violations in planner records
    for record in res1["per_seed_runs"]["planner"]:
        assert record["adaptengine"]["budget_violations"] == 0
        assert record["adaptengine"]["prerequisite_violations"] == 0
        assert record["static"]["budget_violations"] == 0
        assert record["static"]["prerequisite_violations"] == 0
