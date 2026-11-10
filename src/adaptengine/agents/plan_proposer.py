"""A1 Plan Proposer (W8 M.1, D57): an agent proposes a whole day-by-day plan; the engine validates
it (planner.validate_proposal) and returns the deterministic plan with a PROPOSAL_REJECTED record
listing the violated rules if it fails. Non-learning: no reward, update or memory."""

from __future__ import annotations

import json
from dataclasses import replace

from ..core.schema import Plan, PlanContext, PlanDay, PlanStatus
from ..learner.state import ExecutionLog, LearnerState
from ..planner.validate_proposal import parse_days, validate_proposal
from ..replanner import compute_effective_context

PROMPT = """You plan study days for one learner. Propose a day-by-day schedule that reaches mastery
of the goal concept {goal} by day {deadline}, using at most {budget} minutes per day
(day {start} has {first_day_minutes} minutes left). A concept may only be studied after its
prerequisites are mastered. Lessons are done once; exercises may repeat.

Concepts (id: prerequisites; engine belief p; responses):
{concepts}

Activity catalogue (id, type, concept, minutes, difficulty):
{catalogue}

The engine's own plan, for reference:
{reference}

Reply with JSON only: {{"days": [{{"day": <int>, "activities": ["<id>", ...]}}, ...], "rationale": "<= 2 sentences"}}
"""


def _days_json(days) -> list[dict]:
    return [{"day": d.day, "activities": list(d.activities)} for d in days]


def propose_plan(
    engine, state: LearnerState, log: ExecutionLog, ctx: PlanContext, provider
) -> tuple[Plan, dict]:
    reference = engine.replan(state, log, ctx)
    eff, start, _ = compute_effective_context(ctx, log)
    result = {
        "accepted": False,
        "violations": [],
        "rationale": "",
        "reference_days": _days_json(reference.days),
    }
    if eff is None or reference.status != PlanStatus.FEASIBLE:
        result["violations"] = [{"rule": "NO_FEASIBLE_REFERENCE", "status": reference.status.value}]
        return reference, result
    g = engine.graph
    concepts = "\n".join(
        f"- {c}: [{', '.join(g.prerequisites(c))}] p={state.concepts[c].p:.2f} n={state.concepts[c].responses}"
        for c in g.topological_order()
    )
    catalogue = "\n".join(
        f"- {a.activity_id}, {a.type.value.lower()}, {a.target_concept}, {a.duration}, {a.difficulty}"
        for a in sorted(engine.activities.values(), key=lambda a: a.activity_id)
    )
    prompt = PROMPT.format(
        goal=eff.goal, deadline=eff.deadline_day, budget=eff.budget, start=eff.current_day,
        first_day_minutes=eff.budget - eff.minutes_used_today, concepts=concepts,
        catalogue=catalogue, reference=json.dumps(result["reference_days"]),
    )  # fmt: skip
    try:
        text = provider.complete(
            prompt, task="propose_plan", payload={"reference_days": result["reference_days"]}
        )
        obj = json.loads(text)
        if not isinstance(obj, dict):
            raise ValueError("answer is not a JSON object")
        days, bad = parse_days(obj.get("days"))
        result["rationale"] = str(obj.get("rationale", ""))[:400]
    except Exception as e:  # noqa: BLE001 - provider error, malformed JSON: fall back (D57)
        days, bad = None, [{"rule": "MALFORMED", "detail": f"{type(e).__name__}: {str(e)[:200]}"}]
    if days is not None:
        days = tuple(
            PlanDay(
                day=d.day,
                activities=d.activities,
                duration=sum(
                    engine.activities[a].duration for a in d.activities if a in engine.activities
                ),
            )
            for d in days
        )
        bad = validate_proposal(
            g, engine.activities, state, eff, days,
            done_ids=log.completed_ids(), model=engine.model, cfg=engine.config,
        )  # fmt: skip
    result["violations"] = bad
    if bad:
        rec = {"decision": "PROPOSAL_REJECTED", "reason": "AGENT_PLAN_INVALID", "violations": bad}
        return replace(reference, trace=(rec,) + reference.trace), result
    result["accepted"] = True
    trace = [
        {
            "decision": "PROPOSAL_ACCEPTED",
            "reason": "AGENT_PLAN_VALID",
            "rationale": result["rationale"],
        }
    ]
    trace += [
        {
            "decision": "SELECTED",
            "activity_id": aid,
            "target_concept": engine.activities[aid].target_concept,
            "day": d.day,
            "duration": engine.activities[aid].duration,
            "reason": "AGENT_PROPOSED",
        }
        for d in days
        for aid in d.activities
    ]
    plan = Plan(
        status=PlanStatus.FEASIBLE, days=days, reason="AGENT_PROPOSAL_ACCEPTED", trace=tuple(trace)
    )
    return plan, result
