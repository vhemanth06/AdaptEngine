"""E4: OPE estimators on a toy log, learning-progress reward, train/eval smoke, Policy Lab load."""

import json
import os
import random

import pytest

from experiments.policy import learning_progress_reward, ope
from experiments.run_policy import main


class Target:
    """Always picks candidate 0."""

    def propensities(self, xs):
        return [1.0] + [0.0] * (len(xs) - 1)


def logs(n=4000, seed=0):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        feats = [[1.0, float(i == 0)] for i in range(3)]
        a = r.randrange(3)
        mean = 0.8 if a == 0 else 0.2  # candidate 0 pays 0.8: target value 0.8
        out.append(
            {"features": feats, "chosen_index": a, "propensity": 1 / 3,
             "reward": mean + r.uniform(-0.1, 0.1)}
        )  # fmt: skip
    return out


def test_ips_snips_dr_recover_known_value():
    est = ope(logs(), Target())
    for k in ("ips", "snips", "dr"):
        assert abs(est[k] - 0.8) < 0.05, (k, est[k])
    assert ope([], Target())["ips"] is None


def test_ips_hand_computed():
    # two decisions, target picks 0: w = 1/0.5 = 2 on the logged-0 decision, 0 otherwise.
    f = [[1.0], [1.0]]
    d = [
        {"features": f, "chosen_index": 0, "propensity": 0.5, "reward": 0.4},
        {"features": f, "chosen_index": 1, "propensity": 0.5, "reward": 1.0},
    ]
    assert abs(ope(d, Target())["ips"] - (2 * 0.4 + 0) / 2) < 1e-9


def test_learning_progress_reward():
    assert learning_progress_reward([], 1) == 0.0
    assert learning_progress_reward([0, 0, 0], 1) == 0.25  # 1/4 - 0/3
    assert learning_progress_reward([1, 1, 1, 1], 0) == -0.25
    assert -1.0 <= learning_progress_reward([0], 1) <= 1.0


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    d = tmp_path_factory.mktemp("pol")
    frozen = str(d / "frozen.json")
    out = main(["train", "--smoke", "--frozen-path", frozen, "--out-dir", str(d)])
    return d, frozen, out


def test_train_smoke(trained):
    d, frozen, out = trained
    f = json.load(open(frozen))
    assert f["meta"]["engine"] == "product" and len(f["weights"]) == len(f["feature_names"])
    assert f["n_updates"] > 0 and out["meta"]["engine"] == "product"
    assert (d / "policy_train_smoke.json").exists()


def test_eval_smoke_zero_violations(trained):
    d, frozen, _ = trained
    out = main(["eval", "--smoke", "--frozen-path", frozen, "--out-dir", str(d)])
    assert out["meta"]["engine"] == "product"
    (cell,) = out["cells"].values()
    for v in ("deterministic", "frozen", "updating", "random"):
        assert cell[v]["executed_violations"] == 0, v
    for lg in ("from_random", "from_updating"):
        assert {"ips", "snips", "dr"} <= set(cell["ope_frozen"][lg])
    assert os.path.exists(d / "policy_eval_smoke.json")
    assert os.path.exists(d / "policy_logs_smoke" / "random_S1_4node_x10.jsonl")
    assert not os.path.exists(d / "policy_logs")


def test_policy_lab_loads_frozen(trained, monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from frontend.api import app as app_module

    _, frozen, _ = trained
    monkeypatch.setenv("ADAPTENGINE_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setattr(app_module, "POLICY_FROZEN", app_module.Path(frozen))
    c = TestClient(app_module.app)
    sid = c.post(
        "/api/sessions",
        json={"curriculum": "8node", "goal": "C8", "deadline_day": 20, "budget": 10},
    ).json()["session_id"]
    c.post(f"/api/sessions/{sid}/plan", json={})
    r = c.post(f"/api/sessions/{sid}/policy-preview", json={"policy": "bandit_frozen"})
    assert r.status_code == 200 and r.json()["today"]["activities"]
    n = json.load(open(frozen))["n_updates"]  # the tmp file, not the real config one
    vers = {d["policy_version"] for d in r.json()["decisions"] if "policy_version" in d}
    assert vers and vers == {f"linucb-softmax/frozen/n{n}"}


def test_smoke_train_never_writes_real_frozen(tmp_path):
    from experiments.run_policy import FROZEN

    before = os.path.getmtime(FROZEN) if os.path.exists(FROZEN) else None
    main(["train", "--smoke", "--out-dir", str(tmp_path)])
    assert os.path.exists(tmp_path / "policy_frozen_smoke.json")
    assert (os.path.getmtime(FROZEN) if os.path.exists(FROZEN) else None) == before


def test_no_policy_decision_dropped(monkeypatch):
    """Every executed activity that the latest plan logged as POLICY_SELECTED for that day yields
    exactly one decision (plans were once matched by id(), which CPython reuses)."""
    from adaptengine.policy import BanditPolicy

    import experiments.policy as P
    from experiments.common import product_engine

    real, made = P.run_episode, []

    def counting(*args, next_fn, on_execute, **kw):
        last = {}

        def nf(*a, **k):
            today, last["plan"] = next_fn(*a, **k)
            return today, last["plan"]

        def oe(act, correct, day):
            made.append(any(t.get("decision") == "POLICY_SELECTED" and t["day"] == day
                            and t["chosen"] == act.activity_id for t in last["plan"].trace))  # fmt: skip
            on_execute(act, correct, day)

        return real(*args, next_fn=nf, on_execute=oe, **kw)

    monkeypatch.setattr(P, "run_episode", counting)
    n_dec = 0
    for seed in range(2001, 2061, 2):
        pol = BanditPolicy("random", seed=seed)
        r = P.run_policy_episode(
            product_engine("4node_x10", policy=pol), seed, "S1", "4node_x10", pol
        )
        n_dec += len(r["decisions"])
    assert n_dec > 0 and n_dec == sum(made)
