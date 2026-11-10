#!/usr/bin/env python3
"""W8 J.5: train the frozen bandit (FINAL_A5 §6). One BanditPolicy in "updating" mode, zero
initial weights, shared across learners and run sequentially over the even training seeds in
S1 and S4 x 4-node and 8-node (adapt_final, B = 15, calm, 14 days). Writes
config/policy_frozen.json (weights + code hash) and experiments/results/w8_policy_train.json."""

from __future__ import annotations

import json
import os
import sys
import time

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.policy import BanditPolicy  # noqa: E402
from experiments.policy_runner import run_policy_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.w8_common import TRAIN_SEEDS  # noqa: E402

COMBOS = (("S1", "4-node"), ("S4", "4-node"), ("S1", "8-node"), ("S4", "8-node"))


def main(seeds=TRAIN_SEEDS, out=os.path.join(repo_root, "config", "policy_frozen.json")):
    t0, meta = time.time(), stamp()
    pol = BanditPolicy("updating", lam=1.0, alpha=0.3, tau=0.1)
    curve = []
    for i, s in enumerate(seeds):
        for world, cur in COMBOS:
            pol.seed = s
            res, dec = run_policy_episode(cur, world, s, pol)
            curve.append({"seed": s, "world": world, "curriculum": cur, "goal": res["goal_mastered"],
                          "decisions": len(dec), "mean_reward": sum(d["reward"] for d in dec) / max(1, len(dec)),
                          "violations": res["executed_prereq_violations"]})  # fmt: skip
        if (i + 1) % 25 == 0:
            print(
                f"{i + 1}/{len(seeds)} seeds, updates {pol.n_updates}, {time.time() - t0:.0f}s",
                flush=True,
            )
    pol.save(
        out,
        meta={
            **meta,
            "trained_on": "even 6000-6398 x S1,S4 x 4-node,8-node",
            "episodes": len(curve),
        },
    )
    with open(os.path.join(repo_root, "experiments/results/w8_policy_train.json"), "w") as f:
        json.dump({"metadata": {**meta, "runtime_s": round(time.time() - t0, 1)}, "n_updates": pol.n_updates,
                   "weights": dict(zip(pol.to_dict()["feature_names"], pol.weights())), "curve": curve}, f, indent=1)  # fmt: skip
    print("saved", out, "updates", pol.n_updates, "violations", sum(c["violations"] for c in curve))


if __name__ == "__main__":
    main()
