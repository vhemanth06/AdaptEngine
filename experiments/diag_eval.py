"""Matched-budget diagnostic evaluation and tuning harness (W6 Step 5).

Compares Adaptive (EIG) diagnostic assessment against Fixed-Order and Random baselines
at matched item budgets (n_adaptive, 4, 8), reporting three metrics:
1. MAE across all curriculum concepts
2. MAE across assessed concepts only
3. Fraction of concepts left unassessed

Includes a rigorous tuning grid on the tuning cohort (even seeds) with held-out validation (odd seeds).
Never imported from src/.
"""

from __future__ import annotations

import dataclasses
import random
from typing import Any, Mapping, Optional, Sequence

from adaptengine.api import Engine
from adaptengine.core.config import DEFAULT_CONFIG

from adaptengine.core.schema import ActivityType
from adaptengine.learner.state import ConceptStatus, LearnerConcept, LearnerState
from experiments.sim import PROFILES, SimLearner, SimProfile


def compute_diagnostic_errors(
    state: LearnerState,
    true_theta: Mapping[str, float],
    all_concepts: Sequence[str],
) -> dict[str, float]:
    """Compute the three diagnostic error metrics against ground truth theta."""
    mae_all = sum(abs(state.concepts[c].p - true_theta[c]) for c in all_concepts) / len(
        all_concepts
    )

    assessed = [c for c in all_concepts if state.concepts[c].responses > 0]
    if assessed:
        mae_assessed = sum(abs(state.concepts[c].p - true_theta[c]) for c in assessed) / len(
            assessed
        )
    else:
        mae_assessed = mae_all

    unassessed_count = sum(1 for c in all_concepts if state.concepts[c].responses == 0)
    unassessed_frac = unassessed_count / len(all_concepts)

    return {
        "mae_all": round(mae_all, 4),
        "mae_assessed": round(mae_assessed, 4),
        "unassessed_fraction": round(unassessed_frac, 4),
    }


def run_adaptive_diagnostic(
    engine: Engine,
    seed: int,
    profile: SimProfile,
) -> tuple[LearnerState, int]:
    """Run active information gain (EIG) diagnostic probe using key-seeded responses."""
    sim = SimLearner(seed=seed, concepts=engine.graph.concepts(), profile=profile)
    init_state = engine.init_learner()
    diag_res = engine.diagnose(
        init_state,
        goal_concepts=None,
        response_provider=lambda act: sim.respond(
            act.target_concept, act.activity_id, act.difficulty or 0.5, tag="diag"
        ),
        session_id=f"diag-{seed}",
    )
    return diag_res.state, diag_res.total_items


