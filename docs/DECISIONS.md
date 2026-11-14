# Architecture & Methodology Decision Records

This document records the finalized architectural and methodological decisions for AdaptEngine, replacing outdated prototype notes with finalized specifications.

---

## 1. Methodology & Modeling Decisions

- **Mastery Estimation:** Single Bayesian Knowledge Tracing (BKT) model per concept with latent learning transitions ($T_{\text{exercise}} = 0.05, T_{\text{diag}} = 0.0, T_{\text{lesson}} = 0.20$). Replaced older Beta distribution proposals.
- **Mastery Adapter & Oracle:** Standardized `MasteryModel` protocol. `CustomBKT` serves as the exact reference oracle for continuous equations; `PyBKTAdapter` maps continuous difficulty into 3 discrete item classes (easy, medium, hard) adhering to Decision D6.
- **Adaptive Diagnosis (Milestone M2):** Active assessment based on Expected Information Gain (EIG), constrained by a global item cap $N_{\max}$ (8 in W6; 6 since the W7 T3.3 pre-registered selection, D44), per-concept cap (3 in W6; 2 since D44), entropy threshold $H \le 0.50$, and ancestor pruning at $p < 0.40$.
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
| **D19** | *(reserved)* | **No decision was recorded under this ID in W4** | The W4 section heading announced D11–D19 but only D11–D18 were written; R§3 flagged the gap. The ID stays unused so later numbering is stable (W7 T9.1). |

---

## 4. Spaced Review, Remediation & Replanning Decisions (D20 – D30) — Finalized for W5

| # | Decision Topic | Decision Choice | Rationale & Verification |
|---|---|---|---|
| **D20** | Remediation trigger | **Event-driven: a response with `correct = False` leaves $p < \text{remediation\_threshold}$ ($0.40$)** | Replaces contradictory "two wrong answers" text; clean single-model trigger where a failed assessment or response drops mastery below remediation threshold (default $0.40$). |
| **D21** | Remediation content | **Re-issue the concept's lesson before further exercises; clear flag when lesson completes** | Queues the concept's instructional lesson (repeat attempt) to restore prior belief before subsequent exercises; completing this lesson clears `needs_remediation`. |
| **D22** | Concepts with `last_practice_day = None` | **Not review candidates; reviews begin after initial practice/lesson** | Spaced recall requires an anchor day; diagnostic probes do not set practice day, so review starts only once instructional or practice activity occurs. |
| **D23** | Half-life decay baseline | **Fixed per-concept baseline ($h$); `half_life_growth = 1.0` ablation knob** | Retains deterministic baseline $r(t) = 2^{-\Delta t / h}$; half-life growth multiplier default 1.0 provides documented ablation knob. |
| **D24** | Recall threshold | **`recall_threshold = 0.80` in config** | Spaced review item is triggered whenever projected recall $r(t) < 0.80$. |
| **D25** | Review urgency | **$\text{urgency} = (1 - r) \cdot (1 + \text{descendant\_count})$** | Scales with forgetting depth and downstream bottleneck importance; $+1$ ensures leaf concepts maintain positive urgency. |
| **D26** | Priority tier order | **Remediation $\to$ Reviews ($r < \text{threshold}$ by urgency) $\to$ New Lessons/Exercises** | Critical prerequisite remediation precedes retention reviews, which precede new curriculum advancement under the shared daily budget. |
| **D27** | Review content | **Exercise chosen by difficulty policy; repeats allowed via attempt ID** | Exercises selected nearest target success $P_c \approx 0.75$; re-practicing previously completed exercises is permitted via unique attempt IDs. |
| **D28** | `FAILED_ASSESSMENT` event | **Requires exercise `activity_id` and `correct = False` (or None); triggers state update & remediation check** | Fails with `ValidationError` if `correct = True`; updates posterior belief as a failed exercise attempt and triggers remediation check. |
| **D29** | Deadline & budget derivation | **Derived pure function: initial context folded over log events; optional snapshot context** | Effective context is computed purely by folding `DEADLINE_CHANGED` and `BUDGET_CHANGED` events over initial `PlanContext`; snapshot stores optional `"context"` key. |
| **D30** | Replanning after missed day | **Replan from next day; missed day contributes zero minutes** | A missed day records zero elapsed minutes; revised plan begins at $\text{missed\_day} + 1$, preserving all completed work without duplication. |

