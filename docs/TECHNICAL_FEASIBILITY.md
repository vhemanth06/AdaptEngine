# Technical Feasibility & Constraints

This document documents the technical feasibility, toolchain, assumptions, and limitations of AdaptEngine.

---

## 1. Toolchain & Infrastructure

- **Language & Runtime:** Python 3.10+ (tested on Python 3.11).
- **Core Dependencies:**
  - `networkx==3.4.2`: Pinned for directed acyclic graph (DAG) representation, topological sorting, and cycle detection.
  - `pyBKT` (pinned optional adapter): Referenced for discrete class BKT mapping; `CustomBKT` oracle provides an independent, exact reference implementation.
- **Development & Verification:** `pytest==8.3.3`, `pytest-cov==6.0.0`, `ruff==0.8.0`.
- **Infrastructure Requirements:** Standard developer workstation / laptop CPU only. **Zero GPU requirements, zero runtime network access.**
- **Reproducibility Guarantee:** SHA-256 configuration hashing (`config_hash`) and code SHA logging ensure every execution is independently reproducible.

---

## 2. Reference Datasets

- **Primary Environment:** Transparent synthetic simulator with parameter provenance (Planned, Milestone M8).
- **ASSISTments (2009–2010):** Public educational benchmark dataset used for offline sanity-checks of the BKT response model.
- **Junyi Academy:** Public prerequisite taxonomy used as a reference structure for realistic large-scale curriculum DAG design.
- **Missing Data Conventions:** In historical or public datasets, missing durations are filled with clearly labeled synthetic placeholders; unknown prerequisite relationships are never invented.

---

## 3. Feasibility Argument

AdaptEngine's implementation is technically feasible within the project timeline due to deliberate architectural scoping:
1. **Foundation Exists:** The core DAG loader, BKT update equations, state model, and review gate were hardened in Weeks 1–3.
2. **Focused Model Scope:** Adopting a single well-characterized BKT mastery model rather than training unverified neural knowledge tracing models avoids heavy parameter estimation complexities.
3. **Narrow Combinatorial Search:** Small day budgets (5 to 30 minutes) constrain the daily packing search space. Combining feasibility bounds with an exact bin-packing oracle avoids the need for complex custom heuristic search engines.
4. **Library Isolation:** Standard graph operations are delegated to NetworkX, while all business rules and constraints remain inside pure, deterministic engine code.

---

## 4. Key Assumptions

1. **DAG Fidelity:** Prerequisite relationships in the curriculum form a valid, acyclic directed graph and represent hard instructional constraints.
2. **Indivisible Activity Durations:** Activities have fixed integer durations in minutes and cannot be partially completed or split across days.
3. **Single-Concept Tagging:** Each exercise is tagged with exactly one primary target concept.
4. **Binary Scoring:** Exercises are scored strictly correct or incorrect. Partial credit and open-ended submissions are out of scope for the prototype.
5. **Difficulty Bounds:** Activity difficulties are bounded strictly within $[d_{\min}, d_{\max}]$ (default $[0.05, 0.95]$).
6. **Zero Duration Missed Days:** A missed day corresponds to zero practiced minutes.

---

## 5. Challenges & Limitations

1. **Synthetic Parameters:** Parameter values ($p_0 = 0.20, \theta = 0.85, T_*$, guess and slip coefficients) are synthetic heuristics rather than empirically fitted parameters.
2. **Simulator Inductive Bias:** Benchmarks against a simulator from the same model family may overestimate real-world accuracy; mismatched simulator profiles are required in Milestone M8.
3. **Entropy Dynamics:** $H(p)$ measures uncertainty in a latent binary mastery state, not estimation confidence. A surprising response can cause entropy to increase.
4. **Small Prototype Curriculum:** The default fixture consists of 4 Python concepts and 20 activities. Full curriculum scalability will be assessed on larger fixtures in Week 4.
5. **No Network Access:** The engine is strictly offline at runtime; all curriculum and activity metadata must be pre-validated locally.
