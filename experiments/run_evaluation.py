#!/usr/bin/env python3
"""AdaptEngine — Paired Baseline Evaluation Runner (Milestone M8 / TC8.1).

Conducts a paired synthetic evaluation comparing AdaptEngine against baselines:
1. Diagnostic Arms:
   - Adaptive (EIG)
   - Fixed Order (matched at n_adaptive, 4, 8 items)
   - Random (matched at n_adaptive, 4, 8 items)
   Metrics: MAE (all concepts), MAE (assessed concepts), unassessed fraction, items used,
            plus hyperparameter grid tuning on tuning cohort with held-out validation.

2. Planner Arms:
   - adapt: State-aware planning and replanning with spaced review and remediation.
   - no_review: Full replanning, but review disabled (urgency 0.0).
   - no_replan: Initial plan only; missed days or events are not recovered.
   - static: State-agnostic topological sequence packed next-fit into daily budgets.
   Scenarios: calm, missed_day, budget_drop, deadline_cut.
   Metrics: Goal true mastery rate, mean true goal mastery, retention, days used,
            prerequisite violations, budget violations, Brier score, ROC-AUC, explanation coverage,
            and paired bootstrap confidence intervals (95%) vs adapt.

Determinism: runs with identical seeds produce byte-identical results (TC8.1).
No timestamps, hostnames, or machine-specific paths are embedded in output.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Optional

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG, config_hash  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.diag_eval import (  # noqa: E402
    evaluate_diagnostic_binary,
    evaluate_diagnostic_learner,
    run_diagnostic_tuning,
)
from experiments.sim import PROFILES, TRUE_MASTERY_CUTOFF  # noqa: E402
from experiments.stats import (  # noqa: E402
    brier_score,
    paired_bootstrap_ci,
    roc_auc,
)


DEFAULT_OUT = os.path.join(repo_root, "experiments", "results", "evaluation_results.json")


def run_evaluation(
    num_seeds: int = 100,
    seed_start: int = 100,
    quick: bool = False,
    out_path: Optional[str] = DEFAULT_OUT,
) -> dict[str, Any]:
    """Run the paired evaluation; write JSON to out_path (None = don't write)."""
    if quick:
        num_seeds = min(num_seeds, 10)

    seeds = list(range(seed_start, seed_start + num_seeds))
    tuning_seeds = [s for s in seeds if s % 2 == 0]
    heldout_seeds = [s for s in seeds if s % 2 == 1]

    # Git SHA (read-only command)
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        git_sha = "unknown"

    cfg_hash = config_hash(DEFAULT_CONFIG)

    curriculum_4_path = "data/curriculum/curriculum_4node.json"
    activities_4_path = "data/curriculum/activities_4node.json"
    curricula_used = ["4-node"]

    engine_4 = Engine.from_files(curriculum_4_path, activities_4_path, config=DEFAULT_CONFIG)

    # -------------------------------------------------------------------------
    # PART 1: Diagnostic Evaluation & Tuning
    # -------------------------------------------------------------------------
    diag_per_seed: dict[int, Any] = {}
    for s in seeds:
        diag_per_seed[s] = evaluate_diagnostic_learner(engine_4, s, PROFILES["nominal"])

    # Aggregate diagnostic metrics across held-out cohort
    eval_seeds = heldout_seeds if heldout_seeds else seeds

    def agg_diag_arm(extractor):
        all_errs = [extractor(diag_per_seed[s]) for s in eval_seeds]
        mae_all = round(sum(e["mae_all"] for e in all_errs) / len(all_errs), 4)
        mae_assessed = round(sum(e["mae_assessed"] for e in all_errs) / len(all_errs), 4)
        unassessed = round(sum(e["unassessed_fraction"] for e in all_errs) / len(all_errs), 4)
        items = round(sum(e["items_used"] for e in all_errs) / len(all_errs), 3)

        ci_mae_all = paired_bootstrap_ci([e["mae_all"] for e in all_errs])
        ci_mae_assessed = paired_bootstrap_ci([e["mae_assessed"] for e in all_errs])

        return {
            "mae_all": mae_all,
            "mae_all_95ci": list(ci_mae_all),
            "mae_assessed": mae_assessed,
            "mae_assessed_95ci": list(ci_mae_assessed),
            "unassessed_fraction": unassessed,
            "items_used": items,
        }

    diagnostic_summary: dict[str, Any] = {
        "adaptive": agg_diag_arm(lambda r: r["adaptive"]),
        "fixed": {
            "n_adaptive": agg_diag_arm(lambda r: r["fixed"][str(r["adaptive"]["items_used"])]),
            "4_items": agg_diag_arm(lambda r: r["fixed"]["4"]),
            "8_items": agg_diag_arm(lambda r: r["fixed"]["8"]),
        },
        "random": {
            "n_adaptive": agg_diag_arm(lambda r: r["random"][str(r["adaptive"]["items_used"])]),
            "4_items": agg_diag_arm(lambda r: r["random"]["4"]),
            "8_items": agg_diag_arm(lambda r: r["random"]["8"]),
        },
    }

    # Run tuning grid
    tuning_res = run_diagnostic_tuning(
        curriculum_4_path,
        activities_4_path,
        tuning_seeds=tuning_seeds if tuning_seeds else seeds[:2],
        heldout_seeds=heldout_seeds if heldout_seeds else seeds[:2],
        profile=PROFILES["nominal"],
    )
    diagnostic_summary["tuning"] = tuning_res
    # W7 T3.1: proper scoring rules against binary truth on the held-out cohort (primary metric)
    diagnostic_summary["binary_truth"] = evaluate_diagnostic_binary(
        engine_4, eval_seeds, PROFILES["nominal"]
    )

    # -------------------------------------------------------------------------
    # PART 2: Planner Arms Main Table (Nominal Profile, Budget 15, 4 Scenarios)
    # -------------------------------------------------------------------------
    main_scenarios = ["calm", "missed_day", "budget_drop", "deadline_cut"]
    arms = ["adapt", "no_review", "no_replan", "static"]

    planner_runs: dict[str, dict[str, dict[int, Any]]] = {
        sc_name: {arm: {} for arm in arms} for sc_name in main_scenarios
    }

    per_seed_planner: list[dict[str, Any]] = []

    start_state_4 = engine_4.init_learner()

    for s in seeds:
        seed_record: dict[str, Any] = {"seed": s}
        for sc_name in main_scenarios:
            sc = get_scenario(sc_name, engine_4, start_state_4, goal="C4", budget=15)
            if sc is None:
                continue
            for arm in arms:
                res = run_episode(
                    engine_4, seed=s, scenario=sc, arm=arm, profile=PROFILES["nominal"]
                )
                planner_runs[sc_name][arm][s] = res
                if sc_name == "missed_day":
                    seed_record[arm] = res
        per_seed_planner.append(seed_record)

    main_table: dict[str, Any] = {}
    for sc_name in main_scenarios:
        main_table[sc_name] = {}
        sc_arms_runs = planner_runs[sc_name]

        for arm in arms:
            arm_seed_results = [sc_arms_runs[arm][s] for s in seeds]
            adapt_seed_results = [sc_arms_runs["adapt"][s] for s in seeds]

            goal_mastery_rate = round(
                sum(1.0 for r in arm_seed_results if r["goal_mastered"]) / len(arm_seed_results), 4
            )
            mean_true_mastery = round(
                sum(r["goal_true_mastery"] for r in arm_seed_results) / len(arm_seed_results), 4
            )
            mean_retention = round(
                sum(r["retention"] for r in arm_seed_results) / len(arm_seed_results), 4
            )
            mean_days = round(
                sum(r["days_used"] for r in arm_seed_results) / len(arm_seed_results), 3
            )
            total_plan_viol = sum(r["plan_prereq_violations"] for r in arm_seed_results)
            total_exec_viol = sum(r["executed_prereq_violations"] for r in arm_seed_results)
            learners_exec_viol = sum(1 for r in arm_seed_results if r["executed_prereq_violations"])
            total_budget_viol = sum(r["budget_violations"] for r in arm_seed_results)
            trace_cov = round(
                sum(r["plan_trace_coverage"] for r in arm_seed_results) / len(arm_seed_results), 4
            )

            # Held-out attempts for Brier / AUC
            heldout_runs = [sc_arms_runs[arm][s] for s in eval_seeds]
            all_attempts: list[tuple[float, bool]] = [
                (pair[0], pair[1]) for r in heldout_runs for pair in r["attempts"]
            ]
            arm_brier = brier_score(all_attempts)
            arm_auc = roc_auc(all_attempts)

            # Paired differences vs adapt
            diff_mastery = [
                r["goal_true_mastery"] - a["goal_true_mastery"]
                for r, a in zip(arm_seed_results, adapt_seed_results)
            ]
            diff_days = [
                float(r["days_used"] - a["days_used"])
                for r, a in zip(arm_seed_results, adapt_seed_results)
            ]
            diff_ret = [
                r["retention"] - a["retention"]
                for r, a in zip(arm_seed_results, adapt_seed_results)
            ]

            paired_vs_adapt = {
                "goal_true_mastery_diff": round(sum(diff_mastery) / len(diff_mastery), 4),
                "goal_true_mastery_diff_95ci": list(paired_bootstrap_ci(diff_mastery)),
                "days_used_diff": round(sum(diff_days) / len(diff_days), 3),
                "days_used_diff_95ci": list(paired_bootstrap_ci(diff_days)),
                "retention_diff": round(sum(diff_ret) / len(diff_ret), 4),
                "retention_diff_95ci": list(paired_bootstrap_ci(diff_ret)),
            }

            main_table[sc_name][arm] = {
                "goal_mastery_rate": goal_mastery_rate,
                "mean_true_goal_mastery": mean_true_mastery,
                "mean_retention": mean_retention,
                "mean_days_used": mean_days,
                "plan_prereq_violations": total_plan_viol,
                "executed_prereq_violations": total_exec_viol,
                "learners_with_executed_prereq_violations": learners_exec_viol,
                "budget_violations": total_budget_viol,
                "brier": arm_brier,
                "auc": arm_auc,
                "plan_trace_coverage": trace_cov,
                "paired_diff_vs_adapt": paired_vs_adapt,
            }

    # -------------------------------------------------------------------------
    # PART 3: Robustness Table across Profiles and Budgets
    # -------------------------------------------------------------------------
    robustness_profiles = (
        ["high_slip", "fast_forgetter", "rapid_learner"] if not quick else ["fast_forgetter"]
    )
    robustness_budgets = [5, 10, 30] if not quick else [10]

    robustness_table: dict[str, Any] = {}

    for prof_name in robustness_profiles:
        robustness_table[prof_name] = {}
        prof = PROFILES[prof_name]
        for b in robustness_budgets:
            sc = get_scenario("missed_day", engine_4, start_state_4, goal="C4", budget=b)
            if sc is None:
                continue
            budget_res: dict[str, Any] = {}
            for arm in arms:
                arm_results = [
                    run_episode(engine_4, seed=s, scenario=sc, arm=arm, profile=prof) for s in seeds
                ]
                budget_res[arm] = {
                    "goal_mastery_rate": round(
                        sum(1.0 for r in arm_results if r["goal_mastered"]) / len(arm_results), 4
                    ),
                    "mean_true_goal_mastery": round(
                        sum(r["goal_true_mastery"] for r in arm_results) / len(arm_results), 4
                    ),
                    "mean_retention": round(
                        sum(r["retention"] for r in arm_results) / len(arm_results), 4
                    ),
                    "mean_days_used": round(
                        sum(r["days_used"] for r in arm_results) / len(arm_results), 3
                    ),
                    "executed_prereq_violations": sum(
                        r["executed_prereq_violations"] for r in arm_results
                    ),
                }
            robustness_table[prof_name][str(b)] = budget_res

    # 8-node curriculum evaluation in full mode
    eight_node_summary = None
    if not quick:
        curriculum_8_path = "data/curriculum/curriculum_8node.json"
        activities_8_path = "data/curriculum/activities_8node.json"
        curricula_used.append("8-node")
        engine_8 = Engine.from_files(curriculum_8_path, activities_8_path, config=DEFAULT_CONFIG)
        start_state_8 = engine_8.init_learner()
        goal_8 = engine_8.graph.topological_order()[-1]

        eight_node_summary = {}
        for sc_name in ["calm", "missed_day"]:
            sc8 = get_scenario(sc_name, engine_8, start_state_8, goal=goal_8, budget=15)
            if sc8 is not None:
                sc8_res = {}
                for arm in ["adapt", "static"]:
                    runs_8 = [
                        run_episode(
                            engine_8, seed=s, scenario=sc8, arm=arm, profile=PROFILES["nominal"]
                        )
                        for s in seeds
                    ]
                    sc8_res[arm] = {
                        "goal_mastery_rate": round(
                            sum(1.0 for r in runs_8 if r["goal_mastered"]) / len(runs_8), 4
                        ),
                        "mean_true_goal_mastery": round(
                            sum(r["goal_true_mastery"] for r in runs_8) / len(runs_8), 4
                        ),
                        "mean_days_used": round(
                            sum(r["days_used"] for r in runs_8) / len(runs_8), 3
                        ),
                        "executed_prereq_violations": sum(
                            r["executed_prereq_violations"] for r in runs_8
                        ),
                    }
                eight_node_summary[sc_name] = sc8_res

    # Assemble structured results dictionary
    results: dict[str, Any] = {
        "metadata": {
            "num_seeds": num_seeds,
            "split_rule": "even seeds (tuning) vs odd seeds (held-out)",
            "curricula": curricula_used,
            "config_hash": cfg_hash,
            "git_sha": git_sha,
            "profiles": list(PROFILES.keys()),
            "cutoff": TRUE_MASTERY_CUTOFF,
            "limitation": (
                "Synthetic IRT-generated learner responses evaluated against BKT belief updates "
                "on synthetic curriculum fixtures. Real-world dynamics require empirical deployment."
            ),
        },
        "diagnostic": diagnostic_summary,
        "planner": {
            "main_table": main_table,
            "robustness_table": robustness_table,
            "eight_node_curriculum": eight_node_summary,
        },
        "per_seed_runs": {
            "planner": per_seed_planner,
        },
    }

    if out_path is not None:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, sort_keys=True)

    return results


