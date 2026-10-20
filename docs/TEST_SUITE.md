# AdaptEngine Test Suite Documentation

This document provides a comprehensive inventory and explanation of all unit, regression, and integration tests in AdaptEngine, covering both the foundational tests from earlier milestones (Week 1–2 / Milestone M1) and the additions and hardening introduced in Week 3 (Milestone M2 & hardening).

---

## 1. Executive Summary & Test Evolution

| Metric | Week 1–2 Baseline | Week 3 | Week 4 | Week 5 Current |
|---|---|---|---|---|
| **Total Test Count** | 47 tests | 80 tests | 106 tests | **122 tests** |
| **Statement Coverage** | 84.95% | 86.04% | 87.67% | **88.30%** (required $\ge 84\%$) |
| **Execution Time** | ~1.1s | ~1.8s | ~2.2s | **~1.5s** |
| **Test Suites** | 7 files | 10 files | 11 files | **14 files** |
| **Milestones Covered** | M1 (Foundation, Graph, Schema) | M1 + M2 (Adaptive Diagnostic) | M1 + M2 + M3 + M4 | **M1–M6 + M7 (Traces)** |
| **Defect Coverage** | None (defects present) | 100% regression proof D-A..D-H | 100% regression proof + W4 | **100% regression proof + W4 + W5** |

### Running the Test Suite

```bash
# Using Makefile (auto-detects local .venv)
make test

# Linting, formatting, and coverage verification
make check

# Full W5 acceptance runner (M5 review/remediation, M6 replanner, M7 traces)
make w5

# Full W4 acceptance runner (M3 planner, M4 policy, evidence package)
make w4

# Full W3 acceptance runner (diagnostic demo & W3 audit)
make w3
```

---

## 2. Test Suite Architecture & Traceability

The test suite maps directly to the repository's 23-ID authoritative traceability register (`records/TRACEABILITY.md`):

```
                        ┌────────────────────────────────────────────────────────┐
                        │              Authoritative Test Register               │
                        └────────────────────────────────────────────────────────┘
                                   │                                  │
                  ┌────────────────┴───────────────┐                  │
                  ▼                                ▼                  ▼
           Milestone M1 (W1-W3)              Milestone M2 (W3)    Milestone M4 (W2-W3)
        TC1.1: Cycle Detection (Graph)     TC2.1: Bounded Caps    TC4.1: Reference
        TC1.2: Schema & Review Validation  TC2.2: Cold Start             Constants Parity
```

---

## 3. Detailed Test Catalog by Module

---

### Suite 1: Milestone M2 Adaptive Diagnostic (`tests/test_diagnostic.py`)
*Added in Week 3 · 10 Tests · Module Coverage: 90%*

Validates the adaptive testing algorithm, Expected Information Gain (EIG) item selection, caps, stopping conditions, and DAG ancestor pruning.

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 1 | `test_adversarial_learner_bounded_by_n_max` | W3 (TC2.1) | $N \le N_{\max}$ | Simulates an adversarial learner who answers every question wrong. Asserts total items never exceed $N_{\max} = 8$. |
| 2 | `test_alternating_learner_bounded_by_n_max` | W3 (TC2.1) | $N \le N_{\max}$ | Simulates an alternating correct/incorrect learner. Asserts item sequence remains bounded by 8 despite high belief volatility. |
| 3 | `test_entropy_stopping_rule` | W3 (D3) | $H \le H_{\text{stop}}$ | Consistent correct learner stops probing a concept early when entropy $H(p) \le 0.50$ (i.e. $p \ge 0.89$), without exhausting caps. |
| 4 | `test_cold_start_unassessed_preserved` | W3 (TC2.2) | Prior state intact | Testing only `"C1"` ensures untouched concepts (`"C2"`, `"C3"`, `"C4"`) remain at prior $p_0=0.20$, `UNASSESSED`, with 0 responses. |
| 5 | `test_surprise_response_and_cap` | W3 | Entropy growth bounded | A learner starting at $p=0.90$ failing an item drops to $p'=0.6495$; entropy jumps from $0.469$ to $0.935$ bits; caps still bound run. |
| 6 | `test_descendant_skipping_on_low_mastery` | W3 (D8) | Prerequisite pruning | If `"C1"` ends with $p < 0.40$, its descendants (`"C2"`, `"C3"`, `"C4"`) are skipped (`SKIPPED_ANCESTOR_UNMASTERED`) and stay `UNASSESSED`. |
| 7 | `test_no_activity_asked_twice` | W3 | Item uniqueness | Candidate tracking ensures no activity ID is ever administered more than once in a diagnostic run. |
| 8 | `test_input_state_not_mutated` | W3 | Immutability | Input `LearnerState` is verified to be byte-identical before and after the diagnostic run. |
| 9 | `test_deterministic_identical_runs` | W3 | Determinism | Two runs with identical inputs produce identical item logs, probabilities, and EIG values. |
| 10 | `test_tie_breaking_d10` | W3 (D10) | Tie-breaking rule | Equal EIG breaks tie by smallest $\|d - 0.5\|$, then lexicographically by `activity_id`. |

