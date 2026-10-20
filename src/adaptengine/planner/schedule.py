from typing import Mapping, Sequence, Optional, Any
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.schema import Activity, ActivityType, PlanContext, PlanDay
from ..curriculum.graph import CurriculumGraph
from ..learner.adapter import MasteryModel, CustomBKT
from ..learner.mastery import learn


def run_greedy_schedule(
    graph: CurriculumGraph,
    workload: Mapping[str, Sequence[Activity]],
    initial_projected_p: Mapping[str, float],
    ctx: PlanContext,
    model: Optional[MasteryModel] = None,
    cfg: EngineConfig = DEFAULT_CONFIG,
) -> tuple[tuple[PlanDay, ...], list[dict[str, Any]]]:
    """Deterministic, time-budgeted greedy day-by-day scheduler (T4).

    Rules:
    - Eligible: all direct prerequisites have no projected work left (D11, D12),
      and the item fits remaining minutes in the day.
    - Order within concept: queue order (lessons before exercises, D16).
    - Score = w_review*review + w_unlock*unlock + w_fit*fit (review=0 in W4).
    - Ties broken by lexicographic activity_id (D10 rule).
    - Skip item that does not fit, keep filling with lower-ranked items (D15).
    - Trace each SELECTED and DEFERRED item.

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

    current_day = ctx.current_day

    while queues:
        rem_budget = ctx.budget
        day_activity_ids: list[str] = []
        day_duration = 0

        while True:
            # Find all concepts whose prerequisites are completed
            eligible_candidates = []

            for c in sorted(queues.keys()):
                # Direct prerequisites must have no work remaining in queues
                preds = graph.prerequisites(c)
                if any(p in queues for p in preds):
                    continue

                candidate = queues[c][0]
                if candidate.duration > rem_budget:
                    # Item does not fit in remaining minutes of this day
                    trace.append(
                        {
                            "decision": "DEFERRED",
                            "activity_id": candidate.activity_id,
                            "target_concept": c,
                            "day": current_day,
                            "reason": "DOES_NOT_FIT",
                            "duration": candidate.duration,
                            "remaining_budget": rem_budget,
                        }
                    )
                else:
                    # Score the fitting candidate
                    review = 0.0
                    unlock = float(graph.descendant_count(c))
                    if candidate.type == ActivityType.LESSON:
                        fit = 0.0
                    else:
                        pc = model.predict_correct(projected_p[c], candidate.difficulty)
                        fit = 1.0 - abs(pc - cfg.target_success)

                    score = cfg.w_review * review + cfg.w_unlock * unlock + cfg.w_fit * fit
                    eligible_candidates.append((score, candidate, c, review, unlock, fit))

            if not eligible_candidates:
                # No eligible candidate fits in the remaining budget for today
                break

            # Pick highest score, ties by smaller activity_id (D10)
            eligible_candidates.sort(key=lambda item: (-round(item[0], 9), item[1].activity_id))
            score, selected, concept_id, rev, unl, fit = eligible_candidates[0]

            # Place selected activity
            day_activity_ids.append(selected.activity_id)
            day_duration += selected.duration
            rem_budget -= selected.duration

            # Advance queue for concept
            queues[concept_id].pop(0)
            if not queues[concept_id]:
                del queues[concept_id]

            # Update projected p for concept
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
                    "score": score,
                    "score_components": {"review": rev, "unlock": unl, "fit": fit},
                    "projected_p": projected_p[concept_id],
                }
            )

        days.append(
            PlanDay(day=current_day, activities=tuple(day_activity_ids), duration=day_duration)
        )
        current_day += 1

    return tuple(days), trace
