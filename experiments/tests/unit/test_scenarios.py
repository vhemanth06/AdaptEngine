"""V2-TC1: scenario events and the horizon rule."""

from adaptengine.core.schema import EventType

from experiments.core import curricula as C
from experiments.core.scenarios import SCENARIOS, horizon, make_scenario


def test_events_and_horizon():
    e = C.engine("4-node")
    g = C.goal_of(e)
    h = horizon(e, g, 15)
    assert h >= 3
    s = {n: make_scenario(n, e, g, 15) for n in SCENARIOS}
    assert s["calm"].events == () and s["calm"].deadline == h
    assert s["missed_day"].events == ((2, EventType.MISSED, None),)
    assert s["budget_drop"].events == ((2, EventType.BUDGET_CHANGED, 10),)
    assert s["deadline_cut"].events == ((2, EventType.DEADLINE_CHANGED, h - 1),)
    assert s["missed_2days"].events == ((2, EventType.MISSED, None), (3, EventType.MISSED, None))
    assert s["budget_crash"] is None
    assert s["deadline_halved"].events == ((2, EventType.DEADLINE_CHANGED, max(2, h // 2)),)
    assert s["forgetting_21"].deadline == 21 and s["forgetting_21"].events == ()


def test_budget_rules():
    e = C.engine("4-node")
    g = C.goal_of(e)
    assert make_scenario("budget_drop", e, g, 5) is None
    assert make_scenario("budget_crash", e, g, 30).events == ((2, EventType.BUDGET_CHANGED, 5),)
    assert make_scenario("budget_crash", e, g, 15) is None
    assert make_scenario("calm", e, g, 15, deadline=9).deadline == 9
