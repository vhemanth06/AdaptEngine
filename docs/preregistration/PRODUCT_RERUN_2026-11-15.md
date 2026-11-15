# Pre-registration PRODUCT_RERUN — product-engine rerun of the experiment suite E1–E6

- **Registered:** 2026-11-15, before any E1–E6 run of the rewritten suite.
Code hash (src/, SHA-256): `6c55d4f99dc1af50871f35ae113c9bacc11cade68936a579b0cab76bd43b836a`
- Computed by `.venv/bin/python experiments/provenance.py` (SHA-256 over `src/**/*.py`; no git). `scripts/run_experiments.py` parses exactly the line above and refuses to start any runner if the current hash differs.
- Command: `.venv/bin/python scripts/run_experiments.py` (`make final`). Runs E1–E6 in order, then `experiments/make_results.py` if present.
- Any change to `src/` after this file requires a new registration with the new hash.

## 1. Product definition (verbatim from the plan)

**Product engine:** `product_config(profile)` = `load_profile(profile, **PRODUCT_OVERRIDES)` from `adaptengine.core.profiles`. That is θ 0.95, k_responses 1, horizon_aware_mastery off, consolidation **off**, verification_probe on, feasibility_warning on, selection_scope `goal_search`, concept_cap 4, n_max 25, diag_budget_min 12, diag_budget_per_concept 1.0, diagnostic_scope `goal_path`.

**Curricula:** `4node_x10`, `8node_x10` (promoted from `data/drafts/` on 2026-11-15, review manifest reviewer vhemanth06), `synth-20-x10`, `synth-50-x10`. The x10 difficulties are `(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9)`.

**Shared definitions (EVALUATION_PROTOCOL, FINAL_A5):**

- **Worlds** (`experiments/sim.py`):
  - **S0:** θ ~ U(0.10, 0.90) per concept, 2PL a = 3.0.
  - **S1:** S0 + readiness gating sigmoid(10(θ_pre − 0.70)).
  - **S2:** correlated abilities, g ~ U(0.2, 0.8), θ_c = clip(g + N(0, 0.10), 0.05, 0.95).
  - **S3:** per-learner forgetting, h ~ U(5, 30) d.
  - **S4:** the engine's own BKT heuristics: P0 0.20, g(d) = 0.30(1 − d), s(d) = 0.05 + 0.25d, T_lesson 0.20, T_ex 0.05.
  - **S4F:** S4 with `s4_fitted_params("config/fitted_assist09.json")`.
- **True mastery:** θ ≥ `TRUE_MASTERY_CUTOFF` = 0.70.
- **Sim profiles:** nominal (lesson / exercise gain 0.18 / 0.05), high_slip, fast_forgetter (h = 7 d), rapid_learner.
- **Scenarios** (`arms.get_scenario`): calm, missed_day, budget_drop, deadline_cut, missed_2days, budget_crash (30→5), deadline_halved, forgetting_21 (fast_forgetter, 21 days). Horizons are `("w7", 7, 14, 21)`. `w7` is computed from the W7 default engine for every arm.
- **Run modes** (`arms.run_episode`): `adapt`, `adapt_dx`, `no_review` (closed loop); `static`; `static_loop`, `random_eligible` (sequence); any other name, for example `no_replan`, plans once.
- **Statistics:** paired bootstrap 95% CI (2000 resamples, seed 20260), no multiplicity correction, every cell reported.

## 2. Ruling

Product arms use `fitted_S1` in **every** simulated world, as real users get. The only exception is E5 O.3, which compares `fitted_S3` with `fitted_S3_forget`.

## 3. Seeds (held-out; `experiments/common.py`)

| Use | Seeds | Parity |
|---|---|---|
| Profile fitting (FIT_SEEDS) | 2000, 2002, …, 2398 (200) | even |
| Bandit training (TRAIN_SEEDS, E4 train) | 6000, 6002, …, 6398 (200) | even |
| HLR fit (HLR_SEEDS, E5 hlr) | 8000, 8002, …, 8398 (200) | even |
| **Reporting** (REPORT_SEEDS) | 2001, 2003, …, 2399 (200 per cell) | **odd** |
| Headline cell (HEADLINE_SEEDS) | 2001, 2003, …, 3999 (1000) | odd |

Reporting uses odd seeds only. Tuning and fitting never touch odd seeds. Smoke runs use truncated seed lists and write `*_smoke` outputs; they are not results.

## 4. Experiments

