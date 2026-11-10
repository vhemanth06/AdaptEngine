"""Pure feature extractor for ranking policies (W8 J.2; spec in docs/POLICY_SPEC.md).

Per candidate: p, responses, time since practice (days: the planner's clock), projected
P(correct) and |P(correct) - 0.75|, unlock value, review urgency, goal-path flag, activity type,
difficulty class, deterministic rank. Learner level: day index, remaining days, remaining budget
fraction. All features are scaled to about [0, 1]; a bias term comes first.
"""

from __future__ import annotations

import math

FEATURE_NAMES = (
    "bias",
    "p",
    "responses",
    "days_since_practice",
    "p_correct",
    "fit_gap",
    "unlock",
    "review_urgency",
    "on_goal_path",
    "is_lesson",
    "diff_easy",
    "diff_medium",
    "diff_hard",
    "det_rank",
    "day_index",
    "remaining_days",
    "remaining_budget",
)
DIM = len(FEATURE_NAMES)
TARGET_SUCCESS = 0.75


def _class(d) -> str:
    if d is None:
        return ""
    return "easy" if d < 0.35 else "medium" if d < 0.65 else "hard"


def extract(c: dict, ctx: dict) -> list[float]:
    """Feature vector for candidate c in context ctx. Raises ValueError if any value is not finite."""
    dsp = c.get("days_since_practice")
    pc = c.get("p_correct")
    lesson = c.get("type") == "LESSON"
    cls = _class(None if lesson else c.get("difficulty"))
    span = max(1, ctx["deadline_day"] - ctx["start_day"] + 1)
    x = [
        1.0,
        float(c["p"]),
        min(float(c.get("responses", 0)), 10.0) / 10.0,
        1.0 if dsp is None else min(float(dsp), 14.0) / 14.0,
        0.0 if pc is None else float(pc),
        0.0 if pc is None else abs(float(pc) - TARGET_SUCCESS),
        float(c.get("unlock", 0.0)) / (1.0 + float(c.get("unlock", 0.0))),
        min(float(c.get("review_urgency", 0.0)), 5.0) / 5.0,
        1.0 if c.get("on_goal_path") else 0.0,
        1.0 if lesson else 0.0,
        1.0 if cls == "easy" else 0.0,
        1.0 if cls == "medium" else 0.0,
        1.0 if cls == "hard" else 0.0,
        min(float(c.get("det_rank", 0)), 4.0) / 4.0,
        (ctx["day"] - ctx["start_day"]) / span,
        (ctx["deadline_day"] - ctx["day"] + 1) / span,
        float(ctx["remaining_budget"]) / float(ctx["budget"]),
    ]
    if not all(math.isfinite(v) for v in x):
        raise ValueError(f"non-finite feature for {c.get('activity_id')}: {x}")
    return x
