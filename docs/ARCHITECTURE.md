# Architecture

## Modules (Implemented)
- `core/`: Errors, config, schema, validators.
- `curriculum/`: Loader, graph (DAG), review gate.
- `learner/`: State, mastery update, mastery-model adapter.
- `diagnostic/`: Adaptive diagnostic (selection, stopping, results).
- `planner/`: Deterministic path planner, difficulty policy, feasibility bounds, exact bin-packing oracle.
- `review/`: Spaced review forgetting model (half-life decay) and review urgency scoring.
- `replanner/`: Dynamic horizon replanning on events (missed day, failed assessment, deadline changed, budget changed).

## Planned Modules
The following modules are planned but not yet implemented (no files created):
- simulator
- evaluation harness
- agents

---

## 1. Dependency Direction and Layering Rules

The architecture enforces strict unidirectional dependency flow verified by automated AST tests (`tests/test_architecture.py`):

```
core  <--  curriculum  <--  learner  <--  diagnostic / planner / review  <--  replanner  <--  session / api  <--  cli
                                                                                             scripts/ (may import anything; nothing imports scripts/)
```

- A package may import only from packages to its left. No upward or sideways imports.
- `core/` imports nothing from the project. It holds schemas, config, validators and typed errors only, with no learning or planning logic.
- `diagnostic/` and `planner/` depend on `learner/` through the `MasteryModel` protocol, never on external libraries directly.
- `review/` calculates forgetting and urgency based on `LearnerConcept` and curriculum topology.
- `replanner/` imports `planner/` and `review/` to orchestrate replanning over updated state and effective contexts.
- `cli.py` contains no business logic. It parses inputs, invokes `api.py`, and prints results or errors.
- Third-party libraries are isolated to their specific domain: NetworkX only in `curriculum/graph.py`; pyBKT only in `learner/adapter.py`.
- No non-deterministic modules (`random`, `time`, `datetime`) or LLM SDKs are permitted in the deterministic core.

### Layer <-> Package Mapping

| Layer (Design) | Package / File |
|---|---|
| Core (0) | `core/` |
| Curriculum (1) | `curriculum/` |
| Learner State (2) | `learner/` |
| Decision (3) | `diagnostic/` (W3), `planner/` (W4), `review/` (W5) |
| Replanning (4) | `replanner/` (W5) |
| Orchestration (5) | `session.py`, `api.py` (`Engine.record`, `Engine.plan`, `Engine.replan`) |
| Interfaces (6) | `cli.py` |
| Optional Agentic | `agents/` (planned, no files created) |


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
[Learner State] ──> [Adaptive Diagnostic (M2)] ──> [Initial Assessed State + Log]
                    │
                    ▼
         [Engine Facade / API] <── [CLI / Upstream Caller]
                    │
                    ▼
      [(State', Log') <= Engine.record] (Atomic Snapshot)
