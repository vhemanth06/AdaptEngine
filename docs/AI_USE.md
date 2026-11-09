# AdaptEngine — AI Assistance & Model Usage Record

**Accountable Owner:** Hemanth (`vhemanth06`)  
**Repository:** `AdaptEngine`  
**Date of Record:** 21 October 2026  

---

## 1. Overview & Accountable Ownership

All architectural, pedagogical, and algorithmic decisions in this repository are owned, reviewed, and approved by **Hemanth** (`vhemanth06`). AI code assistants (Google Antigravity IDE with Gemini 3.8 Flash High and Claude 3.5 Sonnet) were utilized as pair-programming tools under human supervision.

---

## 2. Tools & Models Used

- **AI Tools:** Google Antigravity IDE (Agentic Assistant), Claude 3.5 Sonnet, Gemini 3.8 Flash (High).
- **Scope of Generation:**
  - Core domain data classes, schemas, and typed exceptions (`src/adaptengine/core/`).
  - Curriculum DAG traversal, cycle detection, and manifest review gate (`src/adaptengine/curriculum/`).
  - Discrete Bayesian Knowledge Tracing (BKT) updates and real `pyBKT` model adapter (`src/adaptengine/learner/`).
  - Information-theoretic adaptive diagnostic engine via Expected Information Gain (`src/adaptengine/diagnostic/`).
  - Constraint-satisfying study plan generator and exact bin-packing branch-and-bound oracle (`src/adaptengine/planner/`).
  - Spaced memory retention model, review queue, and remediation handling (`src/adaptengine/review/`, `src/adaptengine/replanner/`).
  - Atomic single-store persistence protocol and unified CLI (`src/adaptengine/session.py`, `src/adaptengine/cli.py`, `src/adaptengine/api.py`).
  - Verification test suites (`tests/`), standalone acceptance runners (`scripts/`), and baseline evaluator (`experiments/`).

---

## 3. Human Verification & Audit Checks Conducted

