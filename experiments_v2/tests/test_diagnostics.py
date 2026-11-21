"""Diagnostic arms (V2-T2)."""

from adaptengine.core.config import bisection_config

from experiments_v2.core import curricula as C
from experiments_v2.core import diagnostics as D
from experiments_v2.core.simulator import make_learner


def _engines(cur):
    return {"sweep": C.engine(cur), "bisection": C.engine(cur, bisection_config())}, C.engine(cur)


def test_arm_question_counts():
    engines, base = _engines("8-node")
    cfg = engines["bisection"].config
    for seed in (101, 103, 105):
        out = D.simulated_arms(engines, base, seed, "S0")
        assert out["prior_only"]["items"] == 0
        n = out["bisection"]["items"]
        assert cfg.bisection_n_min <= n <= cfg.bisection_n_ceiling
        assert out["fixed@n"]["items"] == n
        assert out["irt_cat_global@n"]["items"] == n
        for arm in ("irt_cat_global@n", "irt_cat_per_concept@n"):
            assert all(0.0 <= p <= 1.0 for p, _ in out[arm]["pairs"])
        assert all("next_brier" in v for v in out.values())


def test_fixed_asks_exactly_n():
    e = C.engine("4-node")
    for n in (1, 4, 9):
        _, k = D.run_fixed(e, D.sim_answer(make_learner(e, 101, "S0")), n)
        assert k == n


def test_scripted_advanced_learner_is_recognised():
    engines, _ = _engines("8-node")
    for arm, e in engines.items():
        goal = C.goal_of(e)
        r = D.run_scripted(e, 101, "advanced", goal)
        nov = D.run_scripted(e, 101, "novice", goal)
        assert sum(p for p, _ in r["pairs"]) > sum(p for p, _ in nov["pairs"]), arm
        if arm == "bisection":  # the sweep's 6 questions cannot reach most of 8 concepts
            assert sum(p > 0.5 for p, _ in r["pairs"]) > len(r["pairs"]) / 2
    known = D.scripted_known(engines["sweep"], "advanced_minus_goal", C.goal_of(engines["sweep"]))
    assert C.goal_of(engines["sweep"]) not in known
