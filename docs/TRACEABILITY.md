# Authoritative Traceability Matrix (23-ID Register)

This document tracks all 23 verification scenarios (TC1.1 through TC8.2) across milestones M1–M8, linking each implemented scenario to its concrete test suite or marking target delivery weeks.

| TC-ID | Milestone | Scenario / Specification | Target | Implementation & Test Evidence | Status |
|---|---|---|---|---|---|
| **TC1.1** | M1 | Inject a cycle into curriculum graph => typed `CycleError` naming concepts | W2 | `tests/test_graph.py::test_cycle_detection`, `tests/test_cli.py::test_cli_validate_error` | **Verified** |
| **TC1.2** | M1 | Valid and invalid curriculum, state, event, config fixtures; unreviewed content rejected; state/log unchanged | **W3** | `tests/test_schema.py::test_valid_fixtures_load`, `tests/test_schema.py::test_invalid_curriculum_fixtures`, `tests/test_loader_review_gate.py::test_ai_reviewer_rejected`, `tests/test_defects_repro.py` | **Verified** |
| **TC2.1** | M2 | Diagnostic stops at entropy threshold or cap, never exceeds $N_{\max} = 8$ | **W3** | `tests/test_diagnostic.py::test_adversarial_learner_bounded_by_n_max`, `tests/test_diagnostic.py::test_entropy_stopping_rule` | **Verified** |
| **TC2.2** | M2 | No prior observations => `UNASSESSED`, prior state preserved | **W3** | `tests/test_diagnostic.py::test_cold_start_unassessed_preserved` | **Verified** |
| **TC2.3** | M2/M3 | Two learners, same goal/budget => different individually valid plans | **W4** | `tests/test_planner.py::test_tc2_3_two_learners_different_valid_plans` | **Verified** |
| **TC3.1** | M3 | Locked prerequisite is never scheduled before evidence-mastered | **W4** | `tests/test_planner.py::test_tc3_1_locked_prerequisite_never_scheduled_before_mastered` | **Verified** |
| **TC3.2** | M3 | No day in generated plan exceeds the configured daily budget | **W4** | `tests/test_planner.py::test_tc3_2_daily_budget_never_exceeded` | **Verified** |
| **TC3.3** | M3 | 5 min vs 30 min daily budgets produce materially different pacing | **W4** | `tests/test_planner.py::test_tc3_3_pacing_disparity_5min_vs_30min` | **Verified** |
| **TC3.4** | M3 | Infeasible goal/deadline returns `INFEASIBLE` with shortfall and corrective options | **W4** | `tests/test_planner.py::test_tc3_4_infeasible_goal_shortfall_and_options` | **Verified** |
| **TC3.5** | M3 | 8+8+4 fixture with 10-min budget passes simple bounds but exact oracle returns `INFEASIBLE` | **W4** | `tests/test_planner.py::test_tc3_5_abstract_8_8_4_oracle_infeasible` | **Verified** |
| **TC3.6** | M3 | Search node limit returns `UNKNOWN`, never a false infeasible | **W4** | `tests/test_planner.py::test_tc3_6_oracle_node_limit_returns_unknown` | **Verified** |
| **TC4.1** | M4 | Wrong answer at low mastery: `0.1707` posterior / `0.2122` after $T=0.05$; adapter matches oracle | W2–**W3** | `tests/test_mastery.py::test_update_values`, `tests/test_adapter.py::test_custom_bkt_reference_parity`, `tests/test_adapter.py::test_adapter_oracle_parity_at_representative_difficulties` | **Verified** |
| **TC4.2** | M4 | Next exercise nearest target success probability ($P_c \approx 0.75$) with D10 tie-break | W3–**W4** | `tests/test_diagnostic.py::test_tie_breaking_d10`, `tests/test_planner.py::test_tc4_2_difficulty_policy_target_success_and_tie_breaking`, `tests/test_planner.py::test_tc4_2_difficulty_policy_unreachable_target` | **Verified** |
| **TC5.1** | M5 | Mastered concept omitted from new learning, trace cites evidence | W5 | *Deferred (Milestone M5 - Target Week 5)* | Deferred |
| **TC5.2** | M5 | Concept with $p < 0.40$ triggers remediation insertion | W5 | `tests/test_diagnostic.py::test_descendant_skipping_on_low_mastery` (diagnostic skip implemented; planner remediation target W5) | **Partial (Diag W3 / Plan W5)** |
| **TC5.3** | M5 | High-urgency review beats lower-urgency new content under shared budget | W5 | *Deferred (Milestone M5 - Target Week 5)* | Deferred |
| **TC6.1** | M6 | Missed day triggers valid replan without lost or duplicated work | W5 | *Deferred (Milestone M6 - Target Week 5)* | Deferred |
| **TC6.2** | M6 | Failed assessment updates state and triggers valid replan | W5 | *Deferred (Milestone M6 - Target Week 5)* | Deferred |
| **TC6.3** | M6 | Deadline change triggers valid replan or `INFEASIBLE` | W5 | *Deferred (Milestone M6 - Target Week 5)* | Deferred |
| **TC6.4** | M6 | Daily budget change triggers valid replan | W5 | *Deferred (Milestone M6 - Target Week 5)* | Deferred |
| **TC7.1** | M7 | Every decision traceable to state, applied constraints, and score components | W5–W6 | *Deferred (Milestone M7 - Target Week 6)* | Deferred |
| **TC8.1** | M8 | Identical random seeds and configuration produce bitwise identical raw results | W6 | `tests/test_diagnostic.py::test_deterministic_identical_runs` (deterministic diagnostic verified; simulator target W6) | **Partial (Diag W3 / Sim W6)** |
| **TC8.2** | M8 | Frontier vs full replanning produces identical decisions with runtime latency measured | W6–W7 | *Deferred (Milestone M8 - Target Week 6)* | Deferred |