Every generated component underwent mandatory human checks prior to acceptance:
1. **Mathematical Soundness:** Manually derived posterior values for Bayes update $p' = \frac{p(1 - s)}{p(1 - s) + (1 - p)g}$ and post-learning transition $p'' = p' + (1 - p')T$, verifying reference constants ($p=0.5, d=0.5 \implies 0.8462$ prior to transition, $0.8538$ after $T=0.05$).
2. **Deterministic Purity Check:** Verified that no module inside `src/adaptengine/` imports `time`, `datetime`, `random`, or accesses wall-clock system time. All timestamps and days are discrete, absolute integers.
3. **Architectural Layering:** Enforced unidirectional layering via AST inspection in `tests/test_architecture.py` (Core $\to$ Curriculum $\to$ Learner $\to$ Diagnostic $\to$ Review/Planner $\to$ Replanner $\to$ Session $\to$ API $\to$ CLI).
4. **Atomic Commit Fault-Injection:** Simulated filesystem and power failure by monkeypatching `os.replace` and `os.fsync` across all 5 event recording operations, confirming zero partial file creation and byte-identical state retention.
5. **Quality Gates:** Required $100\%$ pass on `ruff check .`, `ruff format --check .`, and statement coverage $\ge 84\%$ (achieved $89\%$ across 140+ unit/integration tests).

---

## 4. Defects Missed by Initial AI Generation & Caught in Review

Transparency regarding defects that AI-generated tests initially failed to detect:

1. **Hardcoded Evidence-Mastery Policy:**
   - *Defect:* `LearnerConcept.evidence_mastered` hardcoded $\theta = 0.85$ and $k = 2$ literals, ignoring user-supplied `EngineConfig`.
   - *Remedy:* Replaced with `is_evidence_mastered(concept, cfg)` everywhere; verified through consumer planning tests where changing $\theta=0.99, k=5$ directly forces additional workload.
2. **Non-Atomic Dual-Write CLI Save (FB006):**
   - *Defect:* `cli.py` originally performed separate writes for `save_learner` and `save_log`. An interruption between writes caused state desynchronization.
   - *Remedy:* Unified on single canonical atomic snapshot store (`save_snapshot` using `<path>.<pid>.tmp`, `flush`, `fsync`, `os.replace`).
3. **Uncalled pyBKT Import:**
   - *Defect:* `PyBKTAdapter` imported `Model` from `pyBKT` but delegated to an internal formula without invoking the pyBKT solver.
   - *Remedy:* Installed `pybkt==1.4.3` (with compatible `numpy==1.26.4`), instantiated authentic `pyBKT.models.Model`, and verified parity at discrete difficulty classes.
4. **Diagnostic Attempt ID Collisions:**
   - *Defect:* Probes used `diag-<concept>-<n>` IDs, leading to collisions or inability to repeat assessments across multiple sessions.
   - *Remedy:* Scoped IDs with session identifiers `diag-<session_id>-<concept_id>-<n>`, ensuring idempotency for retries and clean separation across distinct sessions.
5. **Discrepancy Between Diagnostic EIG and Observation Model:**
   - *Defect:* `compute_eig` utilized hardcoded analytical formulas, ignoring injected model parameters.
   - *Remedy:* Unified EIG calculation strictly through the `MasteryModel` protocol (`predict_correct` and Bayes step `update(..., 0.0)`).
6. **Permissive Deserialization Coercion:**
   - *Defect:* `deserialize_learner` coerced `bool(assessed)` and silently defaulted `half_life_days=0` to 30.
   - *Remedy:* Enforced strict type and value validation, rejecting invalid boolean strings, negative uncertainties, and non-positive half-lives.

---

## 5. Explicit Limitations & Scope Boundaries

- **Synthetic Baseline Scope:** Experimental gains demonstrated in `experiments/run_evaluation.py` (M8 / TC8.1) use simulated learners with 2-parameter logistic IRT response curves against BKT belief updates on synthetic 4-node curriculum graphs. Synthetic gains support synthetic claims only; empirical efficacy requires classroom/field trials.
- **pyBKT Parameter Mapping:** The pyBKT adapter operates over discrete classes (`easy`, `medium`, `hard`) mapped to representative points ($d=0.20, 0.50, 0.80$). Continuous difficulty parameterization is handled by the exact reference oracle `CustomBKT`.
- **Heuristic Priors:** Transition probabilities ($T_{\text{lesson}}=0.20, T_{\text{exercise}}=0.05, T_{\text{diag}}=0.0$) and guess/slip multipliers are heuristic prototype priors intended for algorithmic validation.

---

## 5. Week 6 and Week 7 Addendum (recorded 8 November 2026)

- **Week 6 tools:** Google Antigravity IDE (agentic assistant) for the evaluation harness, frontier replanning and documentation; `graphify` (code-graph tool) for repository maps — its output (`graphify-out/`) is a scratch artifact and is being untracked.
- **Week 7 tools:** Claude Code (Anthropic, model Claude Opus 5.5) as an agentic coding assistant, including parallel sub-agents for (a) the real-data BKT fitting pipeline (WP7), (b) the AI-drafted demo content file (T8.1) and (c) the demo frontend (WP8). The review that motivated the Week 7 plan (`report.md`, prototype probes) was also AI-assisted.
- **Scope of W7 generation:** executed-state audit, closed-loop entry point, mid-day budget, exercise repeats, best-effort plans, maintenance reviews, diagnostic flags and state-space diagnostic, simulator worlds S0–S4, evaluation/sensitivity/latency runners, fitting pipeline, FastAPI adapter and React demo, and the documentation updates listed in `docs/WEEK7_REPORT_NOTES.md`.
- **Controls applied in W7:** no git commands during implementation (version control left to the human); every number in the W7 notes comes from a command output or results file with its `code_hash`; selection rules and simulator variants were pre-registered (timestamp + code hash) before running; negative results are kept; AI-drafted content is marked `PENDING_HUMAN_REVIEW` in `data/review_manifest.json` until a human reviews it.
- **Human checks still required:** review of `data/content/content_8node.json`; approval of decisions D41–D48 (`docs/FREEZE_RECORD.md` §2.1); verification of the W7 results before committing.
