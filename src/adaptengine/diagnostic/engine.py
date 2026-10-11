from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Optional, Sequence, Any
from ..core.schema import Activity, ActivityType
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.validators import check_bool
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerState, LearnerConcept, ConceptStatus
from ..learner.mastery import update_mastery
from .scoring import compute_eig, candidate_sort_key


class StopReason(str, Enum):
    ENTROPY = "ENTROPY"
    CONCEPT_CAP = "CONCEPT_CAP"
    GLOBAL_CAP = "GLOBAL_CAP"
    NO_ITEMS = "NO_ITEMS"
    SKIPPED_ANCESTOR_UNMASTERED = "SKIPPED_ANCESTOR_UNMASTERED"
    NOT_REACHED = "NOT_REACHED"


@dataclass(frozen=True)
class DiagnosticItemLog:
    concept_id: str
    activity_id: str
    difficulty: float
    response: bool
    p_before: float
    p_after: float
    eig: float


@dataclass(frozen=True)
class ConceptDiagnosticResult:
    concept_id: str
    p: float
    h: float
    status: ConceptStatus
    n_items: int
    stop_reason: StopReason


@dataclass(frozen=True)
class DiagnosticResult:
    state: LearnerState
    concept_results: dict[str, ConceptDiagnosticResult]
    item_log: tuple[DiagnosticItemLog, ...]
    total_items: int


class AdaptiveDiagnostic:
    def __init__(
        self,
        graph: CurriculumGraph,
        activities: Mapping[str, Activity],
        config: EngineConfig = DEFAULT_CONFIG,
    ):
        self.graph = graph
        self.activities = activities
        self.config = config

    def run(
        self,
        state: LearnerState,
        response_provider: Callable[[Activity], bool],
        goal_concepts: Optional[Sequence[str]] = None,
        model: Optional[Any] = None,
    ) -> DiagnosticResult:
        """Run the adaptive diagnostic M2."""
        if goal_concepts is None:
            goal_set = set(self.graph.concepts())
        else:
            goal_set = set(goal_concepts)

        # Stable topological order (ties by concept_id lexicographically)
        ordered_concepts = [c for c in self.graph.topological_order() if c in goal_set]

        updated_concepts = dict(state.concepts)
        concept_results: dict[str, ConceptDiagnosticResult] = {}
        item_log: list[DiagnosticItemLog] = []
        asked_activities: set[str] = set()
        skipped_concepts: set[str] = set()
        total_items = 0

        for concept_id in ordered_concepts:
            current_c = updated_concepts[concept_id]

            if concept_id in skipped_concepts:
                concept_results[concept_id] = ConceptDiagnosticResult(
                    concept_id=concept_id,
                    p=current_c.p,
                    h=current_c.uncertainty,
                    status=current_c.status,
                    n_items=0,
                    stop_reason=StopReason.SKIPPED_ANCESTOR_UNMASTERED,
                )
                continue

            if total_items >= self.config.n_max:
                concept_results[concept_id] = ConceptDiagnosticResult(
                    concept_id=concept_id,
                    p=current_c.p,
                    h=current_c.uncertainty,
                    status=current_c.status,
                    n_items=0,
                    stop_reason=StopReason.GLOBAL_CAP,
                )
                continue

            n_concept_items = 0
            c_stop_reason: Optional[StopReason] = None

            candidates = [
                a
                for a in self.activities.values()
                if a.target_concept == concept_id and a.type == ActivityType.EXERCISE
            ]

            while c_stop_reason is None and n_concept_items < self.config.concept_cap:
                if total_items >= self.config.n_max:
                    c_stop_reason = StopReason.GLOBAL_CAP
                    break

                unasked = [a for a in candidates if a.activity_id not in asked_activities]
                if not unasked:
                    c_stop_reason = StopReason.NO_ITEMS
                    break

                # Score candidates by EIG and sort deterministically (D10)
                scored = []
                for act in unasked:
                    eig = compute_eig(current_c.p, act, self.config)
                    key = candidate_sort_key(eig, act.difficulty, act.activity_id)
                    scored.append((key, eig, act))

                scored.sort(key=lambda x: x[0])
                _, best_eig, best_act = scored[0]

                # Obtain response
                raw_resp = response_provider(best_act)
                check_bool(raw_resp, "response_provider return")
                asked_activities.add(best_act.activity_id)

                p_before = current_c.p
                attempt_id = f"diag-{concept_id}-{n_concept_items + 1}"

                if model is not None:
                    p_after = model.update(
                        p_before, best_act.difficulty, raw_resp, self.config.t_diag
                    )
                else:
                    p_after = update_mastery(
                        p_before, best_act.difficulty, raw_resp, self.config.t_diag, self.config
                    )

                new_c = LearnerConcept(
                    concept_id=concept_id,
                    p=p_after,
                    lessons_done=current_c.lessons_done,
                    responses=current_c.responses + 1,
                    correct_responses=current_c.correct_responses + (1 if raw_resp else 0),
                    status=ConceptStatus.ASSESSED,
                    seen_attempt_ids=current_c.seen_attempt_ids | {attempt_id},
                    half_life_days=current_c.half_life_days,
                    last_practice_day=current_c.last_practice_day,
                    n_reviews=current_c.n_reviews,
                )
                updated_concepts[concept_id] = new_c
                current_c = new_c
                n_concept_items += 1
                total_items += 1

                item_log.append(
                    DiagnosticItemLog(
                        concept_id=concept_id,
                        activity_id=best_act.activity_id,
                        difficulty=best_act.difficulty,
                        response=raw_resp,
                        p_before=p_before,
                        p_after=p_after,
                        eig=best_eig,
                    )
                )

                if current_c.uncertainty <= self.config.h_stop:
                    c_stop_reason = StopReason.ENTROPY
                    break

            if c_stop_reason is None:
                if n_concept_items >= self.config.concept_cap:
                    c_stop_reason = StopReason.CONCEPT_CAP
                elif total_items >= self.config.n_max:
                    c_stop_reason = StopReason.GLOBAL_CAP
                else:
                    c_stop_reason = StopReason.NO_ITEMS

            final_c = updated_concepts[concept_id]
            concept_results[concept_id] = ConceptDiagnosticResult(
                concept_id=concept_id,
                p=final_c.p,
                h=final_c.uncertainty,
                status=final_c.status,
                n_items=n_concept_items,
                stop_reason=c_stop_reason,
            )

            # Descendant skipping (D8)
            if final_c.p < self.config.skip_threshold:
                descendants = self.graph.descendants(concept_id)
                for desc in descendants:
                    if desc in goal_set and desc not in concept_results:
                        skipped_concepts.add(desc)

        # Ensure any remaining unprobed concepts in goal_set are recorded
        for cid in ordered_concepts:
            if cid not in concept_results:
                c = updated_concepts[cid]
                concept_results[cid] = ConceptDiagnosticResult(
                    concept_id=cid,
                    p=c.p,
                    h=c.uncertainty,
                    status=c.status,
                    n_items=0,
                    stop_reason=StopReason.GLOBAL_CAP,
                )

        return DiagnosticResult(
            state=LearnerState(concepts=updated_concepts),
            concept_results=concept_results,
            item_log=tuple(item_log),
            total_items=total_items,
        )
