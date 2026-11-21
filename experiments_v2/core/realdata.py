"""Real learner data for E3 Part A: ASSISTments 2009 skill-builder and the Cognitive Tutor sample.

Cleaning follows docs/data_manifest.md. The model is standard BKT (prior, learn, guess, slip; no
forgetting), optionally with guess/slip per D6 difficulty class. `fast_em` is a vectorised
Baum-Welch with pyBKT 1.4.3's random-init ranges (prior U(0,1), learn U(0,.4), guess U(0,.4),
slip U(0,.3)), best of 5 restarts by log-likelihood, and pyBKT's stopping rule (|dLL| <= 0.005,
at most 100 iterations). Evaluation is 5-fold cross-validation by student; item difficulty is
recomputed per fold from training students only. The configs in config/ are never rewritten.
"""

from __future__ import annotations

import os
from multiprocessing import get_context

import numpy as np
import pandas as pd

from adaptengine.core import constants as K
from adaptengine.learner.adapter import DEFAULT_CLASS_PARAMS, get_difficulty_class

from .provenance import REPO_ROOT, file_sha256

EXTERNAL = os.path.join(REPO_ROOT, "data", "external")
SEED = 42
MIN_STUDENTS = 100
MIN_ITEM_ANSWERS = 20
CLASSES = ["easy", "medium", "hard", "unrated"]  # unrated: fewer than MIN_ITEM_ANSWERS answers
DATASETS = {"assist09": ["as.csv", "assist09_skill_builder.csv"], "ct": ["ct.csv"]}


# ---------------------------------------------------------------- files and cleaning


def checksums(names) -> dict:
    """{file: {'present', 'sha256', 'matches_CHECKSUMS'}} against data/external/CHECKSUMS."""
    want = {}
    ck = os.path.join(EXTERNAL, "CHECKSUMS")
    if os.path.exists(ck):
        with open(ck, encoding="utf-8") as f:
            for ln in f:
                if ln.strip():
                    h, n = ln.split()
                    want[n] = h
    out = {}
    for n in names:
        p = os.path.join(EXTERNAL, n)
        if not os.path.exists(p):
            out[n] = {"present": False}
            continue
        h = file_sha256(p)
        out[n] = {"present": True, "sha256": h, "matches_CHECKSUMS": want.get(n) == h}
    return out


def data_ok(name: str) -> bool:
    return all(v.get("matches_CHECKSUMS") for v in checksums(DATASETS[name]).values())


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


def load_assist(path: str = os.path.join(EXTERNAL, "as.csv")) -> tuple[pd.DataFrame, dict]:
    """as.csv: original == 1, skill present, one row per (order_id, skill), skills >= 100 students."""
    cols = ["order_id", "user_id", "problem_id", "original", "correct", "skill_name"]
    a = pd.read_csv(path, encoding="ISO-8859-15", usecols=cols, low_memory=False)
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
    return _keep_skills(df, {"raw_rows": len(raw), "rows_with_skill": len(df)})


def item_difficulty(df: pd.DataFrame) -> pd.Series:
    """d = 1 - mean correctness per item, items with at least MIN_ITEM_ANSWERS answers."""
    agg = df.groupby("item").correct.agg(["mean", "size"])
    return 1.0 - agg.loc[agg["size"] >= MIN_ITEM_ANSWERS, "mean"]


def assist_difficulty(users=None, path=os.path.join(EXTERNAL, "assist09_skill_builder.csv")):
    """ASSISTments difficulty from the collapsed file (one row per student-problem)."""
    c = pd.read_csv(
        path, encoding="ISO-8859-15", index_col=0, usecols=[0, 3, 5, 7], low_memory=False
    )
    if users is not None:
        c = c[c.user_id.isin(users)]
    return item_difficulty(c.rename(columns={"problem_id": "item"}))


def classify(d: pd.Series) -> pd.Series:
    """Engine D6 classes on d clipped to [D_MIN, D_MAX]; missing d -> unrated."""
    dc = d.clip(K.D_MIN, K.D_MAX)
    lut = {v: get_difficulty_class(float(v)) for v in dc.dropna().unique()}
    return dc.map(lut).fillna("unrated")