All outputs go to `experiments/results/<name>.json` (or `--out-dir`), with a `provenance.stamp()` and `"engine": "product"`. Executed prerequisite violations must be 0 in every adaptive arm; static baselines (`static`, `static_loop`, `random_eligible`) and the open-loop `product_noreplan` are excluded from that gate.

### E1 — closed-loop grid

`.venv/bin/python experiments/run_grid.py --grid both` → `grid.json`.

- **Arms (primary):** product (adapt_dx), product_nodx (adapt), product_consol (consolidation on), product_norev (no_review), product_noreplan, w8_final (the old W8 config on the fitted profile), static, static_loop, random_eligible.
- **Primary cells:** worlds S0, S1, S4, S4F × curricula 4node_x10, 8node_x10 × budgets 10, 15 × scenarios calm, missed_day, missed_2days × horizons w7, 7, 14, 21; plus forgetting_21 (horizon 21) per world × curriculum × budget. REPORT_SEEDS (200); headline cell S1 | 4node_x10 | B15 | calm | h14 uses HEADLINE_SEEDS (1000).
- **Stress cells:** worlds S0–S4 × 4node_x10, 8node_x10, synth-20-x10 × budgets 5, 15, 30 × scenarios budget_drop, deadline_cut, budget_crash, deadline_halved, horizon w7. Arms: product, product_noreplan, static_loop. REPORT_SEEDS.
- **Metrics:** goal mastery rate, all-required rate, false mastery rate, minute utilisation, diagnostic minutes, items per mastered concept, reach rate, Kaplan-Meier median and RMST, in-loop Brier and AUC, executed/plan prerequisite and budget violations.
- **Comparisons:** every arm vs static_loop, paired by seed, on goal mastery and all-required mastery (paired bootstrap 95% CI).
- **Decisions:** `product_noreplan` is non-adaptive (plans once, open loop) and is excluded from the 0-violation gate, like the static baselines. In-loop AUC is computed from per-seed 100-bin histograms (approximate); Brier is exact.

### E2 — diagnostic accuracy

`.venv/bin/python experiments/run_diag.py` → `diag_matrix.json`.

- **Cells:** worlds S0, S1, S2, S4 × all four curricula (day-0 diagnostic), REPORT_SEEDS.
- **Arms:** prior_only; product (diagnostic_scope "all", every concept scored); product_goalpath (shipped scope, goal + ancestors scored); concept_sweep_w7 (DEFAULT_CONFIG diagnostic fields on the product engine); frontier; state_space; fixed@n; random@n; irt_cat@n.
- **Metrics:** AUC and Brier of the estimated mastery against truth 1[θ ≥ 0.70] at day 0, plus items and minutes used.
- **Decisions:** fixed@n, random@n and irt_cat@n use the product item count for that same learner (matched budget). state_space runs only for ≤ 12 concepts and is not budget-matched. irt_cat uses the simulator's true discrimination a = 3.

### E3 — sensitivity

`.venv/bin/python experiments/run_sensitivity.py` → `sensitivity.json`. A measurement, not a selection.

- **Cells:** worlds S0, S1, S4 × 4node_x10, 8node_x10, budget 15, calm, horizon 14, REPORT_SEEDS.
- **Configs:** one-at-a-time scans around the product config: theta {0.85, 0.90, 0.95, 0.98}; k_responses {1, 2, 3}; mastery_criterion {bkt_threshold, two_threshold, n_consecutive}; horizon_aware_mastery {off, on}; consolidation {off, on}; concept_cap {2, 4, 6}; n_max {12, 25, 40}; diag_budget_per_concept {0, 0.5, 1, 2}; known_threshold {0.6, 0.7, 0.8}; skip_threshold {0.3, 0.4, 0.5}; selection_scope {concept_sweep, frontier, goal_search}; pruning_mode {hard, soft, none}; plus the theta × k_responses factorial. Arm adapt_dx; static_loop once per cell as reference.
- **Comparisons:** each config vs the product config, paired by seed. Combinations rejected by config validation are logged under `meta.skipped`.

### E4 — LinUCB bandit re-ranker

`.venv/bin/python experiments/run_policy.py train` then `.venv/bin/python experiments/run_policy.py eval` → `config/policy_frozen.json`, `policy_train.json`, `policy_eval.json`, `policy_logs/*.jsonl`.

