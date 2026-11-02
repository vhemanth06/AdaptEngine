# AdaptEngine Verification & Commands Guide

This document provides a comprehensive list of all commands available in the AdaptEngine, what they do, the testing architecture, and exactly how you can run and verify them.

---

## 0. Environment & Setup

Before running any validation or tests, you need to set up the python environment and ensure your git workflow is clean.

### Initial Setup
*   **What it does:** Creates an isolated python environment and installs all dependencies and the package itself in editable mode.
*   **Commands:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pip install -e .
    ```

### Git Workflow Commands
*   **What it does:** Stages, commits, and pushes your changes to the repository. This is critical before running the clean checkout verification script because it clones directly from the local git index.
*   **Commands:**
    ```bash
    git add .
    git commit -m "Your commit message"
    # To see the current status:
    git status
    ```

---

## 1. Core CLI Commands

The primary way to interact with the AdaptEngine is through the CLI (`python -m adaptengine`).

### `validate`
*   **What it does:** Parses curriculum and activity JSON files, checks them against the Review Gate (SHA-256 hash), ensures all referenced concepts exist, and guarantees the curriculum is a valid Directed Acyclic Graph (DAG) with no cycles.
*   **Command to check:** `python -m adaptengine validate --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json`
*   **Failure case:** Use the `--allow-unreviewed` flag with broken fixtures to see it catch errors (e.g., `python -m adaptengine validate --curriculum tests/fixtures/invalid/cycle.json --activities dummy.json --allow-unreviewed`).

### `show`
*   **What it does:** Displays the mathematical properties of a curriculum graph, including the root concepts, total nodes, edges, and the guaranteed topological sort order.
*   **Command to check:** `python -m adaptengine show --curriculum data/curriculum/curriculum_4node.json`

### `init-learner`
*   **What it does:** Creates a brand new, novice learner state (`p = 0.20`, Entropy = `0.7219`) for every concept in the curriculum and saves it to a JSON file.
*   **Command to check:** `python -m adaptengine init-learner --curriculum data/curriculum/curriculum_4node.json --out data/my_learner.json`

### `update`
*   **What it does:** Simulates a student completing an activity. It takes the learner's current state, applies the Bayesian Knowledge Tracing (BKT) math based on the activity's difficulty and whether the student was correct/incorrect, updates the execution log, and saves the new immutable state.
*   **Command to check:** `python -m adaptengine update --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --learner data/my_learner.json --log data/my_log.json --activity E-C1-0.6 --response incorrect --day 1 --save`

### `plan`
*   **What it does:** Generates a deterministic, time-budgeted day-by-day learning plan toward a target goal concept within a configured daily minute budget and deadline. Reports `FEASIBLE`, `INFEASIBLE` with calculated shortfall and corrective options, or `UNKNOWN` if the oracle node limit is reached.
*   **Command to check:** `python -m adaptengine plan --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --learner data/my_learner.json --goal C4 --deadline 10 --budget 10`
*   **With machine-readable traces:** Add `--json` to view detailed `SELECTED` and `DEFERRED` decision logs.

---

## 2. Utility & Verification Scripts

### `scripts/run_w6.py` (or `make w6`)
*   **What it does:** Standalone Week 6 MVP acceptance runner executing all 8 verification phases: Environment & meta, Ruff lint/format, Pytest with coverage ($\ge 84\%$), AST architecture layering, TC8.1 byte-identical evaluation rerun, TC8.2 frontier replan equivalence and latency benchmark, zero-violation and 100% trace coverage audit, and evidence packaging in `runs/w6/<timestamp>/`.
*   **Command to check:** `python scripts/run_w6.py` (or `make w6`)

### `experiments/run_evaluation.py` (or `make eval` / `make eval-quick`)
*   **What it does:** Runs the paired synthetic baseline evaluation across 100 seeded learners (or 10 in `--quick` mode), comparing diagnostic arms at matched budgets and 4 planner arms (`adapt`, `no_review`, `no_replan`, `static`) across 4 scenarios (`calm`, `missed_day`, `budget_drop`, `deadline_cut`). Generates `experiments/results/evaluation_results.json` deterministically.
*   **Command to check:** `make eval` or `make eval-quick`

### `scripts/run_w5.py` (or `make w5`)
*   **What it does:** Standalone Week 5 verification runner executing M5 review/remediation, M6 replanning, and M7 trace serialization acceptance scenarios (TC5.1–TC5.3, TC6.1–TC6.4, TC7.1).
*   **Command to check:** `python scripts/run_w5.py` (or `make w5`)

### `scripts/run_w4.py` (or `make w4`)
*   **What it does:** Standalone Week 4 verification runner executing all M3 planner and M4 difficulty policy acceptance scenarios (TC2.3, TC3.1–TC3.6, TC4.2), verifying AST layering rules, and producing an auditable evidence bundle in `runs/w4/<timestamp>/`.
*   **Command to check:** `python scripts/run_w4.py` (or `make w4`)

### `scripts/run_w3.py` (or `make w3`)
*   **What it does:** Standalone Week 3 verification runner executing diagnostic persona demos and W3 audit gates.
*   **Command to check:** `python scripts/run_w3.py` (or `make w3`)

### `experiments/run_smoke.py`
*   **What it does:** Runs a deterministic, hardcoded 6-step transactional trace of a student interacting with the engine.
*   **Command to check:** `python experiments/run_smoke.py`
*   **Pass/Fail:** It will pass and output a JSON stream of state changes. It will fail if the math in `mastery.py` has been tampered with or if non-determinism is introduced.

### `scripts/verify_clean_checkout.sh`
*   **What it does:** Proves the system works from scratch from an isolated working-tree copy. Creates a fresh venv in `/tmp`, installs editable package and dependencies, runs the test suite, executes the full CLI Quickstart flow, runs `examples/api_quickstart.py`, and verifies TC8.1 byte-identical evaluation outputs.
*   **Command to check:** `bash scripts/verify_clean_checkout.sh`
*   **Pass/Fail:** Passes with `CLEAN CHECKOUT OK` only if all dependencies and quickstart commands run without manual intervention.

### `scripts/record_review.py`
*   **What it does:** Computes the SHA-256 hash of a file and adds it to `data/review_manifest.json` as "reviewed content".
*   **Command to check:** `python scripts/record_review.py data/curriculum/curriculum_4node.json "John Doe"`

---

## 3. The Test Suite (`tests/`)

You can run the entire test suite and view coverage using:
`pytest -q --cov=adaptengine --cov-fail-under=84 --cov-report=term-missing`

Here is a breakdown of every test file, when it passes, and when it fails:

### `test_schema.py`
*   **What it tests:** Validates the strict Python dataclasses (`Concept`, `Activity`, `Event`, `PlanContext`, `PlanDay`, `Plan`).
*   **Passes when:** Probabilities, difficulties, and durations conform to type and range invariants.
*   **Fails when:** A file has negative duration, missing IDs, or an invalid budget.

### `test_loader_review_gate.py`
*   **What it tests:** The strict security hash checking of the Review Gate (ADR-016).
*   **Passes when:** The file's SHA-256 hash perfectly matches the one recorded in `review_manifest.json`.
*   **Fails when:** A user edits a file without re-reviewing it, or tries to load a file missing from the manifest. Throws `UnreviewedContentError`.

### `test_graph.py`
*   **What it tests:** Directed Acyclic Graph (DAG) logic and topological sorting using `networkx`.
*   **Passes when:** A valid curriculum flows in one direction with proper roots.
*   **Fails when:** It detects a cycle (Concept A requires B, and B requires A), or self-loops (Concept A requires A). Throws `CycleError`.

### `test_mastery.py`
*   **What it tests:** The Bayesian Knowledge Tracing (BKT) math and Shannon Entropy.
*   **Passes when:** The probability updates (`guess`, `slip`, `bayes_update`) exactly match the precomputed mathematical ground truths.
*   **Fails when:** The math is tampered with, or if probabilities exceed boundary limits (`< 0` or `> 1`).

### `test_adapter.py`
*   **What it tests:** Parity between the `MasteryModel` protocol, discrete difficulty mapping, and analytical custom BKT oracle.
*   **Passes when:** Updates match analytical reference constants and parity tolerance $\le 10^{-9}$.

### `test_diagnostic.py`
*   **What it tests:** Milestone M2 adaptive diagnostic, Expected Information Gain (EIG) item selection, entropy stopping rule, and descendant pruning.
*   **Passes when:** Total items $\le N_{\max}=8$, entropy stops probing, and ancestor failure skips descendants.

### `test_planner.py`
*   **What it tests:** Milestone M3 time-budgeted planner, M4 difficulty policy, analytical feasibility bounds, exact bin-packing oracle, and prerequisite safety.
*   **Passes when:** Prerequisites are strictly preserved, daily budget is never exceeded across 5/10/15/30 min, and exact oracle solves abstract bin-packing.

### `test_state_session.py`
*   **What it tests:** State immutability and JSON persistence.
*   **Passes when:** `LearnerState` is successfully saved to disk and loaded back with identical values.
*   **Fails when:** Code attempts to mutate an existing state in-place (throws `TypeError`), ensuring states are strictly transactional.

### `test_api.py` & `test_cli.py`
*   **What it tests:** End-to-end integration of the CLI parsing and the API boundary (`Engine.record`, `Engine.diagnose`, `Engine.plan`).
*   **Passes when:** CLI commands exit with code `0` and print the expected output.
*   **Fails when:** Files are missing, arguments are malformed, or the curriculum throws validation errors. Exits with code `2`.

### `test_architecture.py`
*   **What it tests:** Enforces architectural rules by scanning the Abstract Syntax Tree (AST) of the `.py` source code.
*   **Passes when:** Core modules only use allowed libraries, isolate File I/O, and preserve the unidirectional dependency graph.
*   **Fails when:** A developer accidentally imports `time`, `random`, or `openai` into the core engine, or imports NetworkX outside `curriculum/graph.py`.

### `test_eval_checks.py`
*   **What it tests:** Independent verification of curriculum prerequisites, daily study budgets, and activity duplication.
*   **Passes when:** Audit catches out-of-order hand-built schedules and confirms engine plans have zero violations.

### `test_sim.py`
*   **What it tests:** Key-seeded 2PL IRT simulator, paired noise isolation, and memory retention dynamics.
*   **Passes when:** Seed determinism and power-law memory decay match analytical expectations.

### `test_arms.py`
*   **What it tests:** Closed-loop episode simulation across 4 planner arms (`adapt`, `no_review`, `no_replan`, `static`).
*   **Passes when:** `adapt` maintains 0 prerequisite and 0 budget violations across all scenarios.

### `test_diag_eval.py`
*   **What it tests:** Matched-budget diagnostic evaluation and hyperparameter tuning grid.
*   **Passes when:** Evaluates error metrics across matched budgets and runs grid search over $(h_{\text{stop}}, \text{concept\_cap}, n_{\text{max}})$.

### `test_stats.py`
*   **What it tests:** Standard library statistics (Brier calibration score, ROC-AUC, paired bootstrap 95% confidence intervals, and trace explanation coverage).
*   **Passes when:** Metrics match mathematical ground truths and coverage is strictly 1.0 for adaptive plans.

### `test_evaluation.py` (TC8.1)
*   **What it tests:** Strict byte-identical reproducibility of evaluation runs across identical seeds.
*   **Passes when:** Two consecutive runs produce bitwise identical JSON results and confirm zero constraint violations.

### `test_replan_frontier.py` (TC8.2)
*   **What it tests:** Frontier replanning via caller-owned `WorkloadCache` against full recomputation.
*   **Passes when:** `plan_full == plan_front` holds bitwise across all curricula, budgets, and 50 random disruption event sequences.

### `test_quickstart.py`
*   **What it tests:** Execution of `examples/api_quickstart.py`.
*   **Passes when:** Script runs cleanly from repository root with exit code 0.

