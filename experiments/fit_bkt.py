"""BKT parameter fitting on real learner data (WP7 T7.2/T7.3/T7.6; real-data part of T3.5).

Model: standard BKT (prior, learn, guess, slip; no forgetting), optionally with guess/slip per item
class (pyBKT `multigs`). Two back-ends fit the same model:

- `pybkt_pipeline`: pyBKT 1.4.3 `Model(seed, num_fits=5).fit` -> `crossvalidate(folds=5,
  metric=['rmse', 'auc'])` -> `params()`. The reference implementation (T7.2).
- `fast_em`: a vectorised numpy Baum-Welch of the same model with pyBKT's random-init ranges
  (prior U(0,1), learn U(0,.4), guess U(0,.4), slip U(0,.3)), best-of-`num_fits` by
  log-likelihood and pyBKT's stopping rule (|dLL| <= 0.005, max 100 iterations). pyBKT 1.4.3 is
  pure Python here (about 66 s for one 5k-row CT skill), so the ASSISTments fits, bootstraps and
  held-out checks use fast_em. `parity_check` and tests/test_fit_bkt.py compare it with pyBKT.

Constraint checks (EDM 2024-style, see `check_params`): a fit is *degenerate* if guess + slip >= 1,
guess > 0.5 or slip > 0.5; prior < PRIOR_MIN (0.01) is flagged separately. Fits are not altered.
The profile writer refuses guess + slip >= 1 (hard rule) and records the other flags as warnings.

CLI:
    python experiments/fit_bkt.py pybkt --data data/external/ct.csv   # T7.2 pyBKT pipeline
    python experiments/fit_bkt.py assist09 [--boot 200]               # T7.3 + config profile
    python experiments/fit_bkt.py ct [--boot 200]                     # T7.6
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
import time
from datetime import datetime, timezone
from multiprocessing import get_context

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adaptengine.core import constants as C  # noqa: E402
from adaptengine.learner.adapter import DEFAULT_CLASS_PARAMS, get_difficulty_class  # noqa: E402
from provenance import code_hash  # noqa: E402

EXTERNAL = os.path.join(REPO_ROOT, "data", "external")
RESULTS = os.path.join(REPO_ROOT, "experiments", "results")
SEED = 42
PRIOR_MIN = 0.01
MIN_STUDENTS = 100
MIN_ITEM_ANSWERS = 20
CLASSES = ["easy", "medium", "hard", "unrated"]  # unrated: item has < MIN_ITEM_ANSWERS answers
PARAMS = ["prior", "learn", "guess", "slip"]
WORKERS = min(8, os.cpu_count() or 1)


# ---------------------------------------------------------------- constraint checks


def check_params(prior: float, learn: float, guess: float, slip: float) -> list[str]:
    """Flags for one (skill, class) fit. Any of the first three makes the fit degenerate."""
    flags = []
    if guess + slip >= 1:
        flags.append("guess+slip>=1")
    if guess > 0.5:
        flags.append("guess>0.5")
    if slip > 0.5:
        flags.append("slip>0.5")
    if prior < PRIOR_MIN:
        flags.append(f"prior<{PRIOR_MIN}")
    return flags


def is_degenerate(flags: list[str]) -> bool:
    return any(not f.startswith("prior") for f in flags)


# ---------------------------------------------------------------- data loading


def load_ct(path: str = os.path.join(EXTERNAL, "ct.csv")) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(path)
    df = raw.rename(
        columns={
            "Anon Student Id": "user",
            "KC(Default)": "skill",
            "Correct First Attempt": "correct",
            "Row": "order",
            "Problem Name": "item",
        }
    )[["user", "skill", "correct", "order", "item"]].dropna(subset=["skill"])
    steps = {"raw_rows": len(raw), "rows_with_skill": len(df)}
    return _keep_skills(df, steps)


def load_assist(
    as_path: str = os.path.join(EXTERNAL, "as.csv"),
) -> tuple[pd.DataFrame, dict]:
    """Clean as.csv: original == 1, skill present, one row per (order_id, skill), >= 100 students."""
    cols = ["order_id", "user_id", "problem_id", "original", "correct", "skill_name"]
    a = pd.read_csv(as_path, encoding="ISO-8859-15", usecols=cols, low_memory=False)
    steps = {"raw_rows": len(a), "raw_answers": int(a.order_id.nunique())}
    a = a[a.original == 1]
    steps["original==1"] = len(a)
    a = a.dropna(subset=["skill_name"])
    steps["with_skill_name"] = len(a)
    a = a.drop_duplicates(["order_id", "skill_name"])
    steps["dedup_order_skill"] = len(a)
    df = a.rename(
        columns={
            "user_id": "user",
            "skill_name": "skill",
            "order_id": "order",
            "problem_id": "item",
        }
    )[["user", "skill", "correct", "order", "item"]]
    return _keep_skills(df, steps)


def _keep_skills(df: pd.DataFrame, steps: dict) -> tuple[pd.DataFrame, dict]:
    n_students = df.groupby("skill").user.nunique()
    steps["skills_before_min_students"] = int(len(n_students))
    df = df[df.skill.isin(n_students[n_students >= MIN_STUDENTS].index)]
    df = df.sort_values(["skill", "user", "order"], kind="mergesort").reset_index(drop=True)
    df["correct"] = df.correct.astype(np.int8)
    steps.update(
        rows_final=len(df),
        skills_final=int(df.skill.nunique()),
        students_final=int(df.user.nunique()),
        correct_rate_final=round(float(df.correct.mean()), 4),
    )
    return df, steps


def assist_difficulty(users=None, path=os.path.join(EXTERNAL, "assist09_skill_builder.csv")):
    """d = 1 - mean correct per problem_id from the collapsed file (optionally only `users`)."""
    c = pd.read_csv(
        path, encoding="ISO-8859-15", index_col=0, usecols=[0, 3, 5, 7], low_memory=False
    )
    if users is not None:
        c = c[c.user_id.isin(users)]
    return item_difficulty(c.rename(columns={"problem_id": "item"}))


def item_difficulty(df: pd.DataFrame) -> pd.Series:
    agg = df.groupby("item").correct.agg(["mean", "size"])
    return 1.0 - agg.loc[agg["size"] >= MIN_ITEM_ANSWERS, "mean"]


def classify(d: pd.Series) -> pd.Series:
    """Engine D6 classes via get_difficulty_class on d clipped to [D_MIN, D_MAX]; NaN -> unrated."""
    dc = d.clip(C.D_MIN, C.D_MAX)
    lut = {v: get_difficulty_class(float(v)) for v in dc.dropna().unique()}
    return dc.map(lut).fillna("unrated")


# ---------------------------------------------------------------- sequences + EM


def make_seqs(seq: np.ndarray, correct: np.ndarray, cls: np.ndarray) -> dict:
    """Ragged time-major layout. Rows must be chronological within each sequence id.

    Sequences are ranked by length (longest first) so step t uses the first n_at[t] of them.
    """
    seq = pd.factorize(seq)[0]
    lengths = np.bincount(seq)
    rank = np.empty(len(lengths), dtype=np.int64)
    rank[np.argsort(-lengths, kind="stable")] = np.arange(len(lengths))
    pos = pd.Series(seq).groupby(seq).cumcount().to_numpy()
    order = np.lexsort((rank[seq], pos))
    n_at = np.searchsorted(-np.sort(lengths)[::-1], -np.arange(lengths.max()), side="left")
    cuts = np.cumsum(n_at)[:-1]
    return {
        "obs": np.split(correct[order].astype(np.int8), cuts),
        "cls": np.split(cls[order].astype(np.int64), cuts),
        "rows": np.split(order, cuts),
        "n_seq": len(lengths),
    }


def _forward(S: dict, prior, learn, guess, slip):
    """Filter for R parameter sets at once (arrays shaped (R,), guess/slip (R, K))."""
    p = np.repeat(prior[:, None], S["n_seq"], axis=1)
    out = []
    for o, k in zip(S["obs"], S["cls"]):
        p = p[:, : len(o)]
        g, s = guess[:, k], slip[:, k]
        e1, e0 = np.where(o, 1 - s, s), np.where(o, g, 1 - g)
        f1 = p * e1
        c = f1 + (1 - p) * e0
        a = f1 / c
        out.append((p * (1 - s) + (1 - p) * g, a, c, e0, e1))
        p = a + (1 - a) * learn[:, None]
    return out


def _em_step(S: dict, prior, learn, guess, slip, K: int):
    """One E-step; returns log-likelihood (R,) and M-step parameter estimates."""
    fw = _forward(S, prior, learn, guess, slip)
    R = len(prior)
    ll = np.zeros(R)
    gn, gd, sn, sd = (np.zeros((R, K)) for _ in range(4))
    x01, x0 = np.zeros(R), np.zeros(R)
    b0 = b1 = np.ones((R, 0))
    L = learn[:, None]
    for t in range(len(fw) - 1, -1, -1):
        _, a, c, e0, e1 = fw[t]
        n = a.shape[1]
        pad = np.ones((R, n - b0.shape[1]))
        b0, b1 = np.hstack([b0, pad]), np.hstack([b1, pad])
        gam1, gam0 = a * b1, (1 - a) * b0
        o, onehot = S["obs"][t], np.eye(K)[S["cls"][t]]
        gn += (gam0 * o) @ onehot
        gd += gam0 @ onehot
        sn += (gam1 * (1 - o)) @ onehot
        sd += gam1 @ onehot
        ll += np.log(c).sum(axis=1)
        if t > 0:  # transitions t-1 -> t for the n sequences still active at t
            w0, w1 = e0 * b0 / c, e1 * b1 / c
            a_prev = fw[t - 1][1][:, :n]
            xi01 = (1 - a_prev) * L * w1
            x01 += xi01.sum(axis=1)
            x0 += ((1 - a_prev) * (1 - L) * w0 + xi01).sum(axis=1)
            b0, b1 = (1 - L) * w0 + L * w1, w1
    with np.errstate(invalid="ignore", divide="ignore"):
        new = (
            gam1.mean(axis=1),
            np.where(x0 > 0, x01 / x0, learn),
            np.where(gd > 0, gn / gd, guess),
            np.where(sd > 0, sn / sd, slip),
        )
    return ll, new


def fast_em(S, K=1, num_fits=5, seed=SEED, init=None, tol=0.005, maxiter=100) -> dict:
    """Best-of-num_fits EM (restarts run vectorised). `init` (a fit dict) replaces restart 0."""
    rng = np.random.RandomState(seed)
    prior, learn = rng.random_sample(num_fits), rng.random_sample(num_fits) * 0.4
    guess, slip = rng.random_sample((num_fits, K)) * 0.4, rng.random_sample((num_fits, K)) * 0.3
    if init is not None:
        prior[0], learn[0] = init["prior"], init["learn"]
        guess[0], slip[0] = init["guess"], init["slip"]
    done, iters, final_ll, prev = np.zeros(num_fits, bool), np.zeros(num_fits, int), None, None
    for i in range(maxiter):
        ll, new = _em_step(S, prior, learn, guess, slip, K)
        final_ll = ll if final_ll is None else np.where(done, final_ll, ll)  # frozen once converged
        iters = np.where(done, iters, i + 1)
        if i > 1:
            done |= np.abs(ll - prev) <= tol
        if done.all():
            break
        prev = ll
        keep = done[:, None]
        prior, learn = np.where(done, prior, new[0]), np.where(done, learn, new[1])
        guess, slip = np.where(keep, guess, new[2]), np.where(keep, slip, new[3])
    b = int(np.argmax(final_ll))
    return {
        "prior": float(prior[b]),
        "learn": float(learn[b]),
        "guess": guess[b].tolist(),
        "slip": slip[b].tolist(),
        "loglik": float(final_ll[b]),
        "iters": int(iters[b]),
        "converged": bool(done[b]),
    }


def predict(S: dict, fit: dict, n_rows: int) -> np.ndarray:
    """One-step-ahead P(correct) per source row (BKT forward filter, no forgetting)."""
    arr = lambda v: np.atleast_2d(np.asarray(v, float))  # noqa: E731
    fw = _forward(
        S, arr(fit["prior"])[0], arr(fit["learn"])[0], arr(fit["guess"]), arr(fit["slip"])
    )
    out = np.full(n_rows, np.nan)
    for (pc, *_), rows in zip(fw, S["rows"]):
        out[rows] = pc[0]
    return out


def loglik(S: dict, fit: dict) -> float:
    arr = lambda v: np.atleast_2d(np.asarray(v, float))  # noqa: E731
    fw = _forward(
        S, arr(fit["prior"])[0], arr(fit["learn"])[0], arr(fit["guess"]), arr(fit["slip"])
    )
    return float(sum(np.log(c).sum() for _, _, c, _, _ in fw))


def parity_vs_pybkt(df: pd.DataFrame, per_skill: dict, path: str) -> dict | None:
    """Compare fast_em per-skill fits with a saved pyBKT run (`pybkt` command) on the same data."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        ref = json.load(f)["per_skill"]
    rows = {}
    for s, fit in per_skill.items():
        if s not in ref:
            continue
        g = df[df.skill == s]
        S = make_seqs(g.user.to_numpy(), g.correct.to_numpy(), np.zeros(len(g), int))
        rows[s] = {
            "max_abs_param_diff": max(abs(fit[p] - ref[s][p]) for p in PARAMS),
            "loglik_fast_em": fit["loglik"],
            "loglik_at_pybkt_params": loglik(S, ref[s]),
        }
    diffs = [r["max_abs_param_diff"] for r in rows.values()]
    dll = [r["loglik_fast_em"] - r["loglik_at_pybkt_params"] for r in rows.values()]
    return {
        "reference": os.path.relpath(path, REPO_ROOT),
        "per_skill": rows,
        "max_abs_param_diff": max(diffs),
        "min_loglik_gain_fast_minus_pybkt": min(dll),
    }