```

### End-to-End Workflow
1. **Load and validate:** Schema validation, reject unknown prerequisites and cycles, enforce review manifest. Any failure halts before state mutation with typed errors.
2. **Diagnose (M2):** Bounded adaptive diagnostic queries expected information gain (EIG) to produce an initial mastery vector with uncertainty and `UNASSESSED` flags.
3. **Plan (M3):** Filter eligible activities by unlocked prerequisites, rank, pack days within budget (5, 10, 15, 30 min), returning a feasibility verdict.
4. **Execute and update:** Learner interaction outcomes are dispatched as typed `Event`s to `Engine.record`, updating mastery and log atomically.
5. **Replan (Implemented, M6):** Missed days or constraint changes trigger replanning over the remaining horizon, preserving completed attempts without loss or duplication.
6. **Evaluate (Planned, M8):** Run paired simulation workloads against frozen baselines with fixed seeds.

---

## 4. Components and Status

| Component | Package / File | Status | Description |
|---|---|---|---|
| Core Schemas & Errors | `core/schema.py`, `core/errors.py` | Hardened (W3) | Dataclasses for Concept, Activity, Event with strict type and range invariants |
| Config & Hashes | `core/config.py` | Hardened (W3, W5) | EngineConfig with validated bounds, synthetic heuristics, and SHA-256 serialization hashing |
| Curriculum Loader | `curriculum/loader.py` | Hardened (W3) | Validated JSON loading, unknown prerequisite rejection, review gate enforcement |
| Curriculum Graph | `curriculum/graph.py` | Hardened (W3) | NetworkX DiGraph wrapper with cycle detection and topological sorting |
| Review Gate | `curriculum/loader.py` | Hardened (W3) | SHA-256 manifest check, named human reviewer enforcement, literal `edges_reviewed` |
| Mastery Model & Oracle | `learner/mastery.py`, `learner/adapter.py` | Implemented (W3) | BKT Bayesian update, learn transition, entropy, and `CustomBKT` oracle |
| pyBKT Adapter | `learner/adapter.py` | Implemented (W3) | Discrete difficulty class mapping (D6) with parity test against custom oracle |
| Learner State & Persistence | `learner/state.py`, `session.py` | Hardened (W3, W5) | Immutable state, evidence semantics, attempt idempotency, atomic snapshot persistence with context |
| Adaptive Diagnostic | `diagnostic/` | Implemented (W3) | M2 EIG-based selection, per-concept/global caps, descendant skipping, cold start |
| Engine Facade | `api.py` | Hardened (W3, W5) | Single mutation boundary `Engine.record`, `Engine.diagnose`, `Engine.plan`, `Engine.replan` |
| CLI Interface | `cli.py` | Hardened (W3, W5) | Thin command-line interface with default review gate, `plan --json`, and `replan` |
| Planner & Feasibility Oracle | `planner/` | Implemented (W4) | Day-by-day packing, difficulty policy, feasibility bounds, exact oracle |
| Review & Remediation | `review/`, `planner/schedule.py` | Implemented (W5) | Half-life decay forgetting baseline, priority tiers (remediation > review > new), repeat lesson insertion |
| Replanner | `replanner/`, `api.py` | Implemented (W5) | Horizon replanning on missed days, failed assessments, deadline changes, budget changes |
| Explainer & Traces | `planner/plan.py` | Implemented (W5) | Machine-readable decision traces, pure JSON serialization with config hash |
| Simulator & Evaluator | Planned | Planned (M8) | Transparent synthetic evaluation harness |

---

## 5. Boundary Rules & Data Model

- **Review Gate:** On by default at all entry points; authoring-only bypass requires an explicit flag that prints a warning to stderr.
- **Fail-Fast Validation:** All validation precedes mutation. Rejected inputs leave existing state and log files strictly byte-identical.
- **Strict Typing:** Correctness must be a boolean; probabilities must be finite in $[0, 1]$; transition rates $T \in [0, 1]$; durations positive integers.
- **Atomic Persistence:** State and log are committed together via temporary file write, flush, fsync, and atomic `os.replace`.
- **Data Model:**
  - `Concept`: `concept_id`, `prerequisites` (tuple of existing concept IDs), `description`.
  - `Activity`: `activity_id`, `type` (`LESSON` / `EXERCISE`), `target_concept`, `duration` (integer minutes), `difficulty` ($\in [d_{\min}, d_{\max}]$ for exercises, absent for lessons). Durations and difficulties are synthetic heuristics.
  - `LearnerConcept`: `concept_id`, `p`, `lessons_done`, `responses`, `correct_responses`, `status` (`UNASSESSED` / `ASSESSED`), `seen_attempt_ids`, `half_life_days`, `last_practice_day`, `needs_remediation: bool = False`.
  - `Event`: `day`, `kind` (`COMPLETED`, `MISSED`, `FAILED_ASSESSMENT`, `DEADLINE_CHANGED`, `BUDGET_CHANGED`), `activity_id`, `minutes_elapsed`, `correct`, `attempt_id`, `value: Optional[int] = None`.
  - `PlanContext`: `goal`, `deadline_day`, `budget`, `current_day`.

---

## 6. Optional Agentic Layer (Planned, No Files Created)

Any future agentic capability is strictly bounded outside the deterministic engine core (disabled by default):
- **A0 Authoring Aid:** Offline generation of draft curriculum files; requires human sign-off in manifest.
- **A1 Plan Proposer:** Proposes daily activity sequences; validated by engine constraints with deterministic fallback.
- **A2 Ranking Policy:** Learns candidate re-ranking (e.g. contextual bandit) among activities that already passed hard prerequisite and budget filters.
- **A3 Orchestrator:** Chooses next macro strategy (continue, review, remediate, re-diagnose) from a closed set.
