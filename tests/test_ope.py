"""W8 J.5: OPE estimators on synthetic logs with a known target value."""

import os
import random
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from experiments.ope import estimate  # noqa: E402
from experiments.policy_runner import learning_progress  # noqa: E402


class Target:
    """Always picks candidate 0."""

    def propensities(self, xs):
        return [1.0] + [0.0] * (len(xs) - 1)


def logs(n=4000, seed=0):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        k = 3
        feats = [[1.0, float(i == 0)] for i in range(k)]
        a = r.randrange(k)
        mean = 0.8 if a == 0 else 0.2  # reward of candidate 0 is 0.8: target value 0.8
        out.append({"features": feats, "chosen_index": a, "propensity": 1 / k,
                    "reward": mean + r.uniform(-0.1, 0.1)})  # fmt: skip
    return out


def test_ips_snips_dr_recover_known_value():
    est = estimate(logs(), Target())
    for k in ("ips", "snips", "dr"):
        assert abs(est[k] - 0.8) < 0.05, (k, est[k])
    assert estimate([], Target())["ips"] is None


def test_learning_progress_reward():
    assert learning_progress([], 1) == 0.0
    assert learning_progress([0, 0, 0], 1) == 0.25  # 1/4 - 0/3
    assert learning_progress([1, 1, 1, 1], 0) == -0.25
    assert -1.0 <= learning_progress([0], 1) <= 1.0