# ---------------------------------------------------------------- fitting helpers


def _skill_fit(args):
    """Standard BKT for one skill frame (rows sorted by user, order)."""
    sdf, seed, init = args
    S = make_seqs(sdf.user.to_numpy(), sdf.correct.to_numpy(), np.zeros(len(sdf), int))
    f = fast_em(S, 1, seed=seed, init=init)
    f.update(guess=f["guess"][0], slip=f["slip"][0], n_students=S["n_seq"], n_answers=len(sdf))
    f["flags"] = check_params(f["prior"], f["learn"], f["guess"], f["slip"])
    return f


def fit_per_skill(df: pd.DataFrame, seed: int = SEED, pool=None) -> dict[str, dict]:
    jobs = [(g, seed, None) for _, g in df.groupby("skill", sort=True)]
    names = sorted(df.skill.unique())
    res = pool.map(_skill_fit, jobs) if pool else list(map(_skill_fit, jobs))
    return dict(zip(names, res))


def class_seqs(df: pd.DataFrame, cls: pd.Series) -> dict:
    """Pooled layout: one sequence per (user, skill); g/s class per answer from `cls`."""
    key = df.user.astype(str) + "\x1f" + df.skill.astype(str)
    return make_seqs(key.to_numpy(), df.correct.to_numpy(), cls.map(CLASSES.index).to_numpy())


