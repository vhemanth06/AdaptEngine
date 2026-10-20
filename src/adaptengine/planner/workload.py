from typing import Mapping, Sequence, Optional
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


def compute_workload(
    graph: CurriculumGraph,
    activities: Mapping[str, Activity],
    state: LearnerState,
    goal: str,
    done_ids: Sequence[str] = (),
    model: Optional[MasteryModel] = None,
    cfg: EngineConfig = DEFAULT_CONFIG,
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
                    "reason": "EVIDENCE_MASTERED",
                    "p": c_state.p,
                    "responses": c_state.responses,
                }
            )
        else:
            required_concepts.append(c)

    workload: dict[str, tuple[Activity, ...]] = {}
    projected_p: dict[str, float] = {}

    for c in required_concepts:
        c_state = state.concepts[c]
        p = c_state.p
        responses = c_state.responses
        concept_workload: list[Activity] = []

        # 1. Unfinished lessons in deterministic order
        c_lessons = sorted(
            [
                a
                for a in activities.values()
                if a.target_concept == c and a.type == ActivityType.LESSON
            ],
            key=lambda a: a.activity_id,
        )
        for lesson in c_lessons:
            if lesson.activity_id not in done_set:
                concept_workload.append(lesson)
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
            concept_workload.append(chosen)
            p = model.update(p, chosen.difficulty, True, cfg.t_exercise)
            responses += 1

        workload[c] = tuple(concept_workload)
        projected_p[c] = c_state.p

    return workload, trace, projected_p
