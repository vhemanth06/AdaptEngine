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

## Quick Start (CLI)

The primary command-line interface is `adaptengine`:

```bash
# 1. Validate curriculum and activities (DAG acyclicity & SHA-256 review gate)
python -m adaptengine validate --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json

# 2. Initialize a new learner profile
python -m adaptengine init-learner --curriculum data/curriculum/curriculum_4node.json --out my_learner.json

# 3. Record an interaction and update mastery (Atomic snapshot protocol)
python -m adaptengine update \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --learner my_learner.json \
    --log my_log.json \
    --activity E-C1-0.6 \
    --response incorrect \
    --day 1 \
    --save

# 4. Generate a deterministic, time-budgeted study plan
python -m adaptengine plan \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --learner my_learner.json \
    --goal C4 \
    --deadline 5 \
    --budget 10

# 5. Dynamic replanning after missed days or constraint updates
python -m adaptengine replan \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --snapshot my_snapshot.json
```

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