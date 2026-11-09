"""Unit tests for planner arms and episode runner (Step 4)."""

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import pytest  # noqa: E402
from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402


@pytest.fixture
def engine():
    return Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        config=DEFAULT_CONFIG,
    )


def test_adapt_zero_violations_all_scenarios(engine):
    """Under adapt arm, prerequisite and budget violations must be 0 across all scenarios."""
    scenarios = ["calm", "missed_day", "budget_drop", "deadline_cut"]
    profile = PROFILES["nominal"]
    start_state = engine.init_learner()

    for sc_name in scenarios:
        sc = get_scenario(sc_name, engine, start_state, goal="C4", budget=15)
        if sc is None:
            continue
        res = run_episode(engine, seed=42, scenario=sc, arm="adapt", profile=profile)
        assert res["plan_prereq_violations"] == 0, f"Plan prereq violation in {sc_name}"
        assert res["executed_prereq_violations"] == 0, f"Executed violation in {sc_name}"
        assert res["budget_violations"] == 0, f"Budget violation in {sc_name}"
        assert res["plan_trace_coverage"] == 1.0


def test_no_replan_missed_day_completes_fewer_than_adapt(engine):
    """Under missed_day scenario, no_replan completes strictly fewer activities than adapt."""
    start_state = engine.init_learner()
    sc = get_scenario("missed_day", engine, start_state, goal="C4", budget=15)
    profile = PROFILES["nominal"]

    res_adapt = run_episode(engine, seed=123, scenario=sc, arm="adapt", profile=profile)
    res_no_replan = run_episode(engine, seed=123, scenario=sc, arm="no_replan", profile=profile)

    assert res_adapt["total_activities_completed"] > res_no_replan["total_activities_completed"]


def test_two_identical_runs_give_identical_output(engine):
    """Determinism check: same inputs produce identical episode output."""
    start_state = engine.init_learner()
    sc = get_scenario("calm", engine, start_state, goal="C4", budget=15)
    profile = PROFILES["nominal"]

    res1 = run_episode(engine, seed=777, scenario=sc, arm="adapt", profile=profile)
    res2 = run_episode(engine, seed=777, scenario=sc, arm="adapt", profile=profile)

    assert res1 == res2
