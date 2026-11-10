"""Statistical metrics and bootstrap confidence interval utilities (W6 Step 6).

Implements Brier score, ROC-AUC, paired bootstrap confidence intervals, and trace coverage audits.
Standard library only; never imported from src/.
"""

from __future__ import annotations

import random
from typing import Optional, Sequence, Tuple

from adaptengine.core.schema import Plan


def brier_score(pairs: Sequence[Tuple[float, bool]]) -> Optional[float]:
    """Compute Brier calibration score (mean squared error between predicted prob and binary outcome)."""
    if not pairs:
        return None
    return round(sum((p - float(y)) ** 2 for p, y in pairs) / len(pairs), 4)


def roc_auc(pairs: Sequence[Tuple[float, bool]]) -> Optional[float]:
    """Compute Area Under the Receiver Operating Characteristic curve (ROC-AUC).

    Returns None if either class (positive or negative) is absent.
    """
    n_pos = sum(1 for _, y in pairs if y)
    n_neg = len(pairs) - n_pos
    if not n_pos or not n_neg:
        return None
    # Mann-Whitney U via midranks (ties count 1/2): same value as the pairwise count, O(n log n)
    ordered = sorted(pairs, key=lambda t: t[0])
    rank_sum, i = 0.0, 0
    while i < len(ordered):
        j = i
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        mid = (i + 1 + j) / 2.0
        rank_sum += mid * sum(1 for _, y in ordered[i:j] if y)
        i = j
    wins = rank_sum - n_pos * (n_pos + 1) / 2.0
    return round(wins / (n_pos * n_neg), 4)


def paired_bootstrap_ci(
    diffs: Sequence[float],
    n_boot: int = 2000,
    seed: int = 20260,
    alpha: float = 0.05,
) -> Tuple[float, float]:
    """Compute (1 - alpha) two-sided bootstrap confidence interval for mean paired differences."""
    if not diffs:
        return 0.0, 0.0
    m = len(diffs)
    if m == 1:
        return round(diffs[0], 4), round(diffs[0], 4)

    r = random.Random(seed)
    means = sorted(sum(diffs[r.randrange(m)] for _ in range(m)) / m for _ in range(n_boot))
    low_idx = int(alpha / 2.0 * n_boot)
    high_idx = int((1.0 - alpha / 2.0) * n_boot) - 1
    return round(means[low_idx], 4), round(means[high_idx], 4)


def audit_plan_trace_coverage(plan: Plan) -> float:
    """Audit explanation coverage across all scheduled activities and trace entries in a plan.

    Requires:
    - SELECTED entries carry decision, reason, day, and (unless ORACLE_ASSIGNED) score_components.
    - DEFERRED entries carry reason.
    - OMITTED entries carry reason, p, responses.

    Returns coverage fraction in [0.0, 1.0]. Adaptive plans must reach 1.0.
    """
    if not (plan.days or plan.best_effort_days):
        return 1.0
    total_activities = sum(len(d.activities) for d in plan.days or plan.best_effort_days)
    if total_activities == 0:
        return 1.0

    # Validate DEFERRED and OMITTED trace integrity
    for tr in plan.trace:
        dec = tr.get("decision")
        if dec == "DEFERRED":
            if "reason" not in tr:
                return 0.0
        elif dec == "OMITTED":
            if "reason" not in tr or "p" not in tr or "responses" not in tr:
                return 0.0

    return round(selected_coverage(plan), 4)


def selected_coverage(plan: Plan) -> float:
    """Fraction of planned (day, activity) occurrences explained by exactly one SELECTED record
    (W7 T1.4). SELECTED records that match no planned occurrence, or duplicate one, count against
    coverage, so a trace holding a superseded greedy schedule cannot score 1.0.
    """
    import collections

    days = plan.days or plan.best_effort_days  # D42: an INFEASIBLE plan explains its best effort
    planned = collections.Counter((d.day, aid) for d in days for aid in d.activities)
    total = sum(planned.values())
    if total == 0:
        return 1.0
    selected: collections.Counter = collections.Counter()
    for tr in plan.trace:
        if tr.get("decision") == "SELECTED":
            aid, reason, day = tr.get("activity_id"), tr.get("reason"), tr.get("day")
            if aid and reason and day is not None:
                if reason == "ORACLE_ASSIGNED" or tr.get("score_components") is not None:
                    selected[(day, aid)] += 1
    covered = sum(min(n, selected[k]) for k, n in planned.items())
    extra = sum(max(0, n - planned[k]) for k, n in selected.items())
    return covered / (total + extra)


