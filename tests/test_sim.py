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
