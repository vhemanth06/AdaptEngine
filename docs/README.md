# AdaptEngine documentation

AdaptEngine is a Python engine that diagnoses what a learner already knows across a prerequisite
graph of concepts, plans study day by day under a daily time budget and a deadline, and replans
after every answer or disruption without ever scheduling a concept before its prerequisites are
mastered. This folder has four parts: `concepts/` explains each idea with its maths, `reference/`
describes how the system is built and used, `project/` holds the live decision and traceability
records, and `archive/` keeps the project's history.

## Start here

- **New to the project:** [reference/ARCHITECTURE.md](reference/ARCHITECTURE.md), then
  [concepts/README.md](concepts/README.md).
- **Want to run or test it:** [reference/TESTING.md](reference/TESTING.md) and the root
  [README.md](../README.md).
- **Want the evidence:** [project/TRACEABILITY.md](project/TRACEABILITY.md) and
  [experiments/README.md](../experiments/README.md) (the final study).
- **Why it is built this way:** [project/DECISIONS.md](project/DECISIONS.md).

## `concepts/`

| File | Purpose |
|---|---|
| [README.md](concepts/README.md) | Reading order and the notation used by every concept file |
| [01_curriculum_graph.md](concepts/01_curriculum_graph.md) | Concepts, the prerequisite graph, knowledge states and the safety rule |
| [02_mastery_bkt.md](concepts/02_mastery_bkt.md) | The mastery belief: Bayesian Knowledge Tracing updates and the mastery rule |
| [03_item_models.md](concepts/03_item_models.md) | Item difficulty to guess and slip: the heuristic and the fitted profiles |
| [04_diagnostic_sweep.md](concepts/04_diagnostic_sweep.md) | The default diagnostic: information-gain sweep |
| [05_diagnostic_bisection.md](concepts/05_diagnostic_bisection.md) | The bisection diagnostic over knowledge states, and confirmation checks |
| [06_planning.md](concepts/06_planning.md) | Workload, priorities, greedy packing and feasibility |
| [07_cpsat.md](concepts/07_cpsat.md) | The CP-SAT and hybrid planners |
| [08_review_remediation.md](concepts/08_review_remediation.md) | Forgetting, spaced review and remediation |
| [09_replanning.md](concepts/09_replanning.md) | Events and replanning |
| [10_evaluation.md](concepts/10_evaluation.md) | Simulated learners, arms, scenarios and the safety audit |
| [11_study_statistics.md](concepts/11_study_statistics.md) | The statistics of the final study |

## `reference/`

| File | Purpose |
|---|---|
| [ARCHITECTURE.md](reference/ARCHITECTURE.md) | Modules, layering rules and dependency direction |
| [API_REFERENCE.md](reference/API_REFERENCE.md) | The public Python API and the data schemas |
| [TESTING.md](reference/TESTING.md) | Test layout, what each test file checks, and the commands to run them |
| [data_manifest.md](reference/data_manifest.md) | The bundled curricula and the external datasets, with checksums and cleaning rules |
| [reuse_inventory.md](reference/reuse_inventory.md) | Third-party libraries and what they are used for |

## `project/`

| File | Purpose |
|---|---|
| [DECISIONS.md](project/DECISIONS.md) | Every design decision (D1–D105) by topic, with status and the current settings |
| [TRACEABILITY.md](project/TRACEABILITY.md) | Requirements and test cases mapped to the tests and results that verify them |
| [AI_USE.md](project/AI_USE.md) | Record of AI assistance and model use in the project |
| [content_reviews/8node_x10_ai_review.md](project/content_reviews/8node_x10_ai_review.md) | Review record of the `8node_x10` curriculum content |

`figures/` holds the demo UI screenshots written by `make demo-figures`.

History (weekly submissions and notes, superseded specifications, old pre-registrations and
figures) is in [archive/README.md](archive/README.md).
