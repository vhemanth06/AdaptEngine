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
  - `k_evidence: int = 2` — Minimum observed responses required for evidence mastery.
- **`__post_init__(self)`:** Validates all parameters: $0 < d_{\min} < d_{\max} < 1$, $0 \le p_0 \le 1$, $0 < \theta \le 1$, $T \in [0, 1]$, positive caps, and valid thresholds. Raises `ValidationError` on bad config.

### `config_hash(cfg: EngineConfig) -> str`
- **Parameters:** `cfg` (`EngineConfig`).
- **Returns:** Deterministic 64-character SHA-256 hexadecimal string.
- **Description:** Serializes the configuration fields into a sorted JSON dictionary and computes its SHA-256 hash for run reproducibility and auditable provenance.

---

## 3. `core/schema.py` — Domain Schemas

### Enum `ActivityType`
`LESSON = "LESSON"`, `EXERCISE = "EXERCISE"`.

### Enum `EventType`
`COMPLETED = "COMPLETED"`, `MISSED = "MISSED"`.

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
- **Fields:** `day: int`, `kind: EventType`, `activity_id: str | None = None`, `minutes_elapsed: int = 0`, `correct: bool | None = None`, `attempt_id: str | None = None`.
- **`__post_init__(self)`:** Validates event invariants:
  - `MISSED` events must have `minutes_elapsed == 0` and `activity_id is None`.
  - `COMPLETED` events must have positive `minutes_elapsed`, a non-empty `activity_id`, and strict boolean `correct`.

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
- **Fields:** `concept_id: str`, `p: float`, `lessons_done: int`, `responses: int`, `correct_responses: int`, `status: ConceptStatus`, `seen_attempt_ids: frozenset[str]`, `half_life_days: float`, `last_practice_day: int`.
- **Properties:**
  - `mastery -> float`: Alias for belief probability $p$.
  - `uncertainty -> float`: Shannon entropy $H(p)$.
  - `assessed -> bool`: Returns `status == ConceptStatus.ASSESSED`.
  - `evidence_mastered -> bool`: Returns `True` iff $p \ge \theta$ **and** `responses >= k_evidence`.

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
- **`save_snapshot(state: LearnerState, log: ExecutionLog, path: str) -> None`:** Saves a combined `{schema_version, learner, log}` document atomically.
- **`load_snapshot(path: str, concept_ids: Iterable[str]) -> tuple[LearnerState, ExecutionLog]`:** Deserializes a combined snapshot document.
- **`save_learner` / `load_learner`:** Saves/loads standalone learner state.
- **`save_log` / `load_log`:** Saves/loads standalone event log.
- **`serialize_learner` / `deserialize_learner`:** Pure dictionary serialization/deserialization for learner state.
- **`serialize_log` / `deserialize_log`:** Pure dictionary serialization/deserialization for execution log.

---

## 13. `api.py` — Engine Facade & Public Mutation Boundary

### Class `Engine`
The central facade for AdaptEngine, acting as the single mutation boundary.

- **`from_files(cls, curriculum_path: str, activities_path: str, manifest_path: str | None = None, config: EngineConfig = DEFAULT_CONFIG, allow_unreviewed: bool = False) -> Engine`:** Factory constructing a validated engine instance from JSON files with review gate validation.
- **`init_learner(self) -> LearnerState`:** Generates cold-start learner state for all concepts in the curriculum DAG.
- **`diagnose(self, state: LearnerState, response_provider: Callable[[Activity], bool], goal_concepts: Sequence[str] | None = None, model: MasteryModel | None = None) -> DiagnosticResult`:** Executes an adaptive diagnostic session.
- **`record(self, state: LearnerState, log: ExecutionLog, event: Event) -> tuple[LearnerState, ExecutionLog]`:** Single mutation boundary: records an event, evaluates Bayesian mastery updates, and returns the updated immutable state and log tuple.

---

## 14. `cli.py` — Command Line Interface

### `main(argv: list[str] | None = None) -> int | None`
- **Parameters:** Optional argument list (defaults to `sys.argv[1:]`).
- **Description:** Entry point for the CLI. Parses arguments and executes subcommands:
  - `validate`: Checks curriculum and activities against schema and review manifest.
  - `show`: Prints topological order and DAG structure.
  - `init-learner`: Generates initial learner JSON.
  - `update`: Records an activity completion event and persists updated state.

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
