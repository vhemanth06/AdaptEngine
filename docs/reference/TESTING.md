# Testing and Commands

How the tests are laid out, what each file checks, and the commands that run them. Every command on this page was run on 21 Nov 2026 from the repository root with the project virtual environment (`.venv`). It replaces the archived `TEST_SUITE.md` and `verification_guide.md` (in `../archive/superseded/`).

Module map: [ARCHITECTURE.md](ARCHITECTURE.md). Setup: [README](../../README.md).

## Counts on 21 Nov 2026

| Suite | Command | Result | Time |
|---|---|---|---|
| Engine | `.venv/bin/pytest -q tests` | 403 passed | ~90 s |
| Engine with lint and coverage | `make check` | 403 passed, 92.64 % coverage (gate: 84 %) | ~140 s |
| Evaluation study | `.venv/bin/pytest -q experiments/tests` | 57 passed | ~50 s |
| Web API | `.venv/bin/pytest -q frontend/api/tests` | 23 passed | ~7 s |
| Browser (Playwright) | `cd frontend/web && npx playwright test` (via `make demo-test`) | 11 passed | ~16 s (build plus tests ~30 s) |

`pyproject.toml` sets `testpaths = ["tests"]`, so a bare `pytest` (and `make test`) runs only the engine suite.

## Layout

```
tests/                      engine tests (403)
  conftest.py
  fixtures/                 valid and invalid curricula, regression pins, recorded CLI runs
  unit/<layer>/             one folder per engine package: core, curriculum, learner,
                            diagnostic, planner, review, replanner
  integration/              Engine API, CLI and closed-loop scenarios
  regression/               pinned outputs and reproductions of fixed defects
  tooling/                  architecture rules, scripts and examples
experiments/tests/          evaluation study tests (57)
  unit/  integration/  tooling/
frontend/api/tests/         web API tests (23); skipped when the demo extra is not installed
frontend/web/e2e/           Playwright browser tests (11)
```

## What each file checks

Descriptions come from each file's module docstring, or from its test names where it has none. Test-case IDs (TC…, F1-TC…, V2-TC…) are listed in [TRACEABILITY.md](../project/TRACEABILITY.md).

### `tests/unit/` (269 tests)

| File | Checks |
|---|---|
| `core/test_schema.py` | `Concept`, `Activity` and `Event` validation; valid fixtures load; every invalid fixture is rejected. |
| `curriculum/test_content.py` | Display-only content files: the real 8-node content covers its activities; invalid and unparseable content is rejected. |
| `curriculum/test_curriculum_x10.py` | The `8node_x10` curriculum (Plan 1, F5-TC1, TC2, TC7). |
| `curriculum/test_graph.py` | DAG checks: cycles and self-loops rejected; precomputed indices match NetworkX; `WorkloadCache` is bounded (W7 T6.1). |
| `curriculum/test_loader_review_gate.py` | Review gate: missing manifest or entry, missing or AI reviewer, `edges_reviewed` false, hash mismatch. |
| `learner/test_adapter.py` | `MasteryModel` protocol, `CustomBKT` reference values, difficulty classes (D6), adapter and oracle parity. |
| `learner/test_mastery.py` | BKT guess and slip table, update values, lesson transition, entropy, bounds. |
| `learner/test_profiles.py` | Fitted item-model profiles (Plan 2, F2-TC1 to TC5). |
| `diagnostic/test_bisection.py` | Bisection diagnostic (Plan 3, F1-TC1, TC2, TC4, TC6). |
| `diagnostic/test_diagnostic.py` | Sweep diagnostic: item caps, entropy stop, cold start, descendant skipping, determinism, tie-breaking (D10), W7 T3.2 options, state-space diagnostic (T3.6). |
| `diagnostic/test_knowledge_space.py` | Knowledge-space inference (Plan 3, F1-TC3, TC5, TC12). |
| `planner/test_confirmation.py` | Learner flags, epsilon confirmation, the planner confirmation path and the closed loop (F1-TC7 to TC9). |
| `planner/test_cpsat_planner.py` | Greedy, pure CP-SAT and hybrid planners (Plan 4, F3-TC1 to TC5, TC7, TC10). |
| `planner/test_cpsat_reviews.py` | Reviews in the CP-SAT model and the CP-SAT trace (F3-TC6, TC8). |
| `planner/test_planner.py` | Greedy planner and oracle: difficulty policy (TC4.2), prerequisite safety (TC3.1), budgets (TC3.2), pacing (TC3.3), infeasible deadline (TC3.4), oracle (TC3.5, TC3.6), two learners (TC2.3), traces (TC7.1), mid-day replan (T2.1). |
| `planner/test_planner_projection.py` | W7 WP2: exercise repeats (T2.3), expected projection (T2.5), best-effort plans (T2.4), closed-loop entry point (T2.2). |
| `review/test_review.py` | Recall values, review due rule, urgency formula (D25), review counting (T2.6). |
| `replanner/test_replan_frontier.py` | Frontier replanning with a `WorkloadCache` gives the same plan as full recomputation (TC8.2), cache hits, engine isolation. |

