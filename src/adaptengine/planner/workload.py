from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.schema import Activity, ActivityType
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerState, is_evidence_mastered
from ..learner.mastery import learn
from ..learner.adapter import MasteryModel, CustomBKT
from .difficulty import select_exercise


class ContentInsufficientError(Exception):
    """Raised when available exercises are insufficient to achieve mastery threshold."""

    pass


class WorkloadCache:
    """Caller-owned memo of per-concept workload projections (explicit value, no hidden state)."""

    def __init__(self):
        self._store: dict[Any, Any] = {}
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

    def copy(self) -> "WorkloadCache":
        c = WorkloadCache()
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
    for a in activities.values():
        ids_by_concept.setdefault(a.target_concept, set()).add(a.activity_id)

    workload: dict[str, tuple[Activity, ...]] = {}
    projected_p: dict[str, float] = {}

    for c in required_concepts:
        c_state = state.concepts[c]
        mine = frozenset(done_set & ids_by_concept.get(c, set()))
        model_id = (
            (type(model).__name__, id(model))
            if hasattr(model, "__dict__")
            else type(model).__name__
        )
        key = (c, c_state, mine, cfg, model_id)

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
        concept_workload_list: list[Activity] = []

        c_lessons = sorted(
            [
                a
                for a in activities.values()
                if a.target_concept == c and a.type == ActivityType.LESSON
            ],
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
        available_exercises = [
            a
            for a in activities.values()
            if a.target_concept == c
            and a.type == ActivityType.EXERCISE
            and a.activity_id not in done_set
        ]

        while not (p >= cfg.theta and responses >= cfg.k_responses):
            if not available_exercises:
                raise ContentInsufficientError(
                    f"Insufficient exercise content for concept '{c}' to reach "
                    f"theta={cfg.theta} and responses={cfg.k_responses} (current p={p:.4f}, responses={responses})"
                )
            chosen = select_exercise(available_exercises, p, cfg.target_success, model, cfg)
            available_exercises.remove(chosen)
            concept_workload_list.append(chosen)
            p = model.update(p, chosen.difficulty, True, cfg.t_exercise)
            responses += 1

        concept_workload_tuple = tuple(concept_workload_list)
        workload[c] = concept_workload_tuple
        projected_p[c] = c_state.p

        if cache is not None:
            cache.put(key, (concept_workload_tuple, tuple(this_concept_trace)))

    return workload, trace, projected_p
