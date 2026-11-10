"""W8 WP-J A2 bandit ranking policy and the scheduler hook (TC3.1, TC7.1, TC8.2)."""

import json
import os
import sys

import numpy as np
import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.core.schema import PlanContext  # noqa: E402
from adaptengine.policy import BanditPolicy, DeterministicPolicy, keyed_uniform  # noqa: E402
from adaptengine.policy.features import DIM, FEATURE_NAMES, extract  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402

C4 = ("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
C8 = ("data/curriculum/curriculum_8node.json", "data/curriculum/activities_8node.json")
CTX = {"day": 2, "start_day": 1, "deadline_day": 14, "budget": 15, "remaining_budget": 9,
       "slot": 1, "seed": 0, "goal": "C4"}  # fmt: skip


def cand(aid, p=0.4, typ="EXERCISE", d=0.4, rank=0):
    return {
        "activity_id": aid, "concept": "C1", "type": typ, "difficulty": None if typ == "LESSON" else d,
        "duration": 2, "p": p, "responses": 2, "days_since_practice": 1,
        "p_correct": None if typ == "LESSON" else 0.6, "unlock": 3.0, "review_urgency": 0.0,
        "on_goal_path": True, "det_rank": rank, "det_score": 3.5,
    }  # fmt: skip


def test_keyed_uniform_is_deterministic_and_in_range():
    xs = [keyed_uniform("a", i) for i in range(500)]
    assert xs == [keyed_uniform("a", i) for i in range(500)]
    assert all(0.0 <= x < 1.0 for x in xs) and 0.4 < sum(xs) / len(xs) < 0.6


def test_features_are_finite_scaled_and_named():
    x = extract(cand("E1"), CTX)
    assert len(x) == DIM == len(FEATURE_NAMES) and x[0] == 1.0
    assert all(-1e-9 <= v <= 1.0 + 1e-9 for v in x)
    xl = extract(cand("L1", typ="LESSON"), CTX)
    assert xl[FEATURE_NAMES.index("is_lesson")] == 1.0 and xl[FEATURE_NAMES.index("p_correct")] == 0
    with pytest.raises(ValueError):
        extract(cand("E1", p=float("nan")), CTX)


@pytest.mark.parametrize("mode", ["frozen", "updating", "random"])
def test_propensities_sum_to_one_and_choice_is_reproducible(mode):
    pol = BanditPolicy(mode, seed=3)
    cs = [cand(f"E{i}", p=0.2 + 0.1 * i, d=0.2 + 0.15 * i, rank=i) for i in range(5)]
    aid, prop, info = pol.choose(cs, CTX)
    assert abs(sum(info["propensities"]) - 1.0) < 1e-6
    assert prop == pytest.approx(
        info["propensities"][[c["activity_id"] for c in cs].index(aid)], abs=1e-6
    )
    assert pol.choose(cs, CTX)[0] == aid
    if mode == "random":
        assert info["propensities"] == [0.2] * 5


def test_choices_follow_propensities():
    pol = BanditPolicy("random", seed=1)
    cs = [cand(f"E{i}", rank=i) for i in range(4)]
    counts = {}
    for s in range(800):
        aid, _, _ = pol.choose(cs, {**CTX, "slot": s})
        counts[aid] = counts.get(aid, 0) + 1
    assert all(150 < v < 250 for v in counts.values())


def test_ridge_update_matches_closed_form():
    pol = BanditPolicy("updating", lam=1.0)
    rng = np.random.RandomState(0)
    X, r = rng.rand(30, DIM), rng.rand(30) * 2 - 1
    for x, y in zip(X, r):
        pol.update(list(x), float(y))
    w = np.linalg.solve(np.eye(DIM) + X.T @ X, X.T @ r)
    assert np.allclose(pol.weights(), w, atol=1e-8)
    frozen = pol.copy(mode="frozen")
    frozen.update(list(X[0]), 1.0)
    assert np.allclose(frozen.weights(), w)  # frozen ignores updates
    with pytest.raises(ValueError):
        pol.update([0.0] * (DIM - 1), 1.0)


def test_save_load_roundtrip(tmp_path):
    pol = BanditPolicy("updating", seed=2)
    pol.update(extract(cand("E1"), CTX), 0.5)
    path = tmp_path / "policy.json"
    pol.save(str(path), meta={"code_hash": "x"})
    back = BanditPolicy.load(str(path), mode="frozen", seed=2)
    assert back.weights() == pytest.approx(pol.weights())
    assert json.load(open(path))["code_hash"] == "x"
    bad = {**json.load(open(path)), "feature_names": ["x"]}
    with pytest.raises(ValueError):
        BanditPolicy.from_dict(bad)


# ------------------------------------------------------------------ scheduler hook (J.1, J.4)


def engines(paths, policy):
    cfg = DEFAULT_CONFIG
    return Engine.from_files(*paths, config=cfg), Engine.from_files(
        *paths, config=cfg, policy=policy
    )


@pytest.mark.parametrize("paths,goal", [(C4, "C4"), (C8, "C8")])
def test_deterministic_policy_gives_bit_identical_plans(paths, goal):
    base, wrapped = engines(paths, DeterministicPolicy())
    for budget in (5, 10, 15, 30):
        ctx = PlanContext(goal=goal, deadline_day=40, budget=budget, current_day=1)
        p0, p1 = base.plan(base.init_learner(), ctx), wrapped.plan(wrapped.init_learner(), ctx)
        assert p0.days == p1.days and p0.status == p1.status
        assert any(t.get("decision") in ("POLICY_SELECTED", "POLICY_FALLBACK") for t in p1.trace)
    for scen in ("calm", "missed_day"):
        sc = get_scenario(scen, base, base.init_learner(), goal=goal, budget=15, horizon=14)
        for seed in range(3):
            r0 = run_episode(base, seed, sc, "adapt", PROFILES["nominal"], "S1")
            r1 = run_episode(wrapped, seed, sc, "adapt", PROFILES["nominal"], "S1")
            assert r0["exercise_log"] == r1["exercise_log"]
            assert r0["executed_minutes_per_day"] == r1["executed_minutes_per_day"]


class Raising:
    name = "raising"

    def choose(self, candidates, context):
        raise RuntimeError("boom")


class Unknown:
    name = "unknown"

    def choose(self, candidates, context):
        return "NOT-AN-ID", 1.0, {}


@pytest.mark.parametrize("bad", [Raising(), Unknown()])
def test_policy_failure_falls_back_to_deterministic(bad):
    base, broken = engines(C4, bad)
    ctx = PlanContext(goal="C4", deadline_day=20, budget=15, current_day=1)
    p0, p1 = base.plan(base.init_learner(), ctx), broken.plan(broken.init_learner(), ctx)
    assert p0.days == p1.days
    fb = [t for t in p1.trace if t.get("decision") == "POLICY_FALLBACK"]
    assert fb and not any(t.get("decision") == "POLICY_SELECTED" for t in p1.trace)
    assert {t["reason"] for t in fb} >= {"SINGLE_CANDIDATE"} | (
        {"RuntimeError"} if isinstance(bad, Raising) else {"StopIteration"}
    )


@pytest.mark.parametrize("mode", ["frozen", "updating", "random"])
def test_bandit_candidates_subset_of_eligible_and_zero_violations(mode):
    for paths, goal in ((C4, "C4"), (C8, "C8")):
        e = Engine.from_files(*paths, policy=BanditPolicy(mode, seed=5))
        sc = get_scenario("calm", e, e.init_learner(), goal=goal, budget=15, horizon=14)
        for seed in range(3):
            for world in ("S1", "S4"):
                r = run_episode(e, seed, sc, "adapt", PROFILES["nominal"], world)
                assert r["executed_prereq_violations"] == 0 and r["budget_violations"] == 0
        plan = e.plan(e.init_learner(), PlanContext(goal=goal, deadline_day=30, budget=15))
        sel = [t for t in plan.trace if t.get("decision") == "POLICY_SELECTED"]
        assert sel
        for t in sel:
            assert t["chosen"] in t["candidates"] and len(t["candidates"]) <= 5
            assert t["propensity"] == pytest.approx(
                t["propensities"][t["candidates"].index(t["chosen"])], abs=1e-6
            )
