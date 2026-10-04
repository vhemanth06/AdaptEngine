# AdaptEngine

**An adaptive learning, diagnostic assessment, and personalized path-planning engine.**

## Context & Problem

Learners differ in prior knowledge, roles, target skills, deadlines, and daily time budgets. A static course order cannot simultaneously serve a beginner with 10 minutes a day and an experienced learner seeking only a short refresher. 

**AdaptEngine** solves this by estimating initial and evolving skill mastery, representing curriculum prerequisites as strict graphs, and generating time-budgeted learning plans. It adapts difficulty, schedules remediation and spaced review, and dynamically replans when the learner misses work or changes constraints—all while exposing exactly *why* a lesson was chosen without requiring private learner telemetry.

## Project Milestones

*   **[M1] Curriculum and Learner-State Model:** Concepts, lessons, exercises, durations, prerequisites, and mastery estimates are represented in a strictly validated, queryable DAG model with mathematical uncertainty tracking (BKT & Shannon Entropy).
*   **[M4] Online Mastery Update and Difficulty Adaptation (Partial):** Quiz/exercise evidence updates per-skill mastery transactionally using Bayesian Knowledge Tracing.
*   **[M2] Short Adaptive Diagnostic:** A bounded diagnostic providing calibrated initial skill estimates compared against fixed baselines. *(Planned)*
*   **[M3] Time-Budgeted Path Generation:** Generating prerequisite-valid day-by-day plans based on goals, deadlines, and daily budgets (e.g., 5/10/15 mins). *(Planned)*
*   **[M5] Spaced Review and Remediation:** Scheduling previously learned concepts for review according to forgetting risk and prerequisite importance. *(Planned)*
*   **[M6] Dynamic Replanning:** Valid revised plans triggered by missed days, failed assessments, or changed constraints. *(Planned)*
*   **[M7] Explainability and Constraints:** Tracing inclusions, omissions, and reviews to observable learner states and policy scores. *(Planned)*
*   **[M8] Comparative Evaluation:** Benchmarking diagnostic accuracy, path feasibility, and runtime against static/greedy baselines. *(Planned)*

## Installation

Requires Python 3.10+.

```bash
# Clone the repository
git clone https://github.com/vhemanth06/AdaptEngine.git
cd AdaptEngine

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies and the package
pip install -r requirements.txt
pip install -e .
```

## Quick Start (CLI)

The primary interface is the `adaptengine` CLI.

```bash
# 1. Validate a curriculum and its activities (DAG validation & SHA-256 Review Gates)
python -m adaptengine validate --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json

# 2. Initialize a new Learner Profile
python -m adaptengine init-learner --curriculum data/curriculum/curriculum_4node.json --out my_learner.json

# 3. Record a student's interaction and update their mastery using Bayes Theorem
python -m adaptengine update \
    --curriculum data/curriculum/curriculum_4node.json \
    --activities data/curriculum/activities_4node.json \
    --learner my_learner.json \
    --log my_log.json \
    --activity E-C1-0.6 \
    --response incorrect \
    --day 1 \
    --save
```

## Testing

The project maintains a strict >80% test coverage requirement. To run the suite:

```bash
pip install -r requirements-dev.txt
pytest -q --cov=adaptengine --cov-fail-under=80
```