---

## 5. Feedback Fix & Policy Hardening Decisions (D31 – D34) — Finalized October 2026

| # | Decision Topic | Decision Choice | Rationale & Verification |
|---|---|---|---|
| **D31** | Lessons vs Evidence Contract | **Option 1: $p \ge \theta \text{ and } \text{responses} \ge k$** | Lessons raise belief via $T_{\text{lesson}} = 0.20$ without incrementing `responses`. Unlocking evidence-mastery requires at least $k$ exercise attempts and $p \ge \theta$. Documented as intentional contract behavior; planner always schedules exercises after lessons. |
| **D32** | Atomic CLI Store (FB006) | **Single canonical snapshot store via `<path>.<pid>.tmp`** | Eliminates dual-write desynchronization. State, log, and context commit in a single atomic `os.replace`. `save_learner` and `save_log` are deprecated to explicit legacy import/export commands. |
| **D33** | Single Observation Model | **MasteryModel protocol used for EIG and state updates** | `compute_eig` delegates to `model.predict_correct` and `model.update(..., 0.0)`. `Engine` holds a single `MasteryModel` instance shared across diagnostic, evidence, difficulty, and planning. |
| **D34** | Diagnostic Attempt ID Scope | **`diag-<session_id>-<concept_id>-<n>`** | Session scoping prevents attempt ID collisions across distinct diagnostic runs, while making exact replay of the same session and items idempotent. |

---

## 6. Evaluation, Frontier Replanning & MVP Hardening Decisions (D35 – D40) — Finalized for W6

| # | Decision Topic | Decision Choice | Rationale & Verification |
|---|---|---|---|
| **D35** | Frontier replanning memoization | **Per-concept memoization via caller-owned `WorkloadCache`** | Explicit caller-owned cache object passed to `plan` and `replan`. `Engine` has no hidden state. Replan equivalence is guaranteed by construction and verified by bitwise `Plan` equality (`==` on days, status, shortfall, trace). CLI remains full recomputation. |
| **D36** | Closed-loop simulator determinism | **Key-seeded pseudo-random draws per interaction** | Every simulated attempt uses a deterministic key `(seed, tag, activity_id, attempt_n)` rather than consuming a shared PRNG stream. Provides paired noise isolation across arms, 4 learner profiles, power-law retention, and documented 0.70 heuristic true mastery cutoff. |
| **D37** | Planner evaluation arms | **Four arms: `adapt`, `no_review`, `no_replan`, `static`** | Disentangles benefits of closed-loop replanning, spaced retention reviews, and learner-state adaptation against a state-ignoring topological baseline. |
| **D38** | Oracle assignment trace parity | **Per-activity `SELECTED` trace records with `reason="ORACLE_ASSIGNED"`** | When exact branch-and-bound packs days after greedy schedule overshoots deadline, each placed activity receives an explicit `SELECTED` record. Ensures 100% explanation trace coverage and satisfies TC7.1. |
| **D39** | Diagnostic evaluation protocol | **50/50 seed split; pre-declared selection rule evaluated once on held-out** | Even seeds form the tuning cohort; odd seeds form the held-out evaluation cohort. Selection rule chooses lowest tuning MAE among configurations consuming $\le 50\%$ items of the fixed arm before running held-out evaluation. |
| **D40** | Scheduler review starvation bound | **Safety termination upon 15 consecutive starvation days or horizon exceeded** | In large curricula ($N \ge 40$) under tight budgets where daily review debt exceeds daily capacity, greedy scheduler terminates when queue progress stalls for 15 consecutive days or calendar horizon is exceeded, allowing exact oracle or shortfall resolution to take over cleanly. |

