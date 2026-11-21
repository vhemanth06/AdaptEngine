# Third-Party Reuse Inventory

This inventory documents all external third-party libraries evaluated, reused, or integrated in AdaptEngine, along with pinned versions, licenses, architectural roles, and isolation rules.

---

## Integrated Dependencies

### 1. NetworkX
- **Version:** `3.4.2` (pinned in `requirements.txt`)
- **License:** 3-Clause BSD License
- **Purpose:** Directed Acyclic Graph (DAG) data structure, topological sorting, prerequisite traversal, cycle detection.
- **How Used:** Wrapped exclusively inside `adaptengine.curriculum.graph.CurriculumGraph`. No other engine package may import NetworkX.
- **Mapping & Constraints:** All node lookups and edge operations check concept existence beforehand to prevent NetworkX from silently creating phantom nodes.

### 2. pyBKT
- **Version:** `1.4.3` (optional pinned library reference)
- **License:** MIT License
- **Purpose:** Established reference implementation of Bayesian Knowledge Tracing (BKT).
- **How Used:** Referenced via `adaptengine.learner.adapter.PyBKTAdapter`. Isolated strictly to `learner/adapter.py`.
- **Mapping Notes (D6):** Maps continuous difficulties $d \in [d_{\min}, d_{\max}]$ into 3 discrete item classes:
  - `easy`: $d < 0.35$ (representative $d = 0.20$, guess $= 0.240$, slip $= 0.100$)
  - `medium`: $0.35 \le d < 0.65$ (representative $d = 0.50$, guess $= 0.150$, slip $= 0.175$)
  - `hard`: $d \ge 0.65$ (representative $d = 0.80$, guess $= 0.060$, slip $= 0.250$)
- **Independent Oracle:** `CustomBKT` in `learner/adapter.py` provides an exact, standalone reference implementation of continuous BKT equations so that the engine operates deterministically offline regardless of library presence.

---

## Evaluated / Candidate Dependencies

### 3. catsim (Candidate for Future CAT Baselines)
- **Status:** Candidate evaluated, not integrated.
- **License:** MIT License
- **Purpose:** Computerized Adaptive Testing simulator using Item Response Theory (IRT).
- **Decision:** Deferred. AdaptEngine focuses on BKT mastery estimation and Expected Information Gain over prerequisite DAGs rather than continuous unidimensional IRT $\theta$.

### 4. halflife-regression / HLR (Candidate for Spaced Review)
- **Status:** Candidate evaluated, not integrated.
- **License:** MIT License / BSD
- **Purpose:** Half-Life Regression for spaced repetition modeling.
- **Decision:** Milestone M5 will adopt a deterministic fixed half-life decay baseline $r(t) = 2^{-\Delta t / h}$. HLR will only be considered if feature mappings and empirical training datasets become available.