### `tests/integration/` (74 tests)

| File | Checks |
|---|---|
| `test_cli.py` | CLI commands: validate, show, model flag, error exit codes and stderr, JSON round trip. |
| `test_cli_config.py` | `--config` and `--model-profile` on every CLI command (Plan 2.5, P2.5-TC1 to TC4); compares against `tests/fixtures/cli_default_runs.json`. |
| `test_closed_loop_planners.py` | Every planner in the closed loop, with F1 and F2 options, and from the CLI (Plan 4, F3-T7). |
| `test_engine_api.py` | The public `Engine` API (`adaptengine.api`). |
| `test_plan_replan_scenarios.py` | Milestone scenarios TC5.1 to TC7.1: planning, replan events, traceability, CLI replan and working ahead. |
| `test_state_session.py` | Response and lesson updates, `last_practice_day`, learner and log round trips, snapshot atomicity, field survival. |

### `tests/regression/` (39 tests)

| File | Checks |
|---|---|
| `test_baseline_pins.py` | Plan 0 regression pins (P0-TC1, TC2; D59): `population_prior.json` and `default.json` in `tests/fixtures/pins/` must be reproduced exactly. |
| `test_defects_repro.py` | Reproductions of fixed defects D-A to D-F and a partial-day replan budget overflow. |
| `test_feedback_fixes.py` | Review feedback fixes: atomic CLI snapshots, config validators, strict deserialization, model injection, pyBKT parity (skipped unless pyBKT is installed). |

### `tests/tooling/` (21 tests)

| File | Checks |
|---|---|
| `test_architecture.py` | AST scan of `src/adaptengine`: layer order (section 1 of ARCHITECTURE.md), NetworkX only in `curriculum/graph.py`, pyBKT only in `learner/adapter.py`, no `time`, `datetime`, `random` or LLM SDK imports. |
| `test_check_content.py` | `scripts/content/check_content.py` and the `8node_x10` content (Plan 1, F5-TC3, TC4). |
| `test_poc_demo.py` | `scripts/demo/poc_demo.py`: different plans per profile, constraints hold, infeasible request gives shortfall and options, completed work is not repeated, events and spaced review. |
| `test_quickstart.py` | `examples/api_quickstart.py` runs cleanly. |

### `experiments/tests/` (57 tests)

| File | Checks |
|---|---|
| `unit/test_audit.py` | Executed-violation audit and plan-level validity checks (V2-TC3). |
| `unit/test_diagnostics.py` | Diagnostic arms (V2-T2). |
| `unit/test_metrics.py` | Scoring rules on hand-computed cases; deterministic paired bootstrap (V2-TC3). |
| `unit/test_realdata.py` | Real-data fitting and cross-validation on synthetic data (V2-T3); real files not needed. |
| `unit/test_scenarios.py` | Scenario events and the horizon rule (V2-TC1). |
| `unit/test_simulator.py` | The simulated learner (V2-TC1). |
| `integration/test_determinism.py` | Identical results apart from timing fields, whatever the worker count (V2-TC4). |
| `integration/test_episode.py` | Closed loop, no-replan and static episodes (V2-TC1). |
| `integration/test_runners_smoke.py` | Every runner's `--smoke` completes and writes a schema-valid file without a code hash (V2-TC6). |
| `tooling/test_prereg_guard.py` | No full run without a registered pre-registration (status and registration time) (V2-TC5). Since D104 the tests `test_other_hash_is_refused` and `test_amendment_hash_counts` are gone (they tested the removed code-hash check); `test_missing_registered_utc_is_refused` was added and `test_registered_with_current_hash_runs` is now `test_registered_runs`. |
| `tooling/test_report.py` | The report pipeline: extract, CSV, tables and figures (V2-TC10 to TC12). |
| `tooling/test_results_schema.py` | The results schema accepts a valid document and rejects broken ones (V2-TC6); `test_existing_results_still_validate` (added with D104) checks that every final results file, which still carries the code and harness hashes of the time, validates. |

