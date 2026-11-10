"""Engine-side validator for agent-proposed plans (W8 M.1, D57).

Rules (each violation is reported with its rule name):
  MALFORMED            days not a list of {day: int, activities: [str]} with increasing days
  UNKNOWN_ACTIVITY     an id not in the catalogue
  DUPLICATE_ACTIVITY   a lesson scheduled twice, or again after it was completed (non-repeatable;
                       exercises are repeatable when cfg.allow_exercise_repeats, D41)
  OUTSIDE_HORIZON      a day before the plan's start day
  DEADLINE_EXCEEDED    a day after the deadline
  OVER_BUDGET          a day's minutes exceed the budget (the start day: budget - minutes used)
  PREREQUISITE_ORDER   work on a concept before its direct prerequisites are mastered under the
                       plan's own projection (lessons learn(), exercises assumed correct)
  GOAL_NOT_REACHED     the projection does not reach mastery on the goal and its prerequisites
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ..core.config import DEFAULT_CONFIG, EngineConfig
from ..core.errors import ValidationError
from ..core.schema import Activity, ActivityType, PlanContext, PlanDay
from ..curriculum.graph import CurriculumGraph
from ..learner.adapter import MasteryModel, make_model
from ..learner.mastery import learn
from ..learner.state import LearnerState, mastered_by


def parse_days(days: Any) -> tuple[Optional[tuple[PlanDay, ...]], list[dict]]:
    if not isinstance(days, list) or not days:
        return None, [{"rule": "MALFORMED", "detail": "days must be a non-empty list"}]
    out, prev = [], None
    for d in days:
        if (
            not isinstance(d, dict)
            or type(d.get("day")) is not int
            or not isinstance(d.get("activities"), list)
            or not all(isinstance(a, str) for a in d["activities"])
        ):
            return None, [{"rule": "MALFORMED", "detail": f"bad day entry {str(d)[:80]}"}]
        if prev is not None and d["day"] <= prev:
            return None, [{"rule": "MALFORMED", "detail": "days must be strictly increasing"}]
        prev = d["day"]
        try:
            out.append(PlanDay(day=d["day"], activities=tuple(d["activities"]), duration=0))
        except ValidationError as e:
            return None, [{"rule": "MALFORMED", "detail": str(e)[:120]}]
    return tuple(out), []


def validate_proposal(
    graph: CurriculumGraph,
    activities: Mapping[str, Activity],
    state: LearnerState,
    ctx: PlanContext,
    days: Sequence[PlanDay],
    *,
    done_ids: Sequence[str] = (),
    model: Optional[MasteryModel] = None,
    cfg: EngineConfig = DEFAULT_CONFIG,
) -> list[dict]:
    """All rule violations of a proposed schedule (empty list = valid)."""
    model = model or make_model(cfg)
    bad: list[dict] = []
    p = {c: s.p for c, s in state.concepts.items()}
    n = {c: s.responses for c, s in state.concepts.items()}
    streak = {c: s.correct_streak for c, s in state.concepts.items()}
    done = set(done_ids)
    lessons_seen: set[str] = set()

    def ok(c: str) -> bool:
        return mastered_by(p[c], n[c], streak[c], cfg)

    for d in days:
        if d.day < ctx.current_day:
            bad.append({"rule": "OUTSIDE_HORIZON", "day": d.day})
        if d.day > ctx.deadline_day:
            bad.append({"rule": "DEADLINE_EXCEEDED", "day": d.day, "deadline": ctx.deadline_day})
        minutes = 0
        for aid in d.activities:
            a = activities.get(aid)
            if a is None:
                bad.append({"rule": "UNKNOWN_ACTIVITY", "day": d.day, "activity_id": aid})
                continue
            minutes += a.duration
            c = a.target_concept
            repeatable = a.type == ActivityType.EXERCISE and cfg.allow_exercise_repeats
            if not repeatable and (
                aid in lessons_seen or (aid in done and not state.concepts[c].needs_remediation)
            ):
                bad.append({"rule": "DUPLICATE_ACTIVITY", "day": d.day, "activity_id": aid})
            lessons_seen.add(aid)
            missing = [q for q in graph.prerequisites(c) if not ok(q)]
            if missing:
                bad.append(
                    {
                        "rule": "PREREQUISITE_ORDER",
                        "day": d.day,
                        "activity_id": aid,
                        "missing_prerequisites": missing,
                    }
                )
            if a.type == ActivityType.LESSON:
                p[c] = learn(p[c], cfg.t_lesson)
            else:
                p[c] = model.update(p[c], a.difficulty, True, cfg.t_exercise)
                n[c] += 1
                streak[c] += 1
        cap = ctx.budget - (ctx.minutes_used_today if d.day == ctx.current_day else 0)
        if minutes > cap:
            bad.append({"rule": "OVER_BUDGET", "day": d.day, "minutes": minutes, "budget": cap})
    unreached = sorted(c for c in {ctx.goal} | graph.ancestors(ctx.goal) if not ok(c))
    if unreached:
        bad.append({"rule": "GOAL_NOT_REACHED", "concepts": unreached})
    return bad