def fit_classes(df: pd.DataFrame, cls: pd.Series, seed: int = SEED, init=None) -> dict:
    """Shared prior/learn across skills, guess/slip per difficulty class (multigs by class)."""
    f = fast_em(class_seqs(df, cls), len(CLASSES), seed=seed, init=init)
    f["guess"] = dict(zip(CLASSES, f["guess"]))
    f["slip"] = dict(zip(CLASSES, f["slip"]))
    f["flags"] = {
        k: check_params(f["prior"], f["learn"], f["guess"][k], f["slip"][k]) for k in CLASSES
    }
    f["answers_per_class"] = {k: int((cls == k).sum()) for k in CLASSES}
    return f


def _as_init(f: dict) -> dict:
    g, s = f["guess"], f["slip"]
    if isinstance(g, dict):
        g, s = [g[k] for k in CLASSES], [s[k] for k in CLASSES]
    return {
        "prior": f["prior"],
        "learn": f["learn"],
        "guess": np.atleast_1d(g),
        "slip": np.atleast_1d(s),
    }


def summarise(values) -> dict:
    v = np.asarray(values, float)
    q = np.percentile(v, [0, 25, 50, 75, 100]) if len(v) else [math.nan] * 5
    return {"n": len(v), "min": q[0], "q25": q[1], "median": q[2], "q75": q[3], "max": q[4]}


