# AdaptEngine

**A deterministic adaptive learning, diagnostic assessment, and personalized path-planning engine.**

## Context & Problem

Learners differ in prior knowledge, target competencies, deadlines, and daily time budgets. A static course sequence cannot simultaneously serve a beginner with 10 minutes a day and an experienced learner needing a quick refresher.

**AdaptEngine** addresses this challenge by:
1. Estimating per-concept mastery with a Bayesian Knowledge Tracing (BKT) model.
2. Holding curriculum prerequisites strictly as a Directed Acyclic Graph (DAG).
3. Planning day-by-day study schedules within strict time budgets (5, 10, 15, or 30 minutes).
4. Explaining every pedagogical decision without requiring invasive learner telemetry.

> **Notice on Heuristic Parameters:** Mathematical parameters ($p_0 = 0.20, \theta = 0.85, T_*$, guess/slip coefficients, and activity difficulties) are **synthetic heuristics** for prototype verification and algorithm testing, not empirically fitted parameters.

---

## Project Milestones

*   **[M1] Curriculum & Learner-State Foundation:** Strictly validated DAG representation with NetworkX, cycle detection, review gates, immutable state, and Shannon entropy uncertainty tracking. *(Implemented & Hardened in W3)*
*   **[M2] Short Adaptive Diagnostic:** Bounded adaptive diagnostic selecting exercises via Expected Information Gain (EIG), subject to per-concept and global caps, entropy stopping, and descendant pruning. *(Implemented in W3)*
*   **[M4] Online Mastery Update & Difficulty Policy:** Discrete Bayesian Knowledge Tracing updates with pinned pyBKT adapter and next-exercise difficulty policy targeting $P_c \approx 0.75$ with D10 tie-breaking. *(Implemented in W3, Policy in W4)*
*   **[M3] Time-Budgeted Path Planning:** Prerequisite-valid day-by-day schedules with feasibility bounds and exact bin-packing oracle. *(Implemented in W4)*
*   **[M5] Spaced Review & Remediation:** Priority scheduling balancing forgetting decay risk against new content under a shared budget, automatic remediation repeat lessons. *(Implemented in W5)*
*   **[M6] Dynamic Replanning:** Pure replanning on missed days, failed assessments, deadline changes, and budget changes without losing or duplicating work. *(Implemented in W5)*
*   **[M7] Explainability & Constraint Traces:** Machine-readable reasons attributing every inclusion and omission to state and policy scores, pure JSON plan serialization with config hash. *(Implemented in W5)*
*   **[M8] Comparative Evaluation:** Benchmarking diagnostic accuracy and planning feasibility against frozen baselines on paired simulation workloads. *(Planned, W6)*

---

## Architecture & Documentation

All technical specifications are documented under `docs/`:
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — System architecture, layering rules, and data models.
- [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) — Complete API and function reference.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — Architectural and pedagogical decision records (D1–D30).
- [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) — Authoritative verification matrix (TC1.1–TC8.2).
- [`docs/MASTERY_MODEL.md`](docs/MASTERY_MODEL.md) — Equations, reference constants, and evidence semantics.
- [`docs/DIAGNOSTIC.md`](docs/DIAGNOSTIC.md) — M2 adaptive diagnostic specification.
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — Roadmap, risks, and fallbacks.
- [`docs/EVALUATION_PROTOCOL.md`](docs/EVALUATION_PROTOCOL.md) — Planned M8 comparative evaluation protocol.
- [`docs/TECHNICAL_FEASIBILITY.md`](docs/TECHNICAL_FEASIBILITY.md) — Feasibility argument and constraints.
- [`docs/reuse_inventory.md`](docs/reuse_inventory.md) — Third-party library inventory.

---

## Installation & Setup

Requires Python 3.10+ (tested on Python 3.11).

