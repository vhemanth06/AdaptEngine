# AdaptEngine — Week 3 (W3) Audit Report

**Date:** 2026-10-11
**Auditor:** AdaptEngine AI Pair Programmer

## 1. Executive Summary & Baseline Metrics

The existing codebase was audited against the W3 plan requirements and defects D-A through D-I.
Baseline checks executed cleanly:
- **Ruff Lint:** `ruff check .` — Passed (all checks clean).
- **Ruff Format:** `ruff format --check .` — Passed (29 files already formatted).
- **Pytest:** `pytest -q --cov` — 47 passed in 1.54s.
- **Statement Coverage:** ~92% overall (~85% on `src/adaptengine` modules).

## 2. Real Module Paths & Public APIs

- `src/adaptengine/core/`:
  - `errors.py`: `AdaptEngineError`, `ValidationError`, `DuplicateIdError`, `UnknownConceptError`, `DifficultyError`, `UnreviewedContentError`, `CycleError`.
  - `constants.py`: `P0=0.20`, `THETA=0.85`, `T_DIAG=0.0`, `T_EXERCISE=0.05`, `T_LESSON=0.20`, `GUESS_COEF=0.30`, `SLIP_BASE=0.05`, `SLIP_COEF=0.25`, `D_MIN=0.05`, `D_MAX=0.95`.
  - `config.py`: `EngineConfig`, `DEFAULT_CONFIG`, `config_hash(cfg: EngineConfig) -> str`.
  - `schema.py`: `ActivityType` (LESSON, EXERCISE), `EventType` (COMPLETED, MISSED, FAILED_ASSESSMENT, DEADLINE_CHANGED, BUDGET_CHANGED), `Concept(concept_id, prerequisites, description)`, `Activity(activity_id, type, target_concept, duration, difficulty, text)`, `Event(day, kind, activity_id, minutes_elapsed, correct)`.
- `src/adaptengine/curriculum/`:
  - `loader.py`: `load_curriculum(path, manifest_path=None, *, allow_unreviewed=False)`, `load_activities(path, concepts, manifest_path=None, *, allow_unreviewed=False)`.
  - `graph.py`: `CurriculumGraph` wrapping NetworkX `DiGraph`. Methods: `concepts`, `roots`, `prerequisites`, `ancestors`, `descendants`, `descendant_count`, `depth`, `topological_order`.
- `src/adaptengine/learner/`:
  - `mastery.py`: `guess(d, cfg)`, `slip(d, cfg)`, `bayes_update(p, d, correct, cfg)`, `learn(p, T)`, `update_mastery(p, d, correct, T, cfg)`, `entropy(p)`.
  - `state.py`: `LearnerConcept`, `ExecutionLog`, `LearnerState`, `initial_state(concept_ids, cfg)`.
- `src/adaptengine/session.py`:
  - `UpdateRecord`, `apply_response`, `apply_lesson`, `load_learner`, `save_learner`, `load_log`, `save_log`.
- `src/adaptengine/api.py`:
  - `Engine` with `from_files`, `init_learner`, `record(state, log, event)`.
- `src/adaptengine/cli.py`:
  - Subcommands: `validate`, `show`, `init-learner`, `update`.
- `experiments/`:
  - `run_smoke.py`: runs a 6-step sequence on C1 without assertions.
  - `run_evaluation.py`: 0 bytes (empty).

## 3. Test Layout & Fixtures

- `tests/test_schema.py`: Tests for `Concept`, `Activity`, `Event` dataclass post-init, valid fixture loads, invalid fixture parameterized tests.
- `tests/test_mastery.py`: Verification of guess/slip table, update values, lesson transition, entropy, and reference constants.
- `tests/test_graph.py`: Graph creation, acyclicity, topological sort.
- `tests/test_loader_review_gate.py`: Manifest check, hash check, reviewer check.
- `tests/test_state_session.py`: Initial state, response application, round-trip persistence.
- `tests/test_api.py`: Engine initialization, recording completed/missed events.
- `tests/test_cli.py`: CLI execution for validate, show, init-learner, update.
- `tests/test_architecture.py`: AST import inspection (networkx only in graph, no network/LLMs, vacuous authoring isolation).
- `tests/fixtures/invalid/`: 14 invalid fixture JSON files.

## 4. Defect Reproduction Results

All defects D-A through D-H were reproduced with failing tests in `tests/test_defects_repro.py`:

| Defect ID | Description | Reproduction Status | Observed Behavior |
|-----------|-------------|---------------------|-------------------|
| **D-A** | CLI review gate bypassed | **Confirmed** | CLI `show`, `init-learner`, and `update` hardcode `allow_unreviewed=True`. Unreviewed or altered files are accepted. |
| **D-B** | Weak validation of Event & LearnerConcept | **Confirmed** | `Event.correct="false"` accepted as truthy without raising `ValidationError`. `LearnerConcept` accepts `uncertainty=-5`, `assessed="false"`, negative day/half-life. |
| **D-C** | Unknown prereq phantom node & list root crash | **Confirmed** | `unknown_prereq.json` creates phantom node `CX` in NetworkX without `UnknownConceptError`. List root JSON raises unhandled `AttributeError: 'list' object has no attribute 'get'`. |
| **D-D** | Lessons set assessed=True, replay mastery runaway, day rewind | **Confirmed** | 8x `apply_lesson` sets `assessed=True` and reaches `p=0.865782 > θ`. `last_practice_day` rewinds from 20 to 1. Missing attempt identity tracking. |
| **D-E** | Config validation & parameter bounds | **Confirmed** | `learn(0.5, 1.5)` returns 1.25 because `T` is not bounded to `[0, 1]`. `guess` and `slip` ignore `cfg.d_min/d_max` and use global constants. |
| **D-F** | Explicit manifest path fails, reviewer='AI' accepted | **Confirmed** | `load_curriculum(..., manifest_path="data/review_manifest.json")` fails with `UnreviewedContentError` because paths are resolved relative to `data/` instead of repo root. `"reviewer": "AI"` is accepted. |
| **D-G** | Non-atomic persistence | **Confirmed** | `save_learner` and `save_log` are two separate file writes without atomic snapshot replacement. |
| **D-H** | Import scanner ignores relative imports; vacuous test; smoke lacks assertions | **Confirmed** | AST scanner ignores `node.level > 0` (all relative imports). `test_tools_authoring_isolation` has `assert True`. `run_smoke.py` has no assertions. |
| **D-I** | Stale records & hardcoded paths | **Confirmed** | `DECISIONS.md` has stale Beta/A*/HLR. `TRACEABILITY.md` has obsolete TC-01..12 without M8. CLI hardcodes activities path in `show` and `init-learner`. |

No defects could not be reproduced; 100% of defect scenarios were confirmed.
