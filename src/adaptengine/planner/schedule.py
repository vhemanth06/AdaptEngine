from typing import Mapping, Sequence, Optional, Any
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.schema import Activity, ActivityType, PlanContext, PlanDay
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerState
from ..learner.adapter import MasteryModel, CustomBKT
from ..learner.mastery import learn
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
) -> tuple[tuple[PlanDay, ...], list[dict[str, Any]]]:
    """Deterministic, time-budgeted greedy day-by-day scheduler with review and remediation (M5).

    Priority Tiers (D26):
    - Tier 0: Remediation repeat lessons (D21)
    - Tier 1: Spaced reviews (r < threshold) ordered by urgency (D25)
    - Tier 2: New curriculum lessons and exercises (D16)

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

    if state is not None:
        for cid, c in state.concepts.items():
            proj_last_practice_day[cid] = c.last_practice_day
            proj_half_life[cid] = c.half_life_days
            if cid not in projected_p:
                projected_p[cid] = c.p
            if c.needs_remediation:
                rem_flagged_concepts.add(cid)

    current_day = ctx.current_day

    while queues:
        # Find concepts due for review on current_day
        reviewed_today: set[str] = set()
        due_reviews: dict[str, tuple[float, float]] = {}
        if state is not None and activities is not None:
            for cid in sorted(state.concepts.keys()):
                last_d = proj_last_practice_day.get(cid)
                if last_d is None:
                    continue
                dt = max(0, current_day - last_d)
                h = proj_half_life.get(cid, 30.0)
                r = 2.0 ** (-float(dt) / float(h))
                if review_urgency_override is not None and cid in review_urgency_override:
                    urg = review_urgency_override[cid]
                    if urg > 0.0:
                        due_reviews[cid] = (r, urg)
                elif r < cfg.recall_threshold:
                    desc_count = graph.descendant_count(cid)
                    urg = (1.0 - r) * (1.0 + float(desc_count))
                    due_reviews[cid] = (r, urg)

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

        rem_budget = ctx.budget
        day_activity_ids: list[str] = []
        day_duration = 0

        while True:
            candidates = []

            # 1. Tier 0: Remediation candidates
            remediation_c = [c for c in sorted(queues.keys()) if c in rem_flagged_concepts]
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
                if cid in reviewed_today:
                    continue
                if activities is not None:
                    c_exs = [
                        a
                        for a in activities.values()
                        if a.target_concept == cid and a.type == ActivityType.EXERCISE
                    ]
                    if c_exs:
                        chosen_ex = select_exercise(
                            c_exs, projected_p[cid], cfg.target_success, model, cfg
                        )
                        if chosen_ex.duration > rem_budget:
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

            if not candidates:
                break

            # Sort by: tier (0 < 1 < 2), then -score, then activity_id (D10, D26)
            candidates.sort(key=lambda item: (item[0], -round(item[1], 9), item[2].activity_id))
            tier, score, selected, concept_id, kind, rev, unl, fit = candidates[0]

            day_activity_ids.append(selected.activity_id)
            day_duration += selected.duration
            rem_budget -= selected.duration

            if kind == "remediation":
                queues[concept_id].pop(0)
                if not queues[concept_id]:
                    del queues[concept_id]
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
            elif kind == "review":
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
                queues[concept_id].pop(0)
                if not queues[concept_id]:
                    del queues[concept_id]
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
        current_day += 1

    return tuple(days), trace
