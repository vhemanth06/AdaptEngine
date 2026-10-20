# Architecture & Methodology Decision Records

This document records the finalized architectural and methodological decisions for AdaptEngine, replacing outdated prototype notes with finalized specifications.

---

## 1. Methodology & Modeling Decisions

- **Mastery Estimation:** Single Bayesian Knowledge Tracing (BKT) model per concept with latent learning transitions ($T_{\text{exercise}} = 0.05, T_{\text{diag}} = 0.0, T_{\text{lesson}} = 0.20$). Replaced older Beta distribution proposals.
- **Mastery Adapter & Oracle:** Standardized `MasteryModel` protocol. `CustomBKT` serves as the exact reference oracle for continuous equations; `PyBKTAdapter` maps continuous difficulty into 3 discrete item classes (easy, medium, hard) adhering to Decision D6.
- **Adaptive Diagnosis (Milestone M2):** Active assessment based on Expected Information Gain (EIG), constrained by a global item cap $N_{\max} = 8$, per-concept cap $3$, entropy threshold $H \le 0.50$, and ancestor pruning at $p < 0.40$.
- **Path Planning & Feasibility:** Deterministic scheduler with feasibility bounds and an exact bin-packing oracle. Replaced earlier custom A* proposals with provable constraint satisfiability.
- **Spaced Review:** Fixed half-life decay baseline $r(t) = 2^{-\Delta t / h}$. Half-Life Regression (HLR) is deferred unless fitting datasets and feature mappings are established.
- **Evidence-Mastered Definition:** Strict separation between instructional exposure (`lessons_done`), assessment observations (`responses`), and evidence-mastered ($\text{evidence\_mastered} := p \ge \theta \text{ and } \text{responses} \ge k$, default $k=2, \theta=0.85$). Lessons never mark concepts as assessed or evidence-mastered.
- **Persistence & Atomicity:** On-disk state and log updates use an atomic snapshot protocol (`path.tmp` write, flush, fsync, `os.replace`), while in-memory transitions remain strictly immutable.

---

## 2. Open Decisions Needing Human Input (D1 – D10) — Defaults Applied

The following decisions were flagged for human sign-off; defaults were applied to maintain progress without blocking:

| # | Decision Topic | Default Applied | Rationale & Verification |
|---|---|---|---|
| **D1** | Global diagnostic item cap $N_{\max}$ | **8 items** | Bound total diagnostic assessment time to ~15 minutes while allowing coverage of key concepts. |
| **D2** | Per-concept diagnostic item cap | **3 items** | Prevents over-testing on a single concept while allowing confidence bounds. |
| **D3** | Entropy stop threshold $H_{\text{stop}}$ | **$H(p) \le 0.50$** ($p \le 0.11$ or $p \ge 0.89$) | Halts when latent mastery certainty exceeds ~89%. |
| **D4** | Minimum responses $k$ for evidence-mastered | **$k = 2$ and $p \ge \theta$** ($0.85$) | Requires at least two consistent observations before unlocking dependents. |
| **D5** | Stored value after exercise update | **Post-transition $p''$** | Reflects latent learning resulting from the practice attempt ($T_{\text{exercise}} = 0.05$). Tests assert both $p'$ and $p''$. |
| **D6** | Discrete difficulty classes for adapter | **3 classes**: easy ($d < 0.35$), medium ($0.35 \le d < 0.65$), hard ($d \ge 0.65$) | Preserves parity with pyBKT while matching continuous oracle at class-representative difficulties ($0.20, 0.50, 0.80$). |
| **D7** | Instructional lesson prior shift | **Yes, via $T_{\text{lesson}} = 0.20$** | Lessons provide exposure and prior shift, but **never** set `assessed` or satisfy evidence-mastered. |
| **D8** | Descendant pruning in diagnostic | **Prune descendants if ancestor ends with $p < 0.40$** | Skips downstream skills when prerequisite fundamentals are unmastered, saving item budget. |
| **D9** | Reviewer identity in manifest | **Named non-"AI" reviewer required for live loading** | `ai_assisted: true` recorded; human sign-off left to repository owner (`vhemanth06`). Live loads reject `"AI"` reviewer. |
| **D10** | Selection tie-breaking rule | **Smaller $|d - 0.50|$, then lexicographic `activity_id`** | Prioritizes informative median-difficulty items deterministically. |

---

## 3. Planning & Difficulty Policy Decisions (D11 – D19) — Finalized for W4

| # | Decision Topic | Decision Choice | Rationale & Verification |
|---|---|---|---|
| **D11** | Multi-day eligibility | **Project workload assuming correct answers** | Project each concept's required instructional and assessment workload assuming correct responses; a concept counts as completed for downstream eligibility once its projected work is scheduled. |
| **D12** | Same-day unlock | **Allowed; within-day order respects prerequisites** | If a prerequisite finishes with time remaining in the day, dependent activities may start on the same day following prerequisite order. |
| **D13** | Unlock count | **Transitive descendant count (`descendant_count`)** | Rewards unlocking bottlenecks and deep downstream dependency subtrees over immediate child counts. |
| **D14** | Difficulty-fit score for lessons | **0.0** | Lessons do not carry difficulty or failure probability, so difficulty fit is neutral (0.0). |
| **D15** | Packing rule | **Skip non-fitting items, continue packing** | When the highest-ranked candidate exceeds remaining minutes, skip it and fill remaining budget with lower-ranked fitting candidates. |
| **D16** | Within-concept order | **Lessons before exercises, enforced by queue** | Instructional lessons precede practice exercises within a concept, enforced by queue sequencing rather than heuristic score. |
| **D17** | Oracle limit | **Node count integer (`oracle_node_limit`)** | Because `time`, `datetime`, and wall-clock modules are strictly prohibited in the deterministic core, search limits are bounded by branch-and-bound node expansions. |
| **D18** | Day numbering | **Absolute integers from `current_day` to `deadline_day`** | Eliminates relative offset ambiguity; plan starts at `current_day` and terminates at or before absolute `deadline_day`. |
| **D19** | Diagnostic comparison harness | **Moved to W6 (M8 evaluation)** | Report places comparative harness in Milestone M8; deferred from W4 to W6 alongside synthetic evaluation workloads. |

