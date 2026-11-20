"""Plan 3 (F1-T8): smoke test and result schema of experiments/run_f1_grid.py."""

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.run_f1_grid import DIAG_ARMS, main  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402


def test_smoke_schema(tmp_path):
    kw = dict(
        n_diag=2,
        n_episodes=2,
        n_tune=2,
        n_scripted=1,
        curricula=("4-node", "8-node-x10"),
        loop_worlds=("S0",),
        diag_worlds=("S0",),
    )
    r = main(str(tmp_path / "f1.json"), **kw)
    md = r["metadata"]
    assert md["preregistration"].startswith("docs/preregistration/F1_")
    assert set(md["frozen_bisection_settings"]) == {
        "bisection_stop_confidence",
        "bisection_n_ceiling",
    }
    assert len(r["tuning"]) == 9
    assert set(r["diagnostic"]["S0"]["4-node"]) == {*DIAG_ARMS, "prior_only", "fixed@n"}
    assert set(r["closed_loop"]) == {"S0", "S4-assist09"}
    cell = r["closed_loop"]["S0"]["8-node-x10"]
    assert {
        "sweep",
        "bisect_noconfirm",
        "bisect_confirm",
        "sweep_fitted",
        "bisect_confirm_fitted",
    } <= set(cell)
    for arm, v in cell.items():
        if arm != "paired":
            assert v["executed_prereq_violations"] == 0
    assert "bisect_confirm_minus_bisect_noconfirm" in cell["paired"]
    assert main(None, **kw)["closed_loop"] == r["closed_loop"]


def test_run_episode_default_unchanged_and_diagnose_extra_keys():
    from experiments.run_f1_grid import engine_for

    e = engine_for("8-node", DIAG_ARMS["bisect"])
    sc = get_scenario("calm", e, e.init_learner(), goal="C8", budget=15)
    plain = run_episode(e, 1000, sc, "adapt", PROFILES["nominal"])
    assert "diag_items" not in plain
    diag = run_episode(e, 1000, sc, "adapt", PROFILES["nominal"], diagnose=True)
    assert diag["diag_items"] > 0 and diag["diag_minutes"] > 0
    assert diag["executed_prereq_violations"] == 0


RESULTS = os.path.join(repo_root, "experiments/results/f1_grid.json")
PREREG = os.path.join(repo_root, "docs/preregistration/F1_2026-11-20.md")


def test_full_results_match_registration_f1_tc10():
    """Run 2 (Amendment 1): produced by the amended code after the amendment, full grid, and H1
    (0 executed prerequisite violations in every closed-loop cell)."""
    import json
    import re

    import pytest

    if not os.path.exists(RESULTS):
        pytest.skip("F1 run 2 pending: python experiments/run_f1_grid.py (docs/PLAN3_NOTES.md)")
    with open(RESULTS, encoding="utf-8") as f:
        r = json.load(f)
    with open(PREREG, encoding="utf-8") as f:
        prereg = f.read()
    amended = re.search(r"code_hash \(amendment 1\):\*\*\s*`([0-9a-f]{64})`", prereg).group(1)
    md = r["metadata"]
    assert md["code_hash"] == amended
    t = re.search(r"\*\*Amendment registered:\*\* (\S+Z)", prereg).group(1)
    assert md["timestamp_utc"] > t.replace("Z", "+00:00")
    assert md["diag_seeds"] == [101, 599, "odd"] and md["episode_seeds"] == [1000, 1199]
    for row in r["closed_loop"].values():
        for cell in row.values():
            for arm, v in cell.items():
                if arm != "paired":
                    assert v["n"] == 200 and v["executed_prereq_violations"] == 0, arm
