"""Plan 2 (F2-T6, D61): smoke test of experiments/run_f2_grid.py and checks on the full results."""

import json
import os
import re
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from experiments.run_f2_grid import ALL_WORLDS, CURRICULA, PROFILE_FILES, main  # noqa: E402
from experiments.stats import ece  # noqa: E402

RESULTS = os.path.join(repo_root, "experiments/results/f2_grid.json")
PREREG = os.path.join(repo_root, "docs/preregistration/F2_2026-11-20.md")


def test_ece_hand_values():
    assert ece([]) is None
    assert ece([(0.2, False), (0.2, True)]) == 0.3  # one bin: |0.2 - 0.5|
    assert ece([(0.05, False), (0.95, True)]) == 0.05


def test_smoke_schema_and_determinism(tmp_path):
    kw = dict(
        n_diag=2, n_episodes=2, worlds=("S0", "S4-assist09"), curricula=("4-node", "8-node-x10")
    )
    r = main(str(tmp_path / "f2.json"), **kw)
    md = r["metadata"]
    assert md["preregistration"].startswith("docs/preregistration/F2_")
    assert md["profiles"]["heuristic"] is None
    assert md["profiles"]["fitted_assist09"]["profile"] == "fitted_assist09"
    assert md["content_review"]["8-node-x10"] == "AI-checked, human review pending (D88)"
    for w in r["worlds"].values():
        for cell in w.values():
            assert set(cell) == {*PROFILE_FILES, "paired_vs_heuristic"}
            assert set(cell["paired_vs_heuristic"]) == {"fitted_assist09", "fitted_ct"}
            for p in PROFILE_FILES:
                assert set(cell[p]) == {"diagnostic", "next_answer", "episodes"}
                assert cell[p]["episodes"]["executed_prereq_violations"] == 0
    assert main(None, **kw)["worlds"] == r["worlds"]


def test_full_results_match_registration_f2_tc6():
    """The full run exists, was produced by the registered code after registration, covers the
    pre-registered grid, and has 0 executed prerequisite violations in every adapt cell (H1)."""
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
    assert md["diag_seeds"] == [101, 599, "odd"] and md["episode_seeds"] == [1000, 1199]
    assert md["content_review"]["8-node-x10"] == "AI-checked, human review pending (D88)"
    assert set(r["worlds"]) == set(ALL_WORLDS)
    for row in r["worlds"].values():
        assert set(row) == set(CURRICULA)
        for cell in row.values():
            for p in PROFILE_FILES:
                assert cell[p]["diagnostic"]["n"] == 250 and cell[p]["episodes"]["n"] == 200
                assert cell[p]["episodes"]["executed_prereq_violations"] == 0
