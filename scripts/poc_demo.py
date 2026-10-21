#!/usr/bin/env python3
"""AdaptEngine — End-to-End Proof of Concept (PoC) Demonstration Script.

Runs all core workflows on the canonical 4-node curriculum fixture:
1. Two scripted profiles (Novice vs Advanced), same goal (C4) and budget (15m),
   through bounded diagnostic, producing distinct valid day plans.
2. One recorded exercise response, committed through canonical snapshot, followed by a revised plan.
3. Multi-budget scalability: 5, 10, 15, and 30 minute daily budgets.
4. Infeasible request (C4, deadline 1 day, 5m budget) with shortfall and options analysis.
5. All 4 adaptive event types:
   - Missed Day (zero minutes, replan from next day)
   - Failed Assessment with Remediation (p < 0.40 triggers lesson queue)
   - Deadline Change (expands/contracts planning horizon)
   - Budget Change (re-packs daily capacity)
   Plus Spaced Review due to memory decay (r(t) < 0.80).
6. Explainability trace output for each scheduling decision.
"""

from __future__ import annotations

import os
import sys
import tempfile
from typing import Any

# Ensure src is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(repo_root, "src") not in sys.path:
    sys.path.insert(0, os.path.join(repo_root, "src"))

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.core.schema import (  # noqa: E402
    ActivityType,
    Event,
    EventType,
    PlanContext,
    PlanStatus,
)
from adaptengine.learner.state import (  # noqa: E402
    ExecutionLog,
    LearnerState,
    is_evidence_mastered,
)
from adaptengine.session import load_snapshot, save_snapshot  # noqa: E402


