from __future__ import annotations

import math

from typing import Any, Mapping, Optional, Sequence
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.schema import Activity, ActivityType
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerState, is_evidence_mastered, mastered_by
from ..learner.mastery import learn
from ..learner.adapter import MasteryModel, CustomBKT
from .difficulty import select_exercise


_MAX_PROJECTED_EXERCISES = 200  # projection guard: exercises per concept


class ContentInsufficientError(Exception):
    """Raised when available exercises are insufficient to achieve mastery threshold."""

    pass


class WorkloadCache:
    """Caller-owned memo of per-concept workload projections (explicit value, no hidden state).

    Keys include a curriculum/activity-catalogue fingerprint, so one cache can't serve a different
    curriculum (T6.1). Bounded: the oldest entry is evicted beyond maxsize.
    """

    def __init__(self, maxsize: int = 4096):
        self._store: dict[Any, Any] = {}
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0

    def get(self, key: Any) -> Optional[Any]:
        v = self._store.get(key)
        if v is None:
            self.misses += 1
        else:
            self.hits += 1
        return v

    def put(self, key: Any, value: Any) -> None:
        self._store[key] = value
        if len(self._store) > self.maxsize:
            del self._store[next(iter(self._store))]

    def copy(self) -> "WorkloadCache":
        c = WorkloadCache(self.maxsize)
        c._store = dict(self._store)
        c.hits = self.hits
        c.misses = self.misses
        return c


