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

---

## 2. Utility & Verification Scripts

### `experiments/run_smoke.py`
*   **What it does:** Runs a deterministic, hardcoded 6-step transactional trace of a student interacting with the engine.
*   **Command to check:** `python experiments/run_smoke.py`
*   **Pass/Fail:** It will pass and output a JSON stream of state changes. It will fail if the math in `mastery.py` has been tampered with or if the random seed causes non-determinism (which we designed the engine to avoid).

### `scripts/verify_clean_checkout.sh`
*   **What it does:** Proves the system works from scratch. It clones the git repo to `/tmp`, sets up a fresh virtual environment, installs dependencies, and runs all tests.
*   **Command to check:** `./scripts/verify_clean_checkout.sh`
*   **Pass/Fail:** Passes only if all dependencies are correctly listed in `requirements.txt` and all tests pass. Fails if local uncommitted files are secretly required to make the engine run.

### `scripts/record_review.py`
*   **What it does:** Computes the SHA-256 hash of a file and adds it to `data/review_manifest.json` as "reviewed content".
*   **Command to check:** `python scripts/record_review.py data/curriculum/curriculum_4node.json "John Doe"`

---

## 3. The Test Suite (`tests/`)

You can run the entire test suite and view coverage using:
`pytest -q --cov=adaptengine --cov-fail-under=80 --cov-report=term-missing`

Here is a breakdown of every test file, when it passes, and when it fails:

### `test_schema.py`
*   **What it tests:** Validates the strict Python dataclasses (`Concept`, `Activity`, `Event`).
*   **Passes when:** Probabilities and difficulties are clamped between `0.0` and `1.0`.
*   **Fails when:** A JSON file has a negative duration, missing IDs, or a difficulty of `1.5`.

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

### `test_state_session.py`
*   **What it tests:** State immutability and JSON persistence.
*   **Passes when:** `LearnerState` is successfully saved to disk and loaded back with identical values.
*   **Fails when:** Code attempts to mutate an existing state in-place (throws `TypeError`), ensuring states are strictly transactional.

### `test_api.py` & `test_cli.py`
*   **What it tests:** End-to-end integration of the CLI parsing and the API boundary (`Engine.record`).
*   **Passes when:** CLI commands exit with code `0` and print the expected output.
*   **Fails when:** Files are missing, arguments are malformed, or the curriculum throws validation errors. Exits with code `2`.

### `test_architecture.py`
*   **What it tests:** Enforces architectural rules by scanning the Abstract Syntax Tree (AST) of the `.py` source code.
*   **Passes when:** Core modules only use allowed libraries and isolate File I/O.
*   **Fails when:** A developer accidentally imports `time`, `random`, or `openai` into the core engine, or uses `open()` in an unapproved file.
