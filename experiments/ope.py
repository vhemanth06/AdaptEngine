"""Off-policy evaluation of a target ranking policy from logged decisions (W8 J.5).

Each logged decision has the candidates' features, the logging propensities, the chosen index and
the observed reward. The value of a policy is its expected per-decision reward.
  IPS   = mean(w r),  w = pi(a|x) / mu(a|x)
  SNIPS = sum(w r) / sum(w)
  DR    = mean(sum_a pi(a|x) rhat(x, a) + w (r - rhat(x, a_logged)))
rhat is a ridge regression on the logged (features, reward) pairs. Never imported from src/.
"""

from __future__ import annotations

import numpy as np


def fit_reward_model(decisions, lam: float = 1.0):
    X = np.array([d["features"][d["chosen_index"]] for d in decisions], float)
    y = np.array([d["reward"] for d in decisions], float)
    return np.linalg.solve(lam * np.eye(X.shape[1]) + X.T @ X, X.T @ y)


def estimate(decisions, target, lam: float = 1.0) -> dict:
    """target: object with propensities(list_of_feature_vectors) -> list of probabilities."""
    if not decisions:
        return {"n": 0, "ips": None, "snips": None, "dr": None}
    w_beta = fit_reward_model(decisions, lam)
    ws, rs, dr = [], [], []
    for d in decisions:
        pi = np.array(target.propensities(d["features"]))
        k, mu = d["chosen_index"], d["propensity"]
        w = pi[k] / mu
        rhat = np.array(d["features"], float) @ w_beta
        ws.append(w)
        rs.append(d["reward"])
        dr.append(float(pi @ rhat + w * (d["reward"] - rhat[k])))
    ws, rs = np.array(ws), np.array(rs)
    return {
        "n": len(decisions),
        "ips": float(np.mean(ws * rs)),
        "snips": float(np.sum(ws * rs) / np.sum(ws)) if np.sum(ws) > 0 else None,
        "dr": float(np.mean(dr)),
        "mean_weight": float(np.mean(ws)),
        "max_weight": float(np.max(ws)),
    }
