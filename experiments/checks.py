"""Independent plan audit for curriculum constraints, budget adherence, and duplication (W6 Step 2).

This module contains verification functions that audit scheduled or executed activity sequences
using public model functions and curriculum graphs. Never imported from src/.
"""

from typing import Callable, Iterable, Union
from adaptengine.core.schema import ActivityType, PlanDay
from adaptengine.learner.mastery import learn


def count_prerequisite_violations(engine, start_state, days: Iterable[PlanDay]) -> int:
    """Audit prerequisite satisfaction along the scheduled or executed activity sequence.

    A concept's work may start once every direct prerequisite is unlocked (p >= theta and
    responses >= k_responses). Replays the sequence optimistically (assuming success on exercises
    and lesson transitions).
    """
    cfg, graph, acts, model = engine.config, engine.graph, engine.activities, engine.model
    p = {c: cs.p for c, cs in start_state.concepts.items()}
    n = {c: cs.responses for c, cs in start_state.concepts.items()}

    def unlocked(c: str) -> bool:
        return p.get(c, 0.0) >= cfg.theta and n.get(c, 0) >= cfg.k_responses

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
