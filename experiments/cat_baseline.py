"""External diagnostic baseline for T3.7: a unidimensional 2PL IRT CAT in the style of the
friend's catsim design (R§7): max-Fisher-information item selection, EAP ability on a grid
(MLE is undefined after all-correct/all-wrong starts), P(mastered) = posterior mass of
theta >= TRUE_MASTERY_CUTOFF. `per_concept=True` keeps one ability per concept instead of one
global ability. Ported from the R§7.3 probe (probe4.py). Never imported from src/.
"""

from __future__ import annotations

import math

from adaptengine.core.schema import ActivityType
from adaptengine.learner.state import LearnerState
from experiments.sim import TRUE_MASTERY_CUTOFF

GRID = [i / 200 for i in range(201)]  # theta grid on the simulator's [0, 1] scale


def _p2pl(theta: float, b: float, a: float) -> float:
    return 1.0 / (1.0 + math.exp(-a * (theta - b)))


def _posterior(obs, a):
    w = [1.0 / len(GRID)] * len(GRID)
    for b, y in obs:
        w = [wi * (_p2pl(t, b, a) if y else 1.0 - _p2pl(t, b, a)) for wi, t in zip(w, GRID)]
    z = sum(w)
    return [x / z for x in w]


def irt_cat(engine, sim, n_items: int, a: float = 3.0, per_concept: bool = False):
    """Run the CAT for n_items; returns (LearnerState with p = P(theta >= cutoff), n_items)."""
    items = sorted(
        (x for x in engine.activities.values() if x.type == ActivityType.EXERCISE),
        key=lambda x: x.activity_id,
    )
    concepts = list(engine.graph.concepts())
    obs: dict = {c: [] for c in concepts} if per_concept else {"*": []}
    asked: set[str] = set()
    for _ in range(min(n_items, len(items))):
        best, best_info = None, -1.0
        for it in items:
            if it.activity_id in asked:
                continue
            post = _posterior(obs[it.target_concept if per_concept else "*"], a)
            th = sum(t * w for t, w in zip(GRID, post))
            p = _p2pl(th, it.difficulty, a)
            info = a * a * p * (1.0 - p)
            if info > best_info + 1e-12:
                best, best_info = it, info
        y = sim.respond(best.target_concept, best.activity_id, best.difficulty, tag="diag")
        asked.add(best.activity_id)
        obs[best.target_concept if per_concept else "*"].append((best.difficulty, y))

    def pm(o):
        return sum(w for t, w in zip(GRID, _posterior(o, a)) if t >= TRUE_MASTERY_CUTOFF)

    s0 = engine.init_learner()
    new = {}
    for c in concepts:
        p = pm(obs[c] if per_concept else obs["*"])
        new[c] = s0.concepts[c].__class__(concept_id=c, p=min(1.0, max(0.0, p)))
    return LearnerState(concepts=new), len(asked)