def run_fixed_diagnostic(
    engine: Engine,
    seed: int,
    profile: SimProfile,
    item_cap: int,
) -> tuple[LearnerState, int]:
    """Run round-robin fixed concept probe using independent SimLearner instance with same seed."""
    sim = SimLearner(seed=seed, concepts=engine.graph.concepts(), profile=profile)
    concepts = list(engine.graph.concepts())
    all_exercises = sorted(
        [a for a in engine.activities.values() if a.type == ActivityType.EXERCISE],
        key=lambda a: a.activity_id,
    )

    state = engine.init_learner()
    items_used = 0
    idx = 0

    while items_used < item_cap and idx < len(all_exercises) * 4:
        cid = concepts[idx % len(concepts)]
        c_exs = [a for a in all_exercises if a.target_concept == cid]
        if c_exs:
            act = c_exs[(idx // len(concepts)) % len(c_exs)]
            resp = sim.respond(
                cid,
                act.activity_id,
                act.difficulty if act.difficulty is not None else 0.5,
                tag="diag",
            )
            c = state.concepts[cid]
            p_up = engine.model.update(
                c.p, act.difficulty if act.difficulty is not None else 0.5, resp, 0.0
            )
            c_new = LearnerConcept(
                concept_id=cid,
                p=p_up,
                lessons_done=c.lessons_done,
                responses=c.responses + 1,
                correct_responses=c.correct_responses + (1 if resp else 0),
                status=ConceptStatus.ASSESSED,
            )
            state = LearnerState(concepts={**state.concepts, cid: c_new})
            items_used += 1
        idx += 1

    return state, items_used


def run_random_diagnostic(
    engine: Engine,
    seed: int,
    profile: SimProfile,
    item_cap: int,
) -> tuple[LearnerState, int]:
    """Run uniform random exercise probe using keyed seed shuffle on independent SimLearner."""
    sim = SimLearner(seed=seed, concepts=engine.graph.concepts(), profile=profile)
    all_exercises = sorted(
        [a for a in engine.activities.values() if a.type == ActivityType.EXERCISE],
        key=lambda a: a.activity_id,
    )

    r = random.Random(f"{seed}|random-order")
    shuffled = list(all_exercises)
    r.shuffle(shuffled)

    state = engine.init_learner()
    items_used = 0

    for act in shuffled[:item_cap]:
        cid = act.target_concept
        resp = sim.respond(
            cid, act.activity_id, act.difficulty if act.difficulty is not None else 0.5, tag="diag"
        )
        c = state.concepts[cid]
        p_up = engine.model.update(
            c.p, act.difficulty if act.difficulty is not None else 0.5, resp, 0.0
        )
        c_new = LearnerConcept(
            concept_id=cid,
            p=p_up,
            lessons_done=c.lessons_done,
            responses=c.responses + 1,
            correct_responses=c.correct_responses + (1 if resp else 0),
            status=ConceptStatus.ASSESSED,
        )
        state = LearnerState(concepts={**state.concepts, cid: c_new})
        items_used += 1

    return state, items_used


def evaluate_diagnostic_learner(
    engine: Engine,
    seed: int,
    profile: SimProfile,
) -> dict[str, Any]:
    """Run adaptive, fixed, and random arms at matched budgets for a single learner."""
    # Hidden ground truth theta
    truth_sim = SimLearner(seed=seed, concepts=engine.graph.concepts(), profile=profile)
    true_theta = truth_sim.initial
    all_concepts = list(engine.graph.concepts())

    # 1. Adaptive
    adapt_state, n_adapt = run_adaptive_diagnostic(engine, seed, profile)
    adapt_errors = compute_diagnostic_errors(adapt_state, true_theta, all_concepts)

    # 2. Fixed at n_adapt, 4, 8
    fixed_res: dict[str, Any] = {}
    for budget in [n_adapt, 4, 8]:
        st, used = run_fixed_diagnostic(engine, seed, profile, item_cap=budget)
        err = compute_diagnostic_errors(st, true_theta, all_concepts)
        fixed_res[str(budget)] = {**err, "items_used": used}

    # 3. Random at n_adapt, 4, 8
    random_res: dict[str, Any] = {}
    for budget in [n_adapt, 4, 8]:
        st, used = run_random_diagnostic(engine, seed, profile, item_cap=budget)
        err = compute_diagnostic_errors(st, true_theta, all_concepts)
        random_res[str(budget)] = {**err, "items_used": used}

    return {
        "seed": seed,
        "adaptive": {**adapt_errors, "items_used": n_adapt},
        "fixed": fixed_res,
        "random": random_res,
    }


def run_diagnostic_tuning(
    curriculum_path: str,
    activities_path: str,
    tuning_seeds: Sequence[int],
    heldout_seeds: Sequence[int],
    profile: Optional[SimProfile] = None,
) -> dict[str, Any]:
    """Grid search over diagnostic stopping parameters on tuning cohort, evaluated on held-out cohort."""
    if profile is None:
        profile = PROFILES["nominal"]

    h_stop_grid = [0.20, 0.30, 0.40, 0.50]
    concept_cap_grid = [1, 2, 3]
    n_max_grid = [4, 6, 8]

    grid_results = []

    for n_m in n_max_grid:
        for h_s in h_stop_grid:
            for c_c in concept_cap_grid:
                cfg = dataclasses.replace(
                    DEFAULT_CONFIG,
                    h_stop=h_s,
                    concept_cap=c_c,
                    n_max=n_m,
                )
                eng = Engine.from_files(curriculum_path, activities_path, config=cfg)

                items_list = []
                mae_list = []
                for s in tuning_seeds:
                    st, used = run_adaptive_diagnostic(eng, s, profile)
                    sim = SimLearner(seed=s, concepts=eng.graph.concepts(), profile=profile)
                    err = compute_diagnostic_errors(st, sim.initial, list(eng.graph.concepts()))
                    items_list.append(used)
                    mae_list.append(err["mae_all"])

                avg_items = sum(items_list) / len(items_list)
                avg_mae = sum(mae_list) / len(mae_list)

                grid_results.append(
                    {
                        "h_stop": h_s,
                        "concept_cap": c_c,
                        "n_max": n_m,
                        "avg_items": round(avg_items, 3),
                        "avg_mae": round(avg_mae, 4),
                    }
                )

    # Selection rule:
    # Among settings using at most 50% of the fixed arm's items on average (<= 4.0 items),
    # choose lowest tuning-half MAE.
    # Ties broken by: smaller n_max, then smaller h_stop, then smaller concept_cap.
    eligible = [r for r in grid_results if r["avg_items"] <= 4.0]
    if not eligible:
        eligible = grid_results

    eligible.sort(key=lambda r: (r["avg_mae"], r["n_max"], r["h_stop"], r["concept_cap"]))
    winner = eligible[0]

    # Evaluate winner on held-out seeds
    winner_cfg = dataclasses.replace(
        DEFAULT_CONFIG,
        h_stop=winner["h_stop"],
        concept_cap=winner["concept_cap"],
        n_max=winner["n_max"],
    )
    winner_eng = Engine.from_files(curriculum_path, activities_path, config=winner_cfg)
    default_eng = Engine.from_files(curriculum_path, activities_path, config=DEFAULT_CONFIG)

    heldout_winner_mae = []
    heldout_winner_items = []
    heldout_default_mae = []
    heldout_default_items = []

    for s in heldout_seeds:
        # Winner
        st_w, used_w = run_adaptive_diagnostic(winner_eng, s, profile)
        sim_w = SimLearner(seed=s, concepts=winner_eng.graph.concepts(), profile=profile)
        err_w = compute_diagnostic_errors(st_w, sim_w.initial, list(winner_eng.graph.concepts()))
        heldout_winner_mae.append(err_w["mae_all"])
        heldout_winner_items.append(used_w)

        # Default
        st_d, used_d = run_adaptive_diagnostic(default_eng, s, profile)
        sim_d = SimLearner(seed=s, concepts=default_eng.graph.concepts(), profile=profile)
        err_d = compute_diagnostic_errors(st_d, sim_d.initial, list(default_eng.graph.concepts()))
        heldout_default_mae.append(err_d["mae_all"])
        heldout_default_items.append(used_d)

    return {
        "grid_results": grid_results,
        "winner": winner,
        "heldout_comparison": {
            "winner_heldout_mae": round(sum(heldout_winner_mae) / len(heldout_winner_mae), 4),
            "winner_heldout_items": round(sum(heldout_winner_items) / len(heldout_winner_items), 3),
            "default_heldout_mae": round(sum(heldout_default_mae) / len(heldout_default_mae), 4),
            "default_heldout_items": round(
                sum(heldout_default_items) / len(heldout_default_items), 3
            ),
        },
    }
