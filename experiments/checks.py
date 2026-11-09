"""Independent plan audit for curriculum constraints, budget adherence, and duplication (W6 Step 2).

This module contains verification functions that audit scheduled or executed activity sequences
using public model functions and curriculum graphs. Never imported from src/.
"""

from typing import Callable, Iterable, Union
from adaptengine.core.schema import ActivityType, EventType, PlanDay
from adaptengine.learner.mastery import learn
from adaptengine.learner.state import ExecutionLog, is_evidence_mastered, mastered_by


def count_executed_prereq_violations(engine, start_state, log: ExecutionLog) -> int:
    """Primary safety audit (D46): replay the real ExecutionLog through engine.record() and count
    activities started while a direct prerequisite was NOT evidence-mastered in the recorded state.

    Unlike the plan-level audit this uses the learner's actual answers, so a wrong answer on a
    prerequisite exercise makes later work on its dependants a violation.
    """
    cfg, graph = engine.config, engine.graph
    state, replay = start_state, ExecutionLog()
    bad = 0
    for e in log.events:
        if e.kind in (EventType.COMPLETED, EventType.FAILED_ASSESSMENT) and e.activity_id:
            c = engine.activities[e.activity_id].target_concept
            if any(
                not is_evidence_mastered(state.concepts[q], cfg) for q in graph.prerequisites(c)
            ):
                bad += 1
        state, replay = engine.record(state, replay, e)
    return bad


def count_plan_prereq_violations(engine, start_state, days: Iterable[PlanDay]) -> int:
    """Secondary (plan-level) audit of prerequisite satisfaction along a scheduled sequence.

    A concept's work may start once every direct prerequisite is unlocked (p >= theta and
    responses >= k_responses). Replays the sequence optimistically (assuming success on exercises
    and lesson transitions), so it checks the plan's own projection, not the learner's evidence.
    """
    cfg, graph, acts, model = engine.config, engine.graph, engine.activities, engine.model
    p = {c: cs.p for c, cs in start_state.concepts.items()}
    n = {c: cs.responses for c, cs in start_state.concepts.items()}
    streak = {c: cs.correct_streak for c, cs in start_state.concepts.items()}

    def unlocked(c: str) -> bool:
        return mastered_by(p.get(c, 0.0), n.get(c, 0), streak.get(c, 0), cfg)

    bad = 0
    for day in sorted(days, key=lambda d: d.day):
        for aid in day.activities:
            a = acts[aid]
            c = a.target_concept
            if any(not unlocked(q) for q in graph.prerequisites(c)):
                bad += 1
            if a.type == ActivityType.LESSON:
                p[c] = learn(p[c], cfg.t_lesson)
            else:
                p[c] = model.update(p[c], a.difficulty, True, cfg.t_exercise)
                n[c] += 1
                streak[c] += 1
    return bad


def count_budget_violations(
    engine, days: Iterable[PlanDay], budget_for_day: Union[int, Callable[[int], int]]
) -> int:
    """Recompute durations from the activity catalogue; do not trust PlanDay.duration."""
    get_budget = budget_for_day if callable(budget_for_day) else (lambda d: budget_for_day)
    return sum(
        1
        for d in days
        if sum(engine.activities[a].duration for a in d.activities) > get_budget(d.day)
    )


def count_duplicate_activities(days: Iterable[PlanDay]) -> int:
    """Count duplicate activity occurrences across days."""
    seen, dup = set(), 0
    for d in days:
        for a in d.activities:
            if a in seen:
                dup += 1
            seen.add(a)
    return dup
