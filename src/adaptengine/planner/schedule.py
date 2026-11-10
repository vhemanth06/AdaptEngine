from typing import Mapping, Sequence, Optional, Any
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.schema import Activity, ActivityType, PlanContext, PlanDay
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerState, is_evidence_mastered
from ..learner.adapter import MasteryModel, CustomBKT
from ..learner.mastery import learn
from ..review.forgetting import recall_at, urgency_from_recall
from ..review.hlr import hlr_half_life
from .difficulty import select_exercise


def run_greedy_schedule(
    graph: CurriculumGraph,
    workload: Mapping[str, Sequence[Activity]],
    initial_projected_p: Mapping[str, float],
    ctx: PlanContext,
    model: Optional[MasteryModel] = None,
    cfg: EngineConfig = DEFAULT_CONFIG,
    state: Optional[LearnerState] = None,
    activities: Optional[Mapping[str, Activity]] = None,
    review_urgency_override: Optional[Mapping[str, float]] = None,
    done_ids: Sequence[str] = (),
    policy: Any = None,
) -> tuple[tuple[PlanDay, ...], list[dict[str, Any]]]:
    """Deterministic, time-budgeted greedy day-by-day scheduler with review and remediation (M5).

    Priority Tiers (D26):
    - Tier 0: Remediation repeat lessons (D21)
    - Tier 1: Spaced reviews (r < threshold) ordered by urgency (D25)
    - Tier 2: New curriculum lessons and exercises (D16)
    - Maintenance (D43): after Tier 2 is exhausted, days until deadline_day hold due reviews only
    - Tier 3 (W8 C.1, D49, cfg.consolidation): once Tier 2 is exhausted, remaining minutes until
      deadline_day hold verification practice on required concepts: unseen exercises first
      (hardest first), lowest projected p first; then repeats of the hardest item
    - D.1: cfg.review_cap_fraction caps review minutes per day while new content is pending;
      cfg.review_goal_path_only reviews only the goal and prerequisites of pending new content
    - J.1: an optional ranking `policy` chooses among the top-K Tier 2 candidates (the engine
      re-checks the choice; any failure falls back to the deterministic order)

    Rules:
    - Precedence: all direct prerequisites completed before scheduling concept (D11, D12).
    - Packing: skip item that does not fit remaining daily budget, continue packing (D15).
    - Ties broken by lexicographic activity_id (D10).
    - Reason codes (T7): RANKED_TOP, DOES_NOT_FIT_REMAINING_TIME, REVIEW_DUE, REMEDIATION_INSERTED.

    Returns:
        (scheduled_days, trace)
    """
    if model is None:
        model = CustomBKT(cfg)

    # Copy workload queues and initial p
    queues: dict[str, list[Activity]] = {c: list(acts) for c, acts in workload.items() if acts}
    projected_p: dict[str, float] = dict(initial_projected_p)
    trace: list[dict[str, Any]] = []
    days: list[PlanDay] = []

    # Spaced review tracking
    proj_last_practice_day: dict[str, Optional[int]] = {}
    proj_half_life: dict[str, float] = {}
    rem_flagged_concepts: set[str] = set()

    satisfied: set[str] = (
        {cid for cid, c in state.concepts.items() if is_evidence_mastered(c, cfg)}
        if state is not None
        else set(graph.concepts()) - set(queues)
    )
    if state is not None:
        for cid, c in state.concepts.items():
            proj_last_practice_day[cid] = c.last_practice_day
            proj_half_life[cid] = (
                hlr_half_life(c, cfg) if cfg.half_life_model == "hlr" else c.half_life_days
            )
            if cid not in projected_p:
                projected_p[cid] = c.p
            if c.needs_remediation:
                rem_flagged_concepts.add(cid)

    # T6.1: exercises-by-concept index built once per call (same order as a full scan)
    exercises_by_concept: dict[str, list[Activity]] = {}
    for a in (activities or {}).values():
        if a.type == ActivityType.EXERCISE:
            exercises_by_concept.setdefault(a.target_concept, []).append(a)

    current_day = ctx.current_day
    max_day = max(ctx.deadline_day * 3, 100)
    consecutive_starvation_days = 0
    # D43 maintenance tier: once new content is exhausted, keep scheduling due reviews (only)
    # until deadline_day, so spaced review can fire after the learning phase.
    maintenance = cfg.maintenance_reviews and state is not None and activities is not None
    consolidate = cfg.consolidation and state is not None and activities is not None
    required = {ctx.goal} | graph.ancestors(ctx.goal) if ctx.goal in graph.concepts() else set()
    last_done = {aid: i for i, aid in enumerate(done_ids)}  # recency of completed activities
    scheduled_ids: set[str] = set()

    while queues or ((maintenance or consolidate) and current_day <= ctx.deadline_day):
        if current_day > max_day:
            break
        queue_progress = False
        # Find concepts due for review on current_day
        reviewed_today: set[str] = set()
        due_reviews: dict[str, tuple[float, float]] = {}
        if state is not None and activities is not None:
            for cid in sorted(state.concepts.keys()):
                r = recall_at(
                    proj_last_practice_day.get(cid),
                    proj_half_life.get(cid, cfg.half_life_days),
                    current_day,
                )
                if r is None:
                    continue
                if review_urgency_override is not None and cid in review_urgency_override:
                    urg = review_urgency_override[cid]
                    if urg > 0.0:
                        due_reviews[cid] = (r, urg)
                elif r < cfg.recall_threshold:
                    due_reviews[cid] = (r, urgency_from_recall(r, graph.descendant_count(cid)))

        # Log REVIEW_DUE trace records for concepts due today
        for cid, (r_val, urg_val) in due_reviews.items():
            trace.append(
                {
                    "decision": "REVIEW_DUE",
                    "reason": "REVIEW_DUE",
                    "concept_id": cid,
                    "r": r_val,
                    "threshold": cfg.recall_threshold,
                    "urgency": urg_val,
                    "day": current_day,
                }
            )

        # T2.1: the start day may already be partly used (mid-day replan)
        rem_budget = ctx.budget - (ctx.minutes_used_today if current_day == ctx.current_day else 0)
        day_activity_ids: list[str] = []
        day_duration = 0
        review_minutes = 0
        review_cap = cfg.review_cap_fraction * ctx.budget
        relevant: Optional[set[str]] = None
        if cfg.review_goal_path_only:
            relevant = {ctx.goal}
            for q in queues:
                relevant |= graph.ancestors(q)

        while True:
            candidates = []

            # 1. Tier 0: Remediation candidates
            # Prerequisite gate (D11/TC3.1) applies to every tier: no activity for a concept
            # while a direct prerequisite still has queued work (W7 fix found by the T4.4 audit)
            # A prerequisite is satisfied only if it was evidence-mastered at plan start or its
            # queued work has been completed in the projection (covers best-effort plans whose
            # workload omits an unmastered prerequisite).
            def gated(c: str) -> bool:
                return any(p in queues or p not in satisfied for p in graph.prerequisites(c))

            remediation_c = [
                c for c in sorted(queues.keys()) if c in rem_flagged_concepts and not gated(c)
            ]
            for c in remediation_c:
                cand = queues[c][0]
                if cand.duration > rem_budget:
                    trace.append(
                        {
                            "decision": "DEFERRED",
                            "activity_id": cand.activity_id,
                            "target_concept": c,
                            "day": current_day,
                            "reason": "DOES_NOT_FIT_REMAINING_TIME",
                            "duration": cand.duration,
                            "remaining_budget": rem_budget,
                        }
                    )
                else:
                    candidates.append((0, 100.0, cand, c, "remediation", 0.0, 0.0, 0.0))

            # 2. Tier 1: Spaced review candidates
            for cid, (r_val, urg_val) in due_reviews.items():
                if cid in reviewed_today or gated(cid):
                    continue
                if relevant is not None and cid not in relevant:
                    continue
                if activities is not None:
                    c_exs = exercises_by_concept.get(cid, [])
                    if c_exs:
                        chosen_ex = select_exercise(
                            c_exs, projected_p[cid], cfg.target_success, model, cfg
                        )
                        if (
                            queues
                            and cfg.review_cap_fraction < 1.0
                            and review_minutes + chosen_ex.duration > review_cap
                        ):
                            trace.append(
                                {
                                    "decision": "DEFERRED",
                                    "activity_id": chosen_ex.activity_id,
                                    "target_concept": cid,
                                    "day": current_day,
                                    "reason": "REVIEW_CAP",
                                    "review_minutes": review_minutes,
                                    "cap": review_cap,
                                }
                            )
                        elif chosen_ex.duration > rem_budget:
                            trace.append(
                                {
                                    "decision": "DEFERRED",
                                    "activity_id": chosen_ex.activity_id,
                                    "target_concept": cid,
                                    "day": current_day,
                                    "reason": "DOES_NOT_FIT_REMAINING_TIME",
                                    "duration": chosen_ex.duration,
                                    "remaining_budget": rem_budget,
                                }
                            )
                        else:
                            pc = model.predict_correct(projected_p[cid], chosen_ex.difficulty)
                            fit = 1.0 - abs(pc - cfg.target_success)
                            candidates.append(
                                (
                                    1,
                                    urg_val,
                                    chosen_ex,
                                    cid,
                                    "review",
                                    urg_val,
                                    float(graph.descendant_count(cid)),
                                    fit,
                                )
                            )

            # 3. Tier 2: New workload candidates
            for c in sorted(queues.keys()):
                # If this concept has remediation waiting, it's already handled in Tier 0
                if c in rem_flagged_concepts:
                    continue
                # Direct prerequisites must have no work remaining in queues
                preds = graph.prerequisites(c)
                if any(p in queues for p in preds):
                    continue

                candidate = queues[c][0]
                if candidate.duration > rem_budget:
                    trace.append(
                        {
                            "decision": "DEFERRED",
                            "activity_id": candidate.activity_id,
                            "target_concept": c,
                            "day": current_day,
                            "reason": "DOES_NOT_FIT_REMAINING_TIME",
                            "duration": candidate.duration,
                            "remaining_budget": rem_budget,
                        }
                    )
                else:
                    review = 0.0
                    unlock = float(graph.descendant_count(c))
                    if candidate.type == ActivityType.LESSON:
                        fit = 0.0
                    else:
                        pc = model.predict_correct(projected_p[c], candidate.difficulty)
                        fit = 1.0 - abs(pc - cfg.target_success)

                    score = cfg.w_review * review + cfg.w_unlock * unlock + cfg.w_fit * fit
                    candidates.append((2, score, candidate, c, "new", review, unlock, fit))

            # 4. Tier 3 (C.1): consolidation once all required new work is scheduled
            if consolidate and not queues and current_day <= ctx.deadline_day:
                for c in sorted(required):
                    if gated(c):
                        continue
                    item = _consolidation_item(
                        exercises_by_concept.get(c, ()), last_done, scheduled_ids
                    )
                    if item is None or item.duration > rem_budget:
                        continue
                    unseen = item.activity_id not in last_done and (
                        item.activity_id not in scheduled_ids
                    )
                    # unseen items first, then the lowest projected p
                    score = (2.0 if unseen else 1.0) - projected_p.get(c, 0.0)
                    candidates.append((3, score, item, c, "consolidation", 0.0, 0.0, 0.0))

            if not candidates:
                break

            # Sort by: tier (0 < 1 < 2 < 3), then -score, then activity_id (D10, D26)
            candidates.sort(key=lambda item: (item[0], -round(item[1], 9), item[2].activity_id))
            if policy is not None and candidates[0][0] == 2:
                pick = _policy_pick(
                    policy,
                    [x for x in candidates if x[0] == 2][: cfg.policy_top_k],
                    projected_p,
                    proj_last_practice_day,
                    state,
                    required,
                    model,
                    ctx,
                    cfg,
                    current_day,
                    rem_budget,
                    len(day_activity_ids),
                    trace,
                )
                candidates.insert(0, candidates.pop(candidates.index(pick)))
            tier, score, selected, concept_id, kind, rev, unl, fit = candidates[0]
            scheduled_ids.add(selected.activity_id)

            day_activity_ids.append(selected.activity_id)
            day_duration += selected.duration
            rem_budget -= selected.duration

            if kind == "remediation":
                queue_progress = True
                queues[concept_id].pop(0)
                if not queues[concept_id]:
                    del queues[concept_id]
                    satisfied.add(concept_id)
                rem_flagged_concepts.discard(concept_id)
                proj_last_practice_day[concept_id] = current_day
                projected_p[concept_id] = learn(projected_p[concept_id], cfg.t_lesson)
                trace.append(
                    {
                        "decision": "SELECTED",
                        "activity_id": selected.activity_id,
                        "target_concept": concept_id,
                        "day": current_day,
                        "duration": selected.duration,
                        "remaining_budget": rem_budget,
                        "reason": "REMEDIATION_INSERTED",
                        "score": score,
                        "score_components": {"review": rev, "unlock": unl, "fit": fit},
                        "projected_p": projected_p[concept_id],
                    }
                )
            elif kind == "consolidation":
                proj_last_practice_day[concept_id] = current_day
                projected_p[concept_id] = model.update(
                    projected_p[concept_id], selected.difficulty, True, cfg.t_exercise
                )
                trace.append(
                    {
                        "decision": "SELECTED",
                        "activity_id": selected.activity_id,
                        "target_concept": concept_id,
                        "day": current_day,
                        "duration": selected.duration,
                        "remaining_budget": rem_budget,
                        "reason": "CONSOLIDATION",
                        "score": score,
                        "score_components": {"review": rev, "unlock": unl, "fit": fit},
                        "projected_p": projected_p[concept_id],
                    }
                )
            elif kind == "review":
                review_minutes += selected.duration
                reviewed_today.add(concept_id)
                proj_last_practice_day[concept_id] = current_day
                projected_p[concept_id] = model.update(
                    projected_p[concept_id], selected.difficulty, True, cfg.t_exercise
                )
                trace.append(
                    {
                        "decision": "SELECTED",
                        "activity_id": selected.activity_id,
                        "target_concept": concept_id,
                        "day": current_day,
                        "duration": selected.duration,
                        "remaining_budget": rem_budget,
                        "reason": "REVIEW_DUE",
                        "score": score,
                        "score_components": {"review": rev, "unlock": unl, "fit": fit},
                        "projected_p": projected_p[concept_id],
                    }
                )
            else:  # kind == "new"
                queue_progress = True
                queues[concept_id].pop(0)
                if not queues[concept_id]:
                    del queues[concept_id]
                    satisfied.add(concept_id)
                proj_last_practice_day[concept_id] = current_day
                if selected.type == ActivityType.LESSON:
                    projected_p[concept_id] = learn(projected_p[concept_id], cfg.t_lesson)
                elif selected.type == ActivityType.EXERCISE:
                    projected_p[concept_id] = model.update(
                        projected_p[concept_id], selected.difficulty, True, cfg.t_exercise
                    )

                trace.append(
                    {
                        "decision": "SELECTED",
                        "activity_id": selected.activity_id,
                        "target_concept": concept_id,
                        "day": current_day,
                        "duration": selected.duration,
                        "remaining_budget": rem_budget,
                        "reason": "RANKED_TOP",
                        "score": score,
                        "score_components": {"review": rev, "unlock": unl, "fit": fit},
                        "projected_p": projected_p[concept_id],
                    }
                )

        if day_activity_ids:
            days.append(
                PlanDay(day=current_day, activities=tuple(day_activity_ids), duration=day_duration)
            )
        if queues and not queue_progress:
            consecutive_starvation_days += 1
            if consecutive_starvation_days >= 15:
                break
        else:
            consecutive_starvation_days = 0
        current_day += 1

    return tuple(days), trace