def skill_summary(per_skill: dict) -> dict:
    deg = [s for s, f in per_skill.items() if is_degenerate(f["flags"])]
    ok = [f for s, f in per_skill.items() if s not in deg]
    flag_counts: dict[str, int] = {}
    for f in per_skill.values():
        for fl in f["flags"]:
            flag_counts[fl] = flag_counts.get(fl, 0) + 1
    gs = [s for s, f in per_skill.items() if "guess+slip>=1" in f["flags"]]
    return {
        "n_skills": len(per_skill),
        "n_guess_plus_slip_ge_1": len(gs),
        "pct_guess_plus_slip_ge_1": round(100 * len(gs) / max(1, len(per_skill)), 1),
        "n_degenerate": len(deg),
        "pct_degenerate": round(100 * len(deg) / max(1, len(per_skill)), 1),
        "degenerate_skills": deg,
        "flag_counts": flag_counts,
        "all": {p: summarise([f[p] for f in per_skill.values()]) for p in PARAMS},
        "non_degenerate": {p: summarise([f[p] for f in ok]) for p in PARAMS},
    }


# ---------------------------------------------------------------- bootstrap


def _boot_skill(args):
    sdf, point, B, seed = args
    rng = np.random.RandomState(seed)
    u = sdf.user.to_numpy()
    first = np.flatnonzero(np.r_[True, u[1:] != u[:-1]])  # rows are grouped by user
    lens = np.diff(np.r_[first, len(sdf)])
    draws = []
    for b in range(B):
        pick = rng.randint(0, len(first), len(first))
        L = lens[pick]
        rows = np.repeat(first[pick], L) + np.arange(L.sum()) - np.repeat(np.cumsum(L) - L, L)
        S = make_seqs(
            np.repeat(np.arange(len(pick)), L), sdf.correct.to_numpy()[rows], np.zeros(L.sum(), int)
        )
        f = fast_em(S, 1, seed=seed + b + 1, init=_as_init(point))
        draws.append([f["prior"], f["learn"], f["guess"][0], f["slip"][0]])
    return np.array(draws)


