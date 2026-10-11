# Graph Report - AdaptEngine  (2026-10-11)

## Corpus Check
- Corpus is ~8,000 words - fits in a single context window. You may not need a graph.

## Summary
- 175 nodes · 544 edges · 18 communities (6 shown, 12 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 85 edges (avg confidence: 0.95)
- Token cost: 5,300 input · 1,500 output

## Community Hubs (Navigation)
- Core Engine and State Immutability
- Curriculum DAG and Concept Schemas
- BKT Mastery and Uncertainty Estimation
- Error Handling and API Validation
- Test Fixtures and Review Gate Generation
- CLI Interface and CI Verification
- Architecture Rules and AST Linting
- Clean Checkout Verification Script
- Benchmark Datasets Manifest
- Package Definition
- Methodology and Decision Records
- Week 0 Milestones and Objectives
- Week 1 Baseline Validation Report

## God Nodes (most connected - your core abstractions)
1. `ValidationError` - 39 edges
2. `Engine` - 23 edges
3. `CurriculumGraph` - 21 edges
4. `Event` - 19 edges
5. `load_curriculum()` - 18 edges
6. `main()` - 17 edges
7. `Concept` - 17 edges
8. `load_activities()` - 15 edges
9. `EventType` - 14 edges
10. `entropy()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `AdaptEngine Core Architecture` --implements--> `Engine`  [INFERRED]
  docs/architecture.md → src/adaptengine/api.py
- `ADR-016: Curriculum Content SHA-256 Review Gate` --rationale_for--> `_check_review_gate()`  [EXTRACTED]
  records/ADR-016.md → src/adaptengine/curriculum/loader.py
- `AdaptEngine Project Overview` --references--> `Engine`  [EXTRACTED]
  README.md → src/adaptengine/api.py
- `CLI Verification Suite & Commands` --references--> `main()`  [EXTRACTED]
  docs/verification_guide.md → src/adaptengine/cli.py
- `Strict Core Schemas (Concept, Activity, Event)` --references--> `Concept`  [EXTRACTED]
  docs/schema.md → src/adaptengine/core/schema.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Engine Pipeline Core Components** — docs_architecture_engine, src_adaptengine_api_engine, src_adaptengine_curriculum_graph_curriculumgraph, src_adaptengine_learner_mastery_update_mastery [INFERRED 0.95]
- **Core Architectural Decision Records (ADRs)** — records_adr_001_bkt_choice, records_adr_002_dag_representation, records_adr_003_shannon_entropy, records_adr_004_state_immutability, records_adr_016_review_gate [EXTRACTED 1.00]

## Communities (18 total, 12 thin omitted)

### Community 0 - "Core Engine and State Immutability"
Cohesion: 0.15
Nodes (21): AdaptEngine Core Architecture, run_experiment(), AdaptEngine Project Overview, Engine, config_hash(), EngineConfig, Event, EventType (+13 more)

### Community 1 - "Curriculum DAG and Concept Schemas"
Cohesion: 0.13
Nodes (11): Curriculum Directed Acyclic Graph, Strict Core Schemas (Concept, Activity, Event), Milestones (M1-M8) to Test Cases (TC-01..12) Traceability, CycleError, Concept, CurriculumGraph, test_cycle_rejected(), test_self_loop_rejected() (+3 more)

### Community 2 - "BKT Mastery and Uncertainty Estimation"
Cohesion: 0.15
Nodes (19): Bayesian Knowledge Tracing (BKT), BKT Transition & Emission Equations, Shannon Entropy Uncertainty Metric, Week 2 Report: BKT Updates, Entropy & Review Gate, bayes_update(), entropy(), guess(), learn() (+11 more)

### Community 3 - "Error Handling and API Validation"
Cohesion: 0.22
Nodes (17): AdaptEngineError, DifficultyError, DuplicateIdError, UnknownConceptError, ValidationError, Activity, ActivityType, load_activities() (+9 more)

### Community 4 - "Test Fixtures and Review Gate Generation"
Cohesion: 0.20
Nodes (15): generate_invalid_fixtures(), main(), make_activities(), hash_file(), main(), UnreviewedContentError, _check_review_gate(), load_curriculum() (+7 more)

### Community 5 - "CLI Interface and CI Verification"
Cohesion: 0.23
Nodes (8): CLI Verification Suite & Commands, GitHub Actions CI Verification Pipeline, main(), test_cli_show(), test_cli_subprocess(), test_cli_validate(), test_cli_validate_error(), test_cli_validate_unreviewed()

## Knowledge Gaps
- **13 isolated node(s):** `adaptengine`, `AdaptEngine Project Overview`, `AdaptEngine Core Architecture`, `Bayesian Knowledge Tracing (BKT)`, `Curriculum Directed Acyclic Graph` (+8 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 38 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ValidationError` connect `Error Handling and API Validation` to `Core Engine and State Immutability`, `Curriculum DAG and Concept Schemas`, `BKT Mastery and Uncertainty Estimation`, `Test Fixtures and Review Gate Generation`?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `ValidationError` (e.g. with `Engine` and `Activity`) actually correct?**
  _`ValidationError` has 12 INFERRED edges - model-reasoned connections that need verification._
- **What connects `adaptengine`, `AdaptEngine Project Overview`, `AdaptEngine Core Architecture` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Curriculum DAG and Concept Schemas` be split into smaller, more focused modules?**
  _Cohesion score 0.1339031339031339 - nodes in this community are weakly interconnected._
- **Why does `CurriculumGraph` connect `Curriculum DAG and Concept Schemas` to `Core Engine and State Immutability`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `Engine` (e.g. with `AdaptEngine Core Architecture` and `run_experiment()`) actually correct?**
  _`Engine` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Why does `Engine` connect `Core Engine and State Immutability` to `Curriculum DAG and Concept Schemas`, `Error Handling and API Validation`, `CLI Interface and CI Verification`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._