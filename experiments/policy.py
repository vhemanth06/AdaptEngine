"""E4: closed-loop episodes with a ranking policy on the product engine, decision logging,
learning-progress rewards and off-policy evaluation (IPS / SNIPS / DR). Never imported from src/.

Each logged decision has the candidates' features, the logging propensities, the chosen index
and the observed reward; a policy's value is its expected per-decision reward.
  IPS   = mean(w r),  w = pi(a|x) / mu(a|x)
  SNIPS = sum(w r) / sum(w)
  DR    = mean(sum_a pi(a|x) rhat(x, a) + w (r - rhat(x, a_logged)))   (rhat: ridge on the log)
"""

from __future__ import annotations

import json

import numpy as np

from experiments.arms import get_scenario, run_episode
from experiments.common import goal_of, product_engine, world_kw
from experiments.sim import PROFILES

WINDOW = 4  # rolling success window w
BUDGET, HORIZON = 15, 14


def learning_progress_reward(hist: list[int], y: int) -> float:
    """Change in the rolling success rate over the last WINDOW attempts, clipped to [-1, 1];
    0 for a first attempt."""
    if not hist:
        return 0.0
    before, after = hist[-WINDOW:], (hist + [y])[-WINDOW:]
    return max(-1.0, min(1.0, sum(after) / len(after) - sum(before) / len(before)))


def run_policy_episode(engine, seed, world, cur, policy, log_path=None) -> dict:
    """One closed-loop (adapt, calm, B 15, 14 d) episode on `engine`, which must have been built
    with `policy` (None = deterministic). Returns the episode result plus "decisions"; a lesson's
    reward is assigned at the next exercise on its concept. A stateful policy is updated online."""
    base = product_engine(cur)
    sc = get_scenario(
        "calm", base, base.init_learner(), goal=goal_of(base), budget=BUDGET, horizon=HORIZON
    )
    last_plan = {"plan": None}
    decisions: list[dict] = []
    consumed: set = set()  # trace indices of the latest plan already turned into decisions
    hist: dict[str, list[int]] = {}
    pending: dict[str, list[dict]] = {}

    def next_fn(state, log, ctx, review_urgency=None):
        today, plan = engine.next_activities(state, log, ctx, review_urgency=review_urgency)
        if plan is not last_plan["plan"]:  # only the latest plan is matched (not id(): reused)
            consumed.clear()
        last_plan["plan"] = plan
        return today, plan

    def on_execute(act, correct, day):
        plan, dec = last_plan["plan"], None
        for i, t in enumerate(plan.trace if plan is not None else ()):
            if (
                t.get("decision") == "POLICY_SELECTED"
                and t["day"] == day
                and t["chosen"] == act.activity_id
                and i not in consumed
            ):
                consumed.add(i)
                dec = {
                    "seed": seed, "day": day, "candidates": t["candidates"], "chosen": t["chosen"],
                    "chosen_index": t["candidates"].index(t["chosen"]),
                    "propensity": t["propensity"], "propensities": t["propensities"],
                    "features": t["features"], "deterministic_choice": t["deterministic_choice"],
                    "reward": None, "policy_version": t["policy_version"],
                }  # fmt: skip
                decisions.append(dec)
                break
        c = act.target_concept
        if correct is None:  # lesson
            if dec is not None:
                pending.setdefault(c, []).append(dec)
            return
        r = learning_progress_reward(hist.setdefault(c, []), int(correct))
        hist[c].append(int(correct))
        for d in ([dec] if dec is not None else []) + pending.pop(c, []):
            d["reward"] = r
            if policy is not None:
                policy.update(d["features"][d["chosen_index"]], r)

    sim_w, sim_kw = world_kw(world)
    res = run_episode(
        engine, seed, sc, "adapt", PROFILES["nominal"], world=sim_w, sim_kw=sim_kw,
        next_fn=next_fn, on_execute=on_execute,
    )  # fmt: skip
    for d in decisions:
        if d["reward"] is None:
            d["reward"] = 0.0
    if log_path:
        with open(log_path, "a") as f:
            f.writelines(json.dumps(d) + "\n" for d in decisions)
    return {**res, "decisions": decisions}


def _ridge(decisions, lam=1.0):
    X = np.array([d["features"][d["chosen_index"]] for d in decisions], float)
    y = np.array([d["reward"] for d in decisions], float)
    return np.linalg.solve(lam * np.eye(X.shape[1]) + X.T @ X, X.T @ y)


def ope(logs, target, reward_model="ridge") -> dict:
    """target: object with propensities(list_of_feature_vectors) -> list of probabilities."""
    if reward_model != "ridge":
        raise ValueError(f"unknown reward_model {reward_model!r}")
    if not logs:
        return {"n": 0, "ips": None, "snips": None, "dr": None}
    beta = _ridge(logs)
    ws, rs, dr = [], [], []
    for d in logs:
        pi = np.array(target.propensities(d["features"]))
        k = d["chosen_index"]
        w = pi[k] / d["propensity"]
        rhat = np.array(d["features"], float) @ beta
        ws.append(w)
        rs.append(d["reward"])
        dr.append(float(pi @ rhat + w * (d["reward"] - rhat[k])))
    ws, rs = np.array(ws), np.array(rs)
    return {
        "n": len(logs),
        "ips": float(np.mean(ws * rs)),
        "snips": float(np.sum(ws * rs) / np.sum(ws)) if np.sum(ws) > 0 else None,
        "dr": float(np.mean(dr)),
        "mean_weight": float(np.mean(ws)),
        "max_weight": float(np.max(ws)),
    }