def load(name: str):
    """(clean frame, cleaning steps, difficulty function of training users)."""
    if name == "assist09":
        df, steps = load_assist()
        return df, steps, assist_difficulty
    df, steps = load_ct()
    return df, steps, lambda users: item_difficulty(df[df.user.isin(users)])


# ---------------------------------------------------------------- BKT by EM


def make_seqs(seq: np.ndarray, correct: np.ndarray, cls: np.ndarray) -> dict:
    """Ragged time-major layout (rows chronological within each sequence), longest first."""
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


def _forward(S, prior, learn, guess, slip):
    """Filter R parameter sets at once (prior/learn (R,), guess/slip (R, K))."""
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


def _em_step(S, prior, learn, guess, slip, n_cls: int):
    fw = _forward(S, prior, learn, guess, slip)
    R = len(prior)
    ll = np.zeros(R)
    gn, gd, sn, sd = (np.zeros((R, n_cls)) for _ in range(4))
    x01, x0 = np.zeros(R), np.zeros(R)
    b0 = b1 = np.ones((R, 0))
    L = learn[:, None]
    for t in range(len(fw) - 1, -1, -1):
        _, a, c, e0, e1 = fw[t]
        n = a.shape[1]
        pad = np.ones((R, n - b0.shape[1]))
        b0, b1 = np.hstack([b0, pad]), np.hstack([b1, pad])
        gam1, gam0 = a * b1, (1 - a) * b0
        o, onehot = S["obs"][t], np.eye(n_cls)[S["cls"][t]]
        gn += (gam0 * o) @ onehot
        gd += gam0 @ onehot
        sn += (gam1 * (1 - o)) @ onehot
        sd += gam1 @ onehot
        ll += np.log(c).sum(axis=1)
        if t > 0:
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


def fast_em(S, n_cls=1, num_fits=5, seed=SEED, tol=0.005, maxiter=100) -> dict:
    rng = np.random.RandomState(seed)
    prior, learn = rng.random_sample(num_fits), rng.random_sample(num_fits) * 0.4
    guess = rng.random_sample((num_fits, n_cls)) * 0.4
    slip = rng.random_sample((num_fits, n_cls)) * 0.3
    done, iters, final_ll, prev = np.zeros(num_fits, bool), np.zeros(num_fits, int), None, None
    for i in range(maxiter):
        ll, new = _em_step(S, prior, learn, guess, slip, n_cls)
        final_ll = ll if final_ll is None else np.where(done, final_ll, ll)
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


def predict(S, fit: dict, n_rows: int) -> np.ndarray:
    """One-step-ahead P(correct) per source row."""
    arr = lambda v: np.atleast_2d(np.asarray(v, float))  # noqa: E731
    fw = _forward(
        S, arr(fit["prior"])[0], arr(fit["learn"])[0], arr(fit["guess"]), arr(fit["slip"])
    )
    out = np.full(n_rows, np.nan)
    for (pc, *_), rows in zip(fw, S["rows"]):
        out[rows] = pc[0]
    return out


def skill_seqs(sdf: pd.DataFrame) -> dict:
    return make_seqs(sdf.user.to_numpy(), sdf.correct.to_numpy(), np.zeros(len(sdf), int))


def fit_per_skill(df: pd.DataFrame, seed: int = SEED) -> dict:
    out = {}
    for s, g in df.groupby("skill", sort=True):
        f = fast_em(skill_seqs(g), 1, seed=seed)
        out[s] = {**f, "guess": f["guess"][0], "slip": f["slip"][0]}
    return out


def class_seqs(df: pd.DataFrame, cls: pd.Series) -> dict:
    """One sequence per (user, skill); guess/slip class per answer."""
    key = df.user.astype(str) + "\x1f" + df.skill.astype(str)
    return make_seqs(key.to_numpy(), df.correct.to_numpy(), cls.map(CLASSES.index).to_numpy())


def fit_classes(df: pd.DataFrame, cls: pd.Series, seed: int = SEED) -> dict:
    """Shared prior/learn across skills, guess/slip per difficulty class."""
    f = fast_em(class_seqs(df, cls), len(CLASSES), seed=seed)
    f["guess"] = dict(zip(CLASSES, f["guess"]))
    f["slip"] = dict(zip(CLASSES, f["slip"]))
    return f