```bash
# Clone repository
git clone https://github.com/vhemanth06/AdaptEngine.git
cd AdaptEngine

# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies and local package in editable mode
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

---

## Developer CLI Guide

AdaptEngine provides a comprehensive, deterministic command-line interface (`adaptengine` or `python -m adaptengine`) designed for curriculum validation, learner session management, Bayesian Knowledge Tracing (BKT) updates, and personalized study path planning.

---

### 1. Invocation & Overview

After installing the package in editable mode (`pip install -e .`), you can invoke the CLI directly:

```bash
adaptengine <command> [options]
```

Or execute it via the Python module runner:

```bash
python -m adaptengine <command> [options]
```

To view global help or subcommand options:

```bash
adaptengine --help
adaptengine <command> --help
```

---

### 2. Core Concepts & File Schemas

To use AdaptEngine effectively, developers interact with four primary file types:

| File Type | CLI Flag | Description |
|:---|:---|:---|
| **Curriculum DAG** | `--curriculum <path.json>` | Strict Directed Acyclic Graph defining learning concepts and prerequisite edges. Enforces cycle detection and root reachability. |
| **Activities Catalog** | `--activities <path.json>` | Catalog of learning activities: Lessons (`L-*`), Exercises (`E-*`), and Assessments (`A-*`) with target concept, duration in minutes, and difficulty parameters. |
| **Review Manifest** | `--manifest <path.json>` | SHA-256 review gate verifying cryptographic authenticity of educational content. Pass `--allow-unreviewed` during content authoring to bypass. |
| **Learner Snapshot** | `--snapshot <path.json>` | Single canonical JSON state combining concept mastery probabilities ($p$), Shannon entropy uncertainties ($H$), append-only event logs, and active planning context. Written via atomic rename. |

---

### 3. Command Reference Cheat Sheet

| Command | Purpose | Key Options |
|:---|:---|:---|
| `validate` | Validates DAG acyclicity, schema integrity, and review manifest. | `--curriculum`, `--activities`, `[--manifest]`, `[--allow-unreviewed]` |
| `show` | Displays concepts, prerequisites, root concepts, and topological order. | `--curriculum`, `[--activities]`, `[--allow-unreviewed]` |
| `init-learner` | Initializes a fresh learner profile and canonical session snapshot. | `--curriculum`, `--snapshot`, `[--goal]`, `[--deadline]`, `[--budget]` |
| `plan` | Generates a prerequisite-valid, time-budgeted daily study schedule. | `--curriculum`, `--activities`, `--snapshot` (or `--learner`), `[--goal]`, `[--deadline]`, `[--budget]`, `[--json]`, `[--model]` |
| `update` | Records activity completion, updates BKT mastery, and saves snapshot. | `--curriculum`, `--activities`, `--snapshot`, `--activity`, `--day`, `[--response]`, `[--attempt-id]`, `[--model]` |
| `missed-day` | Records a missed study day and triggers spaced forgetting decay. | `--curriculum`, `--activities`, `--snapshot`, `--day`, `[--attempt-id]` |
| `failed-assessment`| Records a failed assessment and schedules targeted remediation. | `--curriculum`, `--activities`, `--snapshot`, `--activity`, `--day`, `[--attempt-id]` |
| `change-deadline` | Updates the learner's target completion deadline day in the snapshot. | `--curriculum`, `--activities`, `--snapshot`, `--day`, `--new-deadline` |
| `change-budget` | Updates daily study time budget (5, 10, 15, or 30 min) in the snapshot. | `--curriculum`, `--activities`, `--snapshot`, `--day`, `--new-budget` |
| `replan` | Dynamically replans schedule from current day without duplicating work. | `--curriculum`, `--activities`, `--snapshot`, `[--json]`, `[--model]` |
| `import-legacy` | Converts legacy separate learner state and log files into a unified snapshot. | `--curriculum`, `--activities`, `--learner`, `--log`, `--out-snapshot` |
| `export-legacy` | Exports a canonical snapshot into separate legacy learner and log files. | `--curriculum`, `--activities`, `--snapshot`, `--out-learner`, `--out-log` |

---

### 4. End-to-End Developer Walkthrough

This walkthrough demonstrates the complete lifecycle of an adaptive learning session using the bundled 4-node curriculum dataset.

#### Step 1: Validate Curriculum & Activities
Verify that the curriculum graph is acyclic, all activity concept references exist, durations are strictly positive, and files match the review gate manifest:

```bash
adaptengine validate \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json
```
**Output:**
```text
OK: 4 concepts, 20 activities (reviewed)
```

> **Authoring Tip:** When creating or testing new curriculum files without updating `data/review_manifest.json`, add `--allow-unreviewed` to bypass the cryptographic check.

#### Step 2: Inspect DAG Structure & Prerequisites
Inspect the curriculum structure, identifying root entry concepts, prerequisites, and valid topological learning orders:

```bash
adaptengine show --curriculum data/curriculum/curriculum_4node.json
```
**Output:**
```text
Concepts: ('C1', 'C2', 'C3', 'C4')
Prerequisites: {'C1': (), 'C2': (), 'C3': ('C1', 'C2'), 'C4': ('C3',)}
Roots: ('C1', 'C2')
Topological Order: ('C1', 'C2', 'C3', 'C4')
```

#### Step 3: Initialize a Learner Session Snapshot
Create a new learner session snapshot (`learner_session.json`). This initializes cold-start mastery priors ($p_0 = 0.20$), maximum Shannon uncertainty ($H = 0.7219$ bits), an empty event log, and embeds the target goal, deadline, and daily study budget:

```bash
adaptengine init-learner \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json \
    --goal C4 \
    --deadline 5 \
    --budget 15