- **Train:** one BanditPolicy("updating", lam 1, alpha 0.3, tau 0.1, zero weights), sequential over TRAIN_SEEDS × cells.
- **Cells:** S1, S4 × 4node_x10, 8node_x10, budget 15, calm, horizon 14 d, REPORT_SEEDS.
- **Variants:** deterministic, frozen, updating, random.
- **Metrics:** goal mastery, all-required, Kaplan-Meier median and RMST; off-policy evaluation of the frozen policy from the random and updating logs vs its simulated value.
- **Comparisons:** each variant vs deterministic, paired by seed.
- **Decision:** the `updating` eval variant starts each episode from the frozen weights and updates within that episode only (FINAL_A5 §6).

### E5 — extensions

`.venv/bin/python experiments/run_extensions.py all` → `extensions.json`, `hlr_fit.json`.

- **review_cap (D.1):** worlds S0, S1 × synth-20-x10 × budgets 10, 15, forgetting_21, horizon 21. Arms product_nodx, capped (review_cap_fraction 0.25, review_goal_path_only), product_norev. Reference product_norev. Pass rule, applied to goal mastery: the paired 95% CI of (capped − product_norev) includes or exceeds 0 (fails only if its upper bound < 0).
- **elo (O.1):** mastery_model elo vs bkt; worlds S0, S1, S4 × 4node_x10, B15, calm, h14.
- **hlr (O.2):** HLR-lite weights fitted on product adapt_dx episodes (curricula 4node_x10 and 8node_x10, world S3, scenario forgetting_21, budget 15, fast_forgetter profile) with HLR_SEEDS (200 seeds × 2 curricula); evaluated on REPORT_SEEDS, worlds S0, S3 × 4node_x10, 8node_x10, B15, forgetting_21, h21. Arms fixed, hlr, product_norev, all in mode `adapt` (no diagnostic) to match product_norev.
- **forgets (O.3):** fitted_S3 vs fitted_S3_forget; S3 × 4node_x10, B15, forgetting_21, h21.
- **Metrics and comparisons:** the E1 summary metrics, paired by seed against the stated reference arm.

### E6 — planner cost

`.venv/bin/python experiments/run_planner_cost.py all` → `planner_cost.json`. Single process; latency = median of repeated perf_counter timings (ms).