---

## 7. Week 7 Decisions (D41 – D48) — Proposed for W7, awaiting human approval

| # | Decision Topic | Decision Choice | Rationale & Verification |
|---|---|---|---|
| **D41** | Exercise repetition in new learning | **`allow_exercise_repeats=True`: unseen exercises first, then the least-recently-attempted one** | With 4 exercises per concept a few wrong answers made mastery unreachable (`CONTENT_INSUFFICIENT`) and the learner idle (R§2.3). Attempt IDs keep repeats idempotent; `CONTENT_INSUFFICIENT` now means an empty bank. `tests/test_w7_planner.py::test_repeats_keep_plan_feasible_after_failing_c1_t2_3`. |
| **D42** | Infeasible goals | **Return `INFEASIBLE`/`UNKNOWN` + shortfall + options *and* `best_effort_days` toward the deepest reachable concept on the goal path** | An infeasible verdict used to mean an idle learner. Trace marks the schedule `BEST_EFFORT`. `tests/test_w7_planner.py::test_best_effort_plan_on_infeasible_t2_4`, `::test_deadline_cut_episode_never_idle_t2_4`. |
| **D43** | Spaced review reachability | **`half_life_days` in config; maintenance tier schedules due reviews until `deadline_day`; one recall implementation in `review/forgetting.py`; `n_reviews` counts review attempts only** | Reviews could never fire (hard-coded h = 30, scheduler stopped when new content ended, duplicated recall formula; R§2.5). `tests/test_review.py::test_review_due_fires_with_short_half_life_t2_6`. |
| **D44** | Diagnostic design and selection | **Flags `min_items_per_concept`, `pruning_mode`, `selection_scope`, `prior_mode`; defaults chosen by a pre-registered Brier rule (T3.3) → population prior 0.24, `concept_cap=2`, `n_max=6`** | MAE |p − θ| is an improper metric for a mastery probability; the W6 D39 rule was overridden post hoc. The new rule was registered with its code hash before the run and applied as written (`docs/preregistration/W7_T3.3_2026-11-08.md`, `experiments/results/w7_diag_selection.json`). |
| **D45** | Demo UI | **Adapter only; the engine is the sole decision source** | The FastAPI adapter and React app contain no planning, mastery or eligibility logic; the API test asserts API plans equal direct `Engine` calls (`frontend/api/tests/test_api.py`). |
| **D46** | Primary safety metric | **Executed-state prerequisite audit (replay the real log through `engine.record`); the plan-level audit is secondary** | The W6 optimistic audit hid 183 (adapt) / 640 (static) executed violations in calm (R§2.1). With the closed loop (T2.2) adapt has 0. `experiments/checks.py::count_executed_prereq_violations`. |
| **D47** | Simulator worlds and pre-registration | **Worlds S0–S4 (independent, prerequisite-gated, correlated, forgetting, BKT-generated); every new world/metric/rule is pre-registered with a timestamp and code hash before running** | Avoids tuning the simulator until adapt wins; S0 is kept and reported (`docs/preregistration/W7_T4.1_2026-11-08.md`). |
| **D48** | Fitted parameter profiles | **Fitted BKT parameters are stored as named config profiles (`config/fitted_*.json`) with source and code hash; the D6 heuristic stays the default until a fitted profile beats it on held-out data** | Fits on ASSISTments 2009 / Cognitive Tutor (maths) give realistic ranges, not Python-learner values (T3.5, T7.3, T7.6). |


## 8. Week 8 Decisions (D49 – D60) — Final week, awaiting human approval

Evidence: `docs/WEEK8_REPORT_NOTES.md`, `docs/FINAL_RESULTS.md` (generated from `experiments/results/*.json`), pre-registration `docs/preregistration/FINAL_A5_2026-11-10.md`. Every new behaviour is behind a config flag whose default reproduces W7.