def print_evaluation_summary(results: dict[str, Any]) -> None:
    meta = results["metadata"]
    diag = results["diagnostic"]
    planner = results["planner"]["main_table"]

    print("=" * 76)
    print(f" AdaptEngine — Baseline Evaluation ({meta['num_seeds']} Seeded Learners)")
    print(f" Git SHA: {meta['git_sha'][:10]} | Config Hash: {meta['config_hash'][:10]}")
    print("=" * 76)

    print("\n--- Diagnostic Arms Summary (Held-Out Cohort) ---")
    ad = diag["adaptive"]
    fx_n = diag["fixed"]["n_adaptive"]
    fx_8 = diag["fixed"]["8_items"]
    rn_n = diag["random"]["n_adaptive"]
    rn_8 = diag["random"]["8_items"]

    print(
        f" Adaptive (EIG)   : MAE(all)={ad['mae_all']:.4f} | MAE(assessed)={ad['mae_assessed']:.4f} | Items={ad['items_used']:.1f} | Unassessed={ad['unassessed_fraction']:.1%}"
    )
    print(
        f" Fixed @ n_adapt  : MAE(all)={fx_n['mae_all']:.4f} | MAE(assessed)={fx_n['mae_assessed']:.4f} | Items={fx_n['items_used']:.1f} | Unassessed={fx_n['unassessed_fraction']:.1%}"
    )
    print(
        f" Fixed @ 8 items  : MAE(all)={fx_8['mae_all']:.4f} | MAE(assessed)={fx_8['mae_assessed']:.4f} | Items={fx_8['items_used']:.1f} | Unassessed={fx_8['unassessed_fraction']:.1%}"
    )
    print(
        f" Random @ n_adapt : MAE(all)={rn_n['mae_all']:.4f} | MAE(assessed)={rn_n['mae_assessed']:.4f} | Items={rn_n['items_used']:.1f} | Unassessed={rn_n['unassessed_fraction']:.1%}"
    )
    print(
        f" Random @ 8 items : MAE(all)={rn_8['mae_all']:.4f} | MAE(assessed)={rn_8['mae_assessed']:.4f} | Items={rn_8['items_used']:.1f} | Unassessed={rn_8['unassessed_fraction']:.1%}"
    )

    if "binary_truth" in diag:
        print("\n--- Diagnostic vs binary truth (primary, W7 T3.1; Brier lower is better) ---")
        for name, row in diag["binary_truth"]["arms"].items():
            pv = row["paired_brier_vs_adaptive"]
            print(
                f" {name:11s}: Brier={row['brier']:.4f} AUC={row['auc']} LogLoss={row['log_loss']}"
                f" NextResp={row['next_response_brier']:.4f} Items={row['items_used']:.2f}"
                f" | vs adaptive {pv['diff']:+.4f} {pv['ci95']}"
            )

    if "tuning" in diag and "winner" in diag["tuning"]:
        w = diag["tuning"]["winner"]
        hc = diag["tuning"]["heldout_comparison"]
        print(
            f"\n Tuning Winner: h_stop={w['h_stop']}, concept_cap={w['concept_cap']}, n_max={w['n_max']} (Tuning MAE: {w['avg_mae']:.4f}, Items: {w['avg_items']:.1f})"
        )
        print(
            f" Held-out Winner MAE: {hc['winner_heldout_mae']:.4f} vs Default MAE: {hc['default_heldout_mae']:.4f}"
        )

    print("\n--- Planner Arms Summary (Nominal Profile, Budget 15m) ---")
    for sc in planner:
        print(f"\nScenario: {sc.upper()}")
        for arm in ["adapt", "no_review", "no_replan", "static"]:
            row = planner[sc][arm]
            print(
                f"  {arm:10s} : MasteryRate={row['goal_mastery_rate']:.1%} | MeanTheta={row['mean_true_goal_mastery']:.4f} | Retention={row['mean_retention']:.4f} | Days={row['mean_days_used']:.1f} | Violations=(Exec:{row['executed_prereq_violations']}, Plan:{row['plan_prereq_violations']}, B:{row['budget_violations']})"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="AdaptEngine Evaluation Runner")
    parser.add_argument(
        "--quick", action="store_true", help="Run quick 10-learner evaluation (for CI)"
    )
    parser.add_argument(
        "--seeds", type=int, default=100, help="Number of learners to simulate (default 100)"
    )
    parser.add_argument("--start", type=int, default=100, help="Starting random seed (default 100)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output JSON path")
    args = parser.parse_args()

    results = run_evaluation(
        num_seeds=args.seeds, seed_start=args.start, quick=args.quick, out_path=args.out
    )
    print_evaluation_summary(results)


if __name__ == "__main__":
    main()
