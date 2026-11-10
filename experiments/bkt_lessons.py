"""BKT with lesson steps (W8 B.2) and optional forgets (O.3): Baum-Welch EM, vectorised over
sequences with numpy.

Hidden state L in {0, 1} per (learner, concept). Steps are lessons (no observation; transition
T_lesson) or exercises (emission with guess/slip of the item's D6 class; transition T_exercise).
After every step: P(0 -> 1) = T_kind, P(1 -> 0) = F (0 unless forgets=True).
Never imported from src/.
"""

from __future__ import annotations

import numpy as np

CLASSES = ("easy", "medium", "hard")


def d6_class(d: float) -> int:
    return 0 if d < 0.35 else 1 if d < 0.65 else 2


def to_arrays(seqs: list[list[tuple[int, int, int]]]):
    """seqs: lists of (is_lesson, class, correct) -> padded arrays (N, T)."""
    n, t = len(seqs), max(len(s) for s in seqs)
    kind = np.zeros((n, t), np.int8)  # 1 = lesson
    cls = np.zeros((n, t), np.int64)
    obs = np.zeros((n, t), np.float64)
    mask = np.zeros((n, t), bool)
    for i, s in enumerate(seqs):
        for j, (les, c, y) in enumerate(s):
            kind[i, j], cls[i, j], obs[i, j], mask[i, j] = les, c, y, True
    return kind, cls, obs, mask


def _emissions(p, kind, cls, obs, mask):
    g, s = p["guess"][cls], p["slip"][cls]
    ex = mask & (kind == 0)
    e1 = np.where(ex, np.where(obs == 1, 1 - s, s), 1.0)
    e0 = np.where(ex, np.where(obs == 1, g, 1 - g), 1.0)
    return e0, e1


def _transitions(p, kind, mask):
    """T (0->1) and F (1->0) after each step; identity after the last step / padding."""
    nxt = np.zeros_like(mask)
    nxt[:, :-1] = mask[:, 1:]
    T = np.where(nxt, np.where(kind == 1, p["t_lesson"], p["t_exercise"]), 0.0)
    F = np.where(nxt, p["forget"], 0.0)
    return T, F, nxt


def e_step(p, arrays):
    kind, cls, obs, mask = arrays
    n, t = mask.shape
    e0, e1 = _emissions(p, kind, cls, obs, mask)
    T, F, nxt = _transitions(p, kind, mask)
    a0, a1, c = np.zeros((n, t)), np.zeros((n, t)), np.ones((n, t))
    p1 = np.full(n, p["prior"])
    for j in range(t):
        f0, f1 = (1 - p1) * e0[:, j], p1 * e1[:, j]
        c[:, j] = f0 + f1
        a0[:, j], a1[:, j] = f0 / c[:, j], f1 / c[:, j]
        p1 = a0[:, j] * T[:, j] + a1[:, j] * (1 - F[:, j])
    b0, b1 = np.ones((n, t)), np.ones((n, t))
    for j in range(t - 2, -1, -1):
        w0, w1 = (
            e0[:, j + 1] * b0[:, j + 1] / c[:, j + 1],
            e1[:, j + 1] * b1[:, j + 1] / c[:, j + 1],
        )
        b0[:, j] = (1 - T[:, j]) * w0 + T[:, j] * w1
        b1[:, j] = F[:, j] * w0 + (1 - F[:, j]) * w1
    g0, g1 = a0 * b0, a1 * b1
    # xi for transitions j -> j+1 (only where nxt)
    w0 = np.zeros((n, t))
    w1 = np.zeros((n, t))
    w0[:, :-1] = e0[:, 1:] * b0[:, 1:] / c[:, 1:]
    w1[:, :-1] = e1[:, 1:] * b1[:, 1:] / c[:, 1:]
    x01, x10 = a0 * T * w1 * nxt, a1 * F * w0 * nxt
    ll = float(np.log(c[mask]).sum())
    return g0, g1, x01, x10, nxt, ll


