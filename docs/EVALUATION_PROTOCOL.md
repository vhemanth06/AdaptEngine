# Evaluation Protocol (Planned Milestone M8)

> **Status:** **PLANNED** (Design finalized in Appendix A; scheduled for implementation in Week 6).

This document specifies the experimental protocol, simulator dynamics, frozen baselines, evaluation workloads, and metrics for benchmarking AdaptEngine.

---

## 1. Transparent Synthetic Simulator Design

The evaluation environment relies on a transparent simulator whose internal dynamics intentionally differ from the planner's BKT model:
- **Independent Dynamics:** Simulates learner transitions via an item response or multi-factor dynamic model with forgetting, rather than the planner's discrete BKT equations.
- **Empirical Grounding:** Simulator parameters are sampled from published parameter ranges in public educational datasets (such as ASSISTments and Junyi Academy).
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