---

### Suite 2: Mastery Model Adapter & pyBKT Parity (`tests/test_adapter.py`)
*Added in Week 3 · 5 Tests · Module Coverage: 94%*

Validates the `MasteryModel` protocol, discrete difficulty mapping, and mathematical parity against the analytical BKT oracle.

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 11 | `test_mastery_model_protocol_adherence` | W3 | Protocol conformance | Both `CustomBKT` (analytical oracle) and `PyBKTAdapter` conform to runtime `@runtime_checkable` `MasteryModel`. |
| 12 | `test_custom_bkt_reference_parity` | W3 (TC4.1) | Analytical parity | Validates `CustomBKT` matches the 5 reference constants: `0.8462`, `0.1707`, `0.8538`, `0.2122`, `0.6495`. |
| 13 | `test_difficulty_class_mapping_d6` | W3 (D6) | Discrete mapping | Confirms difficulty $d$ maps to: `easy` ($d < 0.35$), `medium` ($0.35 \le d < 0.65$), `hard` ($d \ge 0.65$). |
| 14 | `test_adapter_oracle_parity_at_representative_difficulties` | W3 (D6) | Parity $\le 10^{-9}$ | `PyBKTAdapter` matches `CustomBKT` within $10^{-9}$ at representative difficulties ($0.20, 0.50, 0.80$) across all $p$, correctness, and $T$. |
| 15 | `test_adapter_response_sequence_with_surprise_response` | W3 | Multi-step update | Runs sequential updates across easy, medium, and hard items, asserting accurate posterior tracking and surprise drop to $0.6495$. |

---

### Suite 3: Defect Reproduction & Regression Suite (`tests/test_defects_repro.py`)
*Added in Week 3 · 14 Tests*

Written during Phase 0 to reproduce every defect D-A through D-H observed during mentor review, ensuring permanent regression protection.