def _boot_class(args):
    df, cls, point, b, seed = args
    rng = np.random.RandomState(seed + b)
    users = df.user.unique()
    pick = pd.Series(rng.randint(0, len(users), len(users))).value_counts()
    parts = []
    for rep in range(1, int(pick.max()) + 1):  # users drawn k times appear as k distinct copies
        chosen = users[pick.index[pick >= rep]]
        part = df[df.user.isin(chosen)].assign(user=lambda x, r=rep: x.user.astype(str) + f"#{r}")
        parts.append(part)
    bdf = pd.concat(parts)
    f = fit_classes(bdf, cls.loc[bdf.index], seed=seed + b + 1, init=_as_init(point))
    return [
        f["prior"],
        f["learn"],
        *[f["guess"][k] for k in CLASSES],
        *[f["slip"][k] for k in CLASSES],
    ]


def ci(draws: np.ndarray, names: list[str]) -> dict:
    lo, med, hi = np.nanpercentile(draws, [2.5, 50, 97.5], axis=0)
    return {n: {"ci95": [lo[i], hi[i]], "boot_median": med[i]} for i, n in enumerate(names)}


# ---------------------------------------------------------------- held-out comparison


def metrics(y: np.ndarray, p: np.ndarray, bins: int = 10) -> dict:
    from sklearn.metrics import roc_auc_score

    pc = np.clip(p, 1e-6, 1 - 1e-6)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    rel = []
    for b in range(bins):
        m = idx == b
        rel.append(
            {
                "bin": [b / bins, (b + 1) / bins],
                "n": int(m.sum()),
                "mean_pred": float(p[m].mean()) if m.any() else None,
                "obs_rate": float(y[m].mean()) if m.any() else None,
            }
        )
    ece = sum(r["n"] * abs(r["mean_pred"] - r["obs_rate"]) for r in rel if r["n"]) / len(y)
    return {
        "n": len(y),
        "rmse": float(np.sqrt(np.mean((p - y) ** 2))),
        "brier": float(np.mean((p - y) ** 2)),
        "logloss": float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc))),
        "auc": float(roc_auc_score(y, p)),
        "ece": float(ece),
        "reliability": rel,
    }


HEURISTIC_PRIOR, HEURISTIC_LEARN = C.P0, C.T_EXERCISE


