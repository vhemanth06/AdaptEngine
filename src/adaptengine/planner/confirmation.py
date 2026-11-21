"""Planner confirmation path for concepts the bisection diagnostic inferred (Plan 3, F1.4, D57).

A diag_confident concept gets short confirmation checks instead of its full workload when testing
first is cheaper in expected minutes (F1.4.4):
1. n = checks added one at a time (most informative unseen item each time) until correct answers
   would lift the observation-only posterior to 1 - confirm_epsilon. This greedy order does not
   always give the smallest possible n. More than confirm_max_checks -> study.
2. P_pass = p * prod(1 - s_i) + (1 - p) * prod(g_i) over the chosen checks.
3. Check first iff T_checks < P_pass * T_full (minutes of the checks vs the normal workload).
"""

from __future__ import annotations

from typing import Optional, Sequence

from ..core.config import EngineConfig
from ..core.schema import Activity
from ..diagnostic.scoring import candidate_sort_key, compute_eig
from ..learner.adapter import MasteryModel


def plan_checks(
    p: float,
    responses: int,
    exercises: Sequence[Activity],
    done_ids: Sequence[str],
    model: MasteryModel,
    cfg: EngineConfig,
) -> Optional[tuple[list[Activity], float]]:
    """(check items, P_pass), or None if confirmation needs more than confirm_max_checks.

    At least confirm_min_direct direct answers are needed in total, so an inferred concept
    (0 responses) always gets at least one check even when its p is already above 1 - epsilon.
    A concept that is still unconfirmed always gets at least one check: confirmation is set only
    by a correct answer, and an empty workload would let its dependants start (F1 grid H1 fix).
    """
    done = set(done_ids)
    last_seen = {aid: i for i, aid in enumerate(done_ids)}
    chosen: list[Activity] = []
    p_obs, pass_known, pass_unknown = p, 1.0, 1.0
    while (
        not chosen
        or p_obs < 1.0 - cfg.confirm_epsilon
        or responses + len(chosen) < cfg.confirm_min_direct
    ):
        if len(chosen) >= cfg.confirm_max_checks:
            return None
        pool = [a for a in exercises if a.activity_id not in done and a not in chosen]
        if not pool and cfg.allow_exercise_repeats:  # D41: least recently attempted
            seen = [a for a in exercises if a not in chosen]
            pool = sorted(seen, key=lambda a: last_seen.get(a.activity_id, -1))[:1]
        if not pool:
            return None
        best = min(
            pool,
            key=lambda a: candidate_sort_key(
                compute_eig(p_obs, a, cfg, model=model), a.difficulty, a.activity_id
            ),
        )
        chosen.append(best)
        pass_known *= model.predict_correct(1.0, best.difficulty)
        pass_unknown *= model.predict_correct(0.0, best.difficulty)
        p_obs = model.update(p_obs, best.difficulty, True, 0.0)
    return chosen, p * pass_known + (1.0 - p) * pass_unknown


def route_concept(
    concept_id: str,
    p: float,
    responses: int,
    full: Sequence[Activity],
    exercises: Sequence[Activity],
    done_ids: Sequence[str],
    model: MasteryModel,
    cfg: EngineConfig,
) -> Optional[tuple[list[Activity], dict]]:
    """(checks, trace record) when testing first is cheaper than the normal workload `full`."""
    planned = plan_checks(p, responses, exercises, done_ids, model, cfg)
    if planned is None or not full:
        return None
    checks, p_pass = planned
    t_checks = sum(a.duration for a in checks)
    t_full = sum(a.duration for a in full)
    if not t_checks < p_pass * t_full:
        return None
    return checks, {
        "decision": "CONFIRMATION",
        "concept_id": concept_id,
        "reason": "CONFIRMATION_CHECK",
        "p": p,
        "n_checks": len(checks),
        "p_pass": p_pass,
        "minutes_checks": t_checks,
        "minutes_full": t_full,
        "activity_ids": [a.activity_id for a in checks],
    }
