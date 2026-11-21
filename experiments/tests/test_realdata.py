"""Real-data fitting and cross-validation on synthetic data (V2-T3); real files not needed."""

import numpy as np
import pandas as pd

from experiments.core import realdata as R


def _simulate(n_users=300, n_items=12, prior=0.3, learn=0.15, guess=0.2, slip=0.1, seed=0):
    rng = np.random.RandomState(seed)
    rows = []
    for u in range(n_users):
        known = rng.rand() < prior
        for t in range(n_items):
            p = 1 - slip if known else guess
            rows.append((u, "S", int(rng.rand() < p), t, f"I{t}"))
            known = known or rng.rand() < learn
    return pd.DataFrame(rows, columns=["user", "skill", "correct", "order", "item"])


def test_em_recovers_known_parameters():
    df = _simulate(n_users=1500)
    f = R.fit_per_skill(df)["S"]
    assert abs(f["prior"] - 0.3) < 0.06
    assert abs(f["learn"] - 0.15) < 0.05
    assert abs(f["guess"] - 0.2) < 0.05
    assert abs(f["slip"] - 0.1) < 0.05


def test_folds_never_share_a_student():
    df = _simulate(n_users=50)
    folds = R.fold_students(df)
    assert sum(len(f) for f in folds) == 50
    for i in range(len(folds)):
        for j in range(i + 1, len(folds)):
            assert not folds[i] & folds[j]


def test_crossvalidated_metrics_in_range():
    df = pd.concat(
        [_simulate(200, seed=1).assign(skill="A"), _simulate(200, seed=2).assign(skill="B")]
    )
    df = df.sort_values(["skill", "user", "order"], kind="mergesort").reset_index(drop=True)
    res = R.crossvalidate(df, lambda users: R.item_difficulty(df[df.user.isin(users)]))
    for m in R.MODELS:
        x = res["pooled_oof"][m]
        assert 0 <= x["brier"] <= 1 and 0 <= x["rmse"] <= 1 and 0 <= x["ece"] <= 1
        assert 0.5 < x["auc"] <= 1 and x["log_loss"] > 0
        assert sum(b["n"] for b in x["reliability"]) == len(df)
