"""Closed-loop episodes with a ranking policy, decision logging and learning-progress rewards
(W8 J.5/J.6; spec docs/POLICY_SPEC.md). Never imported from src/."""

from __future__ import annotations

import json
import os

from adaptengine.policy import BanditPolicy
from experiments.arms import get_scenario, run_episode
from experiments.sim import PROFILES
from experiments.w8_common import FINAL_FLAGS, engine, goal_of

WINDOW = 4  # rolling success window w
SELECT = os.path.join(os.path.dirname(__file__), "results", "w8_calibration_select.json")


def final_spec():
    sel = json.load(open(SELECT))
    c = sel["candidates"][sel["winner"]]
    return c["profile"], dict(c["overrides"])


def final_engine(cur, world, policy=None):
    kind, ov = final_spec()
    prof = "w7_default" if kind == "w7_default" else f"fitted_{world}"
    return engine(cur, prof, policy=policy, **{**ov, **FINAL_FLAGS})


def learning_progress(hist: list[int], y: int) -> float:
    """Change in the rolling success rate over the last WINDOW attempts (0 for a first attempt)."""
    if not hist:
        return 0.0
    before = hist[-WINDOW:]
    after = (hist + [y])[-WINDOW:]
    return max(-1.0, min(1.0, sum(after) / len(after) - sum(before) / len(before)))


def run_policy_episode(cur, world, seed, policy, horizon=14, budget=15):
    """One adapt_final episode with `policy` (None = deterministic). Returns (result, decisions)."""
    e = final_engine(cur, world, policy=policy)
    base = engine(cur)
    sc = get_scenario(
        "calm", base, base.init_learner(), goal=goal_of(base), budget=budget, horizon=horizon
    )
    last_plan = {"plan": None}
    decisions: list[dict] = []
    consumed: set = set()
    hist: dict[str, list[int]] = {}
    pending_lessons: dict[str, list[dict]] = {}

    def next_fn(state, log, ctx, review_urgency=None):
        today, plan = e.next_activities(state, log, ctx, review_urgency=review_urgency)
        last_plan["plan"] = plan
        return today, plan

    def on_execute(act, correct, day):
        plan = last_plan["plan"]
        dec = None
        if plan is not None:
            for i, t in enumerate(plan.trace):
                if (
                    t.get("decision") == "POLICY_SELECTED"
                    and t["day"] == day
                    and t["chosen"] == act.activity_id
                    and (id(plan), i) not in consumed
                ):
                    consumed.add((id(plan), i))
                    k = t["candidates"].index(t["chosen"])
                    dec = {
                        "seed": seed, "day": day, "candidates": t["candidates"], "chosen": t["chosen"],
                        "chosen_index": k, "propensity": t["propensity"], "propensities": t["propensities"],
                        "features": t["features"], "deterministic_choice": t["deterministic_choice"],
                        "reward": None, "policy_version": t["policy_version"],
                    }  # fmt: skip
                    decisions.append(dec)
                    break
        c = act.target_concept
        if correct is None:  # lesson: reward assigned at the next exercise on c
            if dec is not None:
                pending_lessons.setdefault(c, []).append(dec)
            return
        r = learning_progress(hist.setdefault(c, []), int(correct))
        hist[c].append(int(correct))
        for d in ([dec] if dec is not None else []) + pending_lessons.pop(c, []):
            d["reward"] = r
            if policy is not None and hasattr(policy, "update"):
                policy.update(d["features"][d["chosen_index"]], r)

    res = run_episode(
        e,
        seed,
        sc,
        "adapt",
        PROFILES["nominal"],
        world=world,
        next_fn=next_fn,
        on_execute=on_execute,
    )
    for d in decisions:
        if d["reward"] is None:
            d["reward"] = 0.0
    return res, decisions


def make_policy(variant: str, seed: int, frozen_path: str):
    if variant == "deterministic":
        return None
    if variant == "random":
        return BanditPolicy("random", seed=seed)
    mode = "frozen" if variant == "bandit_frozen" else "updating"
    return BanditPolicy.load(frozen_path, mode=mode, seed=seed)
