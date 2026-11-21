"""Diagnostic arms for E2 and E3 Part B, scripted learners, and scoring against truth.

Arms: prior_only (no questions), sweep and bisection (Engine.diagnose), fixed@n (round-robin over
concepts), irt_cat_global@n and irt_cat_per_concept@n (external 2PL CAT: max Fisher information,
EAP on a 201-point grid, P(mastered) = posterior mass of theta >= 0.70). n = bisection's question
count for the same learner. p is scored as P(mastered) against binary truth 1[theta >= 0.70] at
diagnostic time; next-answer Brier uses an independent `probe` draw of every exercise.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from adaptengine.core.schema import ActivityType
from adaptengine.learner.state import ConceptStatus, LearnerConcept, LearnerState

from .simulator import TRUE_MASTERY, keyed_uniform, make_learner

SCRIPTED = ("advanced", "advanced_minus_goal", "mid", "novice")
GRID = [i / 200 for i in range(201)]
IRT_A = 3.0


def exercises(engine) -> list:
    return sorted(
        (a for a in engine.activities.values() if a.type == ActivityType.EXERCISE),
        key=lambda a: a.activity_id,
    )


def run_engine_diagnostic(engine, answer: Callable, seed: int, goal_concepts=None):
    """(end state, questions asked, DiagnosticResult) of the engine's configured diagnostic."""
    r = engine.diagnose(
        engine.init_learner(), answer, goal_concepts=goal_concepts, session_id=str(seed)
    )
    return r.state, r.total_items, r