| # | Test Function | Defect ID | Target Fix | Scenario & Details |
|---|---|---|---|---|
| 16 | `test_repro_da_cli_unreviewed_accepted` | D-A | Default-on review gate | Proves CLI commands reject unreviewed curriculum files by default (non-zero exit code). |
| 17 | `test_repro_db_string_false_accepted` | D-B | Strict boolean types | Rejects `Event(correct="false")` with `ValidationError` instead of treating `"false"` as boolean `True`. |
| 18 | `test_repro_db_learner_concept_invalid_fields` | D-B | Range & invariant checks | Rejects negative uncertainty, non-boolean assessed, negative day, and negative half-life in `LearnerConcept`. |
| 19 | `test_repro_dc_unknown_prereq_phantom_node` | D-C | Unknown prereq check | Asserts `unknown_prereq.json` raises `UnknownConceptError` before NetworkX edge creation. |
| 20 | `test_repro_dc_json_list_root_raw_error` | D-C | Root object type check | Asserts JSON files with root `[...]` raise a clean `ValidationError` instead of unhandled `AttributeError`. |
| 21 | `test_repro_dd_lesson_assessed_and_replay` | D-D | Exposure vs evidence | 8× lesson replay increases belief but leaves `assessed=False` and `evidence_mastered=False`. |
| 22 | `test_repro_dd_last_practice_day_rewind` | D-D | Monotonic practice day | Completing an event on day 20 and then day 1 keeps `last_practice_day == 20`. |
| 23 | `test_repro_de_learn_t_out_of_bounds` | D-E | Bounded transition | $T = 1.5$ raises `ValidationError` instead of producing impossible probabilities ($p > 1.0$). |
| 24 | `test_repro_de_guess_slip_uses_resolved_config` | D-E | Dynamic config | Rejects difficulties outside custom `EngineConfig(d_min=0.10, d_max=0.90)`. |
| 25 | `test_repro_df_explicit_manifest_path` | D-F | Path resolution | Explicit `manifest_path="data/review_manifest.json"` resolves cleanly relative to content root. |
| 26 | `test_repro_df_ai_reviewer_rejected` | D-F | Human sign-off | Rejects review manifests listing `reviewer: "AI"` for live content loading. |
| 27 | `test_repro_dg_atomic_persistence_failure_injection` | D-G | Atomic persistence | Injects `os.replace` failure; original file remains untouched and `.tmp` is cleaned up. |
| 28 | `test_repro_dh_tools_authoring_isolation_real_check` | D-H | Real AST scan | Verifies the AST scanner flags prohibited imports (`random`, `time`, CLI imports). |
| 29 | `test_repro_di_cli_custom_paths` | D-I | CLI path flexibility | CLI commands accept caller-supplied `--curriculum` and `--activities` arguments. |

---

### Suite 4: Architecture & Layering Rules (`tests/test_architecture.py`)
*Rewritten in Week 3 · 3 Tests*

Performs static AST analysis across the entire codebase to enforce layering and determinism rules.

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 30 | `test_layering_and_dependency_rules` | W3 (Sec 2.2) | Unidirectional layering | Enforces $\text{core} \leftarrow \text{curriculum} \leftarrow \text{learner} \leftarrow \text{diagnostic} \leftarrow \text{session/api} \leftarrow \text{cli}$. |
| 31 | `test_third_party_isolation` | W3 (D-H) | Library encapsulation | `networkx` is only in `curriculum/graph.py`; `pybkt` is only in `learner/adapter.py`; no `random`/`time` in decision modules. |
| 32 | `test_tools_authoring_isolation` | W3 (D-H) | Scanner efficacy | Tests that synthetic prohibited imports in authoring fixtures are properly flagged. |

---

### Suite 5: Learner State & Atomic Session (`tests/test_state_session.py`)
*Extended in Week 3 · 6 Tests · Module Coverage: 84%*

Validates learner state immutability, evidence semantics, attempt idempotency, and crash-safe atomic snapshots.

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 33 | `test_initial_state` | W1–W2 | Cold start state | Verifies initial values: $p = 0.20, H \approx 0.7219$, `status = UNASSESSED`, `evidence_mastered = False`. |
| 34 | `test_apply_response` | W1–W2, W3 | Response update & Idempotency | Updates belief, sets `status = ASSESSED`, adds `attempt_id`. Re-sending the same `attempt_id` is an ignored no-op. |
| 35 | `test_apply_lesson_exposure_semantics` | W3 (D-D) | Exposure vs assessment | Lessons increment `lessons_done` and shift prior, but leave `responses = 0` and `status = UNASSESSED`. |
| 36 | `test_last_practice_day_monotonic` | W3 (D-D) | Monotonic time | Day 20 followed by day 5 leaves `last_practice_day == 20`. |
| 37 | `test_learner_log_roundtrip` | W1–W2 | Serialization | Verifies JSON roundtrip serialization for separate state and log files. |
| 38 | `test_snapshot_roundtrip_and_atomic_failure` | W3 (D-G) | Atomic snapshot & crash safety | Verifies unified state+log snapshot saving and proves injected `os.replace` failure preserves original file intact. |

