"""V2-TC1: closed loop, no_replan and static episodes."""

from unittest import mock

from experiments_v2.core import curricula as C
from experiments_v2.core.arms import E1_ARMS
from experiments_v2.core.episode import run_episode, static_days
from experiments_v2.core.scenarios import make_scenario


def _setup(cur="4-node", budget=15, scen="calm"):
    e = C.engine(cur)
    return e, make_scenario(scen, e, C.goal_of(e), budget)


def _count_calls(e, sc, arm, seed):
    calls = []
    real = e.next_activities

    def spy(*a, **k):
        calls.append(a[2].current_day)
        return real(*a, **k)

    with mock.patch.object(e, "next_activities", side_effect=spy):
        r = run_episode(e, seed, sc, E1_ARMS[arm], "S0")
    return r, calls


def test_closed_loop_replans_after_a_wrong_answer():
    e, sc = _setup()
    r, calls = _count_calls(e, sc, "adapt", 1000)
    wrong = sum(1 for _, y in r["attempts"] if not y)
    assert wrong > 0
    assert len(calls) > len(set(calls))  # more than one plan on some day
    assert r["plan_checks"]["plans"] == len(calls)


def test_no_replan_never_replans():
    e, sc = _setup()
    r, calls = _count_calls(e, sc, "no_replan", 1000)
    assert calls == [] and r["plan_checks"]["plans"] == 1


def test_static_is_next_fit_packed():
    e, _ = _setup()
    days = static_days(e, C.goal_of(e), 10)
    flat = [a for d in days for a in d.activities]
    for i, d in enumerate(days):
        assert d.duration == sum(e.activities[a].duration for a in d.activities) <= 10
        if i + 1 < len(days):  # next-fit: the next day's first activity did not fit today
            assert d.duration + e.activities[days[i + 1].activities[0]].duration > 10
    order = list(e.graph.topological_order())
    pos = [order.index(e.activities[a].target_concept) for a in flat]
    assert pos == sorted(pos)


def test_minutes_never_exceed_the_budget_in_force():
    for scen in ("calm", "budget_drop", "missed_day"):
        e, sc = _setup("8-node", 15, scen)
        for arm in ("adapt", "no_review", "no_replan", "static"):
            for seed in (1000, 1001):
                r = run_episode(e, seed, sc, E1_ARMS[arm], "S1")
                # fixed schedules (no_replan, static) do not follow a budget change by design
                fixed = arm in ("no_replan", "static") and scen == "budget_drop"
                assert (r["exec_budget_viol"] == 0) != fixed, (scen, arm)


def test_confirmation_false_pass_uses_theta_at_confirmation():
    from experiments_v2.core.arms import E4_ARMS

    e = C.engine("synth-20", E4_ARMS["bisect_confirm_fitted"].config())
    base = C.engine("synth-20")
    sc = make_scenario("calm", base, C.goal_of(base), 15)
    r = run_episode(e, 1000, sc, E4_ARMS["bisect_confirm_fitted"], "S3")
    assert r["confirmations"] >= r["confirmed_at_diag"]
    assert 0 <= r["false_confirmations"] <= r["confirmations"] > 0
    # the end-of-episode count includes forgetting, so it is kept separately
    assert "false_confirm_at_end" in r
