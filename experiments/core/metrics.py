"""Scoring rules and paired bootstrap confidence intervals (standard library only).

Pairs are (predicted probability, outcome). Values are rounded to 4 decimals, as before.
"""

from __future__ import annotations

import math
import random
from typing import Optional, Sequence, Tuple

Pairs = Sequence[Tuple[float, bool]]
BOOT_N, BOOT_SEED = 2000, 20260


def mean(xs) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def brier(pairs: Pairs) -> Optional[float]:
    return round(sum((p - float(y)) ** 2 for p, y in pairs) / len(pairs), 4) if pairs else None


def log_loss(pairs: Pairs, eps: float = 1e-6) -> Optional[float]:
    if not pairs:
        return None
    tot = 0.0
    for p, y in pairs:
        q = min(1.0 - eps, max(eps, p))
        tot -= math.log(q if y else 1.0 - q)
    return round(tot / len(pairs), 4)


def auc(pairs: Pairs) -> Optional[float]:
    """ROC-AUC by midranks (ties count 1/2); None if a class is absent."""
    n_pos = sum(1 for _, y in pairs if y)
    n_neg = len(pairs) - n_pos
    if not n_pos or not n_neg:
        return None
    ordered = sorted(pairs, key=lambda t: t[0])
    rank_sum, i = 0.0, 0
    while i < len(ordered):
        j = i
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        rank_sum += (i + 1 + j) / 2.0 * sum(1 for _, y in ordered[i:j] if y)
        i = j
    return round((rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg), 4)


def _bin(p: float, n_bins: int) -> int:
    return min(n_bins - 1, max(0, int(p * n_bins)))


def reliability_bins(pairs: Pairs, n_bins: int = 10) -> list[dict]:
    bins: list[list] = [[] for _ in range(n_bins)]
    for p, y in pairs:
        bins[_bin(p, n_bins)].append((p, y))
    return [
        {
            "lo": round(i / n_bins, 2),
            "hi": round((i + 1) / n_bins, 2),
            "n": len(b),
            "mean_p": round(sum(p for p, _ in b) / len(b), 4) if b else None,
            "freq": round(sum(1.0 for _, y in b if y) / len(b), 4) if b else None,
        }
        for i, b in enumerate(bins)
    ]


def ece(pairs: Pairs, n_bins: int = 10) -> Optional[float]:
    """Expected calibration error over equal-width bins."""
    if not pairs:
        return None
    sums = [[0.0, 0.0] for _ in range(n_bins)]
    for p, y in pairs:
        b = sums[_bin(p, n_bins)]
        b[0] += p
        b[1] += float(y)
    return round(sum(abs(sp - sy) for sp, sy in sums) / len(pairs), 4)


def score_all(pairs: Pairs) -> dict:
    return {
        "n": len(pairs),
        "brier": brier(pairs),
        "log_loss": log_loss(pairs),
        "auc": auc(pairs),
        "ece": ece(pairs),
    }


def histogram(pairs: Pairs) -> list:
    """Compact exact form of many pairs: sorted [p, n_correct, n_wrong] rows (p already rounded)."""
    h: dict = {}
    for p, y in pairs:
        row = h.setdefault(p, [0, 0])
        row[0 if y else 1] += 1
    return [[p, a, b] for p, (a, b) in sorted(h.items())]


def merge_histograms(hists) -> list:
    h: dict = {}
    for hist in hists:
        for p, a, b in hist:
            row = h.setdefault(p, [0, 0])
            row[0] += a
            row[1] += b
    return [[p, a, b] for p, (a, b) in sorted(h.items())]


def score_histogram(hist: list, n_bins: int = 10) -> dict:
    """Brier, log-loss, AUC, ECE and reliability bins of the pairs a histogram stands for."""
    n = sum(a + b for _, a, b in hist)
    if not n:
        return {
            "n": 0,
            "brier": None,
            "log_loss": None,
            "auc": None,
            "ece": None,
            "reliability": [],
        }
    eps = 1e-6
    br = sum(a * (p - 1) ** 2 + b * p**2 for p, a, b in hist) / n
    ll = -sum(
        a * math.log(min(1 - eps, max(eps, p))) + b * math.log(1 - min(1 - eps, max(eps, p)))
        for p, a, b in hist
    )
    n_pos = sum(a for _, a, _ in hist)
    n_neg = n - n_pos
    au = None
    if n_pos and n_neg:  # rows are sorted by p, so midranks follow directly
        rank_sum, start = 0.0, 0
        for _, a, b in hist:
            k = a + b
            rank_sum += a * (start + 1 + start + k) / 2.0
            start += k
        au = round((rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg), 4)
    bins = [[0, 0.0, 0.0] for _ in range(n_bins)]
    for p, a, b in hist:
        x = bins[_bin(p, n_bins)]
        x[0] += a + b
        x[1] += p * (a + b)
        x[2] += a
    rel = [
        {
            "lo": round(i / n_bins, 2),
            "hi": round((i + 1) / n_bins, 2),
            "n": c,
            "mean_p": round(sp / c, 4) if c else None,
            "freq": round(sy / c, 4) if c else None,
        }
        for i, (c, sp, sy) in enumerate(bins)
    ]
    return {
        "n": n,
        "brier": round(br, 4),
        "log_loss": round(ll / n, 4),
        "auc": au,
        "ece": round(sum(abs(sp - sy) for _, sp, sy in bins) / n, 4),
        "reliability": rel,
    }


def bootstrap_ci(diffs: Sequence[float], n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> list:
    """95% percentile bootstrap CI of the mean of paired differences (fixed seed)."""
    m = len(diffs)
    if not m:
        return [0.0, 0.0]
    if m == 1:
        return [round(diffs[0], 4)] * 2
    r = random.Random(seed)
    means = sorted(sum(diffs[r.randrange(m)] for _ in range(m)) / m for _ in range(n_boot))
    return [round(means[int(0.025 * n_boot)], 4), round(means[int(0.975 * n_boot) - 1], 4)]


def paired(a: Sequence[float], b: Sequence[float]) -> dict:
    """Mean of a - b over paired units with its 95% bootstrap CI."""
    if len(a) != len(b):
        raise ValueError("paired vectors differ in length")
    d = [x - y for x, y in zip(a, b)]
    return {"diff": round(sum(d) / len(d), 4) if d else 0.0, "ci95": bootstrap_ci(d), "n": len(d)}


def direction(c: dict) -> str:
    """'better' if the CI is above 0, 'worse' if below, else 'no_difference'."""
    lo, hi = c["ci95"]
    return "better" if lo > 0 else "worse" if hi < 0 else "no_difference"