---

### Suite 6: Schema, Configuration & Validation (`tests/test_schema.py`)
*Extended in Week 3 · 14 Tests · Module Coverage: 93%*

Validates core schema dataclasses, input boundaries, and fixture integrity (Milestone M1 / TC1.2).

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 39 | `test_concept_validation` | W1–W2 | Concept ID rules | Validates non-empty string IDs without whitespace. |
| 40 | `test_activity_validation` | W1–W2, W3 | Activity constraints | Rejects float/negative durations; enforces exercise difficulty $\in [d_{\min}, d_{\max}]$; rejects difficulty on lessons. |
| 41 | `test_event_validation` | W1–W2, W3 | Event validation | Enforces strict invariants on `COMPLETED` (requires activity ID and positive minutes) and `MISSED` (0 minutes, no activity). |
| 42 | `test_valid_fixtures_load` | W1–W2 (TC1.2) | Valid fixture loading | Loads `curriculum_4node.json` (4 concepts) and `activities_4node.json` (20 activities: 4 lessons, 16 exercises). |
| 43–46 | `test_invalid_curriculum_fixtures` (4 cases) | W1–W2, W3 (TC1.2) | Typed curriculum errors | Parameterized: `duplicate_concept` (`DuplicateIdError`), `bad_schema_version`, `malformed`, `unknown_prereq` (`UnknownConceptError`). |
| 47–53 | `test_invalid_activity_fixtures` (7 cases) | W1–W2, W3 (TC1.2) | Typed activity errors | Parameterized: duplicate activity, missing difficulty, low difficulty, high difficulty, zero duration, negative duration, unknown concept. |
| 54 | `test_config_bounds_and_hash` | W3 (D-E) | Config validation & hash | Validates config bounds ($d_{\min} < d_{\max}$, $\theta \in (0, 1]$) and deterministic 64-char SHA-256 config hashing. |
| 55 | `test_strict_validators` | W3 (D-B) | Central validator checks | Tests `core/validators.py`: strict bools (rejects `"false"`, `0`, `1`), checks `math.isfinite`, probability $[0, 1]$ bounds. |

---

### Suite 7: Curriculum Loader & Review Gate (`tests/test_loader_review_gate.py`)
*Extended in Week 3 · 8 Tests · Module Coverage: 87%*

Validates content integrity, SHA-256 verification, and review gate enforcement.

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 56 | `test_review_gate_enforced_by_default` | W3 (D-A) | Default-on gate | Loading curriculum without review manifest fails by default with `UnreviewedContentError`. |
| 57 | `test_tampered_content_detected` | W1–W2 | SHA-256 hash check | Modifying a single byte in a curriculum file triggers hash mismatch error. |
| 58 | `test_manifest_path_resolution` | W3 (D-F) | Manifest path resolution | Explicit relative/absolute manifest paths resolve identically against content root. |
| 59 | `test_edges_reviewed_literal_true` | W3 (D-F) | Literal boolean check | `edges_reviewed` must be boolean `True` (rejects `"true"`, `1`, or missing field). |
| 60 | `test_human_reviewer_required` | W3 (D-F) | Human sign-off | Live curriculum rejects `"AI"`, empty, or missing reviewer strings. |
| 61 | `test_ai_assisted_flag_supported` | W3 (D9) | AI assistance metadata | Accepts `ai_assisted: true` when accompanied by a named human reviewer. |
| 62 | `test_authoring_bypass_warning` | W3 (D-A) | Authoring mode warning | Explicit `allow_unreviewed=True` emits a stderr warning and logs the bypass. |
| 63 | `test_content_root_consistency` | W3 (D-F) | Uniform content keys | Manifest keys resolve consistently relative to `data/`. |

---

### Suite 8: Analytical BKT Math & Reference Constants (`tests/test_mastery.py`)
*Created in Week 1–2, Hardened in Week 3 · 9 Tests · Module Coverage: 92%*

