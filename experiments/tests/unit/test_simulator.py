"""V2-TC1: the simulated learner (Plan V2 §V2.3)."""

import statistics

from experiments.core.simulator import PROFILES, SimLearner, keyed_uniform

CONCEPTS = [f"C{i}" for i in range(1, 9)]


def test_s4_theta_is_binary():
    for s in range(20):
        assert set(SimLearner(s, CONCEPTS, world="S4").theta.values()) <= {0.0, 1.0}


def test_s2_abilities_are_correlated():
    a = [SimLearner(s, ["A", "B"], world="S2").theta for s in range(400)]
    x, y = [t["A"] for t in a], [t["B"] for t in a]
    assert statistics.correlation(x, y) > 0.5
    b = [SimLearner(s, ["A", "B"], world="S0").theta for s in range(400)]
    assert abs(statistics.correlation([t["A"] for t in b], [t["B"] for t in b])) < 0.2


def test_s1_readiness():
    sim = SimLearner(1, ["A", "B"], world="S1", prereqs={"A": (), "B": ("A",)})
    assert sim.readiness("A") == 1.0
    sim.theta["A"] = 0.3
    assert sim.readiness("B") < 0.1
    sim.theta["A"] = 0.98
    assert 0.9 < sim.readiness("B") < 1.0
    assert SimLearner(1, ["A"], world="S0").readiness("A") == 1.0


def test_power_law_retention():
    sim = SimLearner(3, ["A"], world="S3")
    h = sim.half_life
    assert 5.0 <= h <= 30.0
    for dt in (0, 1, 7, 30):
        assert sim.retention(dt) == 1.0 / (1.0 + dt / h)
    assert SimLearner(3, ["A"]).retention(10) == 1.0  # S0 nominal: no forgetting
    assert SimLearner(3, ["A"], PROFILES["fast_forgetter"]).retention(7) == 0.5


def test_truth_draw_and_same_seed_same_answers():
    sim = SimLearner(1000, CONCEPTS)
    assert all(0.10 <= v <= 0.90 and round(v, 4) == v for v in sim.theta.values())
    a = [SimLearner(7, CONCEPTS).respond("C1", f"E{i}", 0.5) for i in range(30)]
    b = [SimLearner(7, CONCEPTS).respond("C1", f"E{i}", 0.5) for i in range(30)]
    assert a == b
    s = SimLearner(7, CONCEPTS)
    assert [s.respond("C1", "E1", 0.5) for _ in range(5)] == [
        keyed_uniform(7, "run", "E1", n) < s.p_correct("C1", 0.5) for n in range(5)
    ]


def test_high_slip_only_turns_right_into_wrong():
    flips = 0
    for seed in range(50):
        n = SimLearner(seed, CONCEPTS, PROFILES["nominal"])
        h = SimLearner(seed, CONCEPTS, PROFILES["high_slip"])
        for i in range(10):
            a, b = n.respond("C2", f"E{i}", 0.3), h.respond("C2", f"E{i}", 0.3)
            assert not (b and not a)
            flips += a and not b
    assert flips > 0


def test_learning_gain_and_cap():
    sim = SimLearner(1, ["A"])
    sim.theta["A"] = 0.5
    sim.learn("A", True, 1)
    assert abs(sim.theta["A"] - (0.5 + 0.18 * 0.5)) < 1e-12
    sim.theta["A"] = 0.979
    sim.learn("A", True, 1)
    assert sim.theta["A"] == 0.98
