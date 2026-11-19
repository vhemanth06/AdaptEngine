"""Plan 1 (F5-T6, D86): smoke test and result schema of experiments/run_f5_baseline.py."""

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from experiments.run_f5_baseline import CURRICULA, SCENARIOS, main  # noqa: E402


def test_smoke_and_schema(tmp_path):
    out = tmp_path / "f5.json"
    r = main(str(out), n_diag=2, n_episodes=2, worlds=("S0", "S3"))
    assert out.exists()
    md = r["metadata"]
    assert md["preregistration"].startswith("docs/preregistration/F5_")
    assert md["content_review"]["8-node"] == "reviewed"
    assert md["content_review"]["8-node-x10"].startswith("AI-checked, human review pending (D88)")
    assert set(md["content_review"]) == set(CURRICULA)
    assert set(r["worlds"]) == {"S0", "S3"}
    for w in r["worlds"].values():
        assert set(w["diagnostic"]) == set(CURRICULA)
        assert {"brier", "items", "auc", "n"} <= set(w["diagnostic"]["8-node-x10"])
        assert set(w["diagnostic_paired_x10_minus_8node"]) == {"brier", "items"}
        assert set(w["episodes"]) == set(SCENARIOS)
        for scen in w["episodes"].values():
            assert scen["8-node-x10"]["executed_prereq_violations"] == 0
            assert "goal_mastery" in scen["paired_x10_minus_8node"]
    assert main(None, n_diag=2, n_episodes=2, worlds=("S0", "S3"))["worlds"] == r["worlds"]


RESULTS = os.path.join(repo_root, "experiments/results/f5_baseline.json")
PREREG = os.path.join(repo_root, "docs/preregistration/F5_2026-11-20.md")


def test_full_results_file_matches_registration():
    """P1.5-TC3: the full run's results exist, follow the schema, carry the D88 label, and were
    produced by the code registered in the pre-registration."""
    import json
    import re

    with open(RESULTS, encoding="utf-8") as f:
        r = json.load(f)
    with open(PREREG, encoding="utf-8") as f:
        prereg = f.read()
    assert "**Status: REGISTERED**" in prereg
    registered = re.search(r"code_hash at registration:\*\*\s*`([0-9a-f]{64})`", prereg).group(1)
    md = r["metadata"]
    assert md["code_hash"] == registered
    reg_time = re.search(r"\*\*Registered:\*\* (\S+Z)", prereg).group(1)
    assert md["timestamp_utc"] > reg_time.replace("Z", "+00:00")
    assert md["content_review"]["8-node"] == "reviewed"
    assert md["content_review"]["8-node-x10"].startswith("AI-checked, human review pending (D88)")
    assert md["diag_seeds"] == [101, 599, "odd"] and md["episode_seeds"] == [1000, 1199]
    assert set(r["worlds"]) == {"S0", "S1", "S2", "S3", "S4"}
    for w in r["worlds"].values():
        assert {w["diagnostic"][c]["n"] for c in CURRICULA} == {250}
        for scen in SCENARIOS:
            for c in CURRICULA:
                assert w["episodes"][scen][c]["executed_prereq_violations"] == 0