def m_step(p, arrays, stats, forgets: bool):
    kind, cls, obs, mask = arrays
    g0, g1, x01, x10, nxt, _ = stats
    les, ex = (kind == 1) & nxt, (kind == 0) & nxt
    new = dict(p)
    new["prior"] = float(g1[:, 0].mean())
    for name, sel in (("t_lesson", les), ("t_exercise", ex)):
        den = (g0 * sel).sum()
        if den > 0:
            new[name] = float((x01 * sel).sum() / den)
    if forgets:
        den = (g1 * nxt).sum()
        new["forget"] = float(x10.sum() / den) if den > 0 else 0.0
    exm = mask & (kind == 0)
    for k in range(3):
        sel = exm & (cls == k)
        d0, d1 = (g0 * sel).sum(), (g1 * sel).sum()
        if d0 > 0:
            new["guess"][k] = (g0 * sel * obs).sum() / d0
        if d1 > 0:
            new["slip"][k] = (g1 * sel * (1 - obs)).sum() / d1
    return new


def fit(seqs, forgets=False, num_fits=5, seed=42, tol=0.005, maxiter=200) -> dict:
    """Best-of-num_fits EM (pyBKT-style random init ranges)."""
    arrays = to_arrays(seqs)
    rng = np.random.RandomState(seed)
    best = None
    for _ in range(num_fits):
        p = {
            "prior": rng.uniform(0, 1),
            "t_lesson": rng.uniform(0, 0.4),
            "t_exercise": rng.uniform(0, 0.4),
            "forget": rng.uniform(0, 0.1) if forgets else 0.0,
            "guess": rng.uniform(0, 0.4, 3),
            "slip": rng.uniform(0, 0.3, 3),
        }
        prev, it = None, 0
        for it in range(1, maxiter + 1):
            stats = e_step(p, arrays)
            ll = stats[-1]
            if prev is not None and abs(ll - prev) <= tol:
                break
            prev = ll
            p = m_step(
                {**p, "guess": p["guess"].copy(), "slip": p["slip"].copy()}, arrays, stats, forgets
            )
        ll = e_step(p, arrays)[-1]
        if best is None or ll > best["loglik"]:
            best = {
                **p,
                "guess": p["guess"].copy(),
                "slip": p["slip"].copy(),
                "loglik": ll,
                "iters": it,
            }
    out = {k: float(v) for k, v in best.items() if k not in ("guess", "slip")}
    out["iters"] = int(best["iters"])
    out["guess"] = {c: float(best["guess"][i]) for i, c in enumerate(CLASSES)}
    out["slip"] = {c: float(best["slip"][i]) for i, c in enumerate(CLASSES)}
    out["n_sequences"], out["n_steps"] = len(seqs), int(arrays[3].sum())
    return out


def flags(f: dict) -> dict:
    """Degenerate-fit checks (EDM 2024 style, as experiments/fit_bkt.check_params)."""
    out = {}
    for c in CLASSES:
        g, s = f["guess"][c], f["slip"][c]
        fl = []
        if g + s >= 1:
            fl.append("guess+slip>=1")
        if g > 0.5:
            fl.append("guess>0.5")
        if s > 0.5:
            fl.append("slip>0.5")
        if fl:
            out[c] = fl
    if f["prior"] < 0.01:
        out["prior"] = ["prior<0.01"]
    return out


def sequences_from_episodes(episodes) -> list[list[tuple[int, int, int]]]:
    """One sequence per (episode, concept) from run_episode()['activity_log']."""
    seqs = []
    for ep in episodes:
        by_c: dict = {}
        for c, _, is_lesson, d, y, _day in ep["activity_log"]:
            by_c.setdefault(c, []).append((1, 0, 0) if is_lesson else (0, d6_class(d), int(y)))
        seqs += [s for _, s in sorted(by_c.items())]
    return seqs