def heuristic_class() -> dict:
    """Engine D6 class guess/slip (unrated -> medium), prior p0, learn T_exercise."""
    get = lambda k, p: DEFAULT_CLASS_PARAMS["medium" if k == "unrated" else k][p]  # noqa: E731
    return {
        "prior": K.P0,
        "learn": K.T_EXERCISE,
        "guess": [get(k, "guess") for k in CLASSES],
        "slip": [get(k, "slip") for k in CLASSES],
    }


def _as_vec(f: dict) -> dict:
    return {
        "prior": f["prior"],
        "learn": f["learn"],
        "guess": [f["guess"][k] for k in CLASSES],
        "slip": [f["slip"][k] for k in CLASSES],
    }


# ---------------------------------------------------------------- held-out evaluation


def auc_np(y: np.ndarray, p: np.ndarray) -> float | None:
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if not n_pos or not n_neg:
        return None
    ranks = pd.Series(p).rank(method="average").to_numpy()
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def heldout_metrics(y: np.ndarray, p: np.ndarray, bins: int = 10) -> dict:
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    rel = []
    for b in range(bins):
        m = idx == b
        rel.append(
            {
                "lo": b / bins,
                "hi": (b + 1) / bins,
                "n": int(m.sum()),
                "mean_p": float(p[m].mean()) if m.any() else None,
                "freq": float(y[m].mean()) if m.any() else None,
            }
        )
    ece = sum(r["n"] * abs(r["mean_p"] - r["freq"]) for r in rel if r["n"]) / len(y)
    return {
        "n": int(len(y)),
        "rmse": float(np.sqrt(np.mean((p - y) ** 2))),
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc))),
        "auc": auc_np(y, p),
        "ece": float(ece),
        "reliability": rel,
    }


MODELS = ("heuristic_class_D6", "fitted_class_profile", "fitted_per_skill")


def _fold(args):
    df, test_users, d_train, seed = args
    train = df[~df.user.isin(test_users)]
    test = df[df.user.isin(test_users)].reset_index(drop=True)
    cls_tr, cls_te = classify(train.item.map(d_train)), classify(test.item.map(d_train))
    preds = {}
    S = class_seqs(test, cls_te)
    preds["heuristic_class_D6"] = predict(S, heuristic_class(), len(test))
    fc = fit_classes(train, cls_tr, seed)
    preds["fitted_class_profile"] = predict(S, _as_vec(fc), len(test))
    per_skill = fit_per_skill(train, seed)
    p = np.full(len(test), np.nan)
    for s, g in test.groupby("skill"):
        p[g.index] = predict(skill_seqs(g), per_skill[s], len(g))
    preds["fitted_per_skill"] = p
    return test.correct.to_numpy(), preds, {k: fc[k] for k in ("prior", "learn", "guess", "slip")}


def crossvalidate(df, difficulty_fn, folds: int = 5, seed: int = SEED, procs: int = 1) -> dict:
    """5-fold CV by student; pooled out-of-fold metrics and per-fold metrics per model."""
    users = np.random.RandomState(seed).permutation(df.user.unique())
    splits = np.array_split(users, folds)
    jobs = []
    for k in range(folds):
        train_users = np.concatenate([s for j, s in enumerate(splits) if j != k])
        jobs.append((df, splits[k], difficulty_fn(train_users), seed + k))
    if procs > 1:
        with get_context("fork").Pool(min(procs, folds)) as pool:
            outs = pool.map(_fold, jobs)
    else:
        outs = [_fold(j) for j in jobs]
    y = np.concatenate([o[0] for o in outs])
    res = {"folds": folds, "fold_unit": "student", "pooled_oof": {}, "per_fold": {}}
    for m in MODELS:
        p = np.concatenate([o[1][m] for o in outs])
        res["pooled_oof"][m] = heldout_metrics(y, p)
        res["per_fold"][m] = [
            {k: v for k, v in heldout_metrics(o[0], o[1][m]).items() if k != "reliability"}
            for o in outs
        ]
    res["fold_class_fits"] = [o[2] for o in outs]
    return res


def fold_students(df, folds: int = 5, seed: int = SEED) -> list:
    users = np.random.RandomState(seed).permutation(df.user.unique())
    return [set(s) for s in np.array_split(users, folds)]
