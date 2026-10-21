# AdaptEngine — Decision & Acceptance Freeze Record

**Freeze Date:** 21 October 2026  
**Accountable Owner:** Hemanth (`vhemanth06`)  
**Status:** ALL DECISIONS & CORE ACCEPTANCE GATES FROZEN  

---

## 1. Executive Summary

This record formally freezes all pedagogical, mathematical, architectural, and persistence decisions for **AdaptEngine** as delivered on 21 October 2026. Every item has been reviewed, approved by Hemanth, and verified against concrete automated test suites.

---

## 2. Frozen Decision Register (D1 – D34)

| # | Topic | Frozen Choice | Approval Status | Verification Evidence |
|---|---|---|---|---|
| **D1** | Global diagnostic item cap $N_{\max}$ | 8 items | Approved by Hemanth | `tests/test_diagnostic.py::test_adversarial_learner_bounded_by_n_max` |
| **D2** | Per-concept diagnostic item cap | 3 items | Approved by Hemanth | `tests/test_diagnostic.py::test_per_concept_cap` |
| **D3** | Entropy stopping threshold $H_{\text{stop}}$ | $H(p) \le 0.50$ | Approved by Hemanth | `tests/test_diagnostic.py::test_entropy_stopping_rule` |
| **D4** | Evidence-mastered requirement | $p \ge \theta$ and $\text{responses} \ge k$ | Approved by Hemanth | `tests/test_mastery.py`, `tests/test_feedback_fixes.py` |
| **D5** | Exercise state update | Post-transition $p''$ ($T=0.05$) | Approved by Hemanth | `tests/test_mastery.py::test_update_values` |
| **D6** | Adapter difficulty classes | 3 classes (easy, medium, hard) | Approved by Hemanth | `tests/test_adapter.py::test_adapter_oracle_parity_at_representative_difficulties` |
| **D7** | Lesson prior shift | Yes, via $T_{\text{lesson}} = 0.20$ | Approved by Hemanth | `tests/test_state_session.py::test_apply_lesson` |
| **D8** | Diagnostic descendant pruning | Prune descendants if ancestor $p < 0.40$ | Approved by Hemanth | `tests/test_diagnostic.py::test_descendant_skipping_on_low_mastery` |
| **D9** | Review manifest gate | Named human reviewer required; AI rejected | Approved by Hemanth | `tests/test_loader_review_gate.py::test_ai_reviewer_rejected` |
| **D10** | Activity selection tie-break | Min $|d - 0.50|$, then lexicographic ID | Approved by Hemanth | `tests/test_diagnostic.py::test_tie_breaking_d10` |
| **D11** | Multi-day workload projection | Project workload assuming correct responses | Approved by Hemanth | `tests/test_planner.py::test_tc3_1_locked_prerequisite_never_scheduled_before_mastered` |
| **D12** | Same-day prerequisite unlock | Allowed; within-day respects DAG order | Approved by Hemanth | `tests/test_planner.py::test_same_day_unlock_respects_prerequisites` |
| **D13** | Unlock heuristic score | Transitive descendant count | Approved by Hemanth | `tests/test_planner.py` |
| **D14** | Lesson difficulty fit | Neutral (0.0) | Approved by Hemanth | `tests/test_planner.py` |
| **D15** | Daily budget packing rule | Skip non-fitting item, continue packing | Approved by Hemanth | `tests/test_planner.py::test_packing_skip_continue` |
| **D16** | Within-concept sequence | Lessons before exercises (queue order) | Approved by Hemanth | `tests/test_planner.py` |
| **D17** | Oracle search boundary | Node expansion count (`oracle_node_limit`) | Approved by Hemanth | `tests/test_planner.py::test_tc3_6_oracle_node_limit_returns_unknown` |
| **D18** | Day numbering scheme | Discrete absolute integers | Approved by Hemanth | `tests/test_planner.py` |
| **D19** | Feasibility lower bound | Critical path duration and bin-packing bounds | Approved by Hemanth | `tests/test_planner.py::test_tc3_4_infeasible_goal_shortfall_and_options` |
| **D20** | Remediation trigger | Failed response drops $p < 0.40$ | Approved by Hemanth | `tests/test_w5.py::test_tc5_2_failed_exercise_remediation_flag_and_lesson` |
| **D21** | Remediation content | Re-issue lesson; clear flag on completion | Approved by Hemanth | `tests/test_w5.py::test_tc5_2_failed_exercise_remediation_flag_and_lesson` |
| **D22** | Unpracticed concepts anchor | Excluded from spaced review until practiced | Approved by Hemanth | `tests/test_review.py` |
| **D23** | Spaced review decay model | Fixed half-life $r(t) = 2^{-\Delta t / h}$ | Approved by Hemanth | `tests/test_review.py` |
| **D24** | Recall review threshold | $r(t) < 0.80$ triggers review item | Approved by Hemanth | `tests/test_review.py` |
| **D25** | Review urgency score | $(1 - r)(1 + \text{descendant\_count})$ | Approved by Hemanth | `tests/test_review.py` |
| **D26** | Priority tier order | Remediation $\to$ Reviews $\to$ New Lessons/Exercises | Approved by Hemanth | `tests/test_w5.py::test_tc5_3_high_urgency_review_scheduled_before_new_content` |
| **D27** | Review exercise selection | Exercise nearest $P_c \approx 0.75$; repeats allowed | Approved by Hemanth | `tests/test_review.py` |
| **D28** | `FAILED_ASSESSMENT` event | Requires `correct=False`; triggers remediation check | Approved by Hemanth | `tests/test_w5.py::test_tc6_2_failed_assessment_replan_with_remediation` |
| **D29** | Derived context pure fold | Fold events over initial `PlanContext` | Approved by Hemanth | `tests/test_w5.py::test_tc6_3_deadline_change_replan` |
| **D30** | Missed day replanning | Replan from $\text{missed\_day} + 1$, zero minutes recorded | Approved by Hemanth | `tests/test_w5.py::test_tc6_1_missed_day_replan_no_loss_or_duplication` |
| **D31** | Lessons vs Evidence contract | Option 1: $p \ge \theta$ and $\text{responses} \ge k$ | Approved by Hemanth | `tests/test_feedback_fixes.py::test_lessons_vs_evidence_contract_decision_d31` |
| **D32** | Atomic snapshot store (FB006) | Single canonical snapshot via `<path>.<pid>.tmp` | Approved by Hemanth | `tests/test_feedback_fixes.py::test_cli_atomic_snapshot_accumulation_and_restart` |
| **D33** | Single observation model | `MasteryModel` protocol used for EIG & updates | Approved by Hemanth | `tests/test_feedback_fixes.py::test_spy_model_receives_both_predict_and_update_calls` |
| **D34** | Session-scoped diagnostic IDs | `diag-<session_id>-<concept_id>-<n>` | Approved by Hemanth | `tests/test_feedback_fixes.py::test_session_scoped_diagnostic_ids_accumulate` |

---

## 3. Milestone Acceptance Status

- **M1: Curriculum & Learner State:** **FROZEN & VERIFIED** (`tests/test_graph.py`, `tests/test_schema.py`)
- **M2: Short Adaptive Diagnostic:** **FROZEN & VERIFIED** (`tests/test_diagnostic.py`)
- **M3: Time-Budgeted Path Planning:** **FROZEN & VERIFIED** (`tests/test_planner.py`)
- **M4: Mastery Estimation & Difficulty Policy:** **FROZEN & VERIFIED** (`tests/test_mastery.py`, `tests/test_adapter.py`)
- **M5: Spaced Review & Remediation:** **FROZEN & VERIFIED** (`tests/test_w5.py`, `tests/test_review.py`)
- **M6: Dynamic Replanning:** **FROZEN & VERIFIED** (`tests/test_w5.py`, `tests/test_feedback_fixes.py`)
- **M7: Traceability & Explainability:** **FROZEN & VERIFIED** (`tests/test_w5.py`, `scripts/poc_demo.py`)
- **M8: Paired Baseline Evaluation:** **FROZEN & VERIFIED** (`experiments/run_evaluation.py`, `tests/test_evaluation.py`)