Validates the mathematical equations of Bayesian Knowledge Tracing and Shannon entropy.

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 64 | `test_guess_slip_functions` | W1–W2 | $g(d)$ and $s(d)$ bounds | Verifies $g(d) = 0.30(1-d)$ and $s(d) = 0.05 + 0.25d$ produce valid probabilities in $(0, 1)$. |
| 65 | `test_prior_success_probability` | W1–W2 | $P_c(p, d)$ calculation | Verifies $P_c(p, d) = p(1-s) + (1-p)g$. |
| 66 | `test_bayes_posterior_correct` | W1–W2 | Correct posterior $p'$ | Verifies $p' = \frac{p(1-s)}{P_c}$ matches analytical solutions. |
| 67 | `test_bayes_posterior_wrong` | W1–W2 | Wrong posterior $p'$ | Verifies $p' = \frac{ps}{1-P_c}$ matches analytical solutions. |
| 68 | `test_learning_transition` | W1–W2 | Transition shift $p''$ | Verifies $p'' = p' + (1-p')T$. |
| 69 | `test_entropy_calculation` | W3 (D3) | Shannon entropy | Checks $H(0.5) = 1.0$, $H(0) = 0.0$, $H(1) = 0.0$, and $H(0.9) \approx 0.469$ bits. |
| 70 | `test_entropy_increases_on_surprise` | W3 | Entropy increase on surprise | Proves mathematically that $p=0.90, d=0.50$ wrong causes $H(p)$ to rise from $0.469$ to $0.935$ bits. |
| 71 | `test_transition_t_bounds` | W3 (D-E) | $T \in [0, 1]$ bounds | Asserts $T < 0$ or $T > 1$ raises `ValidationError`. |
| 72 | `test_smoke_constants_exact_match` | W1–W2, W3 | All 5 reference constants | Asserts exact match on reference table: `0.8462`, `0.1707`, `0.8538`, `0.2122`, `0.6495`. |

---

### Suite 9: Prerequisite Graph & DAG Algorithms (`tests/test_graph.py`)
*Created in Week 1–2 · 4 Tests · Module Coverage: 90%*

Validates the NetworkX prerequisite graph implementation (Milestone M1 / TC1.1).

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 73 | `test_topological_sort_and_ancestors` | W1–W2 | Topological sorting | Verifies stable topological order on the 4-node curriculum (`C1` precedes `C2`, `C3`, `C4`). |
| 74 | `test_cycle_detection_tc11` | W1–W2 (TC1.1) | Cycle detection | Injects cyclic dependencies (`C1 -> C2 -> C1`) and asserts a typed `CycleError` naming the cycle concepts. |
| 75 | `test_unknown_prerequisite_rejected` | W1–W2, W3 | Dangling reference check | Asserts referencing non-existent concept IDs raises `UnknownConceptError` before edge creation. |
| 76 | `test_descendants_resolution` | W1–W2 | Transitive descendants | Verifies querying transitive descendants returns `{"C2", "C3", "C4"}` for `"C1"`. |

---

### Suite 10: CLI & Orchestration Facade (`tests/test_cli.py` & `tests/test_api.py`)
*Extended in Week 3 · 4 Tests · CLI Coverage: 65%, API Coverage: 81%*

Validates CLI command line handling and the `Engine` orchestration boundary.

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 77 | `test_cli_validate` | W1–W2 | CLI validate command | Tests `adaptengine validate` on valid curriculum and activity files. |
| 78 | `test_cli_validate_error` | W1–W2 | CLI error exit code | Tests `adaptengine validate` on invalid cycle fixture returns error. |
| 79 | `test_cli_subprocess` | W1–W2, W3 | Subprocess wiring | Runs `python -m adaptengine validate ...` via `subprocess.run(sys.executable, ...)` to confirm CLI entrypoint wiring. |
| 80 | `test_engine_record_boundary` | W1–W2, W3 | Single mutation boundary | Verifies `(state', log') = Engine.record(state, log, event)` correctly records attempts and preserves immutability. |

---

