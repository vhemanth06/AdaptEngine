"""WP7 T7.2: BKT fitting pipeline on tiny synthetic CSVs (no network, no real data)."""

import json
import math
import os
import sys

import pytest

pytest.importorskip("pyBKT")  # optional extra; the main CI matrix has no pyBKT/numpy/pandas
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
import fit_bkt as fb  # noqa: E402
from pyBKT.models import Model  # noqa: E402


def synth_csv(path, n_users=40, skills=("A", "B"), seed=0, n_classes=1):
    """pyBKT as.csv-style CSV from a known BKT process (prior .3, learn .15, guess .2, slip .1)."""
    rng = np.random.RandomState(seed)
    rows = []
    for skill in skills:
        for u in range(n_users):
            known = rng.rand() < 0.3
            for _ in range(rng.randint(3, 12)):
                k = rng.randint(n_classes)
                p = (0.9 - 0.1 * k) if known else (0.2 - 0.05 * k)
                rows.append((len(rows), u, skill, int(rng.rand() < p), k))
                known = known or rng.rand() < 0.15
    df = pd.DataFrame(rows, columns=["order_id", "user_id", "skill_name", "correct", "template_id"])
    df.to_csv(path, index=False)
    return df


def seqs(df, cls=None):
    df = df.sort_values(["user_id", "order_id"], kind="mergesort")
    k = np.zeros(len(df), int) if cls is None else df[cls].to_numpy()
    return df, fb.make_seqs(df.user_id.to_numpy(), df.correct.to_numpy(), k)


@pytest.mark.parametrize("multigs", [False, True])
def test_fast_em_matches_pybkt_from_same_init(tmp_path, multigs):
    K = 2 if multigs else 1
    df = synth_csv(tmp_path / "s.csv", skills=("A",), n_classes=K)
    init = {"prior": 0.3, "learn": 0.1, "guess": np.full(K, 0.2), "slip": np.full(K, 0.1)}
    m = Model(seed=1, num_fits=1, parallel=False)
    m.coef_ = {
        "A": {
            "prior": 0.3,
            "learns": np.array([0.1]),
            "guesses": init["guess"],
            "slips": init["slip"],
        }
    }
    m.fit(data_path=str(tmp_path / "s.csv"), multigs=multigs)
    ref = m.coef_["A"]
    _, S = seqs(df, "template_id" if multigs else None)
    f = fb.fast_em(S, K, num_fits=1, init=init)
    assert f["prior"] == pytest.approx(ref["prior"], abs=1e-6)
    assert f["learn"] == pytest.approx(ref["learns"][0], abs=1e-6)
    np.testing.assert_allclose(f["guess"], ref["guesses"], atol=1e-6)
    np.testing.assert_allclose(f["slip"], ref["slips"], atol=1e-6)


def test_predict_matches_pybkt(tmp_path):
    df = synth_csv(tmp_path / "s.csv", skills=("A",))
    m = Model(seed=3, num_fits=1, parallel=False)
    m.fit(data=df)
    ref = m.coef_["A"]
    fit = {
        "prior": ref["prior"],
        "learn": ref["learns"][0],
        "guess": ref["guesses"],
        "slip": ref["slips"],
    }
    sdf, S = seqs(df)
    ours = fb.predict(S, fit, len(sdf))
    theirs = m.predict(data=df).set_index("order_id").loc[sdf.order_id, "correct_predictions"]
    np.testing.assert_allclose(ours, theirs.to_numpy(), atol=1e-9)


def test_pybkt_pipeline_end_to_end(tmp_path):
    synth_csv(tmp_path / "s.csv")
    res = fb.pybkt_pipeline(str(tmp_path / "s.csv"), seed=7, num_fits=2, folds=3)
    assert set(res["per_skill"]) == {"A", "B"}
    for r in res["per_skill"].values():
        assert all(0 <= r[p] <= 1 for p in fb.PARAMS)
        assert math.isfinite(r["cv_rmse"]) and 0 <= r["cv_auc"] <= 1
        assert isinstance(r["flags"], list)


def test_degenerate_fit_is_flagged():
    """Students who are right first and wrong later: EM can only explain it with G + S >= 1."""
    obs = np.array(([1] * 5 + [0] * 5) * 40)
    S = fb.make_seqs(np.repeat(np.arange(40), 10), obs, np.zeros(len(obs), int))
    f = fb.fast_em(S, 1, num_fits=3)
    flags = fb.check_params(f["prior"], f["learn"], f["guess"][0], f["slip"][0])
    assert "guess+slip>=1" in flags and fb.is_degenerate(flags)
    summary = fb.skill_summary(
        {"bad": {**f, "guess": f["guess"][0], "slip": f["slip"][0], "flags": flags}}
    )
    assert summary["n_degenerate"] == 1 and summary["pct_guess_plus_slip_ge_1"] == 100.0


def test_check_params_rules():
    assert fb.check_params(0.3, 0.1, 0.2, 0.1) == []
    assert fb.check_params(0.005, 0.1, 0.2, 0.1) == ["prior<0.01"]
    assert not fb.is_degenerate(["prior<0.01"])
    assert fb.is_degenerate(fb.check_params(0.3, 0.1, 0.1, 0.6))


def test_profile_writer_enforces_guess_plus_slip(tmp_path):
    fit = {
        "prior": 0.5,
        "learn": 0.1,
        "guess": {"easy": 0.3, "medium": 0.2, "hard": 0.05},
        "slip": {"easy": 0.1, "medium": 0.3, "hard": 0.6},
    }
    out = tmp_path / "p.json"
    prof = fb.write_profile(str(out), fit, {"profile": "t"})
    assert json.loads(out.read_text())["class_params"]["hard"]["slip"] == 0.6
    assert prof["constraint_warnings"] == {"hard": ["slip>0.5"]}
    fit["guess"]["hard"] = 0.45
    with pytest.raises(ValueError, match="guess\\+slip<1"):
        fb.write_profile(str(tmp_path / "bad.json"), fit, {})


def test_classify_uses_engine_boundaries():
    d = pd.Series([0.0, 0.34, 0.35, 0.64, 0.65, 1.0, np.nan])
    expected = ["easy", "easy", "medium", "medium", "hard", "hard", "unrated"]
    assert fb.classify(d).tolist() == expected


def test_metrics_reliability_bins_cover_all():
    y = np.array([0, 1, 1, 0, 1])
    p = np.array([0.1, 0.9, 0.6, 0.4, 1.0])
    m = fb.metrics(y, p)
    assert sum(b["n"] for b in m["reliability"]) == len(y) and m["auc"] == 1.0