### `frontend/api/tests/` (23 tests)

These use FastAPI's `TestClient` (W7 T8.2). Each test file calls `pytest.importorskip`, so they are skipped when the demo extra is not installed.

| File | Checks |
|---|---|
| `conftest.py` | Shared fixtures; FastAPI and the app are imported inside the fixtures. |
| `helpers.py` | Shared helpers (no tests). |
| `test_curricula.py` | Curriculum list and detail. |
| `test_sessions.py` | Session lifecycle: create, plan, events, trace, flags, day handling. |
| `test_parity.py` | API results equal the engine called directly. |
| `test_health_preset.py` | `/api/health` and the demo preset. |

### `frontend/web/e2e/` (11 tests)

| File | Checks |
|---|---|
| `demo.spec.ts` | The demo walkthrough of `frontend/README.md` in deterministic demo mode (Plan FE, FE-TC7); 1 test. |
| `screens.spec.ts` | Every screen in light and dark, failure states, command palette, theme and keys (FE-TC8 to TC10); 10 tests. Screenshots are saved, never compared pixel by pixel. |

## Commands

### Engine tests and lint

```bash
make check                                   # ruff check, ruff format --check, then make test
make test                                    # pytest -q --cov=adaptengine --cov-fail-under=84 (tests/ only)
make lint                                    # ruff check . && ruff format --check .
.venv/bin/pytest -q tests                    # whole engine suite, no coverage
.venv/bin/pytest -q tests/unit/planner       # one layer
.venv/bin/pytest -q tests/integration        # one kind
.venv/bin/ruff check .
.venv/bin/ruff format --check .
make format                                  # rewrites files: ruff format . && ruff check --fix .
```

`make format` changes files, so it was not run for this page; the two check commands above were.

### pyBKT parity

The CI job `pybkt-parity` installs `requirements-pybkt.txt` and runs:

```bash
REQUIRE_PYBKT=1 .venv/bin/python -m pytest -q tests/regression/test_feedback_fixes.py -k test_pybkt_adapter_genuine_parity
```

Without `REQUIRE_PYBKT=1` the test is skipped when pyBKT is missing; with it, a missing pyBKT is a failure.

### Evaluation study

```bash
make exp-test                                # pytest -q experiments/tests
make exp-smoke                               # every runner with --smoke (1-2 learners, output in a temp folder)
```

`make exp-smoke` runs E3, E2, E1, E4, E5, E6 in that order and took 9 s. `make exp-run` (the full study) and `make exp-report` (rebuild tables and figures from `experiments/results/`) write tracked files and were not run here; see `experiments/README.md`.

### Web demo

```bash
make demo-test                               # pytest -q frontend/api/tests, then npm run build and npx playwright test
cd frontend/web && npx playwright test       # browser tests only (needs npm ci and a built dist/)
make demo                                    # start the demo (scripts/demo/demo.py)
```

Needs `pip install -e ".[demo]"`, `npm ci` in `frontend/web`, and once `npx playwright install chromium`.

### Acceptance runners