def run_fixed(engine, answer: Callable, n_items: int) -> tuple[LearnerState, int]:
    """Round-robin over concepts (graph order), cycling each concept's exercises by id; p updated
    with the engine's model (no learning transition)."""
    concepts = list(engine.graph.concepts())
    exs = exercises(engine)
    by_c = {c: [a for a in exs if a.target_concept == c] for c in concepts}
    state, used, idx = engine.init_learner(), 0, 0
    while used < n_items and idx < len(exs) * 4:
        cid = concepts[idx % len(concepts)]
        if by_c[cid]:
            act = by_c[cid][(idx // len(concepts)) % len(by_c[cid])]
            y = answer(act)
            c = state.concepts[cid]
            state = LearnerState(
                concepts={
                    **state.concepts,
                    cid: LearnerConcept(
                        concept_id=cid,
                        p=engine.model.update(c.p, act.difficulty, y, 0.0),
                        lessons_done=c.lessons_done,
                        responses=c.responses + 1,
                        correct_responses=c.correct_responses + (1 if y else 0),
                        status=ConceptStatus.ASSESSED,
                    ),
                }
            )
            used += 1
        idx += 1
    return state, used


def _p2pl(theta: float, b: float, a: float = IRT_A) -> float:
    return 1.0 / (1.0 + math.exp(-a * (theta - b)))


class _Posterior:
    def __init__(self):
        self.w = [1.0 / len(GRID)] * len(GRID)

    def add(self, b: float, y: bool) -> None:
        w = [wi * (_p2pl(t, b) if y else 1.0 - _p2pl(t, b)) for wi, t in zip(self.w, GRID)]
        z = sum(w)
        self.w = [x / z for x in w]

    def mean(self) -> float:
        return sum(t * w for t, w in zip(GRID, self.w))

    def mastered(self) -> float:
        return sum(w for t, w in zip(GRID, self.w) if t >= TRUE_MASTERY)


def run_irt_cat(
    engine, answer: Callable, n_items: int, per_concept: bool
) -> tuple[LearnerState, int]:
    items = exercises(engine)
    concepts = list(engine.graph.concepts())
    post = {c: _Posterior() for c in concepts} if per_concept else {"*": _Posterior()}
    asked: set = set()
    for _ in range(min(n_items, len(items))):
        th = {k: p.mean() for k, p in post.items()}
        best, best_info = None, -1.0
        for it in items:
            if it.activity_id in asked:
                continue
            p = _p2pl(th[it.target_concept if per_concept else "*"], it.difficulty)
            info = IRT_A * IRT_A * p * (1.0 - p)
            if info > best_info + 1e-12:
                best, best_info = it, info
        y = answer(best)
        asked.add(best.activity_id)
        post[best.target_concept if per_concept else "*"].add(best.difficulty, y)
    s0 = engine.init_learner()
    new = {
        c: LearnerConcept(
            concept_id=c, p=min(1.0, max(0.0, post[c if per_concept else "*"].mastered()))
        )
        for c in concepts
    }
    return LearnerState(concepts={**s0.concepts, **new}), len(asked)


def sim_answer(sim, tag: str = "diag") -> Callable:
    return lambda a: sim.respond(a.target_concept, a.activity_id, a.difficulty, tag)


def score(engine, state: LearnerState, truth: dict, n_items: int, probe_sim=None) -> dict:
    """Per-learner scores. truth: concept -> bool. probe_sim: a fresh learner for next-answer
    probes (None for scripted learners)."""
    pairs = [(state.concepts[c].p, truth[c]) for c in sorted(truth)]
    conf = [c for c in truth if state.concepts[c].confirmed]
    dconf = [c for c in truth if state.concepts[c].diag_confident]
    out = {
        "brier": sum((p - y) ** 2 for p, y in pairs) / len(pairs),
        "pairs": pairs,
        "items": n_items,
        "confirmed": len(conf),
        "false_confirm": sum(not truth[c] for c in conf),
        "confident": len(dconf),
        "false_confident": sum(not truth[c] for c in dconf),
    }
    if probe_sim is not None:
        probe = [
            (
                engine.model.predict_correct(state.concepts[a.target_concept].p, a.difficulty),
                probe_sim.respond(a.target_concept, a.activity_id, a.difficulty, "probe"),
            )
            for a in exercises(engine)
        ]
        out["probe"] = probe
        out["next_brier"] = sum((p - y) ** 2 for p, y in probe) / len(probe)
    return out


def simulated_arms(engines: dict, base, seed: int, world: str, goal_concepts=None) -> dict:
    """Every E2 arm for one simulated learner. engines: {'sweep': Engine, 'bisection': Engine};
    base: the DEFAULT_CONFIG engine used for prior_only, fixed@n and the IRT-CATs."""

    def learner(e):
        return make_learner(e, seed, world)

    truth = {c: v >= TRUE_MASTERY for c, v in learner(base).initial.items()}
    out = {"prior_only": score(base, base.init_learner(), truth, 0, learner(base))}
    for name, e in engines.items():
        st, k, _ = run_engine_diagnostic(e, sim_answer(learner(e)), seed, goal_concepts)
        out[name] = score(e, st, truth, k, learner(e))
    n = out["bisection"]["items"]
    for name, fn in (
        ("fixed@n", lambda ans: run_fixed(base, ans, n)),
        ("irt_cat_global@n", lambda ans: run_irt_cat(base, ans, n, False)),
        ("irt_cat_per_concept@n", lambda ans: run_irt_cat(base, ans, n, True)),
    ):
        st, k = fn(sim_answer(learner(base)))
        out[name] = score(base, st, truth, k, learner(base))
    return out


def scripted_known(engine, profile: str, goal: str) -> set:
    order = list(engine.graph.topological_order())
    if profile == "advanced":
        return set(order)
    if profile == "advanced_minus_goal":
        return set(order) - {goal} - set(engine.graph.descendants(goal))
    if profile == "mid":
        return set(order[: len(order) // 2])  # a prefix of a topological order is a down-set
    if profile == "novice":
        return set()
    raise ValueError(f"unknown scripted profile {profile!r}")


def scripted_answer(engine, seed: int, known: set) -> Callable:
    """Answers drawn from the heuristic item model: P(correct) = model(1 or 0, d)."""
    count: dict = {}

    def answer(a):
        n = count[a.activity_id] = count.get(a.activity_id, -1) + 1
        p = engine.model.predict_correct(1.0 if a.target_concept in known else 0.0, a.difficulty)
        return keyed_uniform(seed, "script", a.activity_id, n) < p

    return answer


def run_scripted(engine, seed: int, profile: str, goal: str, goal_concepts: Optional[list] = None):
    known = scripted_known(engine, profile, goal)
    truth = {c: c in known for c in engine.graph.concepts()}
    st, k, _ = run_engine_diagnostic(
        engine, scripted_answer(engine, seed, known), seed, goal_concepts
    )
    return score(engine, st, truth, k)
