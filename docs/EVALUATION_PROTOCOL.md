# Evaluation Protocol (Milestone M8)

> **Status:** **Implemented (W6, M8)** (Implemented in `experiments/` harness; verified by `make eval`, `make eval-quick`, and `tests/test_evaluation.py`).

This document specifies the experimental protocol, simulator dynamics, frozen baselines, evaluation workloads, and metrics for benchmarking AdaptEngine.

---

## 1. Transparent Synthetic Simulator Design

The evaluation environment relies on a transparent simulator whose internal dynamics intentionally differ from the planner's BKT model:
- **Independent Dynamics:** Simulates learner transitions via an item response or multi-factor dynamic model with forgetting, rather than the planner's discrete BKT equations.
- **Empirical Grounding (corrected in W7):** the W6 simulator parameters were synthetic assumptions, not sampled from dataset ranges (see §6.1). W7 fitted BKT parameters on ASSISTments 2009 and Cognitive Tutor data (maths) and records the provenance of every simulator parameter in §8.
- **Mismatched Variants:** Evaluation includes at least one deliberately mismatched profile (e.g., learners with higher slip rates or rapid decay) to measure planner robustness under model misspecification.

---

## 2. Frozen Baselines

All comparative evaluations compare AdaptEngine against standard, frozen baselines under matched conditions:

1. **Fixed-Order Diagnostic:** Administers activities in static prerequisite order up to the same item budget $N_{\max}$.
2. **Random Diagnostic:** Selects valid unasked activities uniformly at random up to $N_{\max}$.
3. **Static Prerequisite Planner:** Schedules all prerequisite-unlocked activities sequentially without adaptive difficulty or review balancing.
4. **Greedy Planner without Review:** Packs activities to maximize new skill coverage while ignoring forgetting decay.
5. **Full Recomputation Replanner:** Recomputes the entire schedule from scratch on every event, used to benchmark frontier replanning speedup.

---

## 3. Paired Workloads & Evaluation Splits

- **Paired Evaluations:** Every candidate method and baseline is evaluated on the exact same synthetic learner profiles, goal sets, deadlines, daily budgets (5, 10, 15, 30 min), and random seeds.
- **Tuning vs. Held-Out Split:**
  - 50% tuning split for parameter exploration.
  - 50% held-out test split evaluated once. Hyperparameters are never tuned on held-out workloads.

---

## 4. Evaluation Metrics

### 1. Constraint Adherence
- **Prerequisite Violations:** Rate of activities scheduled before prerequisites are evidence-mastered (must be strictly 0.0%).
- **Budget Violations:** Rate of days exceeding daily time budgets (must be strictly 0.0%).
- **Feasibility Classification Rate:** Accuracy of feasibility bounds and exact oracle verdicts.

### 2. Prediction & Calibration
- **Diagnostic Estimation Error:** Mean Absolute Error (MAE) between estimated mastery and simulator ground truth at matched item counts.
- **Calibration (Brier Score):** Mean squared error of predicted success probabilities $P_c$ on held-out attempts.
- **Next-Attempt Accuracy:** Area Under ROC Curve (AUC) on held-out learner attempts.

### 3. Learning Outcomes & Efficiency
- **Goal Mastery Rate:** Percentage of target concepts mastered by the deadline.
- **Review Retention:** Retention rate of previously mastered concepts at the end of the horizon.
- **Replanning Latency:** Mean execution time for schedule updates (frontier vs full recomputation).
- **Explanation Coverage:** Percentage of scheduled and omitted actions carrying complete machine-readable decision traces.

---

## 5. Reproducibility & Limitations

- **Strict Repeatability (TC8.1):** Identical random seeds and configurations must yield bitwise identical output logs and summary metrics.
- **Measured Improvement (TC8.2):** At least one concrete, measured improvement will be reported in detail: frontier replanning latency reduction over full recomputation with identical decisions.
- **Prototype Scale Limitations:** Results must be characterized as prototype-scale findings based on synthetic fixtures and simulated learner responses. Repeatability and low latency alone do not constitute proof of human pedagogical efficacy.

---

## 6. Implementation Deviations & Scope Clarifications

The evaluation harness implemented in Week 6 (`experiments/`) satisfies all core requirements with the following concrete implementation notes:
1. **Simulator Parameter Provenance:** Synthetic 2PL IRT parameters ($a=3.0$, $\theta \sim U(0.1, 0.9)$) and heuristic cutoff ($0.70$) are defined as transparent, reproducible synthetic heuristics rather than directly trained on raw external dataset dumps (such as ASSISTments), eliminating heavy external data dependencies while maintaining realistic psychometric response curves.
2. **Key-Derived Uniform Noise:** Randomness is derived strictly from keyed uniform pseudo-random generators (`keyed_uniform(seed, tag, activity_id, n)`), guaranteeing noise isolation and eliminating PRNG stream leakage between paired arms.
3. **Diagnostic Trade-off:** Whole-curriculum diagnostic MAE is evaluated alongside assessed-only MAE. The adaptive diagnostic intentionally stops at threshold/cap ($N \approx 2.96$ items on the 50 held-out learners; corrected in W7), leaving unassessed concepts at the default prior ($0.20$), trading full-coverage certainty for speed.
4. **Frontier Replanning Memoization:** Implemented via caller-owned `WorkloadCache` memoizing per-concept workload projections, achieving identical decisions and measurable latency reduction without introducing stateful side-effects to `Engine`.

