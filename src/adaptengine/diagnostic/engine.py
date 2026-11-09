from dataclasses import dataclass, replace
from types import MappingProxyType
from enum import Enum
from typing import Callable, Mapping, Optional, Sequence
from ..core.errors import UnknownConceptError
from ..core.schema import Activity, ActivityType
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.validators import check_bool
from ..curriculum.graph import CurriculumGraph
from ..learner.state import LearnerState, ConceptStatus
from ..learner.adapter import MasteryModel, CustomBKT
from ..learner.evidence import update_concept_evidence
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
    concept_results: Mapping[str, ConceptDiagnosticResult]  # read-only (T9.1 hygiene)
    item_log: tuple[DiagnosticItemLog, ...]
    total_items: int


class AdaptiveDiagnostic:
    def __init__(
        self,
        graph: CurriculumGraph,
        activities: Mapping[str, Activity],
        config: EngineConfig = DEFAULT_CONFIG,
        model: Optional[MasteryModel] = None,
    ):
        self.graph = graph
        self.activities = activities
        self.config = config
        self.model = model if model is not None else CustomBKT(config)

    def _prune(self, concept_id, p, goal_set, results, skipped, concepts) -> None:
        """Apply the configured pruning after a concept's diagnosis ends (D8, T3.2).

        hard: p < skip_threshold skips every undiagnosed descendant (W6 behaviour).
        soft: undiagnosed descendants keep being assessed, but their prior is capped at p.
        none: no effect.
        """
        mode = self.config.pruning_mode
        if mode == "none":
            return
        for desc in sorted(self.graph.descendants(concept_id)):
            if desc not in goal_set or desc in results:
                continue
            if mode == "hard":
                if p < self.config.skip_threshold:
                    skipped.add(desc)
            elif concepts[desc].responses == 0 and concepts[desc].p > p:
                concepts[desc] = replace(concepts[desc], p=p)

    def _ask(self, concept_id, current_c, act, eig, n_done, response_provider, model, sid):
        raw_resp = response_provider(act)
        check_bool(raw_resp, "response_provider return")
        new_c, _ = update_concept_evidence(
            current_c,
            act.difficulty,
            raw_resp,
            transition=self.config.t_diag,
            model=model,
            cfg=self.config,
            day=None,
            attempt_id=f"diag-{sid}-{concept_id}-{n_done + 1}",
        )
        log = DiagnosticItemLog(
            concept_id=concept_id,
            activity_id=act.activity_id,
            difficulty=act.difficulty,
            response=raw_resp,
            p_before=current_c.p,
            p_after=new_c.p,
            eig=eig,
        )
        return new_c, log

    def _run_frontier(self, ordered, goal_set, concepts, response_provider, model, sid):
        """T3.2 selection_scope="frontier": each step picks the max-EIG unasked item over every
        open concept whose in-goal prerequisites are finished; per-concept stops still apply."""
        cfg = self.config
        results: dict[str, ConceptDiagnosticResult] = {}
        skipped: set[str] = set()
        n_items = {c: 0 for c in ordered}
        asked: set[str] = set()
        item_log: list[DiagnosticItemLog] = []
        total = 0
        exercises = {
            c: [
                a
                for a in self.activities.values()
                if a.target_concept == c and a.type == ActivityType.EXERCISE
            ]
            for c in ordered
        }

        def finish(c, reason):
            fc = concepts[c]
            results[c] = ConceptDiagnosticResult(
                c, fc.p, fc.uncertainty, fc.status, n_items[c], reason
            )
            if reason != StopReason.SKIPPED_ANCESTOR_UNMASTERED:
                self._prune(c, fc.p, goal_set, results, skipped, concepts)

        while True:
            for c in ordered:  # resolve skips and exhausted concepts first
                if c not in results and c in skipped:
                    finish(c, StopReason.SKIPPED_ANCESTOR_UNMASTERED)
                elif c not in results and not any(a.activity_id not in asked for a in exercises[c]):
                    finish(c, StopReason.NO_ITEMS)
            open_c = [
                c
                for c in ordered
                if c not in results
                and all(q in results for q in self.graph.prerequisites(c) if q in goal_set)
            ]
            if not open_c or total >= cfg.n_max:
                break
            scored = []
            for c in open_c:
                for act in exercises[c]:
                    if act.activity_id not in asked:
                        eig = compute_eig(concepts[c].p, act, cfg, model=model)
                        key = candidate_sort_key(eig, act.difficulty, act.activity_id)
                        scored.append((key, eig, c, act))
            scored.sort(key=lambda x: x[0])
            _, eig, c, act = scored[0]
            asked.add(act.activity_id)
            concepts[c], rec = self._ask(
                c, concepts[c], act, eig, n_items[c], response_provider, model, sid
            )
            item_log.append(rec)
            n_items[c] += 1
            total += 1
            if n_items[c] >= cfg.min_items_per_concept and concepts[c].uncertainty <= cfg.h_stop:
                finish(c, StopReason.ENTROPY)
            elif n_items[c] >= cfg.concept_cap:
                finish(c, StopReason.CONCEPT_CAP)

        for c in ordered:
            if c not in results:
                finish(c, StopReason.GLOBAL_CAP if total >= cfg.n_max else StopReason.NOT_REACHED)
        return DiagnosticResult(
            state=LearnerState(concepts=concepts),
            concept_results=MappingProxyType(dict(results)),
            item_log=tuple(item_log),
            total_items=total,
        )

    def run(
        self,
        state: LearnerState,
        response_provider: Callable[[Activity], bool],
        goal_concepts: Optional[Sequence[str]] = None,
        model: Optional[MasteryModel] = None,
        session_id: Optional[str] = None,
    ) -> DiagnosticResult:
        """Run the adaptive diagnostic M2."""
        if goal_concepts is None:
            goal_set = set(self.graph.concepts())
        else:
            for g in goal_concepts:
                if g not in self.graph.concepts():
                    raise UnknownConceptError(f"Goal concept '{g}' not in graph")
            goal_set = set(goal_concepts)

        active_model = model if model is not None else self.model
        sid = session_id if session_id is not None else "1"

        # Stable topological order (ties by concept_id lexicographically)
        ordered_concepts = [c for c in self.graph.topological_order() if c in goal_set]

        updated_concepts = dict(state.concepts)
        if self.config.prior_mode == "population":
            # T3.2: concepts still at the flat cold-start prior (no evidence, p == p0) start at a
            # population base rate instead; a p set by the caller is kept
            for c in ordered_concepts:
                uc = updated_concepts[c]
                if uc.responses == 0 and uc.p == self.config.p0:
                    updated_concepts[c] = replace(uc, p=self.config.population_p0)
        if self.config.selection_scope == "frontier":
            return self._run_frontier(
                ordered_concepts, goal_set, updated_concepts, response_provider, active_model, sid
            )
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

                # Score candidates by EIG using active model and sort deterministically (D10)
                scored = []
                for act in unasked:
                    eig = compute_eig(current_c.p, act, self.config, model=active_model)
                    key = candidate_sort_key(eig, act.difficulty, act.activity_id)
                    scored.append((key, eig, act))

                scored.sort(key=lambda x: x[0])
                _, best_eig, best_act = scored[0]

                # Obtain response
                raw_resp = response_provider(best_act)
                check_bool(raw_resp, "response_provider return")
                asked_activities.add(best_act.activity_id)

                p_before = current_c.p
                attempt_id = f"diag-{sid}-{concept_id}-{n_concept_items + 1}"

                new_c, changed = update_concept_evidence(
                    current_c,
                    best_act.difficulty,
                    raw_resp,
                    transition=self.config.t_diag,
                    model=active_model,
                    cfg=self.config,
                    day=None,
                    attempt_id=attempt_id,
                )
                p_after = new_c.p
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

                if (
                    n_concept_items >= self.config.min_items_per_concept
                    and current_c.uncertainty <= self.config.h_stop
                ):
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

            # Descendant skipping (D8) / soft prior cap (T3.2)
            self._prune(
                concept_id, final_c.p, goal_set, concept_results, skipped_concepts, updated_concepts
            )

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
            concept_results=MappingProxyType(concept_results),
            item_log=tuple(item_log),
            total_items=total_items,
        )
