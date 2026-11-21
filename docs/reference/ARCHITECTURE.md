# Architecture

This page maps the code in `src/adaptengine/`, the web demo in `frontend/` and the evaluation study in `experiments/`. The ideas behind each part are explained in [the concept docs](../concepts/); the public functions are listed in [API_REFERENCE.md](API_REFERENCE.md); tests and commands are in [TESTING.md](TESTING.md).

## Modules

Every file below exists in `src/adaptengine/` (checked 21 Nov 2026).

- `core/`: `errors.py` (typed exceptions), `config.py` (`EngineConfig`, `config_from_file`, `config_hash`), `constants.py` (default numbers), `schema.py` (`Concept`, `Activity`, `Event`, `PlanContext`, `PlanDay`, `Plan`), `validators.py` (boundary checks).
- `curriculum/`: `loader.py` (JSON loading and the review gate), `graph.py` (immutable DAG; prerequisite tuples, ancestor and descendant sets, depths and topological order are precomputed once, W7 T6.1), `content.py` (display-only lesson text and questions; the engine never reads it).
- `learner/`: `state.py` (`LearnerConcept`, `LearnerState`, `ExecutionLog`), `mastery.py` (BKT update formulas), `adapter.py` (`MasteryModel` protocol, `CustomBKT`, `PyBKTAdapter`), `evidence.py` (the single place that rebuilds a concept after a response, plus the confirmation flags), `profiles.py` (fitted item-model profiles and `ClassBKT`, Plan 2).
- `diagnostic/`: `engine.py` (`AdaptiveDiagnostic`, the concept sweep), `scoring.py` (expected information gain and tie-breaking), `bisection.py` (`BisectionDiagnostic`, Plan 3: questions chosen by information about the whole knowledge state, confidence stop), `knowledge_space.py` (scope, down-set enumeration, exact and sampling posteriors, chain-cover bound), `state_space.py` (`StateSpaceDiagnostic`, W7 T3.6; tested, but not selectable through `diagnostic_method`). `DIAGNOSTICS` in `diagnostic/__init__.py` maps `EngineConfig.diagnostic_method` (`"sweep"`, `"bisection"`) to the class `Engine.diagnose` uses.
- `planner/`: `workload.py` (required concepts and projected workload; caller-owned `WorkloadCache`), `schedule.py` (greedy day packing with reviews and remediation), `plan.py` (pipeline and dispatch on `EngineConfig.planner_method`), `difficulty.py` (next-exercise policy), `feasibility.py` (analytical bounds), `oracle.py` (exact bin-packing oracle), `confirmation.py` (short checks instead of full study for concepts the bisection diagnostic inferred; used by `compute_workload` when `confirm_diag_confident` is on), `cpsat_model.py` (the CP-SAT model; the only `ortools` import, loaded lazily), `cpsat_planner.py` (pure CP-SAT and hybrid planners), `cpsat_trace.py` (explanations after a CP-SAT solve).
- `review/`: `forgetting.py` (half-life recall and review urgency).
- `replanner/`: `replan.py` (fold deadline and budget changes over the log, then plan the remaining horizon).
- `session.py`: applying responses and lessons, atomic snapshot persistence.
- `api.py`: the `Engine` facade. `Engine.record` is the single mutation boundary; `Engine.next_activities` (W7 T2.2) is the recommended online loop (replan from the real state, commit today's slice).
- `cli.py` (and `__main__.py`): the `adaptengine` command.

`WorkloadCache` keys hold the concept, its learner state, its completed-attempt history, the config, the model identity and a curriculum plus activity-catalogue fingerprint. The cache is bounded at `maxsize=4096` (oldest evicted). Use one cache per engine and curriculum.

## Web demo (`frontend/`)

- `frontend/api/`: a thin FastAPI adapter over `Engine` (`app.py`), per-session snapshot storage (`store.py`), request and response models (`schemas.py`), and the fixed demo preset (`demo.py`, chosen by `select_demo_preset.py`). It holds no planning, mastery or eligibility logic; engine `ValidationError` becomes HTTP 422. Install with `pip install -e ".[demo]"`.
- `frontend/web/`: a React and Vite single-page app that talks only to `frontend/api`. Playwright tests are in `frontend/web/e2e/`.
- Start both with `make demo` (`scripts/demo.py`).

## Evaluation study (`experiments/`)

The pre-registered study E1 to E6 (Plan V2, D98; renamed from `experiments_v2/`, D102). `core/` (simulated learners, scenarios, closed-loop episodes, audits, metrics, real-data loading, pre-registration guard, provenance), `runners/` (one module per experiment), `results/` (results JSON files), `report/` (extract, then tables, then figures), `preregistration/`. See `experiments/README.md`.

## Dependency direction outside the engine

```
frontend/api  -->  adaptengine  <--  experiments
frontend/web  -->  frontend/api
scripts/      -->  adaptengine (and may import anything; nothing imports scripts/)
```

`frontend/` and `experiments/` import `adaptengine`; `adaptengine` never imports them (no such import exists in `src/`). `tests/tooling/test_architecture.py` enforces the layering inside `src/adaptengine` (section 1) and the library rules below.

## Out of scope

A learned recommendation policy (bandit), the authoring agent (A0) and the optional agent layer (A1 to A3) were planned in early weeks and never built; no files exist for them.

---

## 1. Dependency Direction and Layering Rules

The architecture enforces strict unidirectional dependency flow verified by automated AST tests (`tests/tooling/test_architecture.py`):

```
core  <--  curriculum  <--  learner  <--  diagnostic / planner / review  <--  replanner  <--  session / api  <--  cli
                                                                                             scripts/ (may import anything; nothing imports scripts/)
```

- A package may import only from its own layer or layers to its left. No upward imports.
- `core/` imports nothing from the project. It holds schemas, config, validators and typed errors only, with no learning or planning logic.
- `diagnostic/` and `planner/` depend on `learner/` through the `MasteryModel` protocol, never on external libraries directly. Packages on the same layer (`diagnostic/`, `planner/`, `review/`) may import each other; the planner uses `review/forgetting.py`.
- `review/` calculates forgetting and urgency based on `LearnerConcept` and curriculum topology.
- `replanner/` imports `planner/` and `review/` to orchestrate replanning over updated state and effective contexts.
- `cli.py` contains no business logic. It parses inputs, invokes `api.py`, and prints results or errors.
- Third-party libraries are isolated to their specific domain: NetworkX only in `curriculum/graph.py`; pyBKT only in `learner/adapter.py` (both checked by the test); OR-Tools only in `planner/cpsat_model.py` (by convention).
- No non-deterministic modules (`random`, `time`, `datetime`) or LLM SDKs (`openai`, `anthropic`, `google`, `agents`) may be imported anywhere in `src/adaptengine`. Randomness in the bisection diagnostic and CP-SAT uses fixed seeds from `EngineConfig`.

### Layer <-> Package Mapping

| Layer (Design) | Package / File |
|---|---|
| Core (0) | `core/` |
| Curriculum (1) | `curriculum/` |
| Learner State (2) | `learner/` |
| Decision (3) | `diagnostic/`, `planner/`, `review/` |
| Replanning (4) | `replanner/` |
| Orchestration (5) | `session.py`, `api.py` (`Engine.record`, `Engine.plan`, `Engine.replan`) |
| Interfaces (6) | `cli.py` |


---

## 2. Design Principles (Q1–Q8)

| # | Attribute | Meaning |
|---|---|---|
| Q1 | Constraint safety | Prerequisites and daily budgets are hard constraints enforced by the deterministic engine |
| Q2 | Determinism | Same inputs and configuration always give identical decisions, outputs, and traces |
| Q3 | Traceability | Every selection, omission, and update carries an auditable, machine-readable reason |
| Q4 | Testability | Modules are independently testable in isolation with regression guarantees |
| Q5 | Replaceability | Mastery, review, ranking, and planning models can be swapped via narrow protocols |
| Q6 | Simplicity | Clear, readable architecture maintainable by a single developer |
| Q7 | Measurable performance | Core operations are benchmarkable against frozen baselines on paired workloads |
| Q8 | Bounded autonomy | Optional agents may propose or re-rank, but cannot bypass engine constraints |

---

## 3. System Context & Workflow

AdaptEngine acts as an embedded, deterministic learning path and diagnostic engine:

```
[Curriculum Content JSON] + [Review Manifest] 
                    │
                    ▼
     [Curriculum Loader & Review Gate]
                    │
                    ▼
          [Curriculum DAG (NetworkX)]
                    │
                    ▼
[Learner State] ──> [Diagnostic: sweep or bisection] ──> [Initial Assessed State + Log]
                    │
                    ▼
         [Engine Facade / API] <── [CLI / Upstream Caller]
                    │
                    ▼
      [(State', Log') <= Engine.record] (Atomic Snapshot)
```

### End-to-End Workflow
1. **Load and validate:** The loader (`curriculum/loader.py`) checks the review manifest, the JSON schema, duplicate IDs, unknown prerequisites and unknown activity targets. Cycles (including self-loops) are rejected by `CurriculumGraph` (`curriculum/graph.py`, `CycleError`) when the engine is built. Isolated or unreachable concepts are not rejected. Any failure halts before state mutation with typed errors.
2. **Diagnose:** A bounded diagnostic estimates what the learner already knows. The sweep (`diagnostic_method="sweep"`, default) asks per concept by expected information gain; bisection (`"bisection"`) asks the question that best splits the possible knowledge states.
3. **Plan:** Project the work each required concept needs, pack days within the budget (5, 10, 15, 30 min) in prerequisite order with the greedy planner, or with CP-SAT (`planner_method="cpsat"` or `"hybrid"`), and return a feasibility verdict.
4. **Execute and update:** Learner interaction outcomes are dispatched as typed `Event`s to `Engine.record`, updating mastery and log atomically.
5. **Replan:** Missed days or constraint changes trigger replanning over the remaining horizon, preserving completed attempts without loss or duplication.
6. **Evaluate:** The `experiments/` study runs simulated learners in closed loops and reports pre-registered comparisons (E1 to E6).

---

## 4. Components

| Component | Package / File | Description | Concept doc |
|---|---|---|---|
| Core Schemas & Errors | `core/schema.py`, `core/errors.py`, `core/validators.py` | Dataclasses for Concept, Activity, Event, PlanContext, Plan with strict type and range checks | — |
| Config & Hashes | `core/config.py`, `core/constants.py` | `EngineConfig` with validated bounds, `config_from_file`, SHA-256 `config_hash` | — |
| Curriculum Loader & Review Gate | `curriculum/loader.py` | Validated JSON loading, unknown prerequisite rejection, SHA-256 manifest check with a named human reviewer | [01](../concepts/01_curriculum_graph.md) |
| Curriculum Graph | `curriculum/graph.py` | NetworkX DAG; rejects cycles and self-loops (`CycleError`) and unknown prerequisites (`UnknownConceptError`); precomputed ancestors, descendants, depths and topological order | [01](../concepts/01_curriculum_graph.md) |
| Content | `curriculum/content.py` | Display-only lesson text and questions | [01](../concepts/01_curriculum_graph.md) |
| Mastery Model | `learner/mastery.py`, `learner/adapter.py`, `learner/evidence.py` | BKT update, learn step, entropy, `CustomBKT`, `PyBKTAdapter` (parity-tested), single evidence update site | [02](../concepts/02_mastery_bkt.md) |
| Item-Model Profiles | `learner/profiles.py` | Fitted guess and slip per difficulty class (`ClassBKT`) | [03](../concepts/03_item_models.md) |
| Learner State & Persistence | `learner/state.py`, `session.py` | Immutable state, attempt idempotency, atomic snapshot persistence with context | [02](../concepts/02_mastery_bkt.md) |
| Sweep Diagnostic | `diagnostic/engine.py`, `diagnostic/scoring.py` | EIG selection, per-concept and global caps, descendant skipping, cold start | [04](../concepts/04_diagnostic_sweep.md) |
| Bisection Diagnostic | `diagnostic/bisection.py`, `diagnostic/knowledge_space.py` | Knowledge-state posterior over prerequisite-closed sets, confidence stop | [05](../concepts/05_diagnostic_bisection.md) |
| Confirmation | `planner/confirmation.py` | Short checks instead of full study for concepts bisection inferred | [05](../concepts/05_diagnostic_bisection.md) |
| Greedy Planner & Oracle | `planner/workload.py`, `schedule.py`, `plan.py`, `difficulty.py`, `feasibility.py`, `oracle.py` | Workload projection, day packing, difficulty policy, feasibility bounds, exact oracle, decision traces | [06](../concepts/06_planning.md) |
| CP-SAT Planner | `planner/cpsat_model.py`, `cpsat_planner.py`, `cpsat_trace.py` | Pure CP-SAT and hybrid planners with post-solve explanations | [07](../concepts/07_cpsat.md) |
| Review & Remediation | `review/forgetting.py`, `planner/schedule.py` | Half-life recall, review urgency, priority tiers, repeat lesson insertion | [08](../concepts/08_review_remediation.md) |
| Replanner | `replanner/replan.py`, `api.py` | Horizon replanning on missed days, failed assessments, deadline and budget changes; frontier memoization | [09](../concepts/09_replanning.md) |
| Engine Facade | `api.py` | `Engine.record` (single mutation boundary), `diagnose`, `plan`, `replan`, `next_activities` | — |
| CLI | `cli.py` | Thin command-line interface with default review gate, `plan --json`, `replan`, exit code 2 on errors | — |
| Web Demo | `frontend/api/`, `frontend/web/` | FastAPI adapter and React app over `Engine` | — |
| Evaluation Study | `experiments/` | Pre-registered study E1 to E6: simulated learners, closed-loop episodes, violation audits, metrics, report pipeline | [10](../concepts/10_evaluation.md), [11](../concepts/11_study_statistics.md) |

> **Stateful Purity Note:** The workload cache (`WorkloadCache`) used for frontier replanning is an explicit, caller-owned memoization value passed across calls (`workload_cache=cache`). The `Engine` facade itself maintains no hidden internal state or mutable caches, preserving functional purity and determinism across planning operations.

---

## 5. Boundary Rules & Data Model

- **Review Gate:** On by default at all entry points; authoring-only bypass requires an explicit flag that prints a warning to stderr.
- **Fail-Fast Validation:** All validation precedes mutation. Rejected inputs leave existing state and log files strictly byte-identical.
- **Strict Typing:** Correctness must be a boolean; probabilities must be finite in $[0, 1]$; transition rates $T \in [0, 1]$; durations positive integers.
- **Atomic Persistence:** State and log are committed together via temporary file write, flush, fsync, and atomic `os.replace`.
- **Data Model:**
  - `Concept`: `concept_id`, `prerequisites` (tuple of existing concept IDs), `description`.
  - `Activity`: `activity_id`, `type` (`LESSON` / `EXERCISE`), `target_concept`, `duration` (integer minutes), `difficulty` ($\in [d_{\min}, d_{\max}]$ for exercises, absent for lessons), `text`, `d_min`, `d_max`. Durations and difficulties are synthetic heuristics.
  - `LearnerConcept`: `concept_id`, `p`, `lessons_done`, `responses`, `correct_responses`, `status` (`UNASSESSED` / `ASSESSED`), `seen_attempt_ids`, `half_life_days`, `last_practice_day`, `n_reviews`, `needs_remediation`, `correct_streak`, `diag_confident`, `confirmed`.
  - `Event`: `day`, `kind` (`COMPLETED`, `MISSED`, `FAILED_ASSESSMENT`, `DEADLINE_CHANGED`, `BUDGET_CHANGED`), `activity_id`, `minutes_elapsed`, `correct`, `attempt_id`, `value: Optional[int] = None`.
  - `PlanContext`: `goal`, `deadline_day`, `budget`, `current_day`, `minutes_used_today`.
  - `Plan`: `status`, `days`, `reason`, `shortfall_days`, `options`, `trace`, `best_effort_days`.

Full field lists: [API_REFERENCE.md §3](API_REFERENCE.md#3-coreschemapy--domain-schemas).
