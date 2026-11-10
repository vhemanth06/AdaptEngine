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


# ---------------------------------------------------------------- W8 WP-A (TC8.1)


def _sc(engine, name="calm", horizon=14, budget=15):
    return get_scenario(
        name, engine, engine.init_learner(), goal="C4", budget=budget, horizon=horizon
    )


@pytest.mark.parametrize("arm", ["static_loop", "random_eligible", "adapt_dx"])
def test_w8_arms_deterministic(engine, arm):
    sc = _sc(engine)
    r1 = run_episode(engine, seed=5, scenario=sc, arm=arm, profile=PROFILES["nominal"])
    r2 = run_episode(engine, seed=5, scenario=sc, arm=arm, profile=PROFILES["nominal"])
    assert r1 == r2


def test_static_loop_uses_every_study_day(engine):
    for name, study_days in (("calm", 14), ("missed_day", 13)):
        r = run_episode(engine, 3, _sc(engine, name), "static_loop", PROFILES["nominal"])
        assert r["days_used"] == study_days
        assert r["idle_days_total"] == 0
        assert r["budget_violations"] == 0


def test_random_eligible_has_no_executed_violations(engine):
    for seed in range(20):
        for name in ("calm", "missed_day"):
            r = run_episode(engine, seed, _sc(engine, name), "random_eligible", PROFILES["nominal"])
            assert r["executed_prereq_violations"] == 0
            assert r["budget_violations"] == 0


def test_fixed_horizon_does_not_depend_on_policy(engine):
    import dataclasses

    strict = Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        config=dataclasses.replace(DEFAULT_CONFIG, theta=0.95, k_responses=4),
    )
    for h in (7, 14, 21):
        assert _sc(engine, horizon=h).deadline == _sc(strict, horizon=h).deadline == h
    # The W7 rule depends on the engine's own plan (kept for continuity only)
    assert _sc(engine, horizon="w7").deadline < _sc(strict, horizon="w7").deadline
    with pytest.raises(ValueError):
        _sc(engine, horizon=2)


def test_adapt_dx_charges_diagnostic_minutes_to_day_one(engine):
    sc = _sc(engine, budget=15)
    for seed in range(5):
        r = run_episode(engine, seed, sc, "adapt_dx", PROFILES["nominal"])
        assert r["dx_minutes"] > 0
        day1 = r["executed_minutes_per_day"].get(1, 0)
        assert min(r["dx_minutes"], 15) + day1 <= 15
        assert r["executed_prereq_violations"] == 0
        assert r["minutes_used"] == r["dx_minutes"] + sum(r["executed_minutes_per_day"].values())


def test_w8_episode_metrics_are_consistent(engine):
    r = run_episode(engine, 11, _sc(engine, horizon=7), "adapt", PROFILES["nominal"])
    assert r["minutes_available"] == 7 * 15
    assert r["minute_utilisation"] == round(r["minutes_used"] / 105, 4)
    assert 0 <= r["false_mastered"] <= r["believed_mastered"] <= 4
    assert r["idle_days_unmastered"] <= r["idle_days_total"]
    # static_loop fills every day it can, so its utilisation is at least the adapt arm's here
    s = run_episode(engine, 11, _sc(engine, horizon=7), "static_loop", PROFILES["nominal"])
    assert s["minute_utilisation"] >= r["minute_utilisation"]