def heuristic_fit_cont(d: pd.Series) -> dict:
    """Engine g(d)/s(d) evaluated per answer: encode each distinct d as its own g/s class."""
    dd = d.fillna(0.5).clip(C.D_MIN, C.D_MAX)  # unrated items -> medium representative d = 0.5
    codes, uniq = pd.factorize(dd)
    return {
        "codes": codes,
        "fit": {
            "prior": HEURISTIC_PRIOR,
            "learn": HEURISTIC_LEARN,
            "guess": C.GUESS_COEF * (1 - uniq.to_numpy()),
            "slip": C.SLIP_BASE + C.SLIP_COEF * uniq.to_numpy(),
        },
    }


def heuristic_fit_class() -> dict:
    """Engine D6 class params (DEFAULT_CLASS_PARAMS); unrated items use the medium class."""
    get = lambda k, p: DEFAULT_CLASS_PARAMS["medium" if k == "unrated" else k][p]  # noqa: E731
    return {
        "prior": HEURISTIC_PRIOR,
        "learn": HEURISTIC_LEARN,
        "guess": [get(k, "guess") for k in CLASSES],
        "slip": [get(k, "slip") for k in CLASSES],
    }


def _fold_job(args):
    df, test_users, d_train, seed = args
    train, test = df[~df.user.isin(test_users)], df[df.user.isin(test_users)].reset_index(drop=True)
    d_tr, d_te = train.item.map(d_train), test.item.map(d_train)
    cls_tr, cls_te = classify(d_tr), classify(d_te)
    preds = {}
    # fitted standard BKT per skill (skill params from training students only)
    per_skill = fit_per_skill(train, seed)
    p = np.full(len(test), np.nan)
    for s, g in test.groupby("skill"):
        Sk = make_seqs(g.user.to_numpy(), g.correct.to_numpy(), np.zeros(len(g), int))
        p[g.index] = predict(Sk, per_skill[s], len(g))
    preds["fitted_per_skill"] = p
    fc = fit_classes(train, cls_tr, seed)
    S = class_seqs(test, cls_te)
    preds["fitted_class_profile"] = predict(S, _as_init(fc), len(test))
    preds["heuristic_class_D6"] = predict(S, heuristic_fit_class(), len(test))
    h = heuristic_fit_cont(d_te)
    key = test.user.astype(str) + "\x1f" + test.skill.astype(str)
    Sh = make_seqs(key.to_numpy(), test.correct.to_numpy(), h["codes"])
    preds["heuristic_continuous"] = predict(Sh, h["fit"], len(test))
    return test.correct.to_numpy(), preds


def heldout(df, difficulty_fn, folds=5, seed=SEED, pool=None) -> dict:
    users = np.random.RandomState(seed).permutation(df.user.unique())
    splits = np.array_split(users, folds)
    jobs = []
    for k in range(folds):
        train_users = np.concatenate([s for j, s in enumerate(splits) if j != k])
        jobs.append((df, splits[k], difficulty_fn(train_users), seed + k))
    outs = pool.map(_fold_job, jobs) if pool else list(map(_fold_job, jobs))
    y = np.concatenate([o[0] for o in outs])
    res = {"folds": folds, "fold_unit": "student", "per_fold": {}, "pooled_oof": {}}
    for m in outs[0][1]:
        p = np.concatenate([o[1][m] for o in outs])
        res["pooled_oof"][m] = metrics(y, p)
        res["per_fold"][m] = [
            {k: v for k, v in metrics(o[0], o[1][m]).items() if k != "reliability"} for o in outs
        ]
    return res


# ---------------------------------------------------------------- pyBKT reference (T7.2)


def pybkt_pipeline(data, seed=SEED, num_fits=5, folds=5, skills=".*", parallel=False) -> dict:
    """pyBKT fit -> crossvalidate -> params, with constraint flags. `data`: path or DataFrame."""
    from pyBKT.models import Model

    kw = {"data_path": data} if isinstance(data, str) else {"data": data}
    t0 = time.time()
    m = Model(seed=seed, num_fits=num_fits, parallel=parallel)
    m.fit(skills=skills, **kw)
    p = m.params().xs("default", level="class")["value"].unstack("param")
    t_fit = time.time() - t0
    cv = Model(seed=seed, num_fits=num_fits, parallel=parallel).crossvalidate(
        folds=folds, metric=["rmse", "auc"], skills=skills, **kw
    )
    out = {}
    for skill, r in p.iterrows():
        g, s, pr, ln = r["guesses"], r["slips"], r["prior"], r["learns"]
        out[skill] = {
            "prior": pr,
            "learn": ln,
            "guess": g,
            "slip": s,
            "cv_rmse": float(cv.loc[skill, "rmse"]),
            "cv_auc": float(cv.loc[skill, "auc"]),
            "flags": check_params(pr, ln, g, s),
        }
    return {
        "per_skill": out,
        "fit_seconds": round(t_fit, 1),
        "total_seconds": round(time.time() - t0, 1),
        "settings": {"seed": seed, "num_fits": num_fits, "folds": folds, "parallel": parallel},
    }