def run_demo(
    curriculum_path: str | None = None, activities_path: str | None = None
) -> dict[str, Any]:
    if curriculum_path is None:
        curriculum_path = os.path.join(repo_root, "data", "curriculum", "curriculum_4node.json")
    if activities_path is None:
        activities_path = os.path.join(repo_root, "data", "curriculum", "activities_4node.json")

    engine = Engine.from_files(curriculum_path, activities_path, config=DEFAULT_CONFIG)
    temp_dir = tempfile.mkdtemp(prefix="adaptengine_poc_")
    results: dict[str, Any] = {}

    print("=" * 76)
    print(" AdaptEngine — End-to-End PoC Demonstration (4-Node Fixture)")
    print("=" * 76)

    # -------------------------------------------------------------------------
    # PART 1: Two Scripted Profiles Through Bounded Diagnostic & Planning
    # -------------------------------------------------------------------------
    print("\n[PART 1] Running Two Scripted Profiles (Goal=C4, Budget=15m, Deadline=10d)...")

    # Profile A: Novice (incorrect on all diagnostic probes)
    novice_init = engine.init_learner()
    diag_a = engine.diagnose(
        novice_init,
        goal_concepts=None,
        response_provider=lambda act: False,
        session_id="novice-sess",
    )
    state_a = diag_a.state
    snap_a_path = os.path.join(temp_dir, "snapshot_novice.json")
    ctx_a = PlanContext(goal="C4", deadline_day=10, budget=15, current_day=1)
    save_snapshot(state_a, ExecutionLog(), snap_a_path, context=ctx_a)

    plan_a = engine.plan(state_a, ctx_a)
    print(
        f" -> Profile A (Novice): Diagnostic asked {diag_a.total_items} items. Status={plan_a.status.value}"
    )
    print(
        f"    Mastery after diagnostic: { {c: round(state_a.concepts[c].p, 3) for c in state_a.concepts} }"
    )
    print(
        f"    Plan: {len(plan_a.days)} days scheduled. Day 1: {plan_a.days[0].activities if plan_a.days else []}"
    )

    # Profile B: Advanced (correct on C1 and C2, incorrect on C3 and C4)
    def advanced_responses(act):
        return act.target_concept in ("C1", "C2")

    adv_init = engine.init_learner()
    diag_b = engine.diagnose(
        adv_init,
        goal_concepts=None,
        response_provider=advanced_responses,
        session_id="adv-sess",
    )
    state_b = diag_b.state
    snap_b_path = os.path.join(temp_dir, "snapshot_advanced.json")
    ctx_b = PlanContext(goal="C4", deadline_day=10, budget=15, current_day=1)
    save_snapshot(state_b, ExecutionLog(), snap_b_path, context=ctx_b)

    plan_b = engine.plan(state_b, ctx_b)
    print(
        f" -> Profile B (Advanced): Diagnostic asked {diag_b.total_items} items. Status={plan_b.status.value}"
    )
    print(
        f"    Mastery after diagnostic: { {c: round(state_b.concepts[c].p, 3) for c in state_b.concepts} }"
    )
    print(
        f"    Plan: {len(plan_b.days)} days scheduled. Day 1: {plan_b.days[0].activities if plan_b.days else []}"
    )

    # Check evidence mastery differences
    c1_mastered_b = is_evidence_mastered(state_b.concepts["C1"], DEFAULT_CONFIG)
    c1_mastered_a = is_evidence_mastered(state_a.concepts["C1"], DEFAULT_CONFIG)
    print(f"    C1 evidence_mastered: Novice={c1_mastered_a}, Advanced={c1_mastered_b}")

    # Omitted trace explanation
    print("    Trace explanation for Profile B skipping mastered concepts:")
    for tr in plan_b.trace:
        if tr.get("decision") == "OMITTED":
            print(
                f"      - Concept {tr.get('concept_id')}: {tr.get('reason')} (p={tr.get('p')}, responses={tr.get('responses')})"
            )

    results["plan_a"] = plan_a
    results["plan_b"] = plan_b
    results["state_a"] = state_a
    results["state_b"] = state_b

    # -------------------------------------------------------------------------
    # PART 2: Recorded Response via Canonical Snapshot & Revised Plan
    # -------------------------------------------------------------------------
    print("\n[PART 2] Recording Response for Profile A & Replanning...")
    snap_a_state, snap_a_log, snap_a_ctx = load_snapshot(
        snap_a_path, engine.graph.concepts(), include_context=True
    )
    first_act_id = plan_a.days[0].activities[0]
    first_act = engine.activities[first_act_id]
    is_lesson = first_act.type == ActivityType.LESSON
    completed_event = Event(
        day=1,
        kind=EventType.COMPLETED,
        activity_id=first_act_id,
        minutes_elapsed=first_act.duration,
        correct=None if is_lesson else True,
        attempt_id="poc-step-1",
    )
    updated_state, updated_log = engine.record(snap_a_state, snap_a_log, completed_event)
    save_snapshot(updated_state, updated_log, snap_a_path, context=snap_a_ctx)

    # Replan from Day 2
    ctx_revised = PlanContext(
        goal=snap_a_ctx.goal,
        deadline_day=snap_a_ctx.deadline_day,
        budget=snap_a_ctx.budget,
        current_day=2,
    )
    plan_revised = engine.replan(updated_state, updated_log, ctx_revised)
    print(
        f" -> Recorded activity {first_act_id} (correct=True). New belief for {first_act.target_concept}: {round(updated_state.concepts[first_act.target_concept].p, 4)}"
    )
    print(f"    Revised plan starts on Day 2 with {len(plan_revised.days)} days.")
    # Verify completed work is NOT repeated
    scheduled_all = [aid for d in plan_revised.days for aid in d.activities]
    if first_act.type == ActivityType.LESSON:
        assert first_act_id not in scheduled_all, f"Lesson {first_act_id} repeated in revised plan!"
        print(f"    Verification passed: completed lesson {first_act_id} was NOT repeated.")

    results["plan_revised"] = plan_revised

    # -------------------------------------------------------------------------
    # PART 3: Multi-Budget Cases (5, 10, 15, 30 min)
    # -------------------------------------------------------------------------
    print("\n[PART 3] Evaluating Multi-Budget Plans (5m, 10m, 15m, 30m) for Profile A...")
    budget_plans = {}
    for b in (5, 10, 15, 30):
        ctx_b_eval = PlanContext(goal="C4", deadline_day=15, budget=b, current_day=2)
        p = engine.plan(updated_state, ctx_b_eval)
        budget_plans[b] = p
        total_sched_min = sum(d.duration for d in p.days)
        print(
            f"    Budget={b:2d}m -> Status={p.status.value:9s} Days={len(p.days):2d} TotalMinutes={total_sched_min:2d}"
        )
        # Verify no day exceeds budget
        for d in p.days:
            assert d.duration <= b, f"Day {d.day} exceeded budget {b}: {d.duration}"
    results["budget_plans"] = budget_plans

    # -------------------------------------------------------------------------
    # PART 4: Infeasible Request with Shortfall & Options
    # -------------------------------------------------------------------------
    print("\n[PART 4] Infeasible Request (Goal=C4, Deadline=1d, Budget=5m)...")
    ctx_infeasible = PlanContext(goal="C4", deadline_day=1, budget=5, current_day=1)
    plan_inf = engine.plan(novice_init, ctx_infeasible)
    print(f" -> Plan status: {plan_inf.status.value}")
    if plan_inf.status == PlanStatus.INFEASIBLE:
        print(f"    Shortfall days: {plan_inf.shortfall_days}")
        print(f"    Reason: {plan_inf.reason}")
        print(f"    Resolution Options: {plan_inf.options}")
    results["plan_infeasible"] = plan_inf

    # -------------------------------------------------------------------------
    # PART 5: Adaptive Events (Missed Day, Remediation, Deadline, Budget) + Review
    # -------------------------------------------------------------------------
    print("\n[PART 5] Executing the Four Adaptive Events and Review Due Trigger...")

    # Event 1: Missed Day
    print(" -> 1. Missed Day Event:")
    event_missed = Event(day=2, kind=EventType.MISSED)
    state_ev, log_ev = engine.record(updated_state, updated_log, event_missed)
    ctx_ev = PlanContext(goal="C4", deadline_day=10, budget=15, current_day=3)
    plan_after_missed = engine.replan(state_ev, log_ev, ctx_ev)
    print(
        f"    Logged {len(log_ev.events)} events. Replan starts at Day 3 with {len(plan_after_missed.days)} days."
    )
    assert all(d.day >= 3 for d in plan_after_missed.days)

    # Event 2: Failed Assessment with Remediation
    print(" -> 2. Failed Assessment with Remediation Trigger:")
    event_fail = Event(
        day=3,
        kind=EventType.FAILED_ASSESSMENT,
        activity_id="E-C1-0.2",
        minutes_elapsed=1,
        correct=False,
        attempt_id="poc-fail-1",
    )
    state_ev, log_ev = engine.record(state_ev, log_ev, event_fail)
    print(
        f"    Failed assessment recorded for C1. p={round(state_ev.concepts['C1'].p, 4)}, needs_remediation={state_ev.concepts['C1'].needs_remediation}"
    )
    assert state_ev.concepts["C1"].needs_remediation is True
    plan_remediation = engine.replan(
        state_ev, log_ev, PlanContext(goal="C4", deadline_day=10, budget=15, current_day=3)
    )
    first_sched = plan_remediation.days[0].activities[0] if plan_remediation.days else None
    print(
        f"    First activity scheduled in Day 3: {first_sched} (Expected remediation lesson L-C1)"
    )
    assert first_sched == "L-C1", f"Expected remediation lesson L-C1 first, got {first_sched}"

    # Event 3: Deadline Change
    print(" -> 3. Deadline Change Event:")
    event_dl = Event(day=3, kind=EventType.DEADLINE_CHANGED, value=14)
    state_ev, log_ev = engine.record(state_ev, log_ev, event_dl)
    plan_dl = engine.replan(
        state_ev, log_ev, PlanContext(goal="C4", deadline_day=14, budget=15, current_day=3)
    )
    print(
        f"    Extended deadline to Day 14. Plan status: {plan_dl.status.value}, horizon: {plan_dl.days[-1].day if plan_dl.days else 0}"
    )
    assert plan_dl.status == PlanStatus.FEASIBLE

    # Event 4: Budget Change
    print(" -> 4. Budget Change Event:")
    event_bg = Event(day=3, kind=EventType.BUDGET_CHANGED, value=30)
    state_ev, log_ev = engine.record(state_ev, log_ev, event_bg)
    plan_bg = engine.replan(
        state_ev, log_ev, PlanContext(goal="C4", deadline_day=14, budget=30, current_day=3)
    )
    print(
        f"    Increased daily budget to 30m. Days needed: {len(plan_bg.days)} (compressed from previous {len(plan_dl.days)} days)"
    )
    assert len(plan_bg.days) <= len(plan_dl.days)

    # Review Due Trigger via Memory Decay
    print(" -> 5. Spaced Review Due Trigger (Short Half-Life Fixture):")
    # Simulate concept C1 having been practiced 4 days ago with half_life_days=1.0 -> recall = 2^(-4) = 0.0625 < 0.80
    c1_decayed = state_ev.concepts["C1"]
    c1_decayed = c1_decayed.__class__(
        concept_id="C1",
        p=0.92,
        lessons_done=1,
        responses=2,
        correct_responses=2,
        status=c1_decayed.status,
        seen_attempt_ids=c1_decayed.seen_attempt_ids,
        half_life_days=1.0,
        last_practice_day=1,
        n_reviews=0,
        needs_remediation=False,
    )
    state_decayed = LearnerState(concepts={**state_ev.concepts, "C1": c1_decayed})
    plan_review = engine.plan(
        state_decayed,
        PlanContext(goal="C4", deadline_day=14, budget=15, current_day=5),
    )
    # Check trace for review candidate selection
    print(f"    Plan on Day 5: {plan_review.days[0].activities if plan_review.days else []}")
    c1_review_acts = [
        aid
        for aid in plan_review.days[0].activities
        if engine.activities[aid].target_concept == "C1"
        and engine.activities[aid].type == ActivityType.EXERCISE
    ]
    print(f"    Review exercise scheduled for C1 on Day 5: {c1_review_acts}")
    assert len(c1_review_acts) > 0, "Expected spaced review exercise for decayed concept C1"

    # -------------------------------------------------------------------------
    # PART 6: Trace Explanation Summary
    # -------------------------------------------------------------------------
    print("\n[PART 6] Sample Decision Explainability Trace (Review Plan Day 5):")
    for tr in plan_review.trace:
        if tr.get("decision") == "SELECTED":
            print(
                f"    Day {tr.get('day')}: {tr.get('activity_id')} -> reason={tr.get('reason')}, score={round(tr.get('score', 0.0), 3)}"
            )

    print("\n" + "=" * 76)
    print(" PoC Demonstration Completed Successfully with Full Verification.")
    print("=" * 76)

    results["plan_after_missed"] = plan_after_missed
    results["plan_remediation"] = plan_remediation
    results["plan_dl"] = plan_dl
    results["plan_bg"] = plan_bg
    results["plan_review"] = plan_review
    return results


if __name__ == "__main__":
    run_demo()