def _consolidation_item(exercises, last_done, scheduled_ids) -> Optional[Activity]:
    """C.1: hardest unseen exercise; if none, the hardest one, least recently done first."""
    if not exercises:
        return None
    unseen = [
        a
        for a in exercises
        if a.activity_id not in last_done and a.activity_id not in scheduled_ids
    ]
    if unseen:
        return min(unseen, key=lambda a: (-a.difficulty, a.activity_id))
    return min(
        exercises,
        key=lambda a: (
            -a.difficulty,
            a.activity_id in scheduled_ids,
            last_done.get(a.activity_id, -1),
            a.activity_id,
        ),
    )


def _policy_pick(
    policy,
    top,
    projected_p,
    last_day,
    state,
    required,
    model,
    ctx,
    cfg,
    day,
    rem_budget,
    slot,
    trace,
):
    """J.1/J.4: ask the ranking policy to choose among the deterministic top-K Tier 2 candidates.

    The engine re-checks the answer (must be one of the offered, already-eligible candidates that
    fit the remaining budget); a single candidate, an invalid answer or any error falls back to the
    deterministic choice (POLICY_FALLBACK)."""
    det = top[0]
    cands = []
    for rank, (_, score, act, c, _, rev, unl, fit) in enumerate(top):
        lp = last_day.get(c)
        cands.append(
            {
                "activity_id": act.activity_id,
                "concept": c,
                "type": act.type.value,
                "difficulty": act.difficulty,
                "duration": act.duration,
                "p": projected_p.get(c, 0.0),
                "responses": state.concepts[c].responses if state is not None else 0,
                "days_since_practice": None if lp is None else day - lp,
                "p_correct": (
                    model.predict_correct(projected_p[c], act.difficulty)
                    if act.type == ActivityType.EXERCISE
                    else None
                ),
                "unlock": unl,
                "review_urgency": rev,
                "on_goal_path": c in required,
                "det_rank": rank,
                "det_score": score,
            }
        )
    context = {
        "day": day,
        "start_day": ctx.current_day,
        "deadline_day": ctx.deadline_day,
        "budget": ctx.budget,
        "remaining_budget": rem_budget,
        "slot": slot,
        "seed": cfg.policy_seed,
        "goal": ctx.goal,
    }
    base = {"day": day, "slot": slot, "candidates": [x["activity_id"] for x in cands]}
    base["deterministic_choice"] = det[2].activity_id
    if len(top) <= 1:
        trace.append({"decision": "POLICY_FALLBACK", "reason": "SINGLE_CANDIDATE", **base})
        return det
    try:
        aid, propensity, info = policy.choose(cands, context)
        pick = next(x for x in top if x[2].activity_id == aid)  # StopIteration: not offered
        if pick[2].duration > rem_budget:
            raise ValueError("chosen activity does not fit the remaining budget")
    except Exception as e:  # noqa: BLE001 - any policy failure falls back (spec J, D53)
        trace.append(
            {
                "decision": "AGENT_FALLBACK"
                if getattr(policy, "is_agent", False)
                else "POLICY_FALLBACK",
                "reason": type(e).__name__,
                "detail": str(e)[:200],
                "policy": getattr(policy, "name", type(policy).__name__),
                **base,
            }
        )
        return det
    trace.append(
        {
            "decision": "POLICY_SELECTED",
            "policy": getattr(policy, "name", type(policy).__name__),
            "policy_version": getattr(policy, "version", None),
            "chosen": aid,
            "propensity": propensity,
            **base,
            **(info or {}),
        }
    )
    return pick
