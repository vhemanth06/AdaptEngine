"""Bisection diagnostic over prerequisite-closed knowledge states (Plan 3, F1, D49-D57).

The learner's mastered set is one knowledge state (a down-set of the DAG); every answer reweights
all states, so it informs many concepts at once. Questions maximise the information about the
whole state, I(Y; K), which is the per-concept EIG formula evaluated at the joint marginal (D52):
with noiseless items it asks the concept nearest 50%, i.e. binary search. The run stops when the
most probable state reaches bisection_stop_confidence (D55), at the budget (D56), or when no
informative item is left. The output is the usual DiagnosticResult (F1.3.8).
"""

from __future__ import annotations

import math
from dataclasses import replace
from types import MappingProxyType
from typing import Callable, Mapping, Optional, Sequence

from ..core.config import DEFAULT_CONFIG, EngineConfig
from ..core.errors import UnknownConceptError
from ..core.schema import Activity, ActivityType
from ..core.validators import check_bool
from ..curriculum.graph import CurriculumGraph
from ..learner.adapter import CustomBKT, MasteryModel
from ..learner.evidence import checks_to_confirm
from ..learner.mastery import entropy
from ..learner.state import ConceptStatus, LearnerState, is_evidence_mastered
from .engine import ConceptDiagnosticResult, DiagnosticItemLog, DiagnosticResult, StopReason
from .knowledge_space import make_posterior, select_scope
from .scoring import candidate_sort_key

INFO_FLOOR = 1e-9  # items below this information count as uninformative (F1.3.6)


def _h2(x: float) -> float:
    return entropy(min(1.0, max(0.0, x)))


def item_information(q: float, hi: float, lo: float) -> float:
    """I(Y; K) for an item with P(correct | known) = hi, P(correct | not known) = lo, at marginal q
    (F1.3.4): h(q hi + (1 - q) lo) - q h(hi) - (1 - q) h(lo)."""
    return max(0.0, _h2(q * hi + (1.0 - q) * lo) - q * _h2(hi) - (1.0 - q) * _h2(lo))