# ---------------------------------------------------------------- profile writer


def write_profile(path: str, class_fit: dict, meta: dict) -> dict:
    """Named config profile (T3.5). Refuses guess + slip >= 1; other flags become warnings."""
    classes = {
        k: {"guess": class_fit["guess"][k], "slip": class_fit["slip"][k]} for k in CLASSES[:3]
    }
    warnings = {}
    for k, v in classes.items():
        flags = check_params(class_fit["prior"], class_fit["learn"], v["guess"], v["slip"])
        if "guess+slip>=1" in flags or not all(0 < x < 1 for x in v.values()):
            raise ValueError(f"refusing profile: class {k} violates guess+slip<1 {v}")
        if flags:
            warnings[k] = flags
    profile = {
        **meta,
        "p0": class_fit["prior"],
        "t_exercise": class_fit["learn"],
        "class_params": classes,
        "constraint_warnings": warnings,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(_clean(profile), f, indent=2)
    return profile


# ---------------------------------------------------------------- runners


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(o) else round(float(o), 6)
    if isinstance(o, np.integer):
        return int(o)
    return o


def _checksums(names) -> dict:
    sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
    from download_data import read_checksums, sha256

    exp, out = read_checksums(), {}
    for n in names:
        h = sha256(os.path.join(EXTERNAL, n))
        out[n] = {"sha256": h, "matches_CHECKSUMS": h == exp.get(n)}
    return out


def run_domain(name: str, boot: int, seed: int = SEED) -> dict:
    t_all = time.time()
    timings = {}
    if name == "assist09":
        df, steps = load_assist()
        files = ["as.csv", "assist09_skill_builder.csv"]
        d_full = assist_difficulty()
        diff_fn = assist_difficulty
        d_source = "assist09_skill_builder.csv (collapsed), problem_id, all rows"
    else:
        df, steps = load_ct()
        files = ["ct.csv"]
        d_full = item_difficulty(df)
        diff_fn = lambda users: item_difficulty(df[df.user.isin(users)])  # noqa: E731
        d_source = "ct.csv itself, Problem Name (pyBKT's ct multigs column)"
    cls = classify(df.item.map(d_full))
    stamp = {"code_hash": code_hash(), "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    ctx = get_context("fork")
    with ctx.Pool(WORKERS) as pool:
        t = time.time()
        per_skill = fit_per_skill(df, seed, pool)
        timings["per_skill_fit"] = time.time() - t

        t = time.time()
        class_fit = fit_classes(df, cls, seed)
        timings["class_fit"] = time.time() - t

        t = time.time()
        nstud = df.groupby("skill").user.nunique().sort_values(ascending=False, kind="mergesort")
        top = list(nstud.index[:20])
        jobs = [(df[df.skill == s], per_skill[s], boot, seed) for s in top]
        draws = pool.map(_boot_skill, jobs)
        boot_skill = {
            s: ci(dr, PARAMS) | {"point": {p: per_skill[s][p] for p in PARAMS}}
            for s, dr in zip(top, draws)
        }
        timings["bootstrap_skills"] = time.time() - t

        t = time.time()
        names = (
            ["prior", "learn"] + [f"guess_{k}" for k in CLASSES] + [f"slip_{k}" for k in CLASSES]
        )
        cdraws = np.array(
            pool.map(_boot_class, [(df, cls, class_fit, b, seed) for b in range(boot)])
        )
        class_ci = ci(cdraws, names)
        timings["bootstrap_class"] = time.time() - t

        t = time.time()
        ho = heldout(df, diff_fn, 5, seed, pool)
        timings["heldout_cv"] = time.time() - t
    timings["total"] = time.time() - t_all

    items = d_full.index.intersection(df.item.unique())
    parity = parity_vs_pybkt(df, per_skill, os.path.join(RESULTS, f"bkt_fit_{name}_pybkt.json"))
    return {
        "pybkt_parity": parity,
        "dataset": name,
        "meta": {
            **stamp,
            "seed": seed,
            "runtime_seconds": {k: round(v, 1) for k, v in timings.items()},
            "data_checksums": _checksums(files),
            "backend": "fast_em (numpy Baum-Welch, pyBKT 1.4.3 init ranges/stopping rule)",
            "em": {"num_fits": 5, "tol": 0.005, "maxiter": 100, "forgets": False},
            "constraints": {
                "degenerate_if": ["guess+slip>=1", "guess>0.5", "slip>0.5"],
                "prior_floor_flag": PRIOR_MIN,
                "selection": "best log-likelihood restart; degenerate fits flagged, not refit",
            },
            "workers": WORKERS,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "cleaning": steps,
        "difficulty": {
            "source": d_source,
            "d_definition": "1 - mean correctness per item",
            "min_answers_per_item": MIN_ITEM_ANSWERS,
            "class_rule": "engine get_difficulty_class on d clipped to [D_MIN, D_MAX]: "
            "easy d<0.35, medium d<0.65, hard otherwise",
            "items_rated_in_clean_data": int(len(items)),
            "items_in_clean_data": int(df.item.nunique()),
            "answers_per_class": {k: int((cls == k).sum()) for k in CLASSES},
            "items_per_class": classify(d_full.loc[items]).value_counts().to_dict(),
        },
        "per_skill": per_skill,
        "per_skill_summary": skill_summary(per_skill),
        "class_fit": class_fit | {"bootstrap": class_ci, "n_resamples": boot},
        "bootstrap_skills": {
            "n_resamples": boot,
            "unit": "student",
            "skills": "20 largest by number of students" if len(top) == 20 else f"all {len(top)}",
            "init": "restart 0 = full-data estimate, restarts 1-4 random",
            "per_skill": boot_skill,
        },
        "heldout": ho
        | {
            "heuristic": {
                "prior_p0": HEURISTIC_PRIOR,
                "learn_T_exercise": HEURISTIC_LEARN,
                "continuous": "g=GUESS_COEF*(1-d), s=SLIP_BASE+SLIP_COEF*d, d clipped; unrated d=0.5",
                "class_D6": {k: dict(v) for k, v in DEFAULT_CLASS_PARAMS.items()},
                "unrated": "medium",
            },
            "difficulty_note": "d recomputed per fold from training students only",
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BKT fitting on real data (WP7)")
    ap.add_argument("cmd", choices=["pybkt", "assist09", "ct"])
    ap.add_argument("--data", default=os.path.join(EXTERNAL, "ct.csv"))
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if args.cmd == "pybkt":
        res = pybkt_pipeline(args.data, seed=args.seed)
        res["meta"] = {
            "code_hash": code_hash(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        res["summary"] = skill_summary(res["per_skill"])
        out = args.out or os.path.join(RESULTS, "bkt_fit_ct_pybkt.json")
    else:
        res = run_domain(args.cmd, args.boot, args.seed)
        out = args.out or os.path.join(RESULTS, f"bkt_fit_{args.cmd}.json")
        if args.cmd == "assist09":
            meta = {
                "profile": "fitted_assist09",
                "source": "ASSISTments 2009-10 skill-builder (as.csv, original==1), "
                "multigs by D6 difficulty class, shared prior/learn across 81 skills",
                "source_results": "experiments/results/bkt_fit_assist09.json",
                "code_hash": res["meta"]["code_hash"],
                "timestamp_utc": res["meta"]["timestamp_utc"],
                "caveat": "Fitted on middle-school MATHS data, not Python programming. Use for "
                "realistic ranges/shapes and as a calibration benchmark only; the D6 heuristic "
                "stays the engine default until held-out results on own learners favour this.",
                "ci95": res["class_fit"]["bootstrap"],
            }
            meta["source"] = meta["source"].replace("81", str(res["cleaning"]["skills_final"]))
            write_profile(
                os.path.join(REPO_ROOT, "config", "fitted_assist09.json"), res["class_fit"], meta
            )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(_clean(res), f, indent=2)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
