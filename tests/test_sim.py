"""Unit tests for closed-loop simulator (Step 3)."""

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from experiments.sim import (  # noqa: E402
    PROFILES,
    SimLearner,
    keyed_uniform,
)


def test_keyed_uniform_determinism():
    u1 = keyed_uniform(42, "diag", "E-C1-0.2", 0)
    u2 = keyed_uniform(42, "diag", "E-C1-0.2", 0)
    u3 = keyed_uniform(43, "diag", "E-C1-0.2", 0)
    assert u1 == u2
    assert u1 != u3


def test_same_seed_gives_identical_theta():
    concepts = ("C1", "C2", "C3", "C4")
    l1 = SimLearner(seed=12345, concepts=concepts, profile=PROFILES["nominal"])
    l2 = SimLearner(seed=12345, concepts=concepts, profile=PROFILES["nominal"])
    assert l1.theta == l2.theta
    assert l1.initial == l2.initial


def test_paired_noise_across_separate_instances():
    """Two arms using separate SimLearner instances with the same seed receive identical responses."""
    concepts = ("C1", "C2", "C3", "C4")
    arm_a = SimLearner(seed=999, concepts=concepts, profile=PROFILES["nominal"])
    arm_b = SimLearner(seed=999, concepts=concepts, profile=PROFILES["nominal"])

    r_a1 = arm_a.respond("C1", "E-C1-0.4", difficulty=0.4, tag="run")
    r_b1 = arm_b.respond("C1", "E-C1-0.4", difficulty=0.4, tag="run")
    assert r_a1 == r_b1

    r_a2 = arm_a.respond("C1", "E-C1-0.4", difficulty=0.4, tag="run")
    r_b2 = arm_b.respond("C1", "E-C1-0.4", difficulty=0.4, tag="run")
    assert r_a2 == r_b2


def test_retention_power_law():
    """forget_half_life=7 gives retention 1.0 at dt=0 and 0.5 at dt=7."""
    concepts = ("C1",)
    learner = SimLearner(seed=100, concepts=concepts, profile=PROFILES["fast_forgetter"])
    assert learner._retention(0) == 1.0
    assert abs(learner._retention(7) - 0.5) < 1e-9
    assert abs(learner._retention(14) - 1.0 / 3.0) < 1e-9

    # Nominal profile has no forgetting
    nom_learner = SimLearner(seed=100, concepts=concepts, profile=PROFILES["nominal"])
    assert nom_learner._retention(100) == 1.0


def test_apply_activity_and_settle():
    concepts = ("C1",)
    learner = SimLearner(seed=100, concepts=concepts, profile=PROFILES["fast_forgetter"])
    theta_init = learner.theta["C1"]

    # Lesson gain increases theta
    learner.apply_activity("C1", is_lesson=True, day=1)
    assert learner.theta["C1"] > theta_init

    # Settle to day 8 (7 days later) reduces theta by half
    after_lesson = learner.theta["C1"]
    learner.settle(day=8)
    assert abs(learner.theta["C1"] - after_lesson * 0.5) < 1e-6


def test_worlds_deterministic_and_distinct_t4_2():
    from experiments.sim import WORLDS, SimLearner, PROFILES

    pre = {"C1": (), "C2": (), "C3": ("C1", "C2"), "C4": ("C3",)}
    for w in WORLDS:
        a = SimLearner(7, pre, PROFILES["nominal"], world=w, prereqs=pre)
        b = SimLearner(7, pre, PROFILES["nominal"], world=w, prereqs=pre)
        assert a.theta == b.theta
        assert [a.respond("C3", "E-C3-1", 0.5) for _ in range(5)] == [
            b.respond("C3", "E-C3-1", 0.5) for _ in range(5)
        ]
    s0 = SimLearner(7, pre, PROFILES["nominal"])
    assert SimLearner(7, pre, PROFILES["nominal"], world="S1", prereqs=pre).theta == s0.theta


def test_s1_readiness_gates_gains_t4_2():
    from experiments.sim import SimLearner, PROFILES

    pre = {"C1": (), "C2": ("C1",)}
    s = SimLearner(1, pre, PROFILES["nominal"], world="S1", prereqs=pre)
    s.theta.update({"C1": 0.2, "C2": 0.2})
    s.apply_activity("C2", is_lesson=True, day=1)
    low = s.theta["C2"]
    s.theta.update({"C1": 0.95, "C2": 0.2})
    s.apply_activity("C2", is_lesson=True, day=1)
    assert s.theta["C2"] - 0.2 > 5 * (low - 0.2)


def test_s2_s3_s4_properties_t4_2():
    import statistics
    from experiments.sim import SimLearner, PROFILES

    cs = [f"C{i}" for i in range(8)]
    spreads = [
        statistics.pstdev(SimLearner(s, cs, PROFILES["nominal"], world="S2").theta.values())
        for s in range(50)
    ]
    assert statistics.mean(spreads) < 0.15  # within-learner spread ~ N(0, 0.10)
    s3 = SimLearner(3, cs, PROFILES["nominal"], world="S3")
    assert 5.0 <= s3.half_life <= 30.0
    before = dict(s3.theta)
    s3.settle(20)
    assert all(s3.theta[c] < before[c] for c in cs)
    s4 = SimLearner(3, cs, PROFILES["nominal"], world="S4")
    assert set(s4.theta.values()) <= {0.0, 1.0}
    c = cs[0]
    s4.theta[c] = 1.0
    assert abs(s4.p_correct(c, 0.5) - (1 - (0.05 + 0.25 * 0.5))) < 1e-12
    s4.theta[c] = 0.0
    assert abs(s4.p_correct(c, 0.5) - 0.30 * 0.5) < 1e-12


def test_s4_fitted_world_t7_5(tmp_path):
    import json
    from experiments.sim import SimLearner, PROFILES, s4_fitted_params

    prof = {
        "p0": 0.9,
        "t_exercise": 0.1,
        "class_params": {
            "easy": {"guess": 0.4, "slip": 0.1},
            "medium": {"guess": 0.2, "slip": 0.3},
            "hard": {"guess": 0.05, "slip": 0.6},
        },
    }
    path = tmp_path / "p.json"
    path.write_text(json.dumps(prof))
    kw = s4_fitted_params(str(path))
    s = SimLearner(1, ["C1"], PROFILES["nominal"], world="S4", bkt_params=kw)
    s.theta["C1"] = 1.0
    assert abs(s.p_correct("C1", 0.8) - 0.4) < 1e-12
    s.theta["C1"] = 0.0
    assert abs(s.p_correct("C1", 0.2) - 0.4) < 1e-12
    mastered = sum(
        SimLearner(i, ["C1"], PROFILES["nominal"], world="S4", bkt_params=kw).theta["C1"]
        for i in range(200)
    )
    assert mastered > 150  # p0 = 0.9
