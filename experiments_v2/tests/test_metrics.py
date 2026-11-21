"""V2-TC3: scoring rules on hand-computed cases; deterministic paired bootstrap."""

import math

from experiments_v2.core import metrics as M


def test_scores_by_hand():
    pairs = [(0.9, True), (0.2, False), (0.6, False), (0.4, True)]
    assert M.brier(pairs) == round((0.01 + 0.04 + 0.36 + 0.36) / 4, 4)
    ll = -(math.log(0.9) + math.log(0.8) + math.log(0.4) + math.log(0.4)) / 4
    assert M.log_loss(pairs) == round(ll, 4)
    assert M.auc(pairs) == 0.75  # positives 0.9, 0.4 vs negatives 0.2, 0.6: 3 of 4 pairs
    assert M.auc([(0.5, True), (0.5, False)]) == 0.5
    assert M.auc([(0.5, True)]) is None
    # bins: 0.9 -> bin 9 (|0.9-1|), 0.2 -> 2 (0.2), 0.6 -> 6 (0.6), 0.4 -> 4 (|0.4-1|)
    assert M.ece(pairs) == round((0.1 + 0.2 + 0.6 + 0.6) / 4, 4)
    bins = M.reliability_bins(pairs)
    assert sum(b["n"] for b in bins) == 4 and bins[9]["freq"] == 1.0


def test_paired_bootstrap_deterministic():
    a = [1, 0, 1, 1, 0, 1, 1, 1]
    b = [0, 0, 1, 0, 0, 1, 0, 1]
    r1, r2 = M.paired(a, b), M.paired(a, b)
    assert r1 == r2 and r1["diff"] == 0.375
    lo, hi = r1["ci95"]
    assert lo <= 0.375 <= hi
    assert M.direction({"ci95": [0.1, 0.2]}) == "better"
    assert M.direction({"ci95": [-0.1, 0.2]}) == "no_difference"
