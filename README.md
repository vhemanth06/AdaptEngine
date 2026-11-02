# AdaptEngine

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-89.9%25-brightgreen.svg)](docs/TEST_SUITE.md)
[![Tests](https://img.shields.io/badge/tests-171%20passed-success.svg)](docs/TEST_SUITE.md)
[![Verification](https://img.shields.io/badge/acceptance-23%2F23%20TCs%20Verified-brightgreen.svg)](docs/TRACEABILITY.md)
[![Architecture](https://img.shields.io/badge/architecture-strictly%20layered-blueviolet.svg)](docs/ARCHITECTURE.md)
[![Course](https://img.shields.io/badge/project-CS5903%20Group%2015-orange.svg)](#)

> **A deterministic, mathematically grounded adaptive learning, diagnostic assessment, and personalized path-planning engine.**

---

## Context & Core Principles

Learners differ significantly in prior knowledge, target competencies, deadlines, and daily time availability. Static, one-size-fits-all curriculum sequences cannot simultaneously serve a novice with 10 minutes a day and an advanced learner needing an accelerated path.

**AdaptEngine** resolves this by operating as a stateless, deterministic computational core:
1. **Bayesian Knowledge Tracing (BKT):** Exact closed-form Bayesian probability updating ($p_c$) combined with Shannon entropy uncertainty quantification ($H_c = -p\log_2 p - (1-p)\log_2(1-p)$).
2. **Strict Curriculum DAG Invariants:** Graph-theoretic prerequisite modeling (NetworkX) with cycle detection, transitive reachability, and cryptographic SHA-256 review manifests.
3. **Budget-Constrained Path Planning:** Day-by-day greedy bin-packing with exact integer feasibility bounds and an exact oracle fallback to guarantee strict time boundaries (5, 10, 15, or 30 minutes/day).
4. **Dynamic Rescheduling & Spaced Review:** Priority scheduling balancing forgetting decay ($R(\Delta t) = 2^{-\Delta t / h}$) against new prerequisites, with zero duplicate assignments.
5. **Frontier Replanning:** Pure, memoized workload projection via caller-owned caches (`WorkloadCache`) yielding bitwise identical decisions to full recomputation with measured latency gains.
6. **Full Auditability & Determinism:** Every activity selection, omission, and deferral emits machine-readable explanatory decision traces. Identical seeds guarantee byte-identical outputs across runs.

> **Notice on Prototype Parameters:** Mathematical parameters ($p_0 = 0.20, \theta = 0.85, T_*$, guess/slip coefficients, and activity difficulties) serve as **synthetic heuristics** for prototype verification and algorithm testing, not empirically fitted parameters.

---

## Architectural Layering

AdaptEngine enforces a strict unidirectional dependency rule: **a layer imports only from layers to its left.** Subsystems are isolated, stateless, and fully reproducible.

```text
┌────────────────────────────────────────────────────────────────────────────────┐
│                           CLI Tier (adaptengine.cli)                           │
│                      Pure argument parsing and stdout/JSON                     │
└───────────────────────────────────────┬────────────────────────────────────────┘
                                        │ (calls into)
┌───────────────────────────────────────▼────────────────────────────────────────┐
│                          Application & Engine Facade                           │
│                  (adaptengine.api.Engine, canonical session)                   │
└───────┬───────────────────────────────┬────────────────────────────────┬───────┘
        │                               │                                │
┌───────▼───────────────┐ ┌─────────────▼──────────────┐ ┌───────────────▼───────┐
│ Diagnostic Module(M2) │ │  Path Planner Module (M3)  │ │ Spaced Review & Decay │
│ Expected Info Gain    │ │ Greedy Schedule & Feasible │ │  Remediation Lessons  │
│ Entropy Stop & Pruning│ │   Bin-Packing Oracle (M4)  │ │      (Module M5)      │
└───────┬───────────────┘ └─────────────┬──────────────┘ └───────────────┬───────┘
        │                               │                                │
        └───────────────────────────────┼────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼────────────────────────────────────────┐
│                     Dynamic Replanner & Frontier Cache                         │
│             (adaptengine.replanner.replan, WorkloadCache - M6, M8)             │
└───────────────────────────────────────┬────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼────────────────────────────────────────┐
│                   Learner State & Knowledge Tracing Tier                       │
│           (adaptengine.learner.mastery, pyBKT adapter, log, state)             │
└───────────────────────────────────────┬────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼────────────────────────────────────────┐
│                    Curriculum Graph & Topological Modeling                     │
│                  (adaptengine.curriculum.graph, NetworkX DAG)                  │
└───────────────────────────────────────┬────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼────────────────────────────────────────┐
│                         Core Schemas, Invariants & Config                      │
│                  (schema.py, config.py, audit.py, review_gate)                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Milestones

| Milestone | Scope & Deliverables | Implemented | Verification Gate | Status |
|:---|:---|:---:|:---:|:---:|
| **[M1] Curriculum & State** | Directed Acyclic Graph (DAG), cycle detection, cryptographic review gates, immutable learner state, Shannon entropy. | Week 3 | TC1.1–TC1.3 | **Verified** |
| **[M2] Adaptive Diagnostic** | Bounded diagnostic selecting items via Expected Information Gain (EIG), entropy stopping ($H \le 0.35$), concept caps ($k \le 2$). | Week 3 | TC2.1–TC2.2 | **Verified** |
| **[M3] Path Planning** | Prerequisite-valid daily study schedules, daily budget packing (5, 10, 15, 30 min), feasibility bounds, exact oracle. | Week 4 | TC3.1–TC3.4 | **Verified** |
| **[M4] Online Updates** | Discrete Bayesian Knowledge Tracing updates, next-exercise difficulty policy targeting $P_c \approx 0.75$, pyBKT adapter parity. | Week 3–4 | TC4.1–TC4.4 | **Verified** |
| **[M5] Spaced Review** | Half-life retention decay ($2^{-\Delta t / h}$), priority-ranked review under shared budget, automatic remediation lessons. | Week 5 | TC5.1–TC5.2 | **Verified** |
| **[M6] Dynamic Replanning** | Event-driven replanning on missed days, failed assessments, deadline/budget shifts without duplicate or lost work. | Week 5 | TC6.1–TC6.3 | **Verified** |
| **[M7] Explainability** | Machine-readable decision traces (`SELECTED`, `DEFERRED`, `OMITTED`, `ORACLE_ASSIGNED`), pure JSON serialization with SHA-256 config hash. | Week 5 | TC7.1–TC7.2 | **Verified** |
| **[M8] Evaluation & Cache** | Paired closed-loop IRT simulation (4 profiles, 4 arms), matched-budget diagnostic audit, memoized `WorkloadCache` (TC8.1, TC8.2). | Week 6 | TC8.1–TC8.2 | **Verified** |

---

## Technical Documentation

All specifications, mathematical proofs, and architectural records are located under `docs/`:

| Document | Description |
|:---|:---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture, layering rules, class diagrams, and structural constraints. |
| [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) | Complete Python library reference, dataclass schemas, and engine method signatures. |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Architectural and pedagogical decision records (**D1 through D40**). |
| [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) | Authoritative requirements-to-tests verification matrix (**TC1.1 through TC8.2**). |
| [`docs/MASTERY_MODEL.md`](docs/MASTERY_MODEL.md) | Mathematical equations, BKT formulation, parameter derivations, and entropy metrics. |
| [`docs/DIAGNOSTIC.md`](docs/DIAGNOSTIC.md) | Detailed specification of the M2 Expected Information Gain (EIG) diagnostic algorithm. |
| [`docs/EVALUATION_PROTOCOL.md`](docs/EVALUATION_PROTOCOL.md) | Closed-loop simulation protocol, synthetic IRT learner profiles, and baseline arms. |
| [`docs/WEEK6_REPORT_NOTES.md`](docs/WEEK6_REPORT_NOTES.md) | Week 6 empirical findings, benchmark tables, defect analyses, and verification receipts. |
| [`docs/TEST_SUITE.md`](docs/TEST_SUITE.md) | Detailed test suite organization, categorization, fixtures, and execution guide. |
| [`docs/verification_guide.md`](docs/verification_guide.md) | Comprehensive step-by-step verification checklist and script manual. |
| [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | Milestone roadmap, weekly delivery schedules, risk matrix, and contingency plans. |
| [`docs/TECHNICAL_FEASIBILITY.md`](docs/TECHNICAL_FEASIBILITY.md) | Algorithmic feasibility analyses, complexity bounds, and bin-packing guarantees. |
| [`docs/reuse_inventory.md`](docs/reuse_inventory.md) | Inventory of third-party libraries and runtime dependencies. |

---

## Quickstart

Run the complete pipeline end-to-end in six commands (install, validate, init-learner, plan, update, replan):

```bash
# 1. Install package and dependencies
pip install -e ".[dev]"

# 2. Validate curriculum DAG and activity catalog
python -m adaptengine validate --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json

# 3. Initialize fresh learner snapshot
python -m adaptengine init-learner --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot snapshot.json --goal C4 --deadline 5 --budget 15

# 4. Generate initial adaptive plan
python -m adaptengine plan --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot snapshot.json

# 5. Record activity completion
python -m adaptengine update --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot snapshot.json --activity L-C1 --day 1

# 6. Replan from updated state and log
python -m adaptengine replan --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot snapshot.json
```

**Real output:**
```text
$ python -m adaptengine validate --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json
OK: 4 concepts, 20 activities (reviewed)

$ python -m adaptengine init-learner --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot snapshot.json --goal C4 --deadline 5 --budget 15
Created canonical snapshot file snapshot.json

$ python -m adaptengine plan --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot snapshot.json
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

$ python -m adaptengine update --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot snapshot.json --activity L-C1 --day 1
C1: p 0.2000 -> 0.3600, H 0.7219 -> 0.9427

$ python -m adaptengine replan --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot snapshot.json
Status: FEASIBLE
Reason: GREEDY_FEASIBLE
Schedule (2 days):
  Day 1 (15 min):
    - E-C1-0.2 (1 min)
    - E-C1-0.4 (1 min)
    - L-C2 (4 min)
    - E-C2-0.2 (1 min)
    - E-C2-0.4 (1 min)
    - L-C3 (5 min)
    - E-C3-0.2 (1 min)
    - E-C3-0.4 (1 min)
  Day 2 (7 min):
    - L-C4 (5 min)
    - E-C4-0.2 (1 min)
    - E-C4-0.4 (1 min)
```

---

### Python API Quickstart

Developers embedding AdaptEngine directly in Python services, workers, or notebooks interact with the functional, pure `Engine` facade:

```python
from adaptengine.api import Engine
from adaptengine.core.schema import Event, EventType, PlanContext
from adaptengine.learner.state import ExecutionLog
from adaptengine.planner.plan import serialize_plan
from adaptengine.planner.workload import WorkloadCache

# 1. Initialize Engine from validated curriculum and activity catalog
engine = Engine.from_files(
    "data/curriculum/curriculum_4node.json",
    "data/curriculum/activities_4node.json",
)

# 2. Initialize fresh learner state and execution log
state, log = engine.init_learner(), ExecutionLog()
ctx = PlanContext(goal="C4", deadline_day=5, budget=15)

# 3. Generate initial adaptive plan
plan = engine.plan(state, ctx)
print(f"Plan status: {plan.status.value}, Days: {len(plan.days)}")

# 4. Record execution events (completed lesson, missed study day)
first_act = plan.days[0].activities[0]
first_dur = engine.activities[first_act].duration
state, log = engine.record(
    state,
    log,
    Event(
        day=1,
        kind=EventType.COMPLETED,
        activity_id=first_act,
        minutes_elapsed=first_dur,
    ),
)
state, log = engine.record(state, log, Event(day=2, kind=EventType.MISSED))

# 5. Dynamic replanning with caller-owned frontier workload cache
cache = WorkloadCache()
revised_plan = engine.replan(state, log, ctx, workload_cache=cache)
print(f"Revised plan status: {revised_plan.status.value}, Days: {len(revised_plan.days)}")
print("Config hash:", serialize_plan(revised_plan, engine.config)["config_hash"][:12])
```

Run the standalone executable script:
```bash
python examples/api_quickstart.py
```

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
pip install -e ".[dev]"

# Optional: install pyBKT adapter dependencies
pip install -e ".[dev,pybkt]"
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
If the learner skips Day 2, record a missed day. The engine advances the timeline and applies half-life recall decay ($R(\Delta t) = 2^{-\Delta t / h}$, D23) to practiced concepts:
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

#### Frontier Replanning & Cache Memoization (`WorkloadCache`)
For high-throughput web platforms or microservices, student timeline perturbations (e.g., logging a completed activity, missing a study day, or failing an assessment) often affect only a single concept's state. Recomputing workload projections across the entire curriculum DAG from scratch introduces redundant work.

AdaptEngine provides **Frontier Replanning** (TC8.2):
- **Caller-Owned Cache:** The caller instantiates and passes an explicit `workload_cache = WorkloadCache()` instance to `engine.replan(...)`. The `Engine` instance itself remains purely functional and stateless.
- **Equivalence by Construction:** Cached entries memoize per-concept projections indexed by `(concept, concept_state, completed_concept_activities, config_hash, model_type)`. The planner re-runs the global DAG schedule identically, guaranteeing bitwise-identical `Plan` objects and decision traces to full recomputation.
- **Measured Latency Speedups:**
  - **4-node curriculum:** **$1.33\times$ speedup** ($0.52\text{ ms} \to 0.39\text{ ms}$)
  - **8-node curriculum:** **$1.27\times$ speedup** ($1.01\text{ ms} \to 0.79\text{ ms}$)
  - **20-node synthetic DAG:** **$1.21\times$ speedup** ($3.30\text{ ms} \to 2.71\text{ ms}$)
  - **50-node synthetic DAG:** **$1.09\times$ speedup** ($18.94\text{ ms} \to 17.36\text{ ms}$)

#### Content Integrity Bypass (`--allow-unreviewed`)
By default, AdaptEngine requires curriculum and activities files to be hashed and registered in `data/review_manifest.json`. During local content development and curriculum authoring:
```bash
adaptengine validate --curriculum draft_dag.json --activities draft_act.json --allow-unreviewed
```

#### Idempotency Keys (`--attempt-id`)
In network environments where API calls may retry, include `--attempt-id <unique-uuid>`. AdaptEngine checks `seen_attempt_ids` in learner state; identical attempt IDs are treated as safe no-ops without double-crediting mastery or duplicate log entries.

---

### 6. Process Exit Codes

AdaptEngine adheres to standard UNIX exit code conventions to facilitate integration with automated scripts, CI/CD pipelines, and web backends:

| Exit Code | Meaning | Description |
|:---:|:---|:---|
| **`0`** | **Success / Feasible** | Command completed successfully, or `plan`/`replan` generated a feasible schedule within budget and deadline. |
| **`1`** | **Infeasible Plan** | `plan` or `replan` completed analysis but verified the curriculum cannot fit within the available days and daily budget. Explanatory options and shortfall are printed. |
| **`2`** | **Validation / User Error** | Input validation failure (e.g. cycle detected in DAG, missing required arguments, file not found, unreviewed file without `--allow-unreviewed`). Stderr contains a single-line message without tracebacks. |
| **`3`** | **Unknown Feasibility** | Branch-and-bound search exceeded computational bounds without proving feasibility or infeasibility. |

---

## Verification & Acceptance Runners

AdaptEngine provides comprehensive Makefile targets and standalone Python scripts for automated verification, regression gating, and reproducible evaluation:

```bash
# 1. Full Quality Gate: Ruff linting, formatting check, architecture layering, pytest + 84% coverage gate
make check

# 2. Week 6 Acceptance Runner: Milestone M8 evaluation determinism, frontier equivalence, violation audit, latency benchmark
make w6
# Or execute directly:
python scripts/run_w6.py

# 3. Week 5 Acceptance Runner: Spaced review decay, dynamic replanning, remediation, decision audit traces
make w5
# Or execute directly:
python scripts/run_w5.py

# 4. Week 4 Acceptance Runner: Time-budgeted path planning, bin-packing oracle, bounds proofs
make w4
# Or execute directly:
python scripts/run_w4.py

# 5. Week 3 Acceptance Runner: Curriculum DAG validation, EIG diagnostic, continuous BKT
make w3
# Or execute directly:
python scripts/run_w3.py

# 6. Evaluation Simulation (100-seed full run, bitwise identical output):
make eval

# 7. Quick Evaluation Simulation (10-seed fast run for CI):
make eval-quick

# 8. Clean Working-Tree Reproduction (isolated /tmp virtualenv verification):
bash scripts/verify_clean_checkout.sh
```

---

## Evaluation & Benchmark Highlights (Milestone M8)

The Week 6 evaluation benchmarks AdaptEngine across a paired, closed-loop 2PL Item Response Theory (IRT) simulation on a 50/50 seed split (50 tuning learners, 50 held-out learners) comparing four planning arms:
- **`adapt`:** Full dynamic replanning on disruption events + Bayesian mastery updates.
- **`no_review`:** Dynamic replanning with spaced review urgency disabled ($U_c = 0$).
- **`no_replan`:** Static initial schedule executed without rescheduling (dropped missed days).
- **`static`:** Fixed topological syllabus ignoring student state and daily capacity limits.

### 1. Robustness Under Real-World Disruptions (15 min/day Budget)

| Scenario | Metric | `adapt` | `no_review` | `no_replan` | `static` |
|:---|:---|:---:|:---:|:---:|:---:|
| **Calm** (No disruptions) | Goal Mastery Rate | 30.0% | 30.0% | 30.0% | 38.0%* |
| | Prerequisite Violations | **0** | **0** | **0** | **0** |
| | Budget Violations | **0** | **0** | **0** | **0** |
| | Trace Coverage | **100.0%** | **100.0%** | **100.0%** | 0.0% |
| **Missed Day** (Day 2 skipped) | Goal Mastery Rate | 30.0% | 30.0% | 18.0% | 38.0%* |
| | Prerequisite Violations | **0** | **0** | **0** | **600** |
| | Budget Violations | **0** | **0** | **0** | **0** |
| | Trace Coverage | **100.0%** | **100.0%** | **100.0%** | 0.0% |
| **Budget Drop** (15m $\to$ 10m) | Goal Mastery Rate | 30.0% | 30.0% | 30.0% | 38.0%* |
| | Prerequisite Violations | **0** | **0** | **0** | **0** |
| | Budget Violations | **0** | **0** | **100** | **200** |
| | Trace Coverage | **100.0%** | **100.0%** | **100.0%** | 0.0% |
| **Deadline Cut** (Cut by 1 day) | Goal Mastery Rate | 30.0% | 30.0% | 30.0% | 38.0%* |
| | Prerequisite Violations | **0** | **0** | **0** | **0** |
| | Budget Violations | **0** | **0** | **0** | **0** |
| | Trace Coverage | **100.0%** | **100.0%** | **100.0%** | 0.0% |

*\*Notice on Static Mastery:* The `static` baseline achieves a nominally higher mastery rate solely by executing all coursework regardless of constraints. Under `missed_day`, `static` incurs **600 prerequisite violations** (attempting advanced concepts without prerequisites). Under `budget_drop`, `static` incurs **200 budget overruns**. `adapt` guarantees **0 violations** while rescheduling safe learning paths.

### 2. Diagnostic Assessment Efficiency

| Diagnostic Mode | Items Administered | Question Burden vs Fixed-8 | MAE (Assessed Concepts) | Unassessed Concepts |
|:---|:---:|:---:|:---:|:---:|
| **Adaptive (EIG, M2)** | **2.96** | **-63.0%** | 0.3852 | 48.0% |
| **Fixed Order (Matched)** | 2.96 | -63.0% | 0.2555 | 31.5% |
| **Fixed Order (Full-8)** | 8.00 | Baseline | 0.2784 | 0.0% |

The M2 adaptive diagnostic reduces assessment burden by **63%** (averaging 2.96 items vs 8.0) while concentrating questions on unmastered concepts and halting early once entropy thresholds are satisfied.

---

## Acceptance Test Matrix (TC1.1–TC8.2)

AdaptEngine adheres to a rigorous, formal acceptance register of 23 test categories (**all 23 Verified**):

| Acceptance ID | Requirement Description | Verifying Test Suite | Status |
|:---:|:---|:---|:---:|
| **TC1.1** | DAG cycle detection and topological ordering | `tests/test_graph.py` | **Verified** |
| **TC1.2** | Immutable learner state and entropy tracking | `tests/test_state.py` | **Verified** |
| **TC1.3** | Cryptographic review manifest validation | `tests/test_review_gate.py` | **Verified** |
| **TC2.1** | Adaptive diagnostic stopping criteria and caps | `tests/test_diagnostic.py` | **Verified** |
| **TC2.2** | Expected Information Gain item selection | `tests/test_diagnostic.py` | **Verified** |
| **TC3.1** | Prerequisite-valid path schedule generation | `tests/test_planner.py` | **Verified** |
| **TC3.2** | Daily budget constraint satisfaction | `tests/test_planner.py` | **Verified** |
| **TC3.3** | Infeasibility detection and option reporting | `tests/test_planner.py` | **Verified** |
| **TC3.4** | Exact bin-packing oracle fallback | `tests/test_oracle.py` | **Verified** |
| **TC4.1** | Closed-form Bayesian Knowledge Tracing updates | `tests/test_mastery.py` | **Verified** |
| **TC4.2** | pyBKT adapter equivalence and parity | `tests/test_bkt_adapter.py` | **Verified** |
| **TC4.3** | Next-exercise difficulty targeting ($P_c \approx 0.75$) | `tests/test_policy.py` | **Verified** |
| **TC4.4** | Lesson completion prior shifting | `tests/test_mastery.py` | **Verified** |
| **TC5.1** | Half-life retention decay ($2^{-\Delta t / h}$) | `tests/test_review.py` | **Verified** |
| **TC5.2** | Spaced review prioritization under shared budget | `tests/test_review.py` | **Verified** |
| **TC6.1** | Dynamic replanning on missed days | `tests/test_replanner.py` | **Verified** |
| **TC6.2** | Targeted remediation for failed assessments | `tests/test_replanner.py` | **Verified** |
| **TC6.3** | Timeline adaptation on deadline/budget changes | `tests/test_replanner.py` | **Verified** |
| **TC7.1** | Machine-readable constraint and decision traces | `tests/test_traces.py` | **Verified** |
| **TC7.2** | Plan JSON serialization and SHA-256 config hash | `tests/test_traces.py` | **Verified** |
| **TC8.1** | Deterministic byte-identical evaluation reruns | `tests/test_evaluation.py` | **Verified** |
| **TC8.2** | Frontier replanning decision equivalence and latency | `tests/test_replan_frontier.py` | **Verified** |

---

## Architectural Guardrails & Enforced Rules

To ensure long-term maintainability, testability, and deterministic behavior, AdaptEngine enforces:
- **Layering Integrity:** Enforced by `tests/test_architecture.py`. Layers import only from layers to their left. `scripts/`, `experiments/`, and `examples/` are strictly isolated from `src/`.
- **Zero Hidden State:** The `Engine` instance is functional and stateless. All learner state, execution logs, and cache instances are caller-owned values passed explicitly.
- **Strict Determinism:** Identical inputs yield identical decisions and trace logs. No calls to `time`, `datetime`, or `random` exist under `src/adaptengine/`.
- **High Test Coverage:** Statement coverage is continuously enforced at $\ge 84\%$ (currently **89.94%**).

---

## Academic Project Information

- **Course:** CS5903: Systems Engineering for AI-Driven Applications
- **Group:** Group 15
- **Milestone:** Milestone M8 / Week 6 MVP Release (`v0.2.0-mvp`)
- **License:** Educational / Academic Use Only