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
    pos = [p for p, y in pairs if y]
    neg = [p for p, y in pairs if not y]
    if not pos or not neg:
        return None
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return round(wins / (len(pos) * len(neg)), 4)


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
    if not plan.days:
        return 1.0
    total_activities = sum(len(d.activities) for d in plan.days)
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

    # Validate SELECTED coverage of plan activities
    selected_valid: set[Tuple[int, str]] = set()
    for tr in plan.trace:
        if tr.get("decision") == "SELECTED":
            aid = tr.get("activity_id")
            reason = tr.get("reason")
            day = tr.get("day")
            if aid and reason and day is not None:
                if reason == "ORACLE_ASSIGNED" or tr.get("score_components") is not None:
                    selected_valid.add((day, aid))

    covered = 0
    for d in plan.days:
        for aid in d.activities:
            if (d.day, aid) in selected_valid:
                covered += 1

    return round(covered / total_activities, 4)
