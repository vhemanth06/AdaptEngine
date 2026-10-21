# AdaptEngine Complete API & Function Reference

This document provides a comprehensive reference and technical description for **every class, method, and function** implemented across the `adaptengine` codebase.

---

## Table of Contents
1. [`core/validators.py` — Central Boundary Validation](#1-corevalidatorspy--central-boundary-validation)
2. [`core/config.py` — Engine Configuration & Hashing](#2-coreconfigpy--engine-configuration--hashing)
3. [`core/schema.py` — Domain Schemas](#3-coreschemapy--domain-schemas)
4. [`core/errors.py` — Typed Exception Hierarchy](#4-coreerrorspy--typed-exception-hierarchy)
5. [`curriculum/graph.py` — Prerequisite Directed Acyclic Graph](#5-curriculumgraphpy--prerequisite-directed-acyclic-graph)
6. [`curriculum/loader.py` — File Loader & Content Review Gate](#6-curriculumloaderpy--file-loader--content-review-gate)
7. [`learner/mastery.py` — Analytical Bayesian Knowledge Tracing](#7-learnermasterypy--analytical-bayesian-knowledge-tracing)
8. [`learner/adapter.py` — Mastery Model Adapter & pyBKT Integration](#8-learneradapterpy--mastery-model-adapter--pybkt-integration)
9. [`learner/state.py` — Learner State & Evidence Semantics](#9-learnerstatepy--learner-state--evidence-semantics)
10. [`diagnostic/scoring.py` — Expected Information Gain & Tie-Breaking](#10-diagnosticscoringpy--expected-information-gain--tie-breaking)
11. [`diagnostic/engine.py` — Adaptive Diagnostic Engine](#11-diagnosticenginepy--adaptive-diagnostic-engine)
12. [`session.py` — Session Orchestration & Atomic Persistence](#12-sessionpy--session-orchestration--atomic-persistence)
13. [`api.py` — Engine Facade & Public Mutation Boundary](#13-apipy--engine-facade--public-mutation-boundary)
14. [`cli.py` — Command Line Interface](#14-clipy--command-line-interface)
15. [`scripts/run_w3.py` — Week 3 Standalone Acceptance Runner](#15-scriptsrun_w3py--week-3-standalone-acceptance-runner)
16. [`planner/difficulty.py` — Next-Exercise Difficulty Policy](#16-plannerdifficultypy--next-exercise-difficulty-policy)
17. [`planner/workload.py` — Required Concepts & Workload Projection](#17-plannerworkloadpy--required-concepts--workload-projection)
18. [`planner/feasibility.py` — Analytical Feasibility Bounds](#18-plannerfeasibilitypy--analytical-feasibility-bounds)
19. [`planner/schedule.py` — Greedy Schedule & Day Packing](#19-plannerschedulepy--greedy-schedule--day-packing)
20. [`planner/oracle.py` — Exact Bin-Packing Feasibility Oracle](#20-planneroraclepy--exact-bin-packing-feasibility-oracle)
21. [`planner/plan.py` — Master Planning Orchestrator](#21-plannerplanpy--master-planning-orchestrator)
22. [`scripts/run_w4.py` — Week 4 Standalone Acceptance Runner](#22-scriptsrun_w4py--week-4-standalone-acceptance-runner)
23. [`review/forgetting.py` — Spaced Review & Memory Decay Model](#23-reviewforgettingpy--spaced-review--memory-decay-model)
24. [`replanner/replan.py` — Dynamic Horizon Replanning](#24-replannerreplanpy--dynamic-horizon-replanning)
25. [`scripts/run_w5.py` — Week 5 Standalone Acceptance Runner](#25-scriptsrun_w5py--week-5-standalone-acceptance-runner)

---

## 1. `core/validators.py` — Central Boundary Validation

Provides strict input validation primitives used across all API and persistence boundaries to enforce types, numeric ranges, and invariants.

### `check_bool(value: Any, name: str) -> bool`
- **Parameters:** `value` (candidate boolean), `name` (field name for error messages).
- **Returns:** The verified boolean `True` or `False`.
- **Description:** Enforces strict boolean typing. Rejects truthy/falsy values such as string `"false"`, `"true"`, integer `0`, or `1`.
- **Raises:** `ValidationError` if `type(value) is not bool`.

### `check_probability(value: Any, name: str) -> float`
- **Parameters:** `value` (candidate probability float), `name` (field name).
- **Returns:** The verified float in $[0.0, 1.0]$.
- **Description:** Verifies that a probability value is numeric, finite (rejects `NaN`, $+\infty$, $-\infty$), and bounded within $[0.0, 1.0]$.
- **Raises:** `ValidationError` if non-numeric, non-finite, or $< 0.0$ or $> 1.0$.

### `check_transition(value: Any, name: str) -> float`
- **Parameters:** `value` (candidate transition rate), `name` (field name).
- **Returns:** The verified float in $[0.0, 1.0]$.
- **Description:** Verifies learning transition rate $T$. Prevents transitions outside $[0.0, 1.0]$ which would produce unnormalized probabilities $p > 1.0$.
- **Raises:** `ValidationError` if non-numeric, non-finite, or out of $[0.0, 1.0]$.

### `check_difficulty(value: Any, d_min: float, d_max: float, name: str) -> float`
- **Parameters:** `value` (candidate difficulty), `d_min` (minimum allowed bound), `d_max` (maximum allowed bound), `name` (field name).
- **Returns:** The verified difficulty float in $[d_{\min}, d_{\max}]$.
- **Description:** Validates exercise difficulty against active engine configuration bounds (default $[0.05, 0.95]$).
- **Raises:** `DifficultyError` if value is non-numeric, non-finite, or outside $[d_{\min}, d_{\max}]$.

### `check_non_negative_int(value: Any, name: str) -> int`
- **Parameters:** `value` (candidate integer), `name` (field name).
- **Returns:** The verified integer $\ge 0$.
- **Description:** Enforces non-negative integer typing for counts (e.g. `lessons_done`, `responses`, `day`). Rejects floats and booleans.
- **Raises:** `ValidationError` if not an `int`, or if $< 0$.

### `check_positive_int(value: Any, name: str) -> int`
- **Parameters:** `value` (candidate integer), `name` (field name).
- **Returns:** The verified integer $\ge 1$.
- **Description:** Enforces strictly positive integers (e.g., activity `duration` in minutes).
- **Raises:** `ValidationError` if not an `int`, or if $\le 0$.

### `check_finite_positive_float(value: Any, name: str) -> float`
- **Parameters:** `value` (candidate float), `name` (field name).
- **Returns:** The verified positive float $> 0.0$.
- **Description:** Validates positive continuous quantities, such as memory retention half-life `half_life_days`.
- **Raises:** `ValidationError` if non-numeric, non-finite, or $\le 0.0$.

### `check_valid_id(value: Any, name: str) -> str`
- **Parameters:** `value` (candidate identifier string), `name` (field name).
- **Returns:** The stripped, verified string ID.
- **Description:** Ensures identifier strings (concept IDs, activity IDs, attempt IDs) are non-empty and contain no internal whitespace.
- **Raises:** `ValidationError` if not a `str`, if empty after strip, or contains whitespace.

---

## 2. `core/config.py` — Engine Configuration & Hashing

### Class `EngineConfig`
Immutable dataclass holding engine runtime parameters, bounds, and thresholds.
- **Fields:**
  - `d_min: float = 0.05` — Minimum exercise difficulty.
  - `d_max: float = 0.95` — Maximum exercise difficulty.
  - `p0: float = 0.20` — Default cold-start mastery prior.
  - `theta: float = 0.85` — Mastery threshold ($\theta$).
  - `t_exercise: float = 0.05` — Learning transition probability for exercises ($T_{\text{exercise}}$).
  - `t_lesson: float = 0.20` — Learning transition prior shift for lessons ($T_{\text{lesson}}$).
  - `t_diag: float = 0.00` — Learning transition for diagnostic questions ($T_{\text{diag}}$).
  - `n_max: int = 8` — Global diagnostic item cap ($N_{\max}$).
  - `concept_cap: int = 3` — Per-concept diagnostic item cap.
  - `h_stop: float = 0.50` — Entropy stopping threshold ($H_{\text{stop}}$).
  - `skip_threshold: float = 0.40` — Ancestor mastery threshold below which descendants are skipped.
  - `k_responses: int = 2` — Minimum observed responses required for evidence mastery.
  - `target_success: float = 0.75` — Target prior success probability ($P_c$) for exercise selection.
  - `w_review: float = 1.0` — Review urgency priority weight.
  - `w_unlock: float = 1.0` — Transitive concept unlock weight.
  - `w_fit: float = 1.0` — Difficulty-to-target fit weight.
  - `recall_threshold: float = 0.80` — Forgetting recall threshold ($r < 0.80$ triggers review).
  - `remediation_threshold: float = 0.40` — Post-failure mastery threshold ($p < 0.40$ triggers remediation flag and lesson).
  - `half_life_growth: float = 1.0` — Multiplicative factor for memory half-life expansion on successful practice.
  - `allowed_budgets: tuple[int, ...] = (5, 10, 15, 30)` — Validated daily time budgets in minutes.
  - `oracle_node_limit: int = 1000` — Search node limit for the exact bin-packing feasibility oracle.
- **`__post_init__(self)`:** Validates all parameters: $0 < d_{\min} < d_{\max} < 1$, $0 \le p_0 \le 1$, $0 < \theta \le 1$, $T \in [0, 1]$, positive caps, $k_{\text{responses}} \ge 1$, target success $\in (0, 1)$, thresholds in $(0, 1)$, positive half-life growth, non-empty allowed budgets, and positive oracle node limit. Raises `ValidationError` on bad config.

### `config_hash(cfg: EngineConfig) -> str`
- **Parameters:** `cfg` (`EngineConfig`).
- **Returns:** Deterministic 64-character SHA-256 hexadecimal string.
- **Description:** Serializes the configuration fields into a sorted JSON dictionary and computes its SHA-256 hash for run reproducibility and auditable provenance.

---

## 3. `core/schema.py` — Domain Schemas

### Enum `ActivityType`
`LESSON = "LESSON"`, `EXERCISE = "EXERCISE"`.

### Enum `EventType`
`COMPLETED = "COMPLETED"`, `MISSED = "MISSED"`, `FAILED_ASSESSMENT = "FAILED_ASSESSMENT"`, `DEADLINE_CHANGED = "DEADLINE_CHANGED"`, `BUDGET_CHANGED = "BUDGET_CHANGED"`.

### Enum `PlanStatus`
`FEASIBLE = "FEASIBLE"`, `INFEASIBLE = "INFEASIBLE"`, `UNKNOWN = "UNKNOWN"`.

### Class `Concept`
Dataclass representing a curriculum learning node.
- **Fields:** `concept_id: str`, `prerequisites: tuple[str, ...]` (default empty), `description: str` (default `""`).
- **`__post_init__(self)`:** Validates `concept_id` format and verifies `prerequisites` is a tuple of valid IDs.

### Class `Activity`
Dataclass representing a curriculum learning item.
- **Fields:** `activity_id: str`, `type: ActivityType`, `target_concept: str`, `duration: int`, `difficulty: float | None = None`.
- **`__post_init__(self)`:** Enforces positive integer duration, verifies `LESSON` has no difficulty (`difficulty is None`), and verifies `EXERCISE` has difficulty $\in [d_{\min}, d_{\max}]$.

### Class `Event`
Dataclass representing an execution log entry.
- **Fields:** `day: int`, `kind: EventType`, `activity_id: str | None = None`, `minutes_elapsed: int = 0`, `correct: bool | None = None`, `attempt_id: str | None = None`, `value: int | None = None`.
- **`__post_init__(self)`:** Validates event invariants per kind:
  - `MISSED`: `minutes_elapsed == 0`, `activity_id is None`, `correct is None`.
  - `COMPLETED`: positive `minutes_elapsed`, non-empty `activity_id`, strict boolean `correct`.
  - `FAILED_ASSESSMENT`: non-empty `activity_id`, `correct` is `False` or `None`.
  - `DEADLINE_CHANGED`: `activity_id is None`, non-negative integer `value` representing new deadline day.
  - `BUDGET_CHANGED`: `activity_id is None`, positive integer `value` in `allowed_budgets` (5, 10, 15, 30).

### Class `PlanContext`
Dataclass representing the planning parameters and constraints.
- **Fields:** `goal: str`, `deadline_day: int`, `budget: int`, `current_day: int = 1`.
- **`__post_init__(self)`:** Enforces valid IDs, positive deadline day $\ge \text{current\_day}$, and budget membership in `cfg.allowed_budgets`.

### Class `PlanDay`
Dataclass representing a scheduled day in a plan.
- **Fields:** `day: int`, `activities: tuple[str, ...] = ()`, `duration: int = 0`.
- **`__post_init__(self)`:** Enforces positive day, tuple of valid activity IDs, and non-negative duration minutes.
- **Properties:**
  - `activity_ids -> tuple[str, ...]`: Alias for `activities`.

### Class `Plan`
Dataclass representing the complete generated study plan.
- **Fields:** `status: PlanStatus`, `days: tuple[PlanDay, ...]`, `shortfall_days: int = 0`, `options: tuple[str, ...] = ()`, `trace: tuple[dict, ...] = ()`, `reason: str = ""`.
- **Properties:**
  - `total_activities -> int`: Sum of activity counts across all scheduled days.
  - `total_minutes -> int`: Sum of minutes used across all scheduled days.

---

## 4. `core/errors.py` — Typed Exception Hierarchy

- **`AdaptEngineError(Exception)`:** Base exception for all domain errors in the engine.
- **`ValidationError(AdaptEngineError)`:** Raised on invalid types, missing required fields, or violated invariants.
- **`DuplicateIdError(ValidationError)`:** Raised when concept IDs or activity IDs are duplicated.
- **`UnknownConceptError(ValidationError)`:** Raised when referencing a concept ID not present in the curriculum graph.
- **`DifficultyError(ValidationError)`:** Raised when exercise difficulty is missing or outside configuration bounds.
- **`UnreviewedContentError(AdaptEngineError)`:** Raised when unreviewed or tampered curriculum content is loaded without explicit authorization.
- **`CycleError(AdaptEngineError)`:** Raised when a cyclic dependency is detected in the prerequisite DAG, naming the cycle path.

---

## 5. `curriculum/graph.py` — Prerequisite Directed Acyclic Graph

### Class `CurriculumGraph`
Wraps a NetworkX `DiGraph` representing the curriculum prerequisite DAG. Edges point from prerequisite to dependent concept ($A \to B$ means $A$ is a prerequisite of $B$).

- **`__init__(self, concepts: Iterable[Concept])`:** Validates concept IDs, checks for duplicates, verifies that all prerequisite references exist, creates directed edges, and checks for cycles. Raises `DuplicateIdError`, `UnknownConceptError`, or `CycleError`.
- **`from_concepts(cls, concepts: Iterable[Concept]) -> CurriculumGraph`:** Factory classmethod constructing a validated DAG from a concept sequence.
- **`concepts(self) -> tuple[str, ...]`:** Returns all concept IDs in deterministic insertion order.
- **`roots(self) -> tuple[str, ...]`:** Returns all root concepts (in-degree 0; concepts with no prerequisites).
- **`prerequisites(self, c: str) -> tuple[str, ...]`:** Returns immediate prerequisites (predecessors) of concept `c`.
- **`ancestors(self, c: str) -> set[str]`:** Returns all transitive prerequisites of concept `c`.
- **`descendants(self, c: str) -> set[str]`:** Returns all transitive dependent concepts enabled by concept `c`.
- **`descendant_count(self, c: str) -> int`:** Returns the total count of transitive descendants.
- **`depth(self, c: str) -> int`:** Returns longest prerequisite path distance from any root concept to `c`.
- **`topological_order(self) -> list[str]`:** Returns a deterministic, stable topological ordering of all concepts in the DAG.

---

## 6. `curriculum/loader.py` — File Loader & Content Review Gate

### `_check_review_gate(path: str, manifest_path: str | None = None) -> None`
- **Parameters:** `path` (file being loaded), `manifest_path` (optional path to `review_manifest.json`).
- **Returns:** `None`.
- **Description:** Verifies that the file at `path` is registered in `review_manifest.json`, matches its recorded SHA-256 digest, has literal `edges_reviewed is True`, and was reviewed by a named human (rejects `"AI"` or empty reviewers).
- **Raises:** `UnreviewedContentError` if unreviewed, modified, or lacking human sign-off.

### `load_curriculum(path: str, manifest_path: str | None = None, allow_unreviewed: bool = False) -> tuple[Concept, ...]`
- **Parameters:** `path` (path to curriculum JSON), `manifest_path` (optional manifest path), `allow_unreviewed` (authoring bypass flag).
- **Returns:** Tuple of validated `Concept` objects.
- **Description:** Reads curriculum JSON, enforces review gate (unless `allow_unreviewed=True`), verifies root object shape, and deserializes concepts.
- **Raises:** `UnreviewedContentError`, `ValidationError`, `DuplicateIdError`.

### `load_activities(path: str, concepts: Iterable[Concept] | CurriculumGraph, manifest_path: str | None = None, allow_unreviewed: bool = False, cfg: EngineConfig = DEFAULT_CONFIG) -> tuple[Activity, ...]`
- **Parameters:** `path` (activities JSON path), `concepts` (validated concepts/graph), `manifest_path` (optional manifest path), `allow_unreviewed` (authoring bypass flag), `cfg` (`EngineConfig`).
- **Returns:** Tuple of validated `Activity` objects.
- **Description:** Reads activities JSON, verifies review gate, validates fields, and ensures target concepts exist.
- **Raises:** `UnreviewedContentError`, `ValidationError`, `UnknownConceptError`, `DifficultyError`.

---

## 7. `learner/mastery.py` — Analytical Bayesian Knowledge Tracing

Implements continuous analytical Bayesian Knowledge Tracing functions.

### `guess(d: float, cfg: EngineConfig = DEFAULT_CONFIG) -> float`
- **Formula:** $g(d) = 0.30 \cdot (1 - d)$
- **Returns:** Probability of correctly guessing an item with difficulty $d$.

### `slip(d: float, cfg: EngineConfig = DEFAULT_CONFIG) -> float`
- **Formula:** $s(d) = 0.05 + 0.25 \cdot d$
- **Returns:** Probability of slipping (making an error despite mastery) on an item with difficulty $d$.

### `bayes_update(p: float, d: float, correct: bool, cfg: EngineConfig = DEFAULT_CONFIG) -> float`
- **Formula:**
  - $P_c(p, d) = p(1 - s(d)) + (1 - p)g(d)$
  - If correct: $p' = \frac{p(1 - s)}{P_c}$
  - If wrong: $p' = \frac{ps}{1 - P_c}$
- **Returns:** Intermediate posterior probability $p' \in [0.0, 1.0]$.

### `learn(p: float, T: float) -> float`
- **Formula:** $p'' = p + (1 - p) \cdot T$
- **Returns:** Post-transition probability $p'' \in [0.0, 1.0]$ after applying learning transition rate $T \in [0, 1]$.

### `update_mastery(p: float, d: float, correct: bool, T: float, cfg: EngineConfig = DEFAULT_CONFIG) -> float`
- **Returns:** Complete two-step Bayesian update $p''$: applies `bayes_update` then `learn`. Matches reference constants.

### `entropy(p: float) -> float`
- **Formula:** $H(p) = -p \log_2(p) - (1 - p) \log_2(1 - p)$ (with $H(0) = H(1) = 0$).
- **Returns:** Shannon entropy of the binary latent state in bits $\in [0.0, 1.0]$.

---

## 8. `learner/adapter.py` — Mastery Model Adapter & pyBKT Integration

### Protocol `MasteryModel`
Structural subtyping protocol defining the mastery model interface:
- **`predict_correct(self, p: float, d: float) -> float`:** Predicts prior success probability $P_c(p, d)$.
- **`update(self, p: float, d: float, correct: bool, transition: float) -> float`:** Computes updated posterior $p''$.

### Class `CustomBKT`
Analytical ground-truth oracle implementing `MasteryModel`.
- **`predict_correct(self, p: float, d: float) -> float`:** Evaluates $p(1 - s(d)) + (1 - p)g(d)$.
- **`update(self, p: float, d: float, correct: bool, transition: float) -> float`:** Calls `update_mastery(p, d, correct, transition, self.cfg)`.

### `get_difficulty_class(d: float) -> str`
- **Returns:** String class `'easy'` ($d < 0.35$), `'medium'` ($0.35 \le d < 0.65$), or `'hard'` ($d \ge 0.65$).

### Class `PyBKTAdapter`
Wrapper around the third-party `pyBKT` library (imported only here).
- **`__init__(self, cfg: EngineConfig = DEFAULT_CONFIG, class_params: dict | None = None)`:** Configures representative class parameters ($d_{\text{rep}} \in \{0.20, 0.50, 0.80\}$).
- **`is_library_available(self) -> bool`:** Returns `True` if `pyBKT` is installed in the environment.
- **`get_class_params(self, cls_name: str) -> dict`:** Returns guess and slip values for a given class.
- **`predict_correct(self, p: float, d: float) -> float`:** Maps $d$ to its class and evaluates success probability.
- **`update(self, p: float, d: float, correct: bool, transition: float) -> float`:** Evaluates BKT update matching oracle within $10^{-9}$ at representative difficulties.

---

## 9. `learner/state.py` — Learner State & Evidence Semantics

### Enum `ConceptStatus`
`UNASSESSED = "UNASSESSED"`, `ASSESSED = "ASSESSED"`.

### Class `LearnerConcept`
Immutable dataclass representing mastery and evidence state for a single concept.
- **Fields:** `concept_id: str`, `p: float`, `lessons_done: int`, `responses: int`, `correct_responses: int`, `status: ConceptStatus`, `seen_attempt_ids: frozenset[str]`, `half_life_days: float`, `last_practice_day: int`, `needs_remediation: bool = False`.
- **Properties:**
  - `mastery -> float`: Alias for belief probability $p$.
  - `uncertainty -> float`: Shannon entropy $H(p)$.
  - `assessed -> bool`: Returns `status == ConceptStatus.ASSESSED`.
  - `evidence_mastered -> bool`: Returns `True` iff $p \ge \theta$ **and** `responses >= k_responses` (delegates to `is_evidence_mastered(self, DEFAULT_CONFIG)`).

### `is_evidence_mastered(concept: LearnerConcept, cfg: EngineConfig = DEFAULT_CONFIG) -> bool`
- **Parameters:** `concept` (`LearnerConcept`), `cfg` (`EngineConfig`).
- **Returns:** Boolean `True` iff `concept.p >= cfg.theta` and `concept.responses >= cfg.k_responses`.
- **Description:** Verifies whether a concept has met both mastery probability and minimum response count thresholds under the specified configuration.

### Class `ExecutionLog`
Immutable event history holding a tuple of `Event` objects.
- **`append(self, event: Event) -> ExecutionLog`:** Returns a new `ExecutionLog` with the event appended.
- **`completed_ids(self) -> set[str]`:** Returns the set of completed activity IDs.

### Class `LearnerState`
Immutable container mapping `concept_id -> LearnerConcept`.

### `initial_state(concept_ids: Iterable[str], cfg: EngineConfig = DEFAULT_CONFIG) -> LearnerState`
- **Parameters:** `concept_ids` (collection of concept IDs), `cfg` (`EngineConfig`).
- **Returns:** Cold-start `LearnerState` where all concepts are initialized to $p = p_0$, $0$ responses, and `status = UNASSESSED`.

---

## 10. `diagnostic/scoring.py` — Expected Information Gain & Tie-Breaking

### `compute_eig(p: float, activity: Activity, cfg: EngineConfig = DEFAULT_CONFIG) -> float`
- **Formula:**
  $$EIG(a) = H(p) - \left[ P_c(p, d) \cdot H(p'_{\text{correct}}) + (1 - P_c(p, d)) \cdot H(p'_{\text{wrong}}) \right]$$
- **Returns:** Expected Information Gain (in bits) for testing activity $a$ at current belief $p$.

### `candidate_sort_key(eig: float, difficulty: float, activity_id: str) -> tuple[float, float, str]`
- **Returns:** Deterministic sort tuple: `(-eig, abs(difficulty - 0.5), activity_id)`.
- **Description:** Orders candidates by descending EIG, breaks ties by proximity to medium difficulty ($|d - 0.5|$), and breaks remaining ties alphabetically.

---

## 11. `diagnostic/engine.py` — Adaptive Diagnostic Engine

### Enums & Result Dataclasses
- **`StopReason`:** `ENTROPY`, `CONCEPT_CAP`, `GLOBAL_CAP`, `NO_ITEMS`, `SKIPPED_ANCESTOR_UNMASTERED`.
- **`DiagnosticItemLog`:** Record of a single diagnostic probe: `(concept_id, activity_id, difficulty, response, p_before, p_after, eig)`.
- **`ConceptDiagnosticResult`:** Final state for a concept: `(concept_id, p, h, status, n_items, stop_reason)`.
- **`DiagnosticResult`:** Aggregate result: `(state, concept_results, item_log, total_items)`.

### Class `AdaptiveDiagnostic`
Orchestrates adaptive testing across the curriculum DAG.
- **`__init__(self, graph: CurriculumGraph, activities: Iterable[Activity], config: EngineConfig = DEFAULT_CONFIG)`:** Indexes activities by concept.
- **`run(self, state: LearnerState, response_provider: Callable[[Activity], bool], goal_concepts: Sequence[str] | None = None, model: MasteryModel | None = None) -> DiagnosticResult`:**
  - Traverses concepts in topological order.
  - Probes concepts iteratively using EIG selection with $T_{\text{diag}} = 0.0$.
  - Stops concepts when $H(p) \le H_{\text{stop}}$, per-concept cap is reached, or no items remain.
  - Skips descendant concepts if an ancestor finishes with $p < 0.40$.
  - Halts globally when total items reach $N_{\max} = 8$.

---

## 12. `session.py` — Session Orchestration & Atomic Persistence

### Class `UpdateRecord`
Record returned from session actions: `(concept_id, p_before, p_after, uncertainty_before, uncertainty_after, event)`.

### `apply_response(...) -> tuple[LearnerState, UpdateRecord]`
- **Parameters:** `state`, `activity`, `correct`, `cfg`, `T`, `day`, `attempt_id`.
- **Returns:** `(new_state, record)`.
- **Description:** Records an exercise attempt. Updates $p$, sets `status = ASSESSED`, increments `responses`, and updates `last_practice_day`. If `attempt_id` was already seen, returns unchanged state (idempotent no-op).

### `apply_lesson(...) -> tuple[LearnerState, UpdateRecord]`
- **Parameters:** `state`, `activity`, `cfg`, `day`, `attempt_id`.
- **Returns:** `(new_state, record)`.
- **Description:** Records a lesson completion. Increments `lessons_done` and shifts prior ($T_{\text{lesson}} = 0.20$), but leaves `responses` unchanged and `status = UNASSESSED`.

### Atomic Persistence Functions
- **`_atomic_write_json(data: dict | list, path: str) -> None`:** Writes JSON to `<path>.<pid>.tmp`, calls `flush()` and `os.fsync()`, then atomically renames via `os.replace()`.
- **`save_snapshot(state: LearnerState, log: ExecutionLog, path: str, context: Optional[PlanContext] = None) -> None`:** Saves a combined `{schema_version, learner, log, context}` document atomically.
- **`load_snapshot(path: str, concept_ids: Iterable[str]) -> tuple[LearnerState, ExecutionLog, Optional[PlanContext]]`:** Deserializes a combined snapshot document.
- **`save_learner` / `load_learner`:** Saves/loads standalone learner state.
- **`save_log` / `load_log`:** Saves/loads standalone event log.
- **`serialize_learner` / `deserialize_learner`:** Pure dictionary serialization/deserialization for learner state (including `needs_remediation`).
- **`serialize_log` / `deserialize_log`:** Pure dictionary serialization/deserialization for execution log (including `value`).

---

## 13. `api.py` — Engine Facade & Public Mutation Boundary

### Class `Engine`
The central facade for AdaptEngine, acting as the single mutation boundary.

- **`from_files(cls, curriculum_path: str, activities_path: str, manifest_path: str | None = None, config: EngineConfig = DEFAULT_CONFIG, allow_unreviewed: bool = False) -> Engine`:** Factory constructing a validated engine instance from JSON files with review gate validation.
- **`init_learner(self) -> LearnerState`:** Generates cold-start learner state for all concepts in the curriculum DAG.
- **`diagnose(self, state: LearnerState, response_provider: Callable[[Activity], bool], goal_concepts: Sequence[str] | None = None, model: MasteryModel | None = None) -> DiagnosticResult`:** Executes an adaptive diagnostic session.
- **`record(self, state: LearnerState, log: ExecutionLog, event: Event) -> tuple[LearnerState, ExecutionLog]`:** Single mutation boundary: records an event, evaluates Bayesian mastery updates, sets/clears remediation flags, deduplicates attempts by `attempt_id`, and returns the updated immutable state and log tuple. Supports all 5 event types (`COMPLETED`, `MISSED`, `FAILED_ASSESSMENT`, `DEADLINE_CHANGED`, `BUDGET_CHANGED`).
- **`plan(self, state: LearnerState, ctx: PlanContext, *, done_ids: set[str] | None = None, review_urgency: dict[str, float] | None = None, model: MasteryModel | None = None) -> Plan`:** Generates a deterministic, time-budgeted study plan toward `ctx.goal` within `ctx.budget` minutes per day by `ctx.deadline_day`.
- **`replan(self, state: LearnerState, log: ExecutionLog, initial_ctx: PlanContext, model: MasteryModel | None = None) -> Plan`:** Pure replanning from event log and snapshot: computes effective context folding `DEADLINE_CHANGED` and `BUDGET_CHANGED`, starts from next available day, excludes completed activities, and returns the revised plan or infeasible proof.

---

## 14. `cli.py` — Command Line Interface

### `main(argv: list[str] | None = None) -> int | None`
- **Parameters:** Optional argument list (defaults to `sys.argv[1:]`).
- **Description:** Entry point for the CLI. Parses arguments and executes subcommands:
  - `validate`: Checks curriculum and activities against schema and review manifest.
  - `show`: Prints topological order and DAG structure.
  - `validate`: Checks curriculum and activities against schema and review manifest.
  - `show`: Prints topological order and DAG structure.
  - `init-learner`: Generates initial learner profile and commits canonical snapshot (`--snapshot`).
  - `update`: Records a completed activity (exercise or lesson) and commits through atomic snapshot.
  - `missed-day` / `record-missed-day`: Records a missed study day (zero elapsed minutes) into snapshot.
  - `failed-assessment`: Records a failed assessment exercise attempt, updating belief and checking remediation.
  - `change-deadline`: Updates the target completion deadline day in the snapshot context.
  - `change-budget`: Updates the daily study time budget (in allowed budgets: 5, 10, 15, 30) in snapshot context.
  - `plan`: Read-only study plan generation toward target goal concept within daily budget and deadline. Supports `--json`.
  - `replan`: Dynamic horizon replanning after recorded events or constraint updates. Pure read-only computation from canonical snapshot. Supports `--json`.
  - `import-legacy`: Explicitly imports separate legacy learner and log files into a canonical snapshot.
  - `export-legacy`: Explicitly exports canonical snapshot into separate legacy learner and log files.
  - Subcommands `plan`, `replan`, `update`, `failed-assessment`, and `missed-day` support `--model {custombkt,pybkt}` (defaults to `custombkt` continuous oracle, or select genuine `pybkt` adapter wrapper).


---

## 15. `scripts/run_w3.py` — Week 3 Standalone Acceptance Runner

### `run_cmd(cmd: list[str]) -> tuple[int, str]`
Helper executing shell commands via `subprocess.run`, capturing returncode and output.

### `main() -> None`
Executes all 5 verification gates:
1. Environment and code identity recording (`code_sha.txt`, `config_hash.txt`, `environment.txt`).
2. Ruff linting and formatting validation.
3. Pytest test suite with statement coverage threshold ($\ge 84.95\%$).
4. Reference constants ($0.8462, 0.1707, 0.8538, 0.2122, 0.6495$) and deterministic smoke sequence.
5. AST layering check enforcing unidirectional imports and third-party isolation.
6. Diagnostic demo across 4 scripted learner personas (*All Correct*, *All Wrong*, *Alternating*, *Difficulty Sensitive*).
Outputs an auditable evidence package in `runs/w3/<timestamp>/`.

---

## 16. `planner/difficulty.py` — Next-Exercise Difficulty Policy

### `select_exercise(exercises: Iterable[Activity], p: float, target_success: float = 0.75, model: MasteryModel | None = None, cfg: EngineConfig = DEFAULT_CONFIG) -> Activity`
- **Parameters:** `exercises` (collection of candidate exercise activities), `p` (current mastery belief), `target_success` (target success probability, default $0.75$), `model` (optional `MasteryModel`, defaults to `CustomBKT`), `cfg` (`EngineConfig`).
- **Returns:** The optimal exercise `Activity`.
- **Description:** Selects the exercise whose predicted probability of success $P_c(p, d)$ is nearest to `target_success`. Breaks ties using Decision D10: smaller $|d - 0.50|$, then lexicographically by `activity_id`.
- **Raises:** `ValidationError` if `exercises` contains non-exercise items or is empty.

---

## 17. `planner/workload.py` — Required Concepts & Workload Projection

### Class `ConceptWorkload`
Dataclass representing projected workload for a single concept:
- **Fields:** `concept_id: str`, `activities: list[Activity]`, `total_minutes: int`, `p_final: float`, `responses_final: int`.

### Class `WorkloadProjection`
Dataclass aggregating projected workload across all required concepts:
- **Fields:** `concept_workloads: dict[str, ConceptWorkload]`, `required_concepts: set[str]`, `total_minutes: int`.
- **Properties:** `all_activities -> list[Activity]`.

### `compute_workload(graph: CurriculumGraph, activities: Iterable[Activity], state: LearnerState, goal: str, done_ids: set[str] | None = None, model: MasteryModel | None = None, cfg: EngineConfig = DEFAULT_CONFIG) -> WorkloadProjection`
- **Parameters:** `graph` (`CurriculumGraph`), `activities` (all available activities), `state` (`LearnerState`), `goal` (target concept ID), `done_ids` (already completed activity IDs), `model` (`MasteryModel`), `cfg` (`EngineConfig`).
- **Returns:** `WorkloadProjection`.
- **Description:** Identifies required concepts ($\{goal\} \cup \text{ancestors}(goal) \setminus \text{evidence\_mastered}$). For each concept, queues unfinished lessons then exercises picked by the difficulty policy, updating belief $p$ assuming correct responses ($T_{\text{exercise}}$), until $p \ge \theta$ and $\text{responses} \ge k_{\text{responses}}$.
- **Raises:** `UnknownConceptError` if `goal` is not in `graph`, `ContentInsufficientError` if available exercises run out before reaching evidence mastery.

---

## 18. `planner/feasibility.py` — Analytical Feasibility Bounds

### Class `FeasibilityCheckResult`
Dataclass holding bounds check outcomes:
- **Fields:** `feasible: bool`, `shortfall_days: int`, `options: tuple[str, ...]`, `reason: str`.

### `check_feasibility_bounds(workload: WorkloadProjection, graph: CurriculumGraph, ctx: PlanContext, cfg: EngineConfig = DEFAULT_CONFIG) -> FeasibilityCheckResult`
- **Parameters:** `workload` (`WorkloadProjection`), `graph` (`CurriculumGraph`), `ctx` (`PlanContext`), `cfg` (`EngineConfig`).
- **Returns:** `FeasibilityCheckResult`.
- **Description:** Checks necessary mathematical feasibility conditions in $O(V + E)$:
  1. **Oversized Item:** Verifies that no required activity has $\text{duration} > B$.
  2. **Total Minutes Bound:** Checks if $\lceil \text{total\_minutes} / B \rceil > \text{days\_left}$.
  3. **Critical Path Bound:** Computes longest duration directed path $CP$ in topological order via dynamic programming and checks if $\lceil CP / B \rceil > \text{days\_left}$.
  If infeasible, calculates `shortfall_days` and provides corrective options (increasing budget or extending deadline).

---

## 19. `planner/schedule.py` — Greedy Schedule & Day Packing

### Class `ScheduleResult`
Dataclass holding the greedy schedule output:
- **Fields:** `days: list[PlanDay]`, `trace: list[dict]`, `completed_concepts: set[str]`, `unfinished_workload: dict[str, list[Activity]]`.

### `run_greedy_schedule(workload: WorkloadProjection, graph: CurriculumGraph, ctx: PlanContext, review_urgency: dict[str, float] | None = None, cfg: EngineConfig = DEFAULT_CONFIG) -> ScheduleResult`
- **Parameters:** `workload` (`WorkloadProjection`), `graph` (`CurriculumGraph`), `ctx` (`PlanContext`), `review_urgency` (optional review scores), `cfg` (`EngineConfig`).
- **Returns:** `ScheduleResult`.
- **Description:** Simulates greedy day-by-day packing obeying:
  - **Prerequisites (D11, D12):** A concept is eligible when all its direct prerequisites have completed their projected activities; same-day unlocks are allowed in topological order.
  - **Queue Discipline (D16):** Lessons strictly precede exercises within each concept.
  - **Skip-and-Continue Packing (D15):** If a top-ranked item exceeds remaining daily minutes, lower-ranked eligible items may pack.
  - **Scoring (D13, D14):** Score $= w_{\text{review}} \cdot R + w_{\text{unlock}} \cdot U + w_{\text{fit}} \cdot F$, where $U = \text{descendant\_count}(c)$ and $F = 0.0$ for lessons.
  Emits structured `SELECTED` and `DEFERRED` trace events for every scheduling decision.

---

## 20. `planner/oracle.py` — Exact Bin-Packing Feasibility Oracle

### `solve_oracle(workload: WorkloadProjection, graph: CurriculumGraph, ctx: PlanContext, cfg: EngineConfig = DEFAULT_CONFIG) -> tuple[PlanStatus, list[PlanDay], str]`
- **Parameters:** `workload` (`WorkloadProjection`), `graph` (`CurriculumGraph`), `ctx` (`PlanContext`), `cfg` (`EngineConfig`).
- **Returns:** Tuple of `(PlanStatus, list[PlanDay], reason)`.
- **Description:** Exact branch-and-bound bin-packing algorithm with precedence constraints and pruning by remaining capacity. Explores state transitions up to `cfg.oracle_node_limit`. Returns `FEASIBLE` if an exact schedule exists within `deadline_day`, `INFEASIBLE` if the search space is exhaustively disproven, or `UNKNOWN` if search limit is reached (ensuring zero false-infeasible assertions).

---

## 21. `planner/plan.py` — Master Planning Orchestrator

### `plan(graph: CurriculumGraph, activities: Iterable[Activity], state: LearnerState, ctx: PlanContext, *, done_ids: set[str] | None = None, review_urgency: dict[str, float] | None = None, model: MasteryModel | None = None, cfg: EngineConfig = DEFAULT_CONFIG) -> Plan`
- **Parameters:** `graph` (`CurriculumGraph`), `activities` (all activities), `state` (`LearnerState`), `ctx` (`PlanContext`), `done_ids` (completed activity IDs), `review_urgency` (review priority map), `model` (`MasteryModel`), `cfg` (`EngineConfig`).
- **Returns:** Complete validated `Plan`.
- **Description:** Orchestrates the planning pipeline:
  1. Computes required concepts and projected workload.
  2. Runs $O(V + E)$ analytical bounds checks; immediately returns `INFEASIBLE` with options if violated.
  3. Runs greedy scheduler. If schedule completes within `deadline_day`, returns `FEASIBLE`.
  4. If greedy scheduler exceeds deadline, invokes exact `solve_oracle`. If oracle finds a schedule, returns `FEASIBLE`; if oracle disproves, returns `INFEASIBLE`; if node limit is reached, returns `UNKNOWN`.

### `serialize_plan(plan: Plan, cfg: EngineConfig = DEFAULT_CONFIG) -> dict[str, Any]`
- **Parameters:** `plan` (`Plan`), `cfg` (`EngineConfig`).
- **Returns:** JSON-serializable dictionary with primitives only.
- **Description:** Serializes a generated `Plan` to primitive types for JSON export (`--json`), embedding the active configuration's SHA-256 hash (`config_hash`), status, shortfall days, options, schedule days, and full decision traces.

---

## 22. `scripts/run_w4.py` — Week 4 Standalone Acceptance Runner

### `run_cmd(cmd: list[str]) -> tuple[int, str]`
Helper executing shell commands via `subprocess.run`, capturing returncode and output.

### `main() -> None`
Executes complete Week 4 verification pipeline:
1. Environment and code identity recording (`code_sha.txt`, `config_hash.txt`, `environment.txt`).
2. Ruff linting and formatting validation.
3. Architecture and layering test suite (`tests/test_architecture.py`).
4. Pytest test suite with statement coverage threshold ($\ge 84.0\%$).
5. Verification of all W4 scenarios:
   - TC4.2 Difficulty policy nearest-to-target selection and D10 tie-breaking.
   - Workload projection numbers (6, 6, 7, 7 min = 26 min total).
   - TC3.1 Prerequisite locking.
   - TC3.2 Budget preservation across 5, 10, 15, and 30 minute limits.
   - TC3.3 Pacing disparity between 5-min (7 days) and 30-min (1 day) budgets.
   - TC3.4 Infeasible goal shortfall calculation and corrective options.
   - TC3.5 Abstract 8+8+4 bin-packing oracle infeasibility.
   - TC3.6 Oracle search node limit returning `UNKNOWN`.
   - TC2.3 Two learners with identical goal/budget receiving different valid plans.
   - 8-node curriculum planning verification.
6. Outputs auditable evidence package in `runs/w4/<timestamp>/`.

---

## 23. `review/forgetting.py` — Spaced Review & Memory Decay Model

### `recall(concept: LearnerConcept, current_day: int) -> float`
- **Parameters:** `concept` (`LearnerConcept`), `current_day` (integer target evaluation day).
- **Returns:** Predicted recall probability float $r \in [0.0, 1.0]$.
- **Description:** Evaluates exponential memory retention curve $r = 2^{-\Delta t / h}$, where $\Delta t = \max(0, \text{current\_day} - \text{last\_practice\_day})$ and $h$ is `concept.half_life_days`. If `last_practice_day` is `None` (unpracticed), returns $1.0$ (not a review candidate).

### `is_review_due(concept: LearnerConcept, current_day: int, cfg: EngineConfig = DEFAULT_CONFIG) -> bool`
- **Parameters:** `concept` (`LearnerConcept`), `current_day` (integer day), `cfg` (`EngineConfig`).
- **Returns:** Boolean `True` if `recall(concept, current_day) < cfg.recall_threshold` and `last_practice_day is not None`.

### `review_urgency(concept: LearnerConcept, current_day: int, descendant_count: int, cfg: EngineConfig = DEFAULT_CONFIG) -> float`
- **Parameters:** `concept` (`LearnerConcept`), `current_day` (integer day), `descendant_count` (number of transitive dependent concepts in DAG), `cfg` (`EngineConfig`).
- **Returns:** Continuous urgency score float $\ge 0.0$.
- **Description:** Computes review priority $U = (1.0 - r) \cdot (1.0 + \text{descendant\_count})$. The $+1.0$ ensures leaf concepts have positive urgency when decaying, while concepts unlocking downstream prerequisites receive higher priority. Returns $0.0$ if review is not due.

### `compute_review_urgencies(state: LearnerState, graph: CurriculumGraph, current_day: int, cfg: EngineConfig = DEFAULT_CONFIG) -> dict[str, float]`
- **Parameters:** `state` (`LearnerState`), `graph` (`CurriculumGraph`), `current_day` (integer day), `cfg` (`EngineConfig`).
- **Returns:** Dictionary mapping `concept_id -> urgency` for concepts where review is due.

---

## 24. `replanner/replan.py` — Dynamic Horizon Replanning

### `compute_effective_context(log: ExecutionLog, initial_ctx: PlanContext) -> tuple[PlanContext, int]`
- **Parameters:** `log` (`ExecutionLog`), `initial_ctx` (`PlanContext`).
- **Returns:** Tuple of `(effective_context, next_day)`.
- **Description:** Pure function folding initial plan context over execution log events:
  - Updates deadline on `DEADLINE_CHANGED` events.
  - Updates daily budget on `BUDGET_CHANGED` events.
  - Advances starting day to $\max(\text{initial\_day}, \text{latest\_event\_day} + 1)$ if any events occurred.

### `replan(graph: CurriculumGraph, activities: Iterable[Activity], state: LearnerState, log: ExecutionLog, initial_ctx: PlanContext, model: MasteryModel | None = None, cfg: EngineConfig = DEFAULT_CONFIG) -> Plan`
- **Parameters:** `graph` (`CurriculumGraph`), `activities` (curriculum activities), `state` (`LearnerState`), `log` (`ExecutionLog`), `initial_ctx` (`PlanContext`), `model` (optional `MasteryModel`), `cfg` (`EngineConfig`).
- **Returns:** Revised `Plan` (or `INFEASIBLE` proof).
- **Description:** Orchestrates pure horizon replanning:
  1. Computes effective context from event log (folding deadline and budget changes).
  2. Sets `done_ids = log.completed_ids()` ensuring already-completed activities are not repeated.
  3. Appends `REPLAN_PRESERVED_COMPLETED` trace records for completed items.
  4. Calls `plan(...)` over the remaining horizon.

---

## 25. `scripts/run_w5.py` — Week 5 Standalone Acceptance Runner

### `main() -> None`
Executes complete Week 5 verification pipeline:
1. Environment and code identity recording (`code_sha.txt`, `config_hash.txt`, `environment.txt`).
2. Ruff linting and formatting validation.
3. Architecture and layering test suite (`tests/test_architecture.py`).
4. Pytest test suite with statement coverage threshold ($\ge 84.0\%$).
5. Verification of all W5 scenarios:
   - TC5.1 Mastered concept omitted from new learning; trace cites evidence and $p$.
   - TC5.2 Failed exercise drops $p < 0.40$; `needs_remediation` set; repeat lesson scheduled first; cleared on completion.
   - TC5.3 Spaced review due to memory decay scheduled before new unmastered content under daily budget.
   - TC6.1 Missed day replan starts day after; completed activities preserved without loss or duplication.
   - TC6.2 Failed assessment recorded as failed response; triggers remediation flag and revised plan with repeat lesson.
   - TC6.3 Deadline changes: tightened deadline returns `INFEASIBLE` proof with shortfall; extended deadline returns valid `FEASIBLE` plan.
   - TC6.4 Budget change: increased budget ($B=30$) completes remaining workload in 1 day within budget limit.
   - TC7.1 Full traceability: every decision has machine-readable reason, state, and score components; pure `serialize_plan` validated.
   - CLI replan: command-line `adaptengine replan` executed from snapshot with text and `--json` outputs.
6. Outputs auditable evidence package in `runs/w5/<timestamp>/`.

