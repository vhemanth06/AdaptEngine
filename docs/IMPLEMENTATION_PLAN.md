# Implementation Plan (W3 – W8)

This document tracks the milestone roadmap, weekly deliverables, technical risks, and fallback strategies for AdaptEngine.

---

## 1. Roadmap & Milestone Progress

| Week | Milestone / Goal | Planned Tasks | Key Evidence & Deliverables | Status |
|---|---|---|---|---|
| **W3** | **M2 Complete & Foundation Hardening** | Complete adaptive diagnostic (M2); pinned pyBKT adapter with parity; evidence-state semantics; strict validation & review gate hardening (D-A..D-I); documentation transcribed; `make w3` verification runner. | TC1.2, TC2.1, TC2.2 pass; diagnostic never exceeds $N_{\max}$; code SHA, config hash, lint/test pass in evidence folder. | **Complete** |
| **W4** | **M3 & M4 Difficulty Policy** | Prerequisite filter and deterministic ranking; day-by-day packing for budgets 5/10/15/30 min; next-item difficulty fit policy; feasibility bounds, exact oracle returning `FEASIBLE`/`INFEASIBLE`/`UNKNOWN`; larger curriculum fixtures. | TC2.3, TC3.1–TC3.6, TC4.2 pass; `make w4` verification runner. | **Complete** |
| **W5** | **M5 & M6 Review, Remediation, Replanning** | Half-life decay review baseline; priority policy under shared budget; remediation trigger when $p < 0.40$; 4 replanning event handlers (missed day, failed assessment, deadline changed, budget changed); machine-readable traces and pure plan serialization. | TC5.1–TC5.3, TC6.1–TC6.4, TC7.1 pass; `make w5` verification runner. | **Complete** |
| **W6** | **M8 completion and MVP packaging** | Closed-loop key-seeded simulator, four profiles; four planner arms; matched-budget diagnostic comparison with tuning/held-out split; metrics with paired bootstrap intervals; frontier replanning via workload cache; latency benchmark; oracle-path traces; Quickstart, API example, extras, CLI error tests | TC8.1, TC8.2 pass; `evaluation_results.json`, `replan_latency.json`; `make w6` | Done |
| **W7** | **Stress testing (optional)** | Sensitivity over theta, k, half-life; larger cohorts | Sensitivity table | Planned |
| **W8** | **Final demonstration** | `make poc` across personas, final report, tagged release | Tagged repo, final report | Planned |

---

## 2. Core Functionalities

1. **Deterministic State & Evidence Accounting:** Strict separation between instructional exposure (`lessons_done`), assessment observations (`responses`), and `evidence_mastered` ($p \ge \theta, \text{responses} \ge k$).
2. **DAG Prerequisite Enforcement:** NetworkX DiGraph representation guaranteeing acyclicity, unreachable node rejection, and topological ordering.
3. **Adaptive Diagnostic (M2):** Expected Information Gain (EIG) item selection with global $N_{\max} = 8$ budget, concept cap 3, entropy threshold $0.50$, and descendant pruning at $p < 0.40$.
4. **Time-Budgeted Path Planner (M3):** Feasibility bounds plus exact bin-packing oracle for strict daily minutes.
5. **Spaced Review & Remediation (M5):** Half-life exponential decay model, urgency scoring, priority tiers (remediation > reviews > new content), and automatic repeat lesson scheduling.
6. **Dynamic Replanning (M6):** Pure replanning from event log and snapshot across 4 events (missed day, failed assessment, deadline changed, budget changed) preserving prior work without loss or duplication.
7. **Decision Explanations & Traces (M7):** Full traceability mapping each scheduled, deferred, or omitted activity to learner state and constraint rules, serialized as pure JSON with config hash.

---

## 3. Risks & Fallbacks

| Identified Risk | Potential Impact | Fallback Strategy |
|---|---|---|
| **pyBKT library environment compatibility** | Dependency installation or scalar casting issues across Python/NumPy versions | `CustomBKT` serves as independent exact oracle; discrete class adapter mapping documented; engine runs seamlessly regardless of library presence |
| **Diagnostic does not beat fixed order** | Limited M2 empirical benefit on small graphs | Report findings transparently, analyze information saturation on 4-node DAGs, preserve as tested baseline |
| **Exact oracle combinatorial explosion** | Feasibility search size on larger curriculum DAGs | Enforce strict search node limit returning `UNKNOWN` without false infeasibility claims; restrict exact oracle to small sub-problems |
| **Simulator drift / parameter mismatch** | Evaluation bias toward planner's internal model | Build simulator with dynamics from a different parameter family; evaluate on held-out public dataset distributions |
| **Scope creep / time pressure** | Late milestones incomplete | Prioritize core deterministic engine, CLI, and auditability; defer optional agentic modules (A0–A3) |