### Suite 11: Milestone M3 Planner & M4 Difficulty Policy (`tests/test_planner.py`)
*Added in Week 4 · 26 Tests · Planner Coverage: 84%–100% across submodules*

Validates next-exercise difficulty selection, workload projection, greedy day-packing, analytical feasibility bounds, the exact branch-and-bound bin-packing oracle, and the `adaptengine plan` CLI.

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 81 | `test_difficulty_policy_tc42` | W4 (TC4.2) | Target success & D10 tie-break | Exercises closest to $P_c(p, d) \approx 0.75$ chosen; handles unreachable target ($p=0.36 \to d=0.2$); breaks ties by $\|d - 0.5\|$ then ID. |
| 82 | `test_cold_start_workload_numbers` | W4 | Workload numbers | Reproduces cold-start workload: C1=6m, C2=6m, C3=7m, C4=7m (26m total across lessons and required exercises). |
| 83 | `test_prerequisite_safety_tc31` | W4 (TC3.1) | Prerequisite locking | For all budgets (5, 10, 15, 30), no activity of a concept is scheduled before its prerequisites complete. |
| 84 | `test_daily_budget_adherence_tc32` | W4 (TC3.2) | Daily budget ceiling | For all budgets (5, 10, 15, 30), verifies $\text{minutes\_used} \le B$ across every scheduled day. |
| 85 | `test_pacing_variation_by_budget_tc33` | W4 (TC3.3) | Pacing disparity | Confirms $B=5$ produces 7 days while $B=30$ finishes in 1 day on the 4-node curriculum. |
| 86 | `test_infeasible_short_deadline_tc34` | W4 (TC3.4) | Feasibility bounds | Goal C4 with deadline 1 day and $B=5$ returns `INFEASIBLE` with calculated shortfall and actionable budget/deadline options. |
| 87 | `test_exact_oracle_tc35` | W4 (TC3.5) | Exact bin packing | Abstract 8+8+4 duration set at $B=10$: analytical bounds pass, but exact oracle proves 2 days `INFEASIBLE` and 3 days `FEASIBLE`. |
| 88 | `test_exact_oracle_node_limit_tc36` | W4 (TC3.6) | Honest node limit | Branch-and-bound search capped at `node_limit=1` returns `UNKNOWN`, never a false infeasible. |
| 89 | `test_two_learners_different_valid_plans_tc23` | W4 (TC2.3) | State sensitivity | Novice learner (0 mastered) vs learner with C1 and C2 mastered receive distinct, individually valid plans toward goal C4. |
| 90 | `test_plan_determinism` | W4 (Q2) | Determinism | Identical inputs produce bitwise identical plan schedules and step-by-step decision traces. |
| 91 | `test_cli_plan_text_output` | W4 | CLI human output | Tests `adaptengine plan` text formatting for feasible and infeasible schedules. |
| 92 | `test_cli_plan_json_output` | W4 | CLI machine traces | Tests `adaptengine plan --json` emitting valid JSON with `SELECTED` and `DEFERRED` decision logs. |
| 93 | `test_planner_8node_fixture` | W4 | Scalability | Generates valid 4-day plan toward C8 on the 8-concept curriculum at $B=15$. |
| 94 | `test_plan_goal_already_mastered` | W4 | Edge case | Planning toward an already evidence-mastered goal returns 0 days with `GOAL_ALREADY_MASTERED`. |
| 95 | `test_plan_oracle_scenarios` | W4 | Oracle integration | End-to-end integration: tight deadline triggers exact oracle assignment fallback. |
| 96 | `test_plan_content_insufficient` | W4 | Error safety | Concepts without enough exercises to reach evidence mastery raise typed `ContentInsufficientError`. |
| 97 | `test_plan_validation_errors` | W4 | Validation | Missing goals, negative deadlines, and unallowed budgets raise `ValidationError`. |
| 98 | `test_schema_validations` | W4 | Schema typing | Enforces invariants on `PlanContext`, `PlanDay`, and `Plan`. |
| 99 | `test_is_evidence_mastered_custom` | W4 | Evidence threshold | Verifies `is_evidence_mastered` against custom thresholds ($p \ge \theta$ and $\text{responses} \ge k_{\text{responses}}$). |