| Command | What it does |
|---|---|
| `make w3` (`scripts/acceptance/run_w3.py`) | Week 3 runner: ruff, pytest with coverage gate 84 %, reference constants, layering check, diagnostic persona demo. Writes `runs/w3/<run-id>/`. |
| `make w4` (`scripts/acceptance/run_w4.py`) | Week 4 runner: planner and difficulty-policy scenarios (TC2.3, TC3.1 to TC3.6, TC4.2). Writes `runs/w4/<run-id>/`. |
| `make w5` (`scripts/acceptance/run_w5.py`) | Week 5 runner: review and remediation, replanning, traces (TC5.1 to TC5.3, TC6.1 to TC6.4, TC7.1). Writes `runs/w5/<run-id>/`. |
| `make poc` (`scripts/demo/poc_demo.py`) | End-to-end proof of concept on the 4-node curriculum. |

`runs/` is in `.gitignore`. There is no W6 runner and no `make eval` target.

## CLI

The command is `.venv/bin/adaptengine` (or `.venv/bin/python -m adaptengine`). Subcommands: `validate`, `show`, `init-learner`, `update`, `missed-day` (alias `record-missed-day`), `failed-assessment` (`record-failed-assessment`), `change-deadline` (`record-deadline-change`), `change-budget` (`record-budget-change`), `plan`, `replan`, `import-legacy`, `export-legacy`. Every subcommand accepts `--config FILE` and `--model-profile PATH`; `--help` lists the rest. Errors exit with code 2.

A walkthrough on the 4-node curriculum (the snapshot path is any writable file):

```bash
A="--curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json"

adaptengine validate $A                      # OK: 4 concepts, 20 activities (reviewed)
adaptengine show --curriculum data/curriculum/curriculum_4node.json
adaptengine init-learner --curriculum data/curriculum/curriculum_4node.json \
    --snapshot /tmp/snap.json --goal C4 --deadline 10 --budget 10
adaptengine update $A --snapshot /tmp/snap.json --activity E-C1-0.6 --response incorrect --day 1 --save
adaptengine plan $A --snapshot /tmp/snap.json --goal C4 --deadline 10 --budget 10 [--json]
adaptengine missed-day $A --snapshot /tmp/snap.json --day 2
adaptengine change-budget $A --snapshot /tmp/snap.json --day 3 --new-budget 15
adaptengine change-deadline $A --snapshot /tmp/snap.json --day 3 --new-deadline 12
adaptengine failed-assessment $A --snapshot /tmp/snap.json --activity E-C2-0.4 --day 3
adaptengine replan $A --snapshot /tmp/snap.json [--json]
```

Failure case: a cyclic curriculum is rejected even in authoring mode (exit code 2):

```bash
adaptengine validate --curriculum tests/fixtures/invalid/cycle.json \
    --activities tests/fixtures/invalid/cycle_activities.json --allow-unreviewed
# error: Cycle detected: [('C1', 'C2', 'forward'), ('C2', 'C1', 'forward')]
```

## Scripts

What each script does, how to run it and what it writes is in [`scripts/README.md`](../../scripts/README.md).

| Script | Run as | What it does |
|---|---|---|
| `scripts/content/record_review.py` | `python scripts/content/record_review.py FILE --reviewer NAME --source SRC [--edges-reviewed] [--manifest PATH]` | Records a file's SHA-256 and reviewer in `data/review_manifest.json` (or `--manifest`). `--pending` records `PENDING_HUMAN_REVIEW` instead of a name. |
| `scripts/content/check_content.py` | `python scripts/content/check_content.py data/content/content_8node_x10.json --activities data/curriculum/activities_8node_x10.json --curriculum data/curriculum/curriculum_8node_x10.json` | Content quality checks (answer positions balanced, no duplicates). |
| `scripts/datasets/download_data.py` | `python scripts/datasets/download_data.py --verify-only` | Checks the hashes of `data/external/`; without `--verify-only` it downloads the public files. |
| `scripts/demo/demo.py` | `make demo` or `python scripts/demo/demo.py [--port 8000] [--no-build]` | Rebuilds `frontend/web/dist` if needed and starts the demo server. |
| `scripts/testing/record_pins.py` | `python scripts/testing/record_pins.py {population\|default}` | Re-records `tests/fixtures/pins/*.json`. Only on a deliberate default change; not run here. |

The last two rewrite tracked files, so they were not run for this page. The `run_w*.py` and `poc_demo.py` scripts are in the acceptance runners table above.