```
**Output:**
```text
Created canonical snapshot file learner_session.json
```

#### Step 4: Generate a Study Plan
Compute a deterministic, time-budgeted study plan toward goal concept `C4` (15 minutes per day, deadline Day 5):

```bash
adaptengine plan \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json
```
**Output:**
```text
Status: FEASIBLE
Reason: GREEDY_FEASIBLE
Schedule (2 days):
  Day 1 (12 min):
    - L-C1 (4 min)
    - E-C1-0.2 (1 min)
    - E-C1-0.4 (1 min)
    - L-C2 (4 min)
    - E-C2-0.2 (1 min)
    - E-C2-0.4 (1 min)
  Day 2 (14 min):
    - L-C3 (5 min)
    - E-C3-0.2 (1 min)
    - E-C3-0.4 (1 min)
    - L-C4 (5 min)
    - E-C4-0.2 (1 min)
    - E-C4-0.4 (1 min)
```

##### Structured JSON Output for Backend Integration
Pass `--json` to output machine-readable plan objects with the exact configuration hash and decision audit trace:

```bash
adaptengine plan \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json \
    --json
```
**Output Structure:**
```json
{
  "config_hash": "a26889cc67a002b1d206275e8337349d5563b5845e75fb42dccb6a19221f41e5",
  "status": "FEASIBLE",
  "reason": "GREEDY_FEASIBLE",
  "shortfall_days": 0,
  "options": [],
  "days": [
    {
      "day": 1,
      "activities": ["L-C1", "E-C1-0.2", "E-C1-0.4", "L-C2", "E-C2-0.2", "E-C2-0.4"],
      "duration": 12
    },
    {
      "day": 2,
      "activities": ["L-C3", "E-C3-0.2", "E-C3-0.4", "L-C4", "E-C4-0.2", "E-C4-0.4"],
      "duration": 14
    }
  ],
  "trace": [
    {
      "decision": "GREEDY_DAY_PACK",
      "day": 1,
      "duration": 12,
      "activities": ["L-C1", "E-C1-0.2", "E-C1-0.4", "L-C2", "E-C2-0.2", "E-C2-0.4"]
    }
  ]
}
```

##### Handling Infeasible Schedules
If a learner sets an impossible deadline (e.g. `--deadline 1` with a 10 min/day budget for 26 minutes of coursework), the engine exits with code `1`, computes the exact shortfall, and returns actionable recommendations:

```bash
adaptengine plan \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --learner data/learner_novice.json \
    --goal C4 \
    --deadline 1 \
    --budget 10
```
**Output:**
```text
Status: INFEASIBLE
Reason: INSUFFICIENT_TIME_BUDGET
Shortfall: 2 days
Options:
  - Increase daily budget to 15 min (requires 2 days)
  - Increase daily budget to 30 min (fits in 1 days)
  - Extend deadline by at least 2 days to day 3
```

#### Step 5: Record Activity Completions & Update Mastery
As the learner completes assigned activities, record each interaction in the canonical snapshot.

**1. Recording a Lesson:**
Completing lesson `L-C1` shifts the prior belief via $T_{\text{lesson}} = 0.20$ without requiring correctness feedback:
```bash
adaptengine update \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json \
    --activity L-C1 \
    --day 1 \
    --attempt-id L-C1-d1-1
```
**Output:**
```text
C1: p 0.2000 -> 0.3600, H 0.7219 -> 0.9427
```

**2. Recording an Exercise Attempt:**
Completing exercise `E-C1-0.2` with an answer updates mastery via Bayesian inference:
```bash
adaptengine update \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json \
    --activity E-C1-0.2 \
    --response correct \
    --day 1 \
    --attempt-id E-C1-0.2-d1-2
```
**Output:**
```text
C1: p 0.3600 -> 0.6558, H 0.9427 -> 0.9298
```
> **Idempotency Guarantee:** Passing `--attempt-id` guarantees that replaying or retrying an event will not double-update learner mastery or corrupt logs.

#### Step 6: Handle Real-World Lifecycle Events
AdaptEngine tracks real-world events that perturb learning timelines:

**1. Recording a Missed Study Day:**
If the learner skips Day 2, record a missed day. The engine advances the timeline and applies exponential forgetting decay ($R(t) = e^{-\lambda \Delta t}$) to mastered concepts:
```bash
adaptengine missed-day \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json \
    --day 2
```
**Output:**
```text
Recorded MISSED event for day 2 in learner_session.json
```

**2. Recording a Failed Assessment:**
If the learner fails an end-of-concept assessment or diagnostic quiz, record the failure. The engine updates mastery and marks the concept for immediate remediation:
```bash
adaptengine failed-assessment \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json \
    --activity E-C1-0.8 \
    --day 2