class BisectionDiagnostic:
    def __init__(
        self,
        graph: CurriculumGraph,
        activities: Mapping[str, Activity],
        config: EngineConfig = DEFAULT_CONFIG,
        model: Optional[MasteryModel] = None,
    ):
        self.graph, self.activities, self.config = graph, activities, config
        self.model = model if model is not None else CustomBKT(config)

    def _factors(self, state: LearnerState, scope: Sequence[str]) -> dict:
        """Per-concept prior / earlier-evidence factors (F1.3.1; see knowledge_space)."""
        cfg, out = self.config, {}
        p0 = min(max(cfg.p0, 1e-6), 1 - 1e-6)
        for c in scope:
            uc = state.concepts[c]
            if cfg.bisection_prior == "independent_p0":
                a, b = p0, 1.0 - p0
            else:
                a = b = 1.0
            if uc.responses > 0:  # fold in earlier answers: posterior odds over prior odds
                p = min(max(uc.p, 1e-6), 1 - 1e-6)
                a, b = a * p / p0, b * (1.0 - p) / (1.0 - p0)
            if (a, b) != (1.0, 1.0):
                out[c] = (a, b)
        return out

    def budget(self, bits: float, items: Sequence[Activity], model: MasteryModel) -> tuple:
        """(n_max, questions per bit) per D56 / F1.3.7."""
        cfg = self.config
        if cfg.bisection_alpha is not None:
            q_bit = float(cfg.bisection_alpha)
        else:
            best = max(
                (
                    item_information(
                        0.5,
                        model.predict_correct(1.0, a.difficulty),
                        model.predict_correct(0.0, a.difficulty),
                    )
                    for a in items
                ),
                default=0.0,
            )
            q_bit = 1.0 / best if best > 0 else float(cfg.bisection_n_ceiling)
        want = math.ceil(bits * q_bit - 1e-9)
        return min(len(items), max(cfg.bisection_n_min, min(cfg.bisection_n_ceiling, want))), q_bit

    def run(
        self,
        state: LearnerState,
        response_provider: Callable[[Activity], bool],
        goal_concepts=None,
        model: Optional[MasteryModel] = None,
        session_id: Optional[str] = None,
        item_limit: Optional[int] = None,
    ) -> DiagnosticResult:
        cfg = self.config
        model = model if model is not None else self.model
        if goal_concepts is not None:
            for g in goal_concepts:
                if g not in self.graph.concepts():
                    raise UnknownConceptError(f"Goal concept '{g}' not in graph")
        sid = session_id if session_id is not None else "1"
        scope = select_scope(self.graph, goal_concepts, cfg.bisection_scope)
        post = make_posterior(
            self.graph,
            scope,
            self._factors(state, scope),
            cfg.bisection_exact_state_limit,
            cfg.bisection_samples,
            cfg.bisection_seed,
        )
        in_scope = set(scope)
        items = sorted(
            (
                a
                for a in self.activities.values()
                if a.type == ActivityType.EXERCISE and a.target_concept in in_scope
            ),
            key=lambda a: a.activity_id,
        )
        ok = {
            a.activity_id: (
                model.predict_correct(1.0, a.difficulty),
                model.predict_correct(0.0, a.difficulty),
            )
            for a in items
        }
        n_max, q_bit = self.budget(post.bits, items, model)
        limit = n_max if item_limit is None else min(n_max, item_limit)

        asked: set[str] = set()
        answers: dict[str, list[bool]] = {c: [] for c in scope}
        log: list[DiagnosticItemLog] = []
        run_reason = None
        while True:
            if post.top_state()[1] >= cfg.bisection_stop_confidence:
                run_reason = StopReason.CONFIDENT
                break
            if len(log) >= limit:
                run_reason = StopReason.GLOBAL_CAP
                break
            marg = {c: post.marginal(c) for c in scope}
            best = None
            for a in items:
                c = a.target_concept
                if a.activity_id in asked or len(answers[c]) >= cfg.bisection_concept_cap:
                    continue
                info = item_information(marg[c], *ok[a.activity_id])
                key = candidate_sort_key(info, a.difficulty, a.activity_id)
                if best is None or key < best[0]:
                    best = (key, info, a)
            if best is None or best[1] < INFO_FLOOR:
                run_reason = StopReason.NO_ITEMS
                break
            _, info, a = best
            y = response_provider(a)
            check_bool(y, "response_provider return")
            c = a.target_concept
            hi, lo = ok[a.activity_id]
            post.update(c, hi if y else 1.0 - hi, lo if y else 1.0 - lo)
            asked.add(a.activity_id)
            answers[c].append(y)
            log.append(
                DiagnosticItemLog(
                    c, a.activity_id, a.difficulty, y, marg[c], post.marginal(c), info
                )
            )

        return self._result(state, scope, post, answers, log, run_reason, sid, model, n_max, q_bit)

    def _result(self, state, scope, post, answers, log, run_reason, sid, model, n_max, q_bit):
        cfg = self.config
        new_concepts = dict(state.concepts)
        results = {}
        for c in scope:
            old, ys = new_concepts[c], answers[c]
            p = min(1.0, max(0.0, post.marginal(c)))
            streak = old.correct_streak
            for y in ys:
                streak = streak + 1 if y else 0
            new = replace(
                old,
                p=p,
                responses=old.responses + len(ys),
                correct_responses=old.correct_responses + sum(ys),
                correct_streak=streak,
                status=ConceptStatus.ASSESSED if ys else old.status,
                seen_attempt_ids=old.seen_attempt_ids
                | {f"diag-{sid}-{c}-{i + 1}" for i in range(len(ys))},
            )
            if cfg.confirm_diag_confident:
                new = self._flag(new, len(ys), c, model)
            new_concepts[c] = new
            if not ys:
                reason = StopReason.INFERRED
            elif len(ys) >= cfg.bisection_concept_cap:
                reason = StopReason.CONCEPT_CAP
            else:
                reason = run_reason
            results[c] = ConceptDiagnosticResult(c, p, entropy(p), new.status, len(ys), reason)
        top, top_p = post.top_state()
        info = {
            "mode": post.mode,
            "n_states": post.n_states,
            "bits": post.bits,
            "n_max": n_max,
            "q_bit": q_bit,
            "top_state": tuple(c for c in scope if c in top),
            "top_state_p": top_p,
            "scope": tuple(scope),
        }
        return DiagnosticResult(
            state=LearnerState(concepts=new_concepts),
            concept_results=MappingProxyType(results),
            item_log=tuple(log),
            total_items=len(log),
            info=MappingProxyType(info),
        )

    def _flag(self, concept, n_direct: int, c: str, model: MasteryModel):
        """Confirmation flags at the end of the diagnostic (F1.4.1, F1.4.3)."""
        cfg = self.config
        if is_evidence_mastered(concept, cfg):
            return concept
        if n_direct >= cfg.confirm_min_direct and concept.p >= 1.0 - cfg.confirm_epsilon:
            return replace(concept, confirmed=True, diag_confident=False)
        # a candidate for checks only if a few correct answers on its best item could confirm it
        exs = [
            a
            for a in self.activities.values()
            if a.type == ActivityType.EXERCISE and a.target_concept == c
        ]
        if exs and min(checks_to_confirm(concept.p, a.difficulty, model, cfg) for a in exs) <= (
            cfg.confirm_max_checks
        ):
            return replace(concept, diag_confident=True)
        return concept