- **cpsat:** greedy vs CP-SAT (vs the branch-and-bound "oracle", the default engine's fallback when greedy misses the deadline) on synth-20-x10 and synth-50-x10. L = last day of the greedy plan under a 1000-day deadline; deadlines {L, ceil(0.9L), ceil(0.8L)}; budget 15. Metrics: plan length, latency, audits. Prerequisite and budget violations must be 0 for both planners; the duplicate-activity audit is recorded for both planners and asserted 0 in tests for cpsat only: greedy plans can contain in-plan reviews even with maintenance_reviews=False (as the old run_cpsat_eval docstring noted).
- **replan:** full vs frontier replanning latency, all curricula × event types missed_day, failed_assessment, budget_change (value 10), deadline_change. Replan deadlines 20 / 30 / 40 / 80 (4node / 8node / synth-20 / synth-50), budget 15. These were chosen for the x10 curricula (old values were 10 / 15 / 25 / 60 and budgets {5, 10, 15, 30}).
- **plan:** initial planning latency, all curricula × budgets {5, 15, 30} × deadlines {7, 14, 28}.
- **diag:** wall time of one full product diagnostic per curriculum.

## 5. Measurement only

Nothing is selected from report seeds, and results are reported whatever they show. No parameter, arm or threshold is changed after seeing results; every cell is reported, with no multiplicity correction.

## 6. Not re-run

Fitted parameters (Part B keep list: `config/fitted_*.json`, `fit_bkt_sim` outputs), the agent evaluation, probes, and the B.3 and T3.3 selections. They are used as shipped.

## Amendment 1 (2026-11-15, before any full run)

Made after the final whole-branch review and before any full E1–E6 run; no result of the rewritten suite had been seen. Smoke runs only (truncated seeds, not results). The text above stands, except one typo fixed in §4 E6 (a stray capital). Where the text above and this amendment differ, this amendment describes what the code does.

**E1 — closed-loop grid (additions to §4 E1):**

- **Comparisons:** besides every arm vs static_loop, each ablation arm (product_nodx, product_consol, product_norev, product_noreplan) and `w8_final` vs `product`, paired by seed, on goal mastery and all-required mastery (paired bootstrap 95% CI, as in §1). Stored per cell under `paired_vs_product` (arm − product).
- **Headline cell:** Kaplan-Meier curve points (`km_curve`) for every arm, from the same times and events as the KM median and RMST.
- **Calibration:** per (cell, arm), 10 equal-width reliability bins (mean predicted P(correct), observed rate, n), merged from the 100-bin in-loop histogram (bin k → k // 10).
- **Diagnostic items:** `mean_dx_items` (diagnostic items per episode) beside diagnostic minutes.
- **Skipped stress cells:** `arms.get_scenario` defines no scenario for budget_drop at B5 (no lower allowed budget) and for budget_crash at B5 and B15 (defined only at B30). These 45 of the 180 stress cells are not run; 135 stress cells are effective. Their ids and reasons are recorded in `meta.skipped_cells`. Primary cells: 208.
- **Items per mastered concept:** sum over seeds of executed planned activities (lessons and exercises; diagnostic items excluded) divided by the sum over seeds of required concepts (goal and ancestors) with true θ ≥ 0.70 at episode end. Concepts already mastered at day 0 count in the denominator. Recorded in grid meta.
- **KM censoring:** an episode without goal mastery is censored at its minutes used. This censoring is informative (FINAL_A5 convention). RMST is restricted to τ = the max minutes available in the (cell, arm).

**`w8_final`:** uses the profile `fitted_{world}` (S4F → `fitted_S4`), not `fitted_S1`. This is a second exception to the §2 ruling, beside E5 O.3. Its config differs from the old W8 `adapt_final_dx` only in `diag_budget_min` (12 vs 6) and `feasibility_warning` (True vs False). Both differences are inert: with `diag_budget_per_concept` = 0 the diagnostic budget is `n_max`, and the feasibility warning only annotates the plan.

**E2 — metrics as built (replaces the §4 E2 metrics line):** per (cell, arm): Brier, AUC, MAE of the estimated mastery; Known label accuracy (p ≥ 0.70) and Unknown label accuracy (p < 0.40) with their counts; INFERRED precision (share of concepts stopped as INFERRED that are truly mastered) with the INFERRED count; items used (mean, p90); the stop-reason histogram. No minutes are measured; the "minutes used" in §4 E2 was wrong.

**E3 — metrics:** the E1 summary metrics plus diagnostic items, each config paired by seed vs the product config and vs static_loop.

**E4 — decision logging fix:** the episode logger matched POLICY_SELECTED plan-trace entries to executed activities by `id(plan)`. CPython reuses the id of a freed plan, so some decisions were silently dropped. It now matches only the latest plan (the consumed set is cleared when a new plan arrives). Every policy-selected executed activity is logged once.

**E6 `diag`:** times the shipped goal-path diagnostic (`goal_concepts = [goal]`, diagnostic_scope `goal_path`, goal + ancestors), not a diagnostic over every concept. The §4 E6 "one full product diagnostic" means this flow.

**Synthetic x10 curricula:** activity durations per concept are `[1, 1, 2, 2, 2, 2, 3, 3, 3, 3]` minutes for the ten exercises, in difficulty order.

**Mechanics (no effect on any number):** `provenance.stamp()` adds `experiment_hash`. `scripts/run_experiments.py` checks both registered hashes before every step, including `make_results.py`. It always passes `--resume` to E1, whose checkpoint is keyed on both hashes; lines written under other hashes are counted in `meta.checkpoint_lines_other_hash` and never used. `--from EN` runs EN and every later step; `--only` runs the named steps; both then run `make_results.py` unless `--no-results` is given. `make_results.py` prints a top-of-document WARNING for every input whose code or experiment hash differs from the registered ones, or that is missing. Smoke E4 logs go to `policy_logs_smoke/`. The E5 review_cap pass rule is written `pass = hi ≥ 0`; the rule is unchanged.

**Experiment hash:** SHA-256 over the sorted repo-relative path and bytes of `experiments/**/*.py`, `scripts/run_experiments.py`, `config/fitted_*.json` and `data/curriculum/*_x10.json`, excluding `config/policy_frozen.json` (an E4 output) and everything under `experiments/results/`. Computed by `.venv/bin/python experiments/provenance.py` after every edit above was final. Any change to these files after this amendment requires a new amendment with the new hash, as for `src/` (§ header). The src/ code hash registered above is unchanged.

Experiment hash (SHA-256): `24eabf602925b8f5b0f4e0ff63087612ff6b8dc956e78257eb3fc780f0426715`