```
**Output:**
```text
Recorded FAILED_ASSESSMENT for E-C1-0.8 on day 2
```

**3. Adjusting Deadline or Budget:**
Learners can adapt their pacing mid-stream:
```bash
# Extend the deadline to Day 7
adaptengine change-deadline \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json \
    --day 2 \
    --new-deadline 7

# Adjust daily study budget to 10 minutes
adaptengine change-budget \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json \
    --day 2 \
    --new-budget 10
```

#### Step 7: Dynamic Replanning
When disruptions occur, generate a fresh plan from the current day forward. Replanning reads directly from the canonical snapshot, accounts for all completed activities (preventing duplicate assignments), prioritizes remediation lessons for failed concepts, injects spaced reviews for decayed knowledge, and repacks the remaining horizon:

```bash
adaptengine replan \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json
```
**Output:**
```text
Status: FEASIBLE
Reason: GREEDY_FEASIBLE
Schedule (4 days):
  Day 3 (10 min):
    - L-C1 (4 min)
    - E-C1-0.4 (1 min)
    - L-C2 (4 min)
    - E-C2-0.2 (1 min)
  Day 4 (7 min):
    - E-C2-0.4 (1 min)
    - L-C3 (5 min)
    - E-C3-0.2 (1 min)
  Day 5 (7 min):
    - E-C3-0.4 (1 min)
    - L-C4 (5 min)
    - E-C4-0.2 (1 min)
  Day 6 (1 min):
    - E-C4-0.4 (1 min)
```

#### Step 8: Legacy File Migration (Optional)
If your systems currently store learner state and execution logs in separate files, AdaptEngine provides bi-directional migration commands:

**Import separate files into a unified snapshot:**
```bash
adaptengine import-legacy \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --learner data/learner_novice.json \
    --log legacy_log.json \
    --out-snapshot imported_snapshot.json \
    --goal C4 --deadline 10 --budget 15
```

**Export a unified snapshot into separate files:**
```bash
adaptengine export-legacy \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot learner_session.json \
    --out-learner exported_learner.json \
    --out-log exported_log.json
```

---

### 5. Advanced Flags & Modeling Options

#### Selecting Mastery Inference Engines (`--model`)
Subcommands `plan`, `replan`, `update`, `missed-day`, and `failed-assessment` support the `--model` flag:
- `--model custombkt` *(Default)*: Uses AdaptEngine's continuous analytical Bayesian Knowledge Tracing engine. Fast, numerically exact, with closed-form entropy tracking.
- `--model pybkt`: Delegates mastery updates to the pinned `pyBKT` library adapter. Useful for cross-evaluating against research baselines.

#### Content Integrity Bypass (`--allow-unreviewed`)
By default, AdaptEngine requires curriculum and activities files to be hashed and registered in `data/review_manifest.json`. During local content development and curriculum authoring:
```bash
adaptengine validate --curriculum draft_dag.json --activities draft_act.json --allow-unreviewed
```

#### Idempotency Keys (`--attempt-id`)
In network environments where API calls may retry, include `--attempt-id <unique-uuid>`. AdaptEngine checks `seen_attempt_ids` in learner state; identical attempt IDs are treated as safe no-ops without double-crediting mastery or duplicate log entries.

---

### 6. Process Exit Codes

AdaptEngine adheres to standard UNIX exit code conventions to facilitate integration with automated scripts, pipelines, and web backends:

| Exit Code | Meaning | Description |
|:---:|:---|:---|
| **`0`** | **Success / Feasible** | Command completed successfully, or `plan`/`replan` generated a feasible schedule within budget and deadline. |
| **`1`** | **Infeasible Plan** | `plan` or `replan` completed analysis but verified the curriculum cannot fit within the available days and daily budget. Explanatory options and shortfall are printed. |
| **`2`** | **Validation / User Error** | Input validation failure (e.g. cycle detected in DAG, missing required arguments, file not found, unreviewed file without `--allow-unreviewed`). |
| **`3`** | **Unknown Feasibility** | Branch-and-bound search exceeded computational bounds without proving feasibility or infeasibility. |

---

## Verification & Acceptance Runners

To run unit and integration tests, lint checks, formatting, and coverage checks:

```bash
make check
```

To run the Week 5 standalone acceptance runner (spaced review, remediation, replanning, trace contracts, evidence bundle):

```bash
make w5
# Or execute directly:
python scripts/run_w5.py
```

To run the Week 4 standalone acceptance runner (all W4 test cases, determinism, oracle, and evidence bundle generation):

```bash
make w4
# Or execute directly:
python scripts/run_w4.py
```

To run the Week 3 standalone acceptance runner:

```bash
make w3
# Or execute directly:
python scripts/run_w3.py
```