def compute_workload(
    graph: CurriculumGraph,
    activities: Mapping[str, Activity],
    state: LearnerState,
    goal: str,
    done_ids: Sequence[str] = (),
    model: Optional[MasteryModel] = None,
    cfg: EngineConfig = DEFAULT_CONFIG,
    cache: Optional[WorkloadCache] = None,
) -> tuple[dict[str, tuple[Activity, ...]], list[dict], dict[str, float]]:
    """Compute required concepts and projected workload to reach mastery (T3).

    - Required = goal plus graph.ancestors, minus evidence-mastered concepts.
    - Omitted concepts emit trace with p and responses.
    - For each required concept: queue unfinished lessons, then exercises chosen by
      difficulty policy, updating p with model.update(p, d, True, cfg.t_exercise),
      until p >= theta and responses >= k_responses.
    - D41 (cfg.allow_exercise_repeats): completed exercises may be repeated, unseen first, then
      the least-recently-attempted one. Off = W6 behaviour (completed exercises excluded).
    - T2.5 (cfg.projection_mode="expected"): pad to ceil(sum 1/P(correct)) exercises.
    - If exercises run out before reaching mastery: raises ContentInsufficientError.

    Returns:
        (workload_per_concept, trace_records, initial_projected_p)
    """
    if model is None:
        model = CustomBKT(cfg)

    done_set = frozenset(done_ids)
    all_needed = {goal} | graph.ancestors(goal)
    trace = []
    required_concepts: list[str] = []

    # Filter concepts in deterministic topological order
    for c in graph.topological_order():
        if c not in all_needed:
            continue
        c_state = state.concepts[c]
        if is_evidence_mastered(c_state, cfg):
            trace.append(
                {
                    "decision": "OMITTED",
                    "concept_id": c,
                    "reason": "ALREADY_EVIDENCE_MASTERED",
                    "p": c_state.p,
                    "responses": c_state.responses,
                }
            )
        else:
            required_concepts.append(c)

    ids_by_concept: dict[str, set[str]] = {}
    acts_by_concept: dict[str, list[Activity]] = {}  # T6.1 index, catalogue order
    for a in activities.values():
        ids_by_concept.setdefault(a.target_concept, set()).add(a.activity_id)
        acts_by_concept.setdefault(a.target_concept, []).append(a)
    catalogue = (
        (
            graph.fingerprint,
            hash(
                tuple(
                    (a.activity_id, a.target_concept, a.duration, a.difficulty)
                    for a in activities.values()
                )
            ),
        )
        if cache is not None
        else None
    )

    workload: dict[str, tuple[Activity, ...]] = {}
    projected_p: dict[str, float] = {}

    for c in required_concepts:
        c_state = state.concepts[c]
        c_ids = ids_by_concept.get(c, set())
        # With repeats (D41) the recency order of attempts matters, not just the set
        mine = (
            tuple(x for x in done_ids if x in c_ids)
            if cfg.allow_exercise_repeats
            else frozenset(done_set & c_ids)
        )
        model_id = (
            (type(model).__name__, id(model))
            if hasattr(model, "__dict__")
            else type(model).__name__
        )
        key = (c, c_state, mine, cfg, model_id, catalogue)

        if cache is not None:
            hit = cache.get(key)
            if hit is not None:
                concept_workload, concept_trace = hit
                trace.extend(concept_trace)
                workload[c] = concept_workload
                projected_p[c] = c_state.p
                continue

        this_concept_trace: list[dict[str, Any]] = []
        p = c_state.p
        responses = c_state.responses
        streak = c_state.correct_streak
        concept_workload_list: list[Activity] = []

        c_lessons = sorted(
            (a for a in acts_by_concept.get(c, ()) if a.type == ActivityType.LESSON),
            key=lambda a: a.activity_id,
        )

        # 0. Remediation repeat lesson if flagged (D20, D21, T4)
        if c_state.needs_remediation and c_lessons:
            rem_lesson = c_lessons[0]
            concept_workload_list.append(rem_lesson)
            p = learn(p, cfg.t_lesson)
            rem_trace = {
                "decision": "INSERTED",
                "concept_id": c,
                "activity_id": rem_lesson.activity_id,
                "reason": "REMEDIATION_INSERTED",
                "p": c_state.p,
            }
            this_concept_trace.append(rem_trace)
            trace.append(rem_trace)

        # 1. Unfinished lessons in deterministic order
        for lesson in c_lessons:
            if lesson.activity_id not in done_set and lesson not in concept_workload_list:
                concept_workload_list.append(lesson)
                p = learn(p, cfg.t_lesson)

        # 2. Exercises chosen by difficulty policy
        c_exercises = sorted(
            (a for a in acts_by_concept.get(c, ()) if a.type == ActivityType.EXERCISE),
            key=lambda a: a.activity_id,
        )
        if cfg.allow_exercise_repeats:
            # D41: unseen exercises first, then the least-recently-attempted one
            last_seen = {aid: i for i, aid in enumerate(done_ids) if aid in c_ids}
        else:
            available_exercises = [a for a in c_exercises if a.activity_id not in done_set]
        tick = len(done_ids)

        def candidates() -> list[Activity]:
            if not cfg.allow_exercise_repeats:
                return available_exercises
            unseen = [a for a in c_exercises if a.activity_id not in last_seen]
            if unseen or not c_exercises:
                return unseen
            return [min(c_exercises, key=lambda a: last_seen[a.activity_id])]

        def take(chosen: Activity) -> None:
            nonlocal tick
            concept_workload_list.append(chosen)
            if cfg.allow_exercise_repeats:
                last_seen[chosen.activity_id] = tick
                tick += 1
            else:
                available_exercises.remove(chosen)

        expected_items = 0.0
        n_exercises = 0
        while not mastered_by(p, responses, streak, cfg):
            pool = candidates()
            if not pool or n_exercises >= _MAX_PROJECTED_EXERCISES:
                raise ContentInsufficientError(
                    f"Insufficient exercise content for concept '{c}' to reach "
                    f"theta={cfg.theta} and responses={cfg.k_responses} (current p={p:.4f}, responses={responses})"
                )
            chosen = select_exercise(pool, p, cfg.target_success, model, cfg)
            take(chosen)
            # T2.5: an item answered correctly with probability P(correct) costs 1/P items on average
            expected_items += 1.0 / max(model.predict_correct(p, chosen.difficulty), 1e-9)
            p = model.update(p, chosen.difficulty, True, cfg.t_exercise)
            responses += 1
            streak += 1  # projection assumes correct answers
            n_exercises += 1

        if cfg.projection_mode == "expected":
            # Pad to the expected item count (never fewer than the optimistic projection)
            for _ in range(math.ceil(expected_items - 1e-9) - n_exercises):
                pool = candidates()
                if not pool:
                    break
                take(select_exercise(pool, p, cfg.target_success, model, cfg))

        concept_workload_tuple = tuple(concept_workload_list)
        workload[c] = concept_workload_tuple
        projected_p[c] = c_state.p

        if cache is not None:
            cache.put(key, (concept_workload_tuple, tuple(this_concept_trace)))

    return workload, trace, projected_p