def log_loss(pairs: Sequence[Tuple[float, bool]], eps: float = 1e-6) -> Optional[float]:
    """Mean negative log-likelihood of binary outcomes (p clipped to [eps, 1 - eps])."""
    import math

    if not pairs:
        return None
    tot = 0.0
    for p, y in pairs:
        q = min(1.0 - eps, max(eps, p))
        tot -= math.log(q if y else 1.0 - q)
    return round(tot / len(pairs), 4)


def reliability_bins(pairs: Sequence[Tuple[float, bool]], n_bins: int = 10) -> list[dict]:
    """Equal-width reliability diagram data: per bin count, mean prediction, observed frequency."""
    bins: list[list[Tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for p, y in pairs:
        bins[min(n_bins - 1, int(p * n_bins))].append((p, y))
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


def brier_decomposition(pairs: Sequence[Tuple[float, bool]], n_bins: int = 10) -> dict:
    """Murphy decomposition over equal-width bins: Brier ~ reliability - resolution + uncertainty
    (exact up to within-bin variance of the predictions)."""
    if not pairs:
        return {}
    n = len(pairs)
    base = sum(1.0 for _, y in pairs if y) / n
    rel = res = 0.0
    for b in reliability_bins(pairs, n_bins):
        if b["n"]:
            rel += b["n"] * (b["mean_p"] - b["freq"]) ** 2
            res += b["n"] * (b["freq"] - base) ** 2
    return {
        "reliability": round(rel / n, 4),
        "resolution": round(res / n, 4),
        "uncertainty": round(base * (1.0 - base), 4),
        "base_rate": round(base, 4),
    }


def paired_summary(a: Sequence[float], b: Sequence[float]) -> dict:
    """Mean of per-unit differences a - b with a paired bootstrap 95% CI."""
    d = [x - y for x, y in zip(a, b)]
    return {"diff": round(sum(d) / len(d), 4) if d else 0.0, "ci95": list(paired_bootstrap_ci(d))}


def kaplan_meier(times: Sequence[float], events: Sequence[bool]) -> list[Tuple[float, float]]:
    """Kaplan-Meier survival curve [(t, S(t)), ...] at each distinct event time (W8 A.3).

    times[i] is the event time (events[i] True) or the censoring time (False). At tied times
    events are counted before censorings (the usual convention).
    """
    n_at_risk = len(times)
    s = 1.0
    curve: list[Tuple[float, float]] = [(0.0, 1.0)]
    for t in sorted(set(times)):
        d = sum(1 for x, e in zip(times, events) if x == t and e)
        if d:
            s *= 1.0 - d / n_at_risk
            curve.append((float(t), s))
        n_at_risk -= sum(1 for x in times if x == t)
    return curve


def km_median(times: Sequence[float], events: Sequence[bool]) -> Optional[float]:
    """Smallest time with S(t) <= 0.5; None if the curve never reaches 0.5 (censored median)."""
    return next((t for t, s in kaplan_meier(times, events) if s <= 0.5), None)


def km_rmst(times: Sequence[float], events: Sequence[bool], tau: float) -> float:
    """Restricted mean time to event up to tau: the area under the KM curve on [0, tau]."""
    area, prev_t, prev_s = 0.0, 0.0, 1.0
    for t, s in kaplan_meier(times, events)[1:]:
        if t >= tau:
            break
        area += (t - prev_t) * prev_s
        prev_t, prev_s = t, s
    return round(area + (tau - prev_t) * prev_s, 4)
