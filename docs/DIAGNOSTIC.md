# Adaptive Diagnostic Specification (Milestone M2)

## 1. Overview & Goal

The Adaptive Diagnostic (**Milestone M2**) computes an initial mastery profile for a learner over a curriculum DAG. Instead of presenting a fixed, static assessment or asking an unbounded number of questions, it actively selects the most informative exercises using **Expected Information Gain (EIG)**, enforces strict per-concept and global budget caps, prunes unviable prerequisite branches, and terminates with structured diagnostic results.

---

## 2. Inputs & Cold Start

### Inputs
- **Curriculum Graph:** NetworkX DAG of concepts and prerequisite relationships.
- **Activity Bank:** Table of available `Activity` objects (type `EXERCISE` with difficulties $d \in [d_{\min}, d_{\max}]$).
- **Learner State:** Current `LearnerState` containing `LearnerConcept` states.
- **Goal Concepts (Optional):** Subset of concepts to diagnose (default: all concepts in graph).
- **Engine Configuration:**
  - $N_{\max}$: Global item cap (default **8** under D1).
  - `concept_cap`: Per-concept item cap (default **3** under D2).
  - $H_{\text{stop}}$: Entropy stop threshold (default **0.50** under D3, corresponding to $p \le 0.11$ or $p \ge 0.89$).
  - `skip_threshold`: Descendant skip threshold (default **0.40** under D8).
  - $T_{\text{diag}}$: Diagnostic learning transition (pinned to **0.0**; diagnostics do not introduce learning).
- **Response Provider:** Injected callable `response_provider(activity: Activity) -> bool` returning whether the learner answers correctly.

### Cold Start Semantics (TC2.2)
- Concepts with no prior assessment responses maintain their default prior ($p = p_0 = 0.20$), retain status `UNASSESSED`, and are treated as **unmastered** for prerequisite gating.
- Running the diagnostic never overwrites or resets untouched concepts.

---

## 3. Algorithm & Selection Policy

1. **Concept Ordering:** Concepts are evaluated in a stable topological order determined by the curriculum DAG, with ties broken lexicographically by `concept_id`.
2. **Item Selection (EIG):**
   For all unasked exercises targeting the active concept, the engine evaluates Expected Information Gain without transition:
   $$P_c(p, d) = p \cdot (1 - s(d)) + (1 - p) \cdot g(d)$$
   $$p'_{\text{correct}} = \frac{p \cdot (1 - s(d))}{P_c(p, d)}, \quad p'_{\text{wrong}} = \frac{p \cdot s(d)}{1 - P_c(p, d)}$$
   $$\text{EIG}(a) = H(p) - \left[ P_c \cdot H(p'_{\text{correct}}) + (1 - P_c) \cdot H(p'_{\text{wrong}}) \right]$$
3. **Deterministic Tie-Breaking (Decision D10):**
   When multiple exercises yield equal EIG (within $10^{-9}$), ties are resolved by:
   - Smaller $|d - 0.50|$ (closer to median difficulty)
   - Lexicographically smaller `activity_id`
4. **Stopping Criteria:**
   Evaluation of a concept stops as soon as any of the following is true:
   - **Entropy threshold reached (`ENTROPY`):** $H(p) \le H_{\text{stop}}$ ($0.50$).
   - **Per-concept cap reached (`CONCEPT_CAP`):** 3 items asked for this concept.
   - **Global budget reached (`GLOBAL_CAP`):** Total items across the entire diagnostic reach $N_{\max}$ ($8$).
   - **Exhaustion (`NO_ITEMS`):** No remaining unasked exercises exist for this concept.
5. **Descendant Skipping (Decision D8):**
   When an ancestor concept finishes diagnosis with final mastery $p < \text{skip\_threshold}$ ($0.40$), all of its downstream descendants in the DAG are immediately marked as `SKIPPED_ANCESTOR_UNMASTERED` and skipped. They remain `UNASSESSED` with zero diagnostic items consumed.

---

## 4. Structured Results & Guarantees

### Result Structure
The diagnostic returns a `DiagnosticResult` object:
- `state`: Updated immutable `LearnerState` reflecting all assessed concepts.
- `concept_results`: Mapping `concept_id -> ConceptDiagnosticResult(p, h, status, n_items, stop_reason)`.
  - Possible `stop_reason`s: `ENTROPY`, `CONCEPT_CAP`, `GLOBAL_CAP`, `NO_ITEMS`, `SKIPPED_ANCESTOR_UNMASTERED`, `NOT_REACHED`.
- `item_log`: Chronological tuple of `DiagnosticItemLog(concept_id, activity_id, difficulty, response, p_before, p_after, eig)`.
- `total_items`: Total questions administered ($0 \le \text{total\_items} \le N_{\max}$).

### Invariant Guarantees
1. **Budget Safety:** Total items administered strictly satisfy $\text{total\_items} \le N_{\max}$.
2. **No Duplicates:** An activity is never administered more than once in a diagnostic run.
3. **Immutability:** The input `LearnerState` is never mutated in-place; a new state instance is returned.
4. **Determinism:** Given identical DAG, activities, initial state, config, and responses, the diagnostic produces byte-identical item logs and outcomes.

---

## 5. Verification Test Suite

The diagnostic implementation is verified by `tests/test_diagnostic.py`:
- `test_adversarial_learner_bounded_by_n_max`: Confirms adversarial (always-wrong) learner terminates at or below $N_{\max} = 8$.
- `test_alternating_learner_bounded_by_n_max`: Confirms alternating responses never breach $N_{\max}$.
- `test_entropy_stopping_rule`: Confirms consistent learner halts early when $H \le 0.50$.
- `test_cold_start_unassessed_preserved` (**TC2.2**): Confirms untouched concepts retain prior state and `UNASSESSED`.
- `test_surprise_response_and_cap`: Verifies that a surprise wrong answer at $p = 0.90$ raises entropy and is bounded by concept cap.
- `test_descendant_skipping_on_low_mastery`: Confirms descendants of $p < 0.40$ concepts receive `SKIPPED_ANCESTOR_UNMASTERED`.
- `test_no_activity_asked_twice`: Confirms zero repeated activities.
- `test_input_state_not_mutated`: Confirms input state object immutability.
- `test_deterministic_identical_runs`: Confirms identical logs across duplicate runs.
- `test_tie_breaking_d10`: Confirms $|d - 0.5|$ and lexicographic tie-breaks.
