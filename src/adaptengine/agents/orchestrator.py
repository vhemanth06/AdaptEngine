"""A3 Orchestrator (W8 N.1, D58): the agent picks the next strategy from the engine's closed
option set (planner.options); anything outside the set, a malformed answer or a provider error
falls back to the deterministic default (tier order). Non-learning.

`orchestrated_next(engine, state, log, ctx, provider)` is a drop-in for Engine.next_activities:
it returns today's slice for the chosen option, re-checked by the engine (prerequisites evidence-
mastered in the real state, within today's remaining budget); an invalid slice falls back to
"continue".
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Optional

from ..core.schema import ActivityType, PlanContext, PlanDay
from ..learner.state import is_evidence_mastered
from ..planner.options import build_options, default_option
from ..replanner import compute_effective_context

PROMPT = """You steer an adaptive study session. Today is day {day}; goal {goal}; {left} minutes left today.
Choose exactly one of these engine-generated options:
{options}
Reply with JSON only: {{"option": "<id>", "rationale": "<= 2 sentences"}}"""


def choose_option(provider, options: list[dict], ctx_info: dict) -> tuple[str, dict]:
    ids = [o["id"] for o in options]
    default = default_option(options)
    info = {"options": ids, "default": default}
    if provider is None:
        return default, {**info, "source": "deterministic"}
    prompt = PROMPT.format(
        options="\n".join(f"- {o['id']}: {o['why']}" for o in options), **ctx_info
    )
    try:
        obj = json.loads(
            provider.complete(prompt, task="orchestrate", payload={"options": options})
        )
        choice = obj.get("option") if isinstance(obj, dict) else None
        if choice not in ids:
            raise ValueError(f"option {choice!r} is outside the engine's option set")
        return choice, {**info, "source": "agent", "rationale": str(obj.get("rationale", ""))[:300]}
    except Exception as e:  # noqa: BLE001 - D58: fall back to the deterministic tier order
        return default, {
            **info,
            "source": "fallback",
            "error": f"{type(e).__name__}: {str(e)[:160]}",
        }


def _safe(engine, state, aid: str) -> bool:
    c = engine.activities[aid].target_concept
    return all(
        is_evidence_mastered(state.concepts[q], engine.config)
        for q in engine.graph.prerequisites(c)
    )


def _probe_item(engine, concept: str, done: set) -> Optional[str]:
    exs = [
        a
        for a in engine.activities.values()
        if a.target_concept == concept and a.type == ActivityType.EXERCISE
    ]
    if not exs:
        return None
    return min(exs, key=lambda a: (a.activity_id in done, -a.difficulty, a.activity_id)).activity_id


def orchestrated_next(
    engine, state, log, ctx: PlanContext, provider, review_urgency=None, record=None
):
    eff, start, _ = compute_effective_context(ctx, log)
    if eff is None:
        return engine.next_activities(state, log, ctx, review_urgency=review_urgency)
    options = build_options(engine.graph, state, ctx.goal, start, engine.config)
    left = eff.budget - eff.minutes_used_today
    choice, info = choose_option(provider, options, {"day": start, "goal": ctx.goal, "left": left})
    kind, _, concept = choice.partition(":")
    today, plan = engine.next_activities(state, log, ctx, review_urgency=review_urgency)
    acts: list[str] = []
    if kind == "remediate":
        sub, plan = engine.next_activities(
            state, log, replace(ctx, goal=concept), review_urgency=review_urgency
        )
        acts = list(sub.activities) if sub else []
    elif kind in ("review", "rediagnose"):
        item = _probe_item(engine, concept, set(log.completed_ids()))
        acts = ([item] if item else []) + list(today.activities if today else ())
    elif kind == "consolidate":
        from ..planner import plan as run_plan

        cfg = replace(engine.config, consolidation=True)
        plan = run_plan(
            engine.graph, engine.activities, state, eff,
            done_ids=log.completed_ids(), model=engine.model, cfg=cfg,
        )  # fmt: skip
        first = next((d for d in plan.days if d.day == start), None)
        acts = list(first.activities) if first else []
    else:
        acts = list(today.activities if today else ())
    # Engine re-check: prerequisite-safe in the real state and within today's budget
    used, kept = 0, []
    for aid in acts:
        if not _safe(engine, state, aid) or used + engine.activities[aid].duration > left:
            break
        kept.append(aid)
        used += engine.activities[aid].duration
    if acts and not kept:
        info = {**info, "rejected": choice}
        choice, kept = "continue", list(today.activities if today else ())
    if record is not None:
        record.append({"day": start, "choice": choice, **info})
    if not kept:
        return None, plan
    day = PlanDay(
        day=start, activities=tuple(kept), duration=sum(engine.activities[a].duration for a in kept)
    )
    return day, plan