---

### Suite 12: Spaced Review & Forgetting Model (`tests/test_review.py`)
*Added in Week 5 · 4 Tests · Module Coverage: 97%*

Validates the half-life exponential forgetting model $r(t) = 2^{-\Delta t / h}$, review due checks, and curriculum-topology-weighted review urgency scoring.

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 100 | `test_recall_exponential_decay` | W5 (D23) | Analytical recall formula | Proves $r=1.0$ at $\Delta t = 0$, $r=0.5$ at $\Delta t = h$, $r=0.25$ at $\Delta t = 2h$, and $r=1.0$ for non-practiced concepts. |
| 101 | `test_is_review_due` | W5 (D24) | Recall threshold check | Confirms review is due only when $r < 0.80$ and concept was previously practiced. |
| 102 | `test_review_urgency_calculation` | W5 (D25) | Urgency weighting | Validates urgency $U = (1 - r) \cdot (1 + \text{descendants})$. Leaf concepts have multiplier $1$; root concepts with descendants have higher urgency. |
| 103 | `test_compute_review_urgencies_mapping` | W5 | Batch calculation | Computes urgencies across full curriculum DAG on a given day, filtering concepts where review is not due. |

---

### Suite 13: Milestone M5/M6/M7 Week 5 Acceptance Suite (`tests/test_w5.py`)
*Added in Week 5 · 9 Tests · Complete M5/M6/M7 verification*

Validates spaced review under shared budget, automatic remediation, pure replanning from execution logs, trace contracts, and CLI replan.

| # | Test Function | Origin | Target Invariant | Scenario & Details |
|---|---|---|---|---|
| 104 | `test_tc5_1_mastered_concept_omitted_from_new_learning` | W5 (TC5.1) | Evidence-mastered omission | Evidence-mastered concepts ($p \ge 0.85, \text{responses} \ge 2$) omitted from new learning; trace cites evidence and $p$. |
| 105 | `test_tc5_2_failed_exercise_remediation_flag_and_lesson` | W5 (TC5.2) | Remediation trigger | Failed exercise leaving $p < 0.40$ sets `needs_remediation`; plan queues repeat lesson first; completing lesson clears flag. |
| 106 | `test_tc5_3_high_urgency_review_scheduled_before_new_content` | W5 (TC5.3) | Priority tier scheduling | Urgent review due to memory decay scheduled before new unmastered content in day's budget. |
| 107 | `test_tc6_1_missed_day_replan_no_loss_or_duplication` | W5 (TC6.1) | Missed day replanning | Missed day replans from day after; completed work appears once in log and never again in new schedule. |
| 108 | `test_tc6_2_failed_assessment_replan_with_remediation` | W5 (TC6.2) | Assessment failure replan | Failed assessment recorded as failed response; triggers remediation flag and revised plan with remediation lesson. |
| 109 | `test_tc6_3_deadline_change_replan` | W5 (TC6.3) | Deadline change replan | Tightened deadline returns `INFEASIBLE` with shortfall; extended deadline returns valid `FEASIBLE` plan. |
| 110 | `test_tc6_4_budget_change_replan` | W5 (TC6.4) | Budget change replan | Increased daily budget ($B=30$) packs entire remaining workload into 1 day within budget. |
| 111 | `test_tc7_1_comprehensive_traceability_and_serialization` | W5 (TC7.1) | Traceability & JSON serialization | Every decision has machine-readable reason, state, constraint, score; pure `serialize_plan` includes `config_hash`. |
| 112 | `test_cli_replan_subcommand` | W5 | CLI replan | Subcommand `adaptengine replan` executes from snapshot, supports text and `--json` outputs. |

---

## 4. Verification Command & Reproducibility

All 122 tests can be executed at once:

```bash
make test
```

Expected output:
```text
122 passed in 1.50s
Required test coverage of 84% reached. Total coverage: 88.30%
```

