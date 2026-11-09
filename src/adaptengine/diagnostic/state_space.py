"""Prerequisite-consistent knowledge-state diagnostic (W7 T3.6, R§8.3).

The latent state is a mastery *pattern* over the goal concepts that respects the DAG: a concept
can be mastered only if all its in-goal prerequisites are. The posterior over patterns is exact
(enumeration), using the engine's observation model through the MasteryModel protocol:
P(correct | mastered) = predict_correct(1, d), P(correct | not) = predict_correct(0, d).
Items are chosen by expected information gain over patterns; per-concept p is the marginal.
Above MAX_CONCEPTS goal concepts it falls back to the per-concept AdaptiveDiagnostic.
"""

from __future__ import annotations

import math
from dataclasses import replace
from types import MappingProxyType
from typing import Callable, Mapping, Optional, Sequence

from ..core.config import DEFAULT_CONFIG, EngineConfig
from ..core.schema import Activity, ActivityType
from ..core.validators import check_bool
from ..curriculum.graph import CurriculumGraph
from ..learner.adapter import CustomBKT, MasteryModel
from ..learner.mastery import entropy
from ..learner.state import ConceptStatus, LearnerState
from .engine import (
    AdaptiveDiagnostic,
    ConceptDiagnosticResult,
    DiagnosticItemLog,
    DiagnosticResult,
    StopReason,
)
from .scoring import candidate_sort_key

MAX_CONCEPTS = 12


def consistent_patterns(graph: CurriculumGraph, concepts: Sequence[str]) -> list[frozenset[str]]:
    """All mastered-sets closed under (in-goal) prerequisites, built in topological order."""
    goal = set(concepts)
    pats: list[frozenset[str]] = [frozenset()]
    for c in (x for x in graph.topological_order() if x in goal):
        pre = [q for q in graph.prerequisites(c) if q in goal]
        pats += [s | {c} for s in pats if all(q in s for q in pre)]
    return pats


def _h(ws: Sequence[float]) -> float:
    return -sum(w * math.log2(w) for w in ws if w > 0.0)


class StateSpaceDiagnostic:
    def __init__(
        self,
        graph: CurriculumGraph,
        activities: Mapping[str, Activity],
        config: EngineConfig = DEFAULT_CONFIG,
        model: Optional[MasteryModel] = None,
    ):
        self.graph, self.activities, self.config = graph, activities, config
        self.model = model if model is not None else CustomBKT(config)

    def run(
        self,
        state: LearnerState,
        response_provider: Callable[[Activity], bool],
        goal_concepts: Optional[Sequence[str]] = None,
        session_id: Optional[str] = None,
    ) -> DiagnosticResult:
        cfg, model = self.config, self.model
        concepts = sorted(goal_concepts or self.graph.concepts())
        if len(concepts) > MAX_CONCEPTS:
            return AdaptiveDiagnostic(self.graph, self.activities, cfg, model).run(
                state, response_provider, goal_concepts, session_id=session_id
            )
        prior = {}
        for c in concepts:
            uc = state.concepts[c]
            pop = cfg.prior_mode == "population" and uc.responses == 0 and uc.p == cfg.p0
            prior[c] = cfg.population_p0 if pop else uc.p
        pats = consistent_patterns(self.graph, concepts)
        w = [math.prod(prior[c] if c in s else 1.0 - prior[c] for c in concepts) for s in pats]
        w = [x / sum(w) for x in w]
        items = sorted(
            (
                a
                for a in self.activities.values()
                if a.target_concept in prior and a.type == ActivityType.EXERCISE
            ),
            key=lambda a: a.activity_id,
        )
        p_ok = {
            a.activity_id: (
                model.predict_correct(1.0, a.difficulty),
                model.predict_correct(0.0, a.difficulty),
            )
            for a in items
        }

        def marginal(ws, c):
            return sum(x for x, s in zip(ws, pats) if c in s)

        def posterior(ws, a, y):
            hi, lo = p_ok[a.activity_id]
            new = [
                x * ((hi if y else 1 - hi) if a.target_concept in s else (lo if y else 1 - lo))
                for x, s in zip(ws, pats)
            ]
            z = sum(new)
            return [x / z for x in new], z

        asked: set[str] = set()
        n_items = {c: 0 for c in concepts}
        log: list[DiagnosticItemLog] = []
        while len(log) < cfg.n_max:
            if max(entropy(marginal(w, c)) for c in concepts) <= cfg.h_stop:
                break
            h0, best = _h(w), None
            for a in items:
                if a.activity_id in asked or n_items[a.target_concept] >= cfg.concept_cap:
                    continue
                post_r, pr = posterior(w, a, True)
                post_w, _ = posterior(w, a, False)
                eig = max(0.0, h0 - (pr * _h(post_r) + (1 - pr) * _h(post_w)))
                key = candidate_sort_key(eig, a.difficulty, a.activity_id)
                if best is None or key < best[0]:
                    best = (key, eig, a)
            if best is None:
                break
            _, eig, a = best
            y = response_provider(a)
            check_bool(y, "response_provider return")
            c = a.target_concept
            p_before = marginal(w, c)
            w, _ = posterior(w, a, y)
            asked.add(a.activity_id)
            n_items[c] += 1
            log.append(
                DiagnosticItemLog(c, a.activity_id, a.difficulty, y, p_before, marginal(w, c), eig)
            )

        sid = session_id if session_id is not None else "1"
        new_concepts = dict(state.concepts)
        results = {}
        done = max(entropy(marginal(w, c)) for c in concepts) <= cfg.h_stop
        for c in concepts:
            p = min(1.0, max(0.0, marginal(w, c)))
            mine = [x for x in log if x.concept_id == c]
            old = new_concepts[c]
            new_concepts[c] = replace(
                old,
                p=p,
                responses=old.responses + len(mine),
                correct_responses=old.correct_responses + sum(x.response for x in mine),
                status=ConceptStatus.ASSESSED if mine else old.status,
                seen_attempt_ids=old.seen_attempt_ids
                | {f"diag-{sid}-{c}-{i + 1}" for i in range(len(mine))},
            )
            if done:
                reason = StopReason.ENTROPY
            elif len(log) >= cfg.n_max:
                reason = StopReason.GLOBAL_CAP
            elif n_items[c] >= cfg.concept_cap:
                reason = StopReason.CONCEPT_CAP
            else:
                reason = StopReason.NO_ITEMS
            results[c] = ConceptDiagnosticResult(
                c, p, entropy(p), new_concepts[c].status, n_items[c], reason
            )
        return DiagnosticResult(
            state=LearnerState(concepts=new_concepts),
            concept_results=MappingProxyType(results),
            item_log=tuple(log),
            total_items=len(log),
        )
