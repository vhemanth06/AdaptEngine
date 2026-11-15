"""Diagnostic baselines for E2 (fixed order, random order, 2PL IRT-CAT), each spending exactly
`n` items on a learner and returning P(mastered) per concept. Ported from the pre-rewrite
diag_eval.py / cat_baseline.py. Never imported from src/."""

from __future__ import annotations

import random

import numpy as np

from adaptengine.core.schema import ActivityType
from experiments.sim import TRUE_MASTERY_CUTOFF

GRID = np.linspace(0.0, 1.0, 201)  # theta grid on the simulator's [0, 1] scale


def prior_p(engine) -> float:
    """Starting P(mastered) for every concept, the same one the product diagnostic starts from."""
    c = engine.config
    return c.population_p0 if c.prior_mode == "population" else c.p0


def _exercises(engine):
    return sorted(
        (a for a in engine.activities.values() if a.type == ActivityType.EXERCISE),
        key=lambda a: a.activity_id,
    )


def _bkt_run(engine, learner, items) -> dict[str, float]:
    p = dict.fromkeys(engine.graph.concepts(), prior_p(engine))
    for a in items:
        y = learner.respond(a.target_concept, a.activity_id, a.difficulty, tag="diag")
        p[a.target_concept] = engine.model.update(p[a.target_concept], a.difficulty, y, 0.0)
    return p


def fixed_order(engine, learner, n: int) -> dict[str, float]:
    """Round-robin over concepts in topological order, each concept's items mid-difficulty first."""
    by_c: dict[str, list] = {c: [] for c in engine.graph.topological_order()}
    for a in sorted(_exercises(engine), key=lambda a: (abs(a.difficulty - 0.5), a.activity_id)):
        by_c[a.target_concept].append(a)
    rounds = max((len(v) for v in by_c.values()), default=0)
    order = [by_c[c][k] for k in range(rounds) for c in by_c if k < len(by_c[c])]
    return _bkt_run(engine, learner, order[:n])


def random_order(engine, learner, n: int, seed: int) -> dict[str, float]:
    items = _exercises(engine)
    random.Random(f"{seed}|random-order").shuffle(items)
    return _bkt_run(engine, learner, items[:n])


def irt_cat(engine, learner, n: int, a: float = 3.0) -> dict[str, float]:
    """One global 2PL ability, max-information item selection, EAP posterior on a grid;
    P(mastered) = posterior mass of theta >= the mastery cutoff, the same for every concept.
    a=3 is the simulator's true discrimination (an advantage in the 2PL worlds)."""
    items = _exercises(engine)
    b = np.array([x.difficulty for x in items])
    logw = np.zeros(len(GRID))

    def post():
        w = np.exp(logw - logw.max())
        return w / w.sum()

    asked: set[int] = set()
    for _ in range(min(n, len(items))):
        th = float(GRID @ post())
        pr = 1.0 / (1.0 + np.exp(-a * (th - b)))
        info = pr * (1.0 - pr)
        info[list(asked)] = -1.0
        k = int(np.argmax(info))
        it = items[k]
        y = learner.respond(it.target_concept, it.activity_id, it.difficulty, tag="diag")
        asked.add(k)
        pg = 1.0 / (1.0 + np.exp(-a * (GRID - it.difficulty)))
        logw += np.log(pg if y else 1.0 - pg)
    p = float(post()[GRID >= TRUE_MASTERY_CUTOFF].sum())
    return dict.fromkeys(engine.graph.concepts(), min(1.0, max(0.0, p)))