## 7. Week 7 Pre-registered Rules

Each rule below was written, hashed and logged in `docs/WEEK7_REPORT_NOTES.md` before the corresponding run, and is applied as written. Full text: `docs/preregistration/`.

### 7.1 Diagnostic configuration selection (T3.3, replaces D39)

Registered 2026-11-08T17:57:34Z, code_hash `a2a144aa…7ceaf` (`docs/preregistration/W7_T3.3_2026-11-08.md`).

- Grid (648 configs): `min_items_per_concept` {1, 2} × `pruning_mode` {hard, soft, none} × `selection_scope` {concept_sweep, frontier} × `prior_mode` {flat, population} × `h_stop` {0.20, 0.35, 0.50} × `concept_cap` {2, 3, 4} × `n_max` {4, 6, 8}; 4-node, world S0, nominal; tuning = even seeds 100–198, held-out = odd seeds 101–199.
- Metric: per-learner Brier vs 1[θ ≥ 0.70].
- Rule: among configs with ≤ 8 mean items on the tuning cohort, lowest tuning Brier; ties → fewer items → smallest settings tuple. Winner becomes the default iff its held-out Brier is below the shipped default's.

### 7.2 Mismatched simulator variants and stress cases (T4.1)

Registered 2026-11-08T18:05:23Z, code_hash `8ef52d54…3b8e02` (`docs/preregistration/W7_T4.1_2026-11-08.md`).

- Worlds S0–S4 (`experiments/sim.py`); arms adapt, adapt_expected, no_review, no_replan, static; scenarios calm, missed_day, budget_drop, deadline_cut + stress missed_2days, budget_crash (30→5), deadline_halved, forgetting_21 (fast_forgetter, 21 days; also engine h = 7 arms).
- Curricula 4-node / 8-node / synth-20; budgets 5/10/15/30; N = 200 per cell; headline S1, 4-node, B=15, calm, N = 1000 (S0 counterpart also N = 1000).
- Primary metrics: executed prerequisite violations; goal true-mastery rate (adapt − static, paired 95% CI). Secondary metrics as listed in the registration file. Hypotheses H1–H3 reported whatever the outcome.

## 8. Simulator Parameter Provenance (W7 T4.3, T7.5)

Real-data ranges come from `experiments/results/bkt_fit_assist09.json` (ASSISTments 2009 skill-builder, 81 skills) and `experiments/results/bkt_fit_ct.json` (Cognitive Tutor, 9 KCs). **Both are school-maths datasets, not Python**: they give realistic ranges and shapes, not values for this project's learners.

| Parameter (`experiments/sim.py`) | Value / range | Source |
|---|---|---|
| Initial ability θ (S0, S1, S3) | U(0.10, 0.90) per concept, independent | Synthetic assumption. Implied base rate of 1[θ ≥ 0.70] = 0.24 (T3.3); fitted BKT priors are higher (median 0.680 ASSISTments, 0.586 CT) |
| 2PL discrimination a | 3.0 | Synthetic assumption |
| Correlated abilities (S2) | g ~ U(0.2, 0.8), θ_c = clip(g + N(0, 0.10), 0.05, 0.95) | Synthetic assumption (multivariate-Elo motivation, R§2.4) |
| Lesson gain / exercise gain (nominal) | 0.18 / 0.05 of the remaining gap | Synthetic assumption. Fitted per-opportunity learn rates: ASSISTments median 0.113 [IQR 0.060–0.207], CT 0.230 [0.134–0.384]; the nominal exercise gain is at the low end |
| rapid_learner gains | 0.30 / 0.10 | Synthetic assumption (inside the fitted learn IQRs) |
| Slip (high_slip profile) | 0.15 extra slips (nominal 0) | Fitted slip medians 0.196 (ASSISTments), 0.140 (CT) |
| Readiness gating (S1) | sigmoid(10 (θ_pre − 0.70)) | Synthetic assumption (PSI-KT-style prerequisite influence, R§8.10) |
| Forgetting | fast_forgetter h = 7 d power law; S3 per-learner h ~ U(5, 30) d | Synthetic assumption (neither dataset has usable retention intervals) |
| S4 world | P0 0.20, g(d) = 0.30(1 − d), s(d) = 0.05 + 0.25d, T_lesson 0.20, T_ex 0.05 | The engine's own heuristics (well-specified world) |
| S4-fitted world (exploratory) | P0 0.741, learn 0.0725, guess easy/med/hard 0.369/0.147/0.058, slip 0.132/0.342/0.646 | `config/fitted_assist09.json` (pooled multigs fit, 200-bootstrap CIs in the profile) |
| TRUE_MASTERY_CUTOFF | 0.70 | Synthetic definition of "really knows it" |