| # | Decision Topic | Decision Choice | Rationale & Verification |
|---|---|---|---|
| **D49** | Use of remaining budget | **Consolidation tier (`consolidation`): once all required work is scheduled, verification practice (unseen hardest items, lowest-confidence concepts first) until the deadline; a wrong answer reopens the concept through the closed loop** | W7 adapt used 52.7–59.8 of 120 minutes and idled 3–4 days while 39–51% of "mastered" concepts were truly unmastered (R§1.3). Headline final grid: utilisation 0.29 (W7) → 0.95; adapt_final vs adapt_cal (same calibration without C.1/C.2) goal +0.196 [+0.173, +0.221], all-required +0.360. `tests/test_w8_engine.py` (only after all required work; 0 violations; utilisation rises). |
| **D50** | Unlock evidence quality | **Verification probe (`verification_probe`): one hard item before dependents unlock when > 50% of a prerequisite's exercise evidence is easy and none is hard** | Easy items are answered correctly well below mastery (fitted easy-class guess 0.62–0.68 in S0/S1). Part of adapt_final; its effect is not separated from D49 in the grid (one ablation arm for both). `tests/test_w8_engine.py::test_probe_*`. |
| **D51** | Mastery strictness | **Horizon-aware two-part criterion (`horizon_aware_mastery`): when slack > 50% the plan uses θ and H ≤ 0.35 with k = 3; otherwise the W7 rule** | Chosen by the pre-registered B.3 rule (candidate F5 won among those within 0.002 Brier of the best, by goal mastery vs static_loop). Same decisions as W7 at small slack (test). |
| **D52** | Diagnostic role | **The diagnostic becomes optional in the product flow (Skip → plan from the prior); the engine's diagnostic is unchanged** | Held-out grid: adapt_final_dx − adapt_final headline goal −0.017 [−0.027, −0.007]; mean over 192 non-forgetting cells −0.005; over all 208 cells 1 better, 191 n.s., 16 worse. The pre-registered "≈ equal → optional" condition (CI includes 0) is not met because the diagnostic is slightly *worse* (it spends study minutes); the rule did not define this case, and making it optional follows its intent (deviation recorded in the notes). |
| **D53** | A2 bandit policy | **LinUCB + softmax ranking of the top-5 eligible new-content candidates, logged propensities, learning-progress reward, ridge update; the single feedback-driven policy; off by default** | Spec `docs/POLICY_SPEC.md`. 0 executed violations for every variant (tests and evaluation). Held-out: no variant differs from deterministic (e.g. S1 8-node frozen +0.010 [−0.015, +0.035]); per-learner updating changes no choice (≤ 0.0007 propensity shift); OPE of the frozen policy from random logs within 0.007 of its simulated value (`FINAL_RESULTS.md` §3). Kept off by default. |
| **D54** | A0 authoring aid | **Drafts only (`data/drafts/`), schema + authoring checks, human review gate (`scripts/record_review.py` rejects AI/PENDING names)** | `docs/AUTHORING.md`; `tests/test_authoring.py`; the live loader rejects unreviewed drafts. |
| **D55** | A2′ LLM ranker | **Non-learning proposer over the same candidates; strict JSON validation; cache by prompt hash; `AGENT_FALLBACK` on any failure** | `tests/test_agent_policy.py`: 6 adversarial outputs → fallback with plans equal to deterministic and 0 violations. Live evaluation not run (no model connected). |
| **D56** | Agentic layer defaults | **Disabled by default; optional `[agents]` extra; network only through `authoring/providers.py` when explicitly enabled** | `tests/test_architecture.py::test_core_never_imports_agentic_layer_or_providers`, `::test_agentic_layer_is_off_by_default`. |
| **D57** | A1 plan proposer | **Engine-validated proposals (8 rules); deterministic plan + `PROPOSAL_REJECTED` with reasons on failure** | `tests/test_plan_proposer.py` (each rule rejected with its reason); demo button in Plan + Why?. |
| **D58** | A3 orchestrator | **Closed option set generated by the engine; default = tier order; anything else falls back** | `tests/test_orchestrator.py`; Study screen strategy chip. |
| **D59** | Alternative mastery model | **Elo/1PL model behind `MasteryModel` (`mastery_model = "elo"`), off by default** | Held-out (adapt_final loop, 4-node, B = 15, 14 d): higher AUC (S1 0.683 vs 0.637) but lower goal mastery (S1 −0.145 [−0.205, −0.090], S4 −0.200 [−0.255, −0.145]); BKT stays the default (`FINAL_RESULTS.md` §4). |
| **D60** | Exact scheduler | **CP-SAT (`scheduler = "cpsat"`, optional `[solver]`); same audits as greedy/oracle; falls back to greedy + oracle when OR-Tools is absent** | Fallback tested; the CP-SAT parity test is skipped here (OR-Tools not installed); evaluation not run. |
| **D61** | Product mastery strictness | **Product mastery θ = 0.95 with k = 1 (θ is the only real condition; at least one answer so an inferred estimate alone never masters), always (`PRODUCT_OVERRIDES`); `EngineConfig` defaults keep W7; overrides the W8 B.3 winner F5 (D51)** | Owner judgment on realistic practice: nobody masters a concept in 2–3 questions. Known cost (F3/F4 in `experiments/results/w8_calibration_select.json`): goal mastery vs static_loop −0.255 on S0 8-node for F3/F4 (F5 was −0.08; goal mastery 0.87 → 0.695), mean secondary diff vs static_loop F5 +0.053 → F3/F4 +0.009 (F1 +0.054); S1 4-node +0.185. k was first set to 4, then lowered to 1 by the owner (2026-11-14): an extra floor question on concepts the diagnostic already estimates as known is waste; with `fitted_S1` θ = 0.95 alone needs ≈ 5 medium correct answers from the prior. Under `w7_default` numbers θ = 0.95 is reached after 2 correct answers. F3 (θ 0.95, k 2) is the closest measured W8 candidate. Tests: `tests/test_w9_product.py`. |
| **D62** | Goal-search diagnostic | **`selection_scope="goal_search"`: concept chosen by min(\|open ancestors\|+1, \|open descendants\|+1); estimate floored onto open ancestors and INFERRED when p ≥ `known_threshold` 0.70; hard pruning downward; budget min(`n_max`, max(`diag_budget_min`, round(rate·N))), product 12/1.0/25; a budget-cut concept does not propagate (frontend prefix replay); no binary credit, practice confirms** | Literature basis: ALEKS (16–30 questions, prerequisite inference, later re-checks); CAT/CD-CAT precision-or-cap stopping; BKT individualized priors. Tests: `tests/test_w9_diagnostic.py`. |
| **D63** | Web-app defaults and curricula | **`PRODUCT_OVERRIDES` + `fitted_S1` default learner model; sessions without a `"rules"` key keep legacy rules (replay); 10-exercise curricula `4node_x10` / `8node_x10` (new ids, human review pending, old files untouched)** | Caveat: `fitted_S1` was fitted on simulated S1 learners; its high guess rates largely reflect partial knowledge under the simulator's 0.70 cutoff. The web product and the W9 simulation arms both use `diagnostic_scope="goal_path"`: only the session goal and its prerequisites are diagnosed (on the 8-node curriculum C4 is off C8's path, so it is never asked); the goal is fixed at session creation (`diag_goal` in meta) so a later goal change cannot break replay of recorded answers. Consolidation (D49) is off in `PRODUCT_OVERRIDES` (owner, 2026-11-14: the plan ends once the goal is mastered, no post-mastery "Verify" days); the W9 strict arms still build on `FINAL_FLAGS`, which keep it on. `config_hash` of `DEFAULT_CONFIG` changed because of the three new (behaviour-neutral) fields, so hashes stored in old plans/results will not match a fresh hash. Tests: `frontend/api/tests/test_api.py`, `tests/test_w9_content.py`. |
