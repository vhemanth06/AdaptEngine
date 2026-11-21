# Decisions

A decision record states one choice the project made (a method, a default value, a file layout, a rule), why it was made, and how it is verified. Each decision has a permanent number (D1, D2, …). Numbers are never reused or renumbered, so links from code comments, tests and older documents keep pointing at the same decision. The decision text is kept as it was adopted; when a later decision changes it, the old row stays and its status says so.

Status values:

- **Active**: in effect now.
- **Amended by Dxx**: still in effect, but part of it was changed by Dxx (the amending row says "amends").
- **Superseded by Dxx**: replaced by Dxx (the replacing row says "supersedes").
- **Historical**: concerns something that was removed or a process that ended; still true as a record.

Decisions are grouped by topic; [Index by number](#index-by-number) lists every number with its section and origin. [Current settings](#current-settings) lists the default values in effect.

## Current settings

Default values of `EngineConfig` as read from the code (`from adaptengine.core.config import DEFAULT_CONFIG, bisection_config`) on 2026-11-21. `bisection_config()` is `DEFAULT_CONFIG` with the two overrides in its rows; every other value is the same.

| Setting | Config key | Value | Decision(s) | Concept doc |
|---|---|---|---|---|
| Diagnostic: global item cap | `n_max` | `6` | [D1](#d1), [D44](#d44) | [04_diagnostic_sweep.md](../concepts/04_diagnostic_sweep.md) |
| Diagnostic: per-concept item cap | `concept_cap` | `2` | [D2](#d2), [D44](#d44) | [04_diagnostic_sweep.md](../concepts/04_diagnostic_sweep.md) |
| Diagnostic: entropy stop | `h_stop` | `0.5` | [D3](#d3) | [04_diagnostic_sweep.md](../concepts/04_diagnostic_sweep.md) |
| Diagnostic: descendant pruning threshold | `skip_threshold` | `0.4` | [D8](#d8) | [04_diagnostic_sweep.md](../concepts/04_diagnostic_sweep.md) |
| Diagnostic: pruning mode | `pruning_mode` | `"hard"` | [D8](#d8), [D44](#d44) | [04_diagnostic_sweep.md](../concepts/04_diagnostic_sweep.md) |
| Diagnostic: minimum items per concept | `min_items_per_concept` | `1` | [D44](#d44) | [04_diagnostic_sweep.md](../concepts/04_diagnostic_sweep.md) |
| Diagnostic: selection scope | `selection_scope` | `"concept_sweep"` | [D44](#d44) | [04_diagnostic_sweep.md](../concepts/04_diagnostic_sweep.md) |
| Diagnostic method | `diagnostic_method` | `"sweep"` | [D49](#d49) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| Evidence-mastered: minimum responses k | `k_responses` | `2` | [D4](#d4), [D31](#d31) | [02_mastery_bkt.md](../concepts/02_mastery_bkt.md) |
| Mastery threshold θ | `theta` | `0.85` | [D4](#d4), [D31](#d31) | [02_mastery_bkt.md](../concepts/02_mastery_bkt.md) |
| Learner prior p0 | `p0` | `0.2` | [D59](#d59) | [02_mastery_bkt.md](../concepts/02_mastery_bkt.md) |
| Sweep prior mode | `prior_mode` | `"flat"` | [D44](#d44), [D59](#d59) | [04_diagnostic_sweep.md](../concepts/04_diagnostic_sweep.md) |
| Population prior (used when `prior_mode = "population"`) | `population_p0` | `0.24` | [D44](#d44), [D59](#d59), [D59a](#d59a) | [04_diagnostic_sweep.md](../concepts/04_diagnostic_sweep.md) |
| Learning transition after an exercise | `t_exercise` | `0.05` | [D5](#d5) | [02_mastery_bkt.md](../concepts/02_mastery_bkt.md) |
| Learning transition after a lesson | `t_lesson` | `0.2` | [D7](#d7), [D31](#d31) | [02_mastery_bkt.md](../concepts/02_mastery_bkt.md) |
| Learning transition during the diagnostic | `t_diag` | `0.0` | [D5](#d5) | [02_mastery_bkt.md](../concepts/02_mastery_bkt.md) |
| Item model profile | `model_profile` | `"heuristic"` | [D48](#d48), [D60](#d60) | [03_item_models.md](../concepts/03_item_models.md) |
| Heuristic guess coefficient | `guess_coef` | `0.3` | [D6](#d6), [D48](#d48) | [03_item_models.md](../concepts/03_item_models.md) |
| Heuristic slip base | `slip_base` | `0.05` | [D6](#d6), [D48](#d48) | [03_item_models.md](../concepts/03_item_models.md) |
| Heuristic slip coefficient | `slip_coef` | `0.25` | [D6](#d6), [D48](#d48) | [03_item_models.md](../concepts/03_item_models.md) |
| Target success probability for exercises | `target_success` | `0.75` | [D27](#d27) | [06_planning.md](../concepts/06_planning.md) |
| Exercise repeats in new learning | `allow_exercise_repeats` | `True` | [D41](#d41) | [06_planning.md](../concepts/06_planning.md) |
| Oracle node limit | `oracle_node_limit` | `1000` | [D17](#d17) | [06_planning.md](../concepts/06_planning.md) |
| Planner method | `planner_method` | `"greedy"` | [D62](#d62) | [06_planning.md](../concepts/06_planning.md) |
| CP-SAT deterministic time limit per solve (work units) | `cpsat_max_work_units` | `10.0` | [D68](#d68) | [07_cpsat.md](../concepts/07_cpsat.md) |
| CP-SAT seed | `cpsat_seed` | `0` | [D68](#d68) | [07_cpsat.md](../concepts/07_cpsat.md) |
| Review half-life (days) | `half_life_days` | `30.0` | [D23](#d23), [D43](#d43) | [08_review_remediation.md](../concepts/08_review_remediation.md) |
| Half-life growth (ablation knob) | `half_life_growth` | `1.0` | [D23](#d23) | [08_review_remediation.md](../concepts/08_review_remediation.md) |
| Review recall threshold | `recall_threshold` | `0.8` | [D24](#d24) | [08_review_remediation.md](../concepts/08_review_remediation.md) |
| Maintenance reviews until the deadline | `maintenance_reviews` | `True` | [D43](#d43) | [08_review_remediation.md](../concepts/08_review_remediation.md) |
| Remediation threshold | `remediation_threshold` | `0.4` | [D20](#d20) | [08_review_remediation.md](../concepts/08_review_remediation.md) |
| Bisection prior | `bisection_prior` | `"uniform_states"` | [D51](#d51) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| Bisection scope | `bisection_scope` | `"goal_ancestors"` | [D54](#d54) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| Bisection stop mass (top-state posterior) | `bisection_stop_confidence` | `0.8` | [D55](#d55) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| Bisection budget floor | `bisection_n_min` | `6` | [D56](#d56) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| Bisection budget ceiling | `bisection_n_ceiling` | `40` | [D56](#d56) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| Bisection exact enumeration limit (states) | `bisection_exact_state_limit` | `5000` | [D53](#d53) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| Bisection Monte Carlo samples | `bisection_samples` | `4000` | [D53](#d53) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| Planner confirmation of diagnosed concepts | `confirm_diag_confident` | `False` | [D57](#d57) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| Confirmation ε | `confirm_epsilon` | `0.02` | [D57](#d57) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| Confirmation: maximum checks | `confirm_max_checks` | `3` | [D57](#d57) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| `bisection_config()` preset: diagnostic method | `bisection_config().diagnostic_method` | `"bisection"` | [D49](#d49), [D99](#d99) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |
| `bisection_config()` preset: planner confirmation | `bisection_config().confirm_diag_confident` | `True` | [D57](#d57), [D99](#d99) | [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md) |

## 1. Curriculum, content and review gate

Which curricula and content exist, how they are checked, and when they may be loaded (the review gate). Concept doc: [01_curriculum_graph.md](../concepts/01_curriculum_graph.md).

See also [D86](#d86) (F5 sanity evaluation of the `8node_x10` curriculum), listed under [7. Evaluation and the final study](#7-evaluation-and-the-final-study).

| # | Decision Topic | Decision Choice | Rationale & Verification | Status |
|---|---|---|---|---|
| <a id="d9"></a>**D9** | Reviewer identity in manifest | **Named non-"AI" reviewer required for live loading** | `ai_assisted: true` recorded; human sign-off left to repository owner (`vhemanth06`). Live loads reject `"AI"` reviewer. | **Active** |
| <a id="d80"></a>**D80** | Larger curriculum (F5; Plan 1 Phase A, Plan 6 Phase B) | **A 16-concept Python curriculum (`16node`) that extends the 8-node one: C1–C8 and their edges stay as they are; C9–C16 are added. The 16-node curriculum itself is built in Plan 6** | Make F5: Agreed. Concept list and edges: Adopted (Plan 1.5). Plan 1 builds only Phase A (`8node_x10`). *Status: Phase A implemented; Phase B not implemented (D91).* | **Amended by [D91](#d91)** |
| <a id="d81"></a>**D81** | Exercises per concept | **10 exercises per concept, 3 easy / 4 medium / 3 hard under the D6 classes (difficulties 0.1, 0.2, 0.3 / 0.4, 0.45, 0.55, 0.6 / 0.7, 0.8, 0.9); 1 lesson per concept. C1–C8 keep their 4 existing exercises unchanged plus 6 new ones (`E-Cn-0.1`, `0.3`, `0.45`, `0.55`, `0.7`, `0.9`)** | Adopted (Plan 1.5): 10. With 4 items per concept, F1's bisection and confirmation checks would repeat items early (D41). `tests/unit/curriculum/test_curriculum_x10.py`. | **Active** |
| <a id="d82"></a>**D82** | File names | **New files only, originals untouched: `curriculum_8node_x10.json`, `activities_8node_x10.json`, `content_8node_x10.json` (Phase A); `*_16node.json` (Phase B)** | 8-concept x10 curriculum: Agreed; file names: Adopted (Plan 1.5). `8node_x10` is a full demo curriculum and separates "more exercises" from "more concepts". Original hashes checked in `tests/unit/curriculum/test_curriculum_x10.py::test_originals_unchanged_f5_tc1`. | **Amended by [D91](#d91)** (Phase B `*_16node.json` files never built) |
| <a id="d83"></a>**D83** | Content authorship and review | **Content is AI-drafted, then reviewed by the owner. The review gate (D9) is unchanged: until the review is recorded in `data/review_manifest.json` (with `ai_assisted: true`), the new files load only with `allow_unreviewed=True`, and every demo or result using them says so** | Adopted (Plan 1.5), amended by D88: the owner review is replaced by an AI review plus an honest `PENDING_HUMAN_REVIEW` manifest entry; a named human review stays optional. The 48 new `8node_x10` exercises were drafted and AI-reviewed by Claude on 2026-11-20 (`docs/project/content_reviews/8node_x10_ai_review.md`). `tests/unit/curriculum/test_loader_review_gate.py` reads the pending files from the manifest; the F5 result file records the review status. | **Amended by [D88](#d88)** |
| <a id="d84"></a>**D84** | Synthetic generator | **`generate_synthetic_curriculum(..., exercises_per_concept=4)`; 4 gives byte-identical output to before, 10 uses the D81 spread (durations 1/2/2 by class, ids `E-Cn-1 … E-Cn-10`). Runner names `synth-N-x10`** | Adopted (Plan 1.5). `tests/test_synth.py` pins the default output (sha256 of synth-8/20/50) and checks the x10 spread. | **Historical** (the generator and `tests/test_synth.py` were in the old harness, removed by [D102](#d102); the final study generates its synthetic curricula in `experiments/core/curricula.py`) |
| <a id="d85"></a>**D85** | Content quality checks | **`scripts/check_content.py`: schema and catalogue match (`load_content`), balanced correct-answer positions per concept (no index in more than half), no duplicate or near-duplicate prompts (≥ 90% similar with the same correct answer), optional per-concept difficulty spread, and sandboxed verification of every `"verify": "output"` item** | Adopted (Plan 1.5). The sandbox runs the snippet in `python -I -S` in an empty temp dir with no environment, CPU and memory limits, a 5 s timeout, and an audit hook that blocks file, import, os, process and network events. `tests/tooling/test_check_content.py`. | **Active** |
| <a id="d87"></a>**D87** | Two phases | **Phase A (`8node_x10`: 48 new exercises, checker, review under D88) is complete and usable before Phase B (`16node`) starts; the 16-node files reuse the C1–C8 entries of `8node_x10` unchanged, enforced by a consistency check. F5 can stop after Phase A** | Agreed. *Status: Phase A implemented; Phase B not implemented (D91).* | **Amended by [D91](#d91)** |
| <a id="d88"></a>**D88** | Review handling for AI-drafted content (Plan 1.5; amends D83, keeps D9) | **AI-drafted content is checked by `scripts/check_content.py` (incl. running every `verify: output` snippet), reviewed item by item by the AI in a review file, fixed where it fails, and recorded honestly in `data/review_manifest.json`: `reviewer: "PENDING_HUMAN_REVIEW"`, `ai_assisted: true`, current `sha256`, `source: "ai-drafted, ai-checked"`, and no `edges_reviewed` for curricula. The loader treats a pending reviewer (case-insensitive, spaces ignored) as unreviewed, so the files load only with `allow_unreviewed=True`, and demo views and result files that use them say "content: AI-checked, human review pending". A named human review is optional, outside the plans, and recorded with `scripts/record_review.py --reviewer <name>`; it unblocks the files** | Adopted. Gap closed first: before Plan 1.5 the gate rejected only the reviewer `"AI"`, so a `PENDING_HUMAN_REVIEW` entry with a correct hash would have unlocked a file. D9 (named human reviewer; AI rejected) is unchanged. `record_review.py` gains `--pending` and `--ai-assisted`. `tests/unit/curriculum/test_loader_review_gate.py` (P1.5-TC1, F5-TC7), `docs/project/content_reviews/8node_x10_ai_review.md` (P1.5-TC2). *Status for `8node_x10` superseded by D93 (owner review recorded, 2026-11-20).* | **Amended by [D93](#d93)**; amends [D83](#d83) |
| <a id="d93"></a>**D93** | Human review of `8node_x10` (amends D88's status for these files) | **The owner reviewed `curriculum_8node_x10.json` (edges), `activities_8node_x10.json` and `content_8node_x10.json` on 2026-11-20. The manifest records reviewer `vhemanth06` with `ai_assisted: true` (curriculum entry `edges_reviewed: true`). The files are unchanged: their sha256 hashes equal the D88 entries. The D88 mechanism is unchanged (a pending entry never passes the gate); `content_8node.json` stays pending** | Adopted (owner, 2026-11-20). `tests/unit/curriculum/test_loader_review_gate.py::test_8node_x10_review_recorded_d93`; experiment runners now load `8node_x10` without `allow_unreviewed` and label it "reviewed" (same bytes, same results); stored result files from before D93 keep their old label. | **Active**; amends [D88](#d88) |

## 2. Mastery model and item models

How the engine turns answers and lessons into a mastery probability, and which item model predicts a correct answer. Concept docs: [02_mastery_bkt.md](../concepts/02_mastery_bkt.md), [03_item_models.md](../concepts/03_item_models.md).

Summary notes from the original file's "Methodology & Modeling Decisions" list (not numbered decisions):

- **Mastery Estimation:** Single Bayesian Knowledge Tracing (BKT) model per concept with latent learning transitions ($T_{\text{exercise}} = 0.05, T_{\text{diag}} = 0.0, T_{\text{lesson}} = 0.20$). Replaced older Beta distribution proposals.
- **Mastery Adapter & Oracle:** Standardized `MasteryModel` protocol. `CustomBKT` serves as the exact reference oracle for continuous equations; `PyBKTAdapter` maps continuous difficulty into 3 discrete item classes (easy, medium, hard) adhering to Decision D6.
- **Evidence-Mastered Definition:** Strict separation between instructional exposure (`lessons_done`), assessment observations (`responses`), and evidence-mastered ($\text{evidence\_mastered} := p \ge \theta \text{ and } \text{responses} \ge k$, default $k=2, \theta=0.85$). Lessons never mark concepts as assessed or evidence-mastered.

| # | Decision Topic | Decision Choice | Rationale & Verification | Status |
|---|---|---|---|---|
| <a id="d4"></a>**D4** | Minimum responses $k$ for evidence-mastered | **$k = 2$ and $p \ge \theta$** ($0.85$) | Requires at least two consistent observations before unlocking dependents. | **Active** |
| <a id="d5"></a>**D5** | Stored value after exercise update | **Post-transition $p''$** | Reflects latent learning resulting from the practice attempt ($T_{\text{exercise}} = 0.05$). Tests assert both $p'$ and $p''$. | **Active** |
| <a id="d6"></a>**D6** | Discrete difficulty classes for adapter | **3 classes**: easy ($d < 0.35$), medium ($0.35 \le d < 0.65$), hard ($d \ge 0.65$) | Preserves parity with pyBKT while matching continuous oracle at class-representative difficulties ($0.20, 0.50, 0.80$). | **Active** |
| <a id="d7"></a>**D7** | Instructional lesson prior shift | **Yes, via $T_{\text{lesson}} = 0.20$** | Lessons provide exposure and prior shift, but **never** set `assessed` or satisfy evidence-mastered. | **Active** |
| <a id="d31"></a>**D31** | Lessons vs Evidence Contract | **Option 1: $p \ge \theta \text{ and } \text{responses} \ge k$** | Lessons raise belief via $T_{\text{lesson}} = 0.20$ without incrementing `responses`. Unlocking evidence-mastery requires at least $k$ exercise attempts and $p \ge \theta$. Documented as intentional contract behavior; planner always schedules exercises after lessons. | **Active** |
| <a id="d33"></a>**D33** | Single Observation Model | **MasteryModel protocol used for EIG and state updates** | `compute_eig` delegates to `model.predict_correct` and `model.update(..., 0.0)`. `Engine` holds a single `MasteryModel` instance shared across diagnostic, evidence, difficulty, and planning. | **Active** |
| <a id="d48"></a>**D48** | Fitted parameter profiles | **Fitted BKT parameters are stored as named config profiles (`config/fitted_*.json`) with source and code hash; the D6 heuristic stays the default until a fitted profile beats it on held-out data** | Fits on ASSISTments 2009 / Cognitive Tutor (maths) give realistic ranges, not Python-learner values (T3.5, T7.3, T7.6). | **Active** |
| <a id="d60"></a>**D60** | Item model profile (Plan 2, F2) | **`EngineConfig.model_profile`: `"heuristic"` (default, current behaviour) or a path to `config/fitted_*.json`; the chosen model is used everywhere in the engine (D33). Recommended fitted profile: `config/fitted_assist09.json` (class guess/slip). The profile's prior is never used; its learn rate only with `use_profile_learn` (default off). `fitted_sim.json` must not be used. Cognitive Tutor (`config/fitted_ct.json`) is a cross-check profile only. The heuristic stays the default until a fitted profile beats it on held-out data (D48)** | Adopted (Plan 2). Week 7 fits predict held-out real answers better than the heuristic (ASSISTments Brier 0.195 vs 0.225, ECE 0.009 vs 0.132). `learner/profiles.py` (`load_profile`, `ClassBKT`, `build_model`, `profile_config`); `tests/unit/learner/test_profiles.py`. | **Active** |

## 3. Diagnostic: sweep and bisection

How the first assessment chooses questions and when it stops: the concept sweep (default) and bisection over knowledge states. Concept docs: [04_diagnostic_sweep.md](../concepts/04_diagnostic_sweep.md), [05_diagnostic_bisection.md](../concepts/05_diagnostic_bisection.md).

Summary notes from the original file's "Methodology & Modeling Decisions" list (not numbered decisions):

- **Adaptive Diagnosis (Milestone M2):** Active assessment based on Expected Information Gain (EIG), constrained by a global item cap $N_{\max}$ (8 in W6; 6 since the W7 T3.3 pre-registered selection, D44), per-concept cap (3 in W6; 2 since D44), entropy threshold $H \le 0.50$, and ancestor pruning at $p < 0.40$.

| # | Decision Topic | Decision Choice | Rationale & Verification | Status |
|---|---|---|---|---|
| <a id="d1"></a>**D1** | Global diagnostic item cap $N_{\max}$ | **8 items** | Bound total diagnostic assessment time to ~15 minutes while allowing coverage of key concepts. | **Superseded by [D44](#d44)** (sweep `n_max` is now 6) |
| <a id="d2"></a>**D2** | Per-concept diagnostic item cap | **3 items** | Prevents over-testing on a single concept while allowing confidence bounds. | **Superseded by [D44](#d44)** (sweep `concept_cap` is now 2) |
| <a id="d3"></a>**D3** | Entropy stop threshold $H_{\text{stop}}$ | **$H(p) \le 0.50$** ($p \le 0.11$ or $p \ge 0.89$) | Halts when latent mastery certainty exceeds ~89%. | **Active** |
| <a id="d8"></a>**D8** | Descendant pruning in diagnostic | **Prune descendants if ancestor ends with $p < 0.40$** | Skips downstream skills when prerequisite fundamentals are unmastered, saving item budget. | **Active** |
| <a id="d10"></a>**D10** | Selection tie-breaking rule | **Smaller $|d - 0.50|$, then lexicographic `activity_id`** | Prioritizes informative median-difficulty items deterministically. | **Active** |
| <a id="d34"></a>**D34** | Diagnostic Attempt ID Scope | **`diag-<session_id>-<concept_id>-<n>`** | Session scoping prevents attempt ID collisions across distinct diagnostic runs, while making exact replay of the same session and items idempotent. | **Active** |
| <a id="d39"></a>**D39** | Diagnostic evaluation protocol | **50/50 seed split; pre-declared selection rule evaluated once on held-out** | Even seeds form the tuning cohort; odd seeds form the held-out evaluation cohort. Selection rule chooses lowest tuning MAE among configurations consuming $\le 50\%$ items of the fixed arm before running held-out evaluation. | **Superseded by [D44](#d44)** (the W6 MAE rule was replaced by the pre-registered Brier rule) |
| <a id="d44"></a>**D44** | Diagnostic design and selection | **Flags `min_items_per_concept`, `pruning_mode`, `selection_scope`, `prior_mode`; defaults chosen by a pre-registered Brier rule (T3.3) → population prior 0.24, `concept_cap=2`, `n_max=6`** *(prior default partly superseded by D59: the default sweep prior is now 0.20; 0.24 via `population_prior_config()`)* | MAE |p − θ| is an improper metric for a mastery probability; the W6 D39 rule was overridden post hoc. The new rule was registered with its code hash before the run and applied as written (`docs/archive/preregistration/W7_T3.3_2026-11-08.md`, `experiments/results/w7_diag_selection.json`). | **Amended by [D59](#d59)**; supersedes [D1](#d1), [D2](#d2), [D39](#d39) |
| <a id="d49"></a>**D49** | New diagnostic (Plan 3, F1) | **`"bisection"`, selected by `EngineConfig.diagnostic_method`; the sweep stays the default and the baseline; added modularly through the `DIAGNOSTICS` registry** | Agreed. `diagnostic/bisection.py`; `tests/unit/diagnostic/test_bisection.py`. | **Active** |
| <a id="d50"></a>**D50** | Knowledge-state model | **The mastered set is prerequisite-closed (a down-set); per-concept mastery is the posterior marginal** | Agreed. `diagnostic/knowledge_space.py`; `tests/unit/diagnostic/test_knowledge_space.py`. | **Active** |
| <a id="d51"></a>**D51** | Bisection prior | **Uniform over knowledge states; `"independent_p0"` only as an experiment arm** | Agreed (uniform); comparison arm Adopted (Plan 3). | **Active** |
| <a id="d52"></a>**D52** | Question choice | **Maximum information about the whole state, I(Y;K) at the joint marginal; ties as D10** | Agreed. Noiseless chain solved in ⌈log2(L+1)⌉ (`test_noiseless_chain_is_binary_search_f1_tc4`). | **Active** |
| <a id="d53"></a>**D53** | Inference | **Exact enumeration up to `bisection_exact_state_limit` (5,000); above it seeded sequential Monte Carlo over down-sets; exact mode is the test oracle** | Adopted (Plan 3). Pure Python (no new dependency); seeded SplitMix64 because `random` is not allowed in `src/`; Rao-Blackwellised marginals. | **Active** |
| <a id="d54"></a>**D54** | Scope | **With a goal: goal ∪ ancestors(goal); otherwise all concepts** | Adopted (Plan 3). The F1 closed-loop experiment diagnoses goal ∪ ancestors for every arm. | **Active** |
| <a id="d55"></a>**D55** | Stopping | **Top-state posterior ≥ `bisection_stop_confidence` (0.80), or the budget, or no informative items** | Adopted (Plan 3); value tuned on tuning seeds in F1-T8 and frozen for the held-out runs. | **Active** |
| <a id="d56"></a>**D56** | Budget | **n_max = clamp(⌈bits · q_bit⌉, 6, 40), at most the items available; q_bit from the active item model; `bisection_alpha` an optional override** | Agreed. `tests/unit/diagnostic/test_bisection.py::test_budget_formula_f1_tc6`. | **Active** |
| <a id="d57"></a>**D57** | Planner confirmation | **Opt-in `confirm_diag_confident`: confirmed when the observation-only posterior reaches 1 − ε (ε = 0.02) with ≥ 1 direct answer; checks replace the workload when the minutes rule says testing first is cheaper, up to `confirm_max_checks` (3); gating strict; D4 unchanged for ordinary learning** | Agreed (planner confirms); ε and cost rule Adopted (Plan 3). `planner/confirmation.py`, `learner/evidence.py`; `tests/unit/planner/test_confirmation.py`. | **Active** |
| <a id="d59"></a>**D59** | Sweep diagnostic default prior (Plan 0) | **Default `prior_mode = "flat"`: the sweep starts untouched concepts at the learner's `p0 = 0.20`, replacing the pre-registered population prior 0.24 (D44, which this partly supersedes). `population_prior_config()` in `core/config.py` restores `prior_mode = "population"`, `population_p0 = 0.24` and reproduces the earlier default behaviour exactly** | Owner-approved exception to the opt-in rule, made first so every later plan pins against the final defaults. The result scripts behind the committed results (`experiments/run_evaluation.py`, `experiments/run_diag_matrix.py`) run on `population_prior_config()` and still reproduce the results in the committed result files (metadata such as `code_hash`, `git_sha` and timestamps differ). Both priors are compared as arms in Plan 3 (F1.8). Agreed. `tests/regression/test_baseline_pins.py` (P0-TC1, P0-TC2). | **Active**; amends [D44](#d44) |
| <a id="d59a"></a>**D59a** | Name of the population-prior preset (Plan 0.5) | **The preset that restores the population prior is named by what it does: `population_prior_config()` (was `w7_config()`). Its behaviour is unchanged: `EngineConfig(prior_mode="population", population_p0=0.24)`. The Plan 0 pin file, constants, test names and `record_pins.py` argument are renamed the same way (`population_prior.json`, `POPULATION_PRIOR_CONFIG`, `population`); no alias for the old name is kept** | Pure rename: no config field changes, so `config_hash` values stay as recorded in `docs/archive/notes/PLAN0_NOTES.md`; the pin file is renamed with byte-identical content. File names of committed results (`experiments/results/w7_*.json`) and earlier W7 comments are not renamed, so links to them still hold. Agreed. P0.5-TC1–TC3 (`docs/archive/notes/PLAN0_NOTES.md`). | **Active** |

## 4. Planning: greedy and CP-SAT

How the planner turns the remaining work into a day-by-day schedule: greedy with an exact oracle, CP-SAT, and the hybrid. Concept docs: [06_planning.md](../concepts/06_planning.md), [07_cpsat.md](../concepts/07_cpsat.md).

Summary notes from the original file's "Methodology & Modeling Decisions" list (not numbered decisions):

- **Path Planning & Feasibility:** Deterministic scheduler with feasibility bounds and an exact bin-packing oracle. Replaced earlier custom A* proposals with provable constraint satisfiability.

| # | Decision Topic | Decision Choice | Rationale & Verification | Status |
|---|---|---|---|---|
| <a id="d11"></a>**D11** | Multi-day eligibility | **Project workload assuming correct answers** | Project each concept's required instructional and assessment workload assuming correct responses; a concept counts as completed for downstream eligibility once its projected work is scheduled. | **Active** |
| <a id="d12"></a>**D12** | Same-day unlock | **Allowed; within-day order respects prerequisites** | If a prerequisite finishes with time remaining in the day, dependent activities may start on the same day following prerequisite order. | **Active** |
| <a id="d13"></a>**D13** | Unlock count | **Transitive descendant count (`descendant_count`)** | Rewards unlocking bottlenecks and deep downstream dependency subtrees over immediate child counts. | **Active** |
| <a id="d14"></a>**D14** | Difficulty-fit score for lessons | **0.0** | Lessons do not carry difficulty or failure probability, so difficulty fit is neutral (0.0). | **Active** |
| <a id="d15"></a>**D15** | Packing rule | **Skip non-fitting items, continue packing** | When the highest-ranked candidate exceeds remaining minutes, skip it and fill remaining budget with lower-ranked fitting candidates. | **Active** |
| <a id="d16"></a>**D16** | Within-concept order | **Lessons before exercises, enforced by queue** | Instructional lessons precede practice exercises within a concept, enforced by queue sequencing rather than heuristic score. | **Active** |
| <a id="d17"></a>**D17** | Oracle limit | **Node count integer (`oracle_node_limit`)** | Because `time`, `datetime`, and wall-clock modules are strictly prohibited in the deterministic core, search limits are bounded by branch-and-bound node expansions. | **Active** |
| <a id="d18"></a>**D18** | Day numbering | **Absolute integers from `current_day` to `deadline_day`** | Eliminates relative offset ambiguity; plan starts at `current_day` and terminates at or before absolute `deadline_day`. | **Active** |
| <a id="d19"></a>**D19** | *(reserved)* | **No decision was recorded under this ID in W4** | The W4 section heading announced D11–D19 but only D11–D18 were written; R§3 flagged the gap. The ID stays unused so later numbering is stable (W7 T9.1). | **Historical** (reserved ID; no decision was recorded under it) |
| <a id="d29"></a>**D29** | Deadline & budget derivation | **Derived pure function: initial context folded over log events; optional snapshot context** | Effective context is computed purely by folding `DEADLINE_CHANGED` and `BUDGET_CHANGED` events over initial `PlanContext`; snapshot stores optional `"context"` key. | **Active** |
| <a id="d41"></a>**D41** | Exercise repetition in new learning | **`allow_exercise_repeats=True`: unseen exercises first, then the least-recently-attempted one** | With 4 exercises per concept a few wrong answers made mastery unreachable (`CONTENT_INSUFFICIENT`) and the learner idle (R§2.3). Attempt IDs keep repeats idempotent; `CONTENT_INSUFFICIENT` now means an empty bank. `tests/unit/planner/test_planner_projection.py::test_repeats_keep_plan_feasible_after_failing_c1_t2_3`. | **Active** |
| <a id="d42"></a>**D42** | Infeasible goals | **Return `INFEASIBLE`/`UNKNOWN` + shortfall + options *and* `best_effort_days` toward the deepest reachable concept on the goal path** | An infeasible verdict used to mean an idle learner. Trace marks the schedule `BEST_EFFORT`. `tests/unit/planner/test_planner_projection.py::test_best_effort_plan_on_infeasible_t2_4`, `::test_deadline_cut_episode_never_idle_t2_4`. | **Active** |
| <a id="d43"></a>**D43** | Spaced review reachability | **`half_life_days` in config; maintenance tier schedules due reviews until `deadline_day`; one recall implementation in `review/forgetting.py`; `n_reviews` counts review attempts only** | Reviews could never fire (hard-coded h = 30, scheduler stopped when new content ended, duplicated recall formula; R§2.5). `tests/unit/review/test_review.py::test_review_due_fires_with_short_half_life_t2_6`. | **Active** |
| <a id="d62"></a>**D62** | Three planners (Plan 4, F3) | **`planner_method`: `"greedy"` (default), `"cpsat"`, `"hybrid"`; shared workload, bounds check and `Plan` output; `plan.py` dispatches** | Agreed. `planner/cpsat_planner.py`; `tests/unit/planner/test_cpsat_planner.py`. | **Active** |
| <a id="d63"></a>**D63** | Greedy untouched | **Greedy and its oracle unchanged; Week 7 behaviour reproducible** | Agreed. `tests/unit/planner/test_cpsat_planner.py::test_greedy_default_unchanged_f3_tc1`, baseline pins. | **Active** |
| <a id="d64"></a>**D64** | Hybrid | **Greedy first; when greedy misses the deadline CP-SAT decides (verdict, packing, exact shortfall and options), replacing the oracle in this mode** | Agreed. `::test_hybrid_equals_greedy_on_time_and_cpsat_on_takeover_f3_tc7`. | **Active** |
| <a id="d65"></a>**D65** | Reviews in the model | **Pure CP-SAT schedules every plan including reviews: optional tasks rewarded inside their due window, never making a goal infeasible** | Agreed. `tests/unit/planner/test_cpsat_reviews.py`. | **Active** |
| <a id="d66"></a>**D66** | One shared model | **Pure CP-SAT and hybrid's takeover use the same model** | Agreed. `planner/cpsat_model.py`. | **Active** |
| <a id="d67"></a>**D67** | Objective | **Lexicographic: goal finish; remediation early; weighted concept finish (descendants + 1); review reward; maximum daily load** | Agreed. Level 5 minimises the peak daily load (idle days are not modelled separately). | **Active** |
| <a id="d68"></a>**D68** | Determinism | **1 worker, `cpsat_seed`, deterministic work-unit limit per level, greedy hint, fixed variable order** | Agreed. `::test_cpsat_deterministic_f3_tc3`. | **Active** |
| <a id="d69"></a>**D69** | Optional dependency | **`[cpsat]` extra (`ortools==9.14.6206`), imported only when selected; a clear error, never a silent greedy fallback** | Agreed. `::test_missing_ortools_clear_error_f3_tc10`. | **Active** |
| <a id="d70"></a>**D70** | Same workload | **CP-SAT decides when, not what** | Agreed. Choosing exercise counts stays an open item. | **Active** |
| <a id="d71"></a>**D71** | CP-SAT trace | **Greedy's record shape; post-solve explanations tested for truth; one `CPSAT_SOLVE` record** | Agreed. `planner/cpsat_trace.py`; `tests/unit/planner/test_cpsat_reviews.py::test_one_record_per_activity_and_reasons_true_f3_tc8`. | **Active** |

## 5. Review, remediation and replanning

Spaced reviews, remediation after failed answers, and replanning after events. Concept docs: [08_review_remediation.md](../concepts/08_review_remediation.md), [09_replanning.md](../concepts/09_replanning.md).

Summary notes from the original file's "Methodology & Modeling Decisions" list (not numbered decisions):

- **Spaced Review:** Fixed half-life decay baseline $r(t) = 2^{-\Delta t / h}$. Half-Life Regression (HLR) is deferred unless fitting datasets and feature mappings are established.

| # | Decision Topic | Decision Choice | Rationale & Verification | Status |
|---|---|---|---|---|
| <a id="d20"></a>**D20** | Remediation trigger | **Event-driven: a response with `correct = False` leaves $p < \text{remediation\_threshold}$ ($0.40$)** | Replaces contradictory "two wrong answers" text; clean single-model trigger where a failed assessment or response drops mastery below remediation threshold (default $0.40$). | **Active** |
| <a id="d21"></a>**D21** | Remediation content | **Re-issue the concept's lesson before further exercises; clear flag when lesson completes** | Queues the concept's instructional lesson (repeat attempt) to restore prior belief before subsequent exercises; completing this lesson clears `needs_remediation`. | **Active** |
| <a id="d22"></a>**D22** | Concepts with `last_practice_day = None` | **Not review candidates; reviews begin after initial practice/lesson** | Spaced recall requires an anchor day; diagnostic probes do not set practice day, so review starts only once instructional or practice activity occurs. | **Active** |
| <a id="d23"></a>**D23** | Half-life decay baseline | **Fixed per-concept baseline ($h$); `half_life_growth = 1.0` ablation knob** | Retains deterministic baseline $r(t) = 2^{-\Delta t / h}$; half-life growth multiplier default 1.0 provides documented ablation knob. | **Active** |
| <a id="d24"></a>**D24** | Recall threshold | **`recall_threshold = 0.80` in config** | Spaced review item is triggered whenever projected recall $r(t) < 0.80$. | **Active** |
| <a id="d25"></a>**D25** | Review urgency | **$\text{urgency} = (1 - r) \cdot (1 + \text{descendant\_count})$** | Scales with forgetting depth and downstream bottleneck importance; $+1$ ensures leaf concepts maintain positive urgency. | **Active** |
| <a id="d26"></a>**D26** | Priority tier order | **Remediation $\to$ Reviews ($r < \text{threshold}$ by urgency) $\to$ New Lessons/Exercises** | Critical prerequisite remediation precedes retention reviews, which precede new curriculum advancement under the shared daily budget. | **Active** |
| <a id="d27"></a>**D27** | Review content | **Exercise chosen by difficulty policy; repeats allowed via attempt ID** | Exercises selected nearest target success $P_c \approx 0.75$; re-practicing previously completed exercises is permitted via unique attempt IDs. | **Active** |
| <a id="d28"></a>**D28** | `FAILED_ASSESSMENT` event | **Requires exercise `activity_id` and `correct = False` (or None); triggers state update & remediation check** | Fails with `ValidationError` if `correct = True`; updates posterior belief as a failed exercise attempt and triggers remediation check. | **Active** |
| <a id="d30"></a>**D30** | Replanning after missed day | **Replan from next day; missed day contributes zero minutes** | A missed day records zero elapsed minutes; revised plan begins at $\text{missed\_day} + 1$, preserving all completed work without duplication. | **Active** |
| <a id="d35"></a>**D35** | Frontier replanning memoization | **Per-concept memoization via caller-owned `WorkloadCache`** | Explicit caller-owned cache object passed to `plan` and `replan`. `Engine` has no hidden state. Replan equivalence is guaranteed by construction and verified by bitwise `Plan` equality (`==` on days, status, shortfall, trace). CLI remains full recomputation. | **Active** |
| <a id="d40"></a>**D40** | Scheduler review starvation bound | **Safety termination upon 15 consecutive starvation days or horizon exceeded** | In large curricula ($N \ge 40$) under tight budgets where daily review debt exceeds daily capacity, greedy scheduler terminates when queue progress stalls for 15 consecutive days or calendar horizon is exceeded, allowing exact oracle or shortfall resolution to take over cleanly. | **Active** |

## 6. Interfaces: CLI, store, demo

The command line, the on-disk store and the demo UI. None of them make decisions; the engine does.

Summary notes from the original file's "Methodology & Modeling Decisions" list (not numbered decisions):

- **Persistence & Atomicity:** On-disk state and log updates use an atomic snapshot protocol (`path.tmp` write, flush, fsync, `os.replace`), while in-memory transitions remain strictly immutable.

| # | Decision Topic | Decision Choice | Rationale & Verification | Status |
|---|---|---|---|---|
| <a id="d32"></a>**D32** | Atomic CLI Store (FB006) | **Single canonical snapshot store via `<path>.<pid>.tmp`** | Eliminates dual-write desynchronization. State, log, and context commit in a single atomic `os.replace`. `save_learner` and `save_log` are deprecated to explicit legacy import/export commands. | **Active** |
| <a id="d45"></a>**D45** | Demo UI | **Adapter only; the engine is the sole decision source** | The FastAPI adapter and React app contain no planning, mastery or eligibility logic; the API test asserts API plans equal direct `Engine` calls (`frontend/api/tests/test_parity.py`). | **Active** |
| <a id="d89"></a>**D89** | Command line access to config options (Plan 2.5) | **Every CLI command accepts `--config <file.json>` (EngineConfig field overrides; unknown keys and invalid values rejected through `EngineConfig` validation) and `--model-profile <path>`. Precedence: `DEFAULT_CONFIG` < `--config` < `--model-profile`; the result goes to every `Engine.from_files` call. `--model` defaults to "not given", so the Engine builds its model from the config; when given, the model is built from the effective config. `--model` with a non-heuristic profile is an error. Without the new options the CLI is unchanged** | Adopted (Plan 2.5). Before, the CLI always ran on `DEFAULT_CONFIG` and `--model` (default `custombkt`) always overrode the config, so a fitted profile could never be used from the terminal. `core/config.py::config_from_file`, `cli.py::_effective_config`; `tests/integration/test_cli_config.py`. | **Active** |
| <a id="d92"></a>**D92** | Demo UI scope (Plan FE) | **Look, shell and components follow `FRONTEND_REBUILD_SPEC.md`. Eight screens: Overview, Setup, Diagnostic, Curriculum map, Plan + Why?, Study, Disruptions, Autopilot. Setup exposes `redo`'s three switches (diagnostic, item model, planner). Policy Lab, Authoring Studio, the agent features and the Evaluation tab are not in the UI; the `/api/evaluation` route stays. No web-only engine settings. D45 holds: every label comes from engine fields** | Adopted (owner, 2026-11-20). Per-file adaptations in `docs/archive/notes/FRONTEND_NOTES.md`; `frontend/web/e2e/screens.spec.ts` (8 screens, light and dark; removed tabs absent). | **Amended by [D97](#d97)** |
| <a id="d94"></a>**D94** | Demo mode and preset | **The scripted learner answers right exactly on its known set. One demo preset lives in `frontend/api/demo.py`, served by `GET /api/demo-preset`, chosen by the fixed procedure of Plan FE §FE.6 (`frontend/api/select_demo_preset.py`). Result: `8node_x10`, goal C8, deadline 10, 10 min/day, bisection, heuristic item model, CP-SAT, known {C1, C2, C3, C6}, too-tight variant 5 min/day. No candidate asked fewer bisection than sweep questions (here 8 vs 6), so that claim is dropped from the walkthrough (§FE.6 fallback); Study step 5 answers wrong on check `E-C2-0.1`, which replans at once and leaves C2 "check pending" (a wrong answer on the first check, `E-C1-0.1`, still passes the ε test, so it is not used)** | Adopted (owner, 2026-11-20). `frontend/api/tests/test_health_preset.py::test_demo_preset` re-checks every claimed step; the selection record is in `docs/archive/notes/FRONTEND_NOTES.md`. | **Active** |
| <a id="d95"></a>**D95** | Browser tests | **Playwright covers the demo walkthrough plus smoke tests (every screen in light and dark, an unknown session, the API down, ⌘K, the theme switch, keys 1–4). Screenshots of every screen in both themes are saved as pictures (`docs/figures/ui_<screen>_<theme>.png` via `make demo-figures`) and are never compared pixel by pixel** | Adopted (owner, 2026-11-20). `frontend/web/e2e/demo.spec.ts`, `frontend/web/e2e/screens.spec.ts`; `grep -r toHaveScreenshot frontend/web/e2e` finds nothing. | **Active** |
| <a id="d96"></a>**D96** | Study days in the demo ("Next day") | **The learner keeps to the daily budget. The session context's `current_day` is the learner's day: a finished day stays on screen as "Day N complete", also once its budget is used (the engine's next slice is not shown as today), and only "Next day →" (top bar or Study; `POST /api/sessions/{sid}/next-day`) or a missed day moves it on. Events are recorded on the learner's day. Next day replans the remaining work from the new day; unused minutes are not carried over and nothing is logged. The deadline day is the last day (409). A Setup re-plan keeps the day. No engine change: the planner already starts from max(context day, day implied by the log)** | Adopted (owner, 2026-11-21; amended the same day: a finished day waits for "Next day" instead of rolling over). Before, the engine rolled to the next day silently once the budget was used, and with minutes left but nothing that fits (7 of 10 min used, next lesson longer than 3 min) day 1 never ended. `frontend/api/tests/test_sessions.py::test_finished_day_waits_for_next_day`, `::test_next_day_not_past_the_deadline`, `frontend/api/tests/test_parity.py::test_end_to_end_plan_matches_direct_engine`; `frontend/web/e2e/screens.spec.ts` ("a finished day shows as complete until Next day"). | **Active** |
| <a id="d97"></a>**D97** | Demo screens reduced to six (amends D92) | **Disruptions and Autopilot are removed from the UI: Overview, Setup, Diagnostic, Curriculum map, Plan + Why?, Study. Replans come from Study (closed loop), "Next day →" (D96) and Setup's re-plan of goal, deadline and budget. The palette's "Miss today" command went with Disruptions. `recharts` (used only by Autopilot) is removed. The API is unchanged: `/api/events` (incl. `MISSED`, `BUDGET_CHANGED`, `DEADLINE_CHANGED`) and `/api/simulate` stay with their tests** | Adopted (owner, 2026-11-21). The walkthrough's Disruptions and Autopilot steps are replaced by one "Next day" step; `frontend/web/e2e/screens.spec.ts` checks the 6 screens and that both tabs are absent; 12 screenshots in `docs/figures/`. | **Active**; amends [D92](#d92) |

## 7. Evaluation and the final study

The simulator, the evaluation arms and metrics, pre-registration, and the final study in `experiments/`. Concept docs: [10_evaluation.md](../concepts/10_evaluation.md), [11_study_statistics.md](../concepts/11_study_statistics.md).

| # | Decision Topic | Decision Choice | Rationale & Verification | Status |
|---|---|---|---|---|
| <a id="d36"></a>**D36** | Closed-loop simulator determinism | **Key-seeded pseudo-random draws per interaction** | Every simulated attempt uses a deterministic key `(seed, tag, activity_id, attempt_n)` rather than consuming a shared PRNG stream. Provides paired noise isolation across arms, 4 learner profiles, power-law retention, and documented 0.70 heuristic true mastery cutoff. | **Active** |
| <a id="d37"></a>**D37** | Planner evaluation arms | **Four arms: `adapt`, `no_review`, `no_replan`, `static`** | Disentangles benefits of closed-loop replanning, spaced retention reviews, and learner-state adaptation against a state-ignoring topological baseline. | **Active** |
| <a id="d38"></a>**D38** | Oracle assignment trace parity | **Per-activity `SELECTED` trace records with `reason="ORACLE_ASSIGNED"`** | When exact branch-and-bound packs days after greedy schedule overshoots deadline, each placed activity receives an explicit `SELECTED` record. Ensures 100% explanation trace coverage and satisfies TC7.1. | **Active** |
| <a id="d46"></a>**D46** | Primary safety metric | **Executed-state prerequisite audit (replay the real log through `engine.record`); the plan-level audit is secondary** | The W6 optimistic audit hid 183 (adapt) / 640 (static) executed violations in calm (R§2.1). With the closed loop (T2.2) adapt has 0. `experiments/checks.py::count_executed_prereq_violations`. | **Active** |
| <a id="d47"></a>**D47** | Simulator worlds and pre-registration | **Worlds S0–S4 (independent, prerequisite-gated, correlated, forgetting, BKT-generated); every new world/metric/rule is pre-registered with a timestamp and code hash before running** | Avoids tuning the simulator until adapt wins; S0 is kept and reported (`docs/archive/preregistration/W7_T4.1_2026-11-08.md`). | **Active** |
| <a id="d58"></a>**D58** | F1 evaluation | **Sweep vs bisection (with and without confirmation), pre-registered, worlds S0–S4, end-to-end metrics primary; repeated with the fitted model as the F2 Stage-2 2×2 (D61)** | Adopted (Plan 3). `docs/archive/preregistration/F1_2026-11-20.md`, `experiments/run_f1_grid.py`, `experiments/results/f1_grid.json`. | **Superseded by [D98](#d98)** (the F1 grid was not run in the final study) |
| <a id="d61"></a>**D61** | F2 evaluation (Plan 2) | **Stage 1: heuristic vs fitted_assist09 (and Cognitive Tutor as a robustness check) under the sweep diagnostic and closed-loop adapt, worlds S0–S4 and the ASSISTments-driven S4 world, W7 and Plan 1 curricula. Stage 2 (sweep vs bisection × heuristic vs fitted) runs in Plan 3. Pre-registered (D47)** | Adopted (Plan 2). `docs/archive/preregistration/F2_2026-11-20.md`, `experiments/run_f2_grid.py`, `experiments/results/f2_grid.json`. | **Superseded by [D98](#d98)** (the F2 grid was not run in the final study) |
| <a id="d72"></a>**D72** | F3 evaluation | **Greedy vs hybrid vs pure CP-SAT, pre-registered; pure CP-SAT on a pre-registered subset; full grid in Plan 7 (D90)** | Adopted (Plan 4). `docs/archive/preregistration/F3_2026-11-20.md` (draft), `experiments/run_f3_grid.py`. | **Superseded by [D98](#d98)** (the F3 grid was not run in the final study) |
| <a id="d86"></a>**D86** | F5 sanity evaluation | **Re-run the W7 baseline (sweep diagnostic, greedy closed loop, `DEFAULT_CONFIG`) on `8node` vs `8node_x10`, worlds S0–S4, W7 seeds, so later F1/F3/F4 results on the new curricula have a known baseline** | Adopted (Plan 1.5). Runner `experiments/run_f5_baseline.py`; pre-registration `docs/archive/preregistration/F5_2026-11-20.md` registered before the full run (D47); results `experiments/results/f5_baseline.json`. | **Historical** (the F5 baseline ran in the old harness; the final study leaves it out, [D101](#d101)) |
| <a id="d90"></a>**D90** | When full experiments run (Plan 3.5) | **Full pre-registered grids run at the end, in Plan 7. Each feature plan builds its runner, writes its draft pre-registration, does its tuning step and a smoke run; Plan 7 registers each grid with the final code hash and runs them all, running shared cells once. F1 run 2 moves to Plan 7 under Amendment 2 (design unchanged). Finished results (F5 baseline, F2 Stage 1, F1 run 1) stay as they are** | Adopted (owner's choice). The F1 planner fix was re-checked first on every run-1 violation cell (`experiments/results/f1_safety_check.json`: 0 violations in 37 cells × 200 learners). | **Superseded by [D98](#d98)** (Plan 7 was not run) |
| <a id="d91"></a>**D91** | Plans 5 and 6 skipped (carried over from Plan 7 T1) | **F4 (prerequisite regression handling) and F5 Phase B (16-concept curriculum) are not implemented; their content is not needed for the project goal. D73–D79 (Plan 5, F4): Not implemented (D91). D80 and D87: Phase A implemented; Phase B not implemented (D91)** | Adopted (owner, 2026-11-20). D73–D79 were drafted in the Plan 5 file and never recorded in this log; they stay unimplemented. The F4 and F5 Phase B test cases are not part of the project (`docs/project/TRACEABILITY.md`). | **Active**; amends [D80](#d80), [D82](#d82), [D87](#d87) |
| <a id="d98"></a>**D98** | Final study in `experiments_v2/`, superseding Plan 7 | **All results for the report come from one study, run on the final engine with one code hash, in a new folder with its own code and its own pre-registrations. Plan 7 and the pending pre-registrations (F1 Amendment 2, the F3 draft) are superseded and not run; they stay in `docs/` as history with a note. `experiments/` and its results are unchanged** | Adopted (owner, 2026-11-21). `experiments_v2/` (six runners, pre-registrations E1–E6), `experiments_v2/NOTES.md`; superseded notes at the top of `docs/archive/preregistration/F1_2026-11-20.md` and `F3_2026-11-20.md`. | **Amended by [D102](#d102)**; supersedes [D58](#d58), [D61](#d61), [D72](#d72), [D90](#d90) |
| <a id="d99"></a>**D99** | Baseline and arms | **The baseline is `DEFAULT_CONFIG`. Each experiment changes only the setting it studies: diagnostic method, item model, planner, confirmation checks, or one sensitivity parameter. Bisection runs at its defaults; CP-SAT at its frozen settings. E1 and E5 run without a diagnostic. Improvement is claimed only where a pre-registered paired contrast shows it** | Adopted (owner, 2026-11-21). `experiments_v2/core/arms.py` (every arm = `DEFAULT_CONFIG` or `bisection_config()` plus listed overrides). | **Active** |
| <a id="d100"></a>**D100** | Report pipeline | **Results JSON → `extract` → CSV data files (each row carries its source file and code hash) → `render` → tables (LaTeX and Markdown) and figures (PDF and PNG). Styling lives only in `experiments_v2/report/style.py`. Render scripts never read results JSON** | Adopted (owner, 2026-11-21). `make v2-report`, `make v2-figures`; `experiments_v2/tests/test_report.py` (V2-TC10–TC12). | **Active** |
| <a id="d101"></a>**D101** | What the study leaves out | **No experiment about the development history (earlier failed runs and their fixes), no F5 sanity baseline, no 0.24-prior sweep arm, no M8 or W6 runs. Those results remain in `experiments/` and the repository record** | Adopted (owner, 2026-11-21). | **Active** |
| <a id="d102"></a>**D102** | Old harness removed; `experiments_v2/` renamed to `experiments/` | **The old evaluation harness (Week 6 – Plan 4.5 runners and `experiments/results/`) is deleted from the working tree and `experiments_v2/` is renamed `experiments/`, so the repository has one evaluation folder. The old folder is archived outside the repository (`../AdaptEngine_archive/experiments_old_20261121.tgz`) and stays in git history. No experiment is re-run: the results JSONs keep their original `experiments_v2/…` paths and the harness hash they were produced with; the pre-registrations are not edited** | The final study is the only one the report uses (D98, D101). Engine code hash and `config_hash(DEFAULT_CONFIG)` unchanged; report tables and CSVs differ only in the source path, figures byte-identical; record in `experiments/NOTES.md` (Rename). Adopted (owner, 2026-11-21). | **Active**; amends [D98](#d98) |
| <a id="d103"></a>**D103** | Documentation reorganised | **`docs/` was split into `concepts/`, `reference/`, `project/` and `archive/`; `FREEZE_RECORD` and the old specs were archived; D-numbers are unchanged** | Adopted 2026-11-21. Concept explanations live in `docs/concepts/`, reference material in `docs/reference/`, project records (this file) in `docs/project/`, and superseded or historical documents in `docs/archive/` (e.g. `docs/archive/superseded/FREEZE_RECORD.md`). This file was regrouped by topic at the same time; no decision text changed. | **Active** |

## Index by number

Every D-number in numeric order, with its section and where it was first recorded (from the section headings of the earlier version of this file).

| Decision | Section | Origin | Status |
|---|---|---|---|
| [D1](#d1) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Before W4 (open decisions, defaults applied) | **Superseded by [D44](#d44)** |
| [D2](#d2) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Before W4 (open decisions, defaults applied) | **Superseded by [D44](#d44)** |
| [D3](#d3) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Before W4 (open decisions, defaults applied) | **Active** |
| [D4](#d4) | [2. Mastery model and item models](#2-mastery-model-and-item-models) | Before W4 (open decisions, defaults applied) | **Active** |
| [D5](#d5) | [2. Mastery model and item models](#2-mastery-model-and-item-models) | Before W4 (open decisions, defaults applied) | **Active** |
| [D6](#d6) | [2. Mastery model and item models](#2-mastery-model-and-item-models) | Before W4 (open decisions, defaults applied) | **Active** |
| [D7](#d7) | [2. Mastery model and item models](#2-mastery-model-and-item-models) | Before W4 (open decisions, defaults applied) | **Active** |
| [D8](#d8) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Before W4 (open decisions, defaults applied) | **Active** |
| [D9](#d9) | [1. Curriculum, content and review gate](#1-curriculum-content-and-review-gate) | Before W4 (open decisions, defaults applied) | **Active** |
| [D10](#d10) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Before W4 (open decisions, defaults applied) | **Active** |
| [D11](#d11) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W4 | **Active** |
| [D12](#d12) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W4 | **Active** |
| [D13](#d13) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W4 | **Active** |
| [D14](#d14) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W4 | **Active** |
| [D15](#d15) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W4 | **Active** |
| [D16](#d16) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W4 | **Active** |
| [D17](#d17) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W4 | **Active** |
| [D18](#d18) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W4 | **Active** |
| [D19](#d19) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W4 | **Historical** |
| [D20](#d20) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W5 | **Active** |
| [D21](#d21) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W5 | **Active** |
| [D22](#d22) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W5 | **Active** |
| [D23](#d23) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W5 | **Active** |
| [D24](#d24) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W5 | **Active** |
| [D25](#d25) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W5 | **Active** |
| [D26](#d26) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W5 | **Active** |
| [D27](#d27) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W5 | **Active** |
| [D28](#d28) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W5 | **Active** |
| [D29](#d29) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W5 | **Active** |
| [D30](#d30) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W5 | **Active** |
| [D31](#d31) | [2. Mastery model and item models](#2-mastery-model-and-item-models) | October 2026 (feedback fix) | **Active** |
| [D32](#d32) | [6. Interfaces: CLI, store, demo](#6-interfaces-cli-store-demo) | October 2026 (feedback fix) | **Active** |
| [D33](#d33) | [2. Mastery model and item models](#2-mastery-model-and-item-models) | October 2026 (feedback fix) | **Active** |
| [D34](#d34) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | October 2026 (feedback fix) | **Active** |
| [D35](#d35) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W6 | **Active** |
| [D36](#d36) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | W6 | **Active** |
| [D37](#d37) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | W6 | **Active** |
| [D38](#d38) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | W6 | **Active** |
| [D39](#d39) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | W6 | **Superseded by [D44](#d44)** |
| [D40](#d40) | [5. Review, remediation and replanning](#5-review-remediation-and-replanning) | W6 | **Active** |
| [D41](#d41) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W7 | **Active** |
| [D42](#d42) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W7 | **Active** |
| [D43](#d43) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | W7 | **Active** |
| [D44](#d44) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | W7 | **Amended by [D59](#d59)** |
| [D45](#d45) | [6. Interfaces: CLI, store, demo](#6-interfaces-cli-store-demo) | W7 | **Active** |
| [D46](#d46) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | W7 | **Active** |
| [D47](#d47) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | W7 | **Active** |
| [D48](#d48) | [2. Mastery model and item models](#2-mastery-model-and-item-models) | W7 | **Active** |
| [D49](#d49) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 3 (F1) | **Active** |
| [D50](#d50) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 3 (F1) | **Active** |
| [D51](#d51) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 3 (F1) | **Active** |
| [D52](#d52) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 3 (F1) | **Active** |
| [D53](#d53) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 3 (F1) | **Active** |
| [D54](#d54) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 3 (F1) | **Active** |
| [D55](#d55) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 3 (F1) | **Active** |
| [D56](#d56) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 3 (F1) | **Active** |
| [D57](#d57) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 3 (F1) | **Active** |
| [D58](#d58) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan 3 (F1) | **Superseded by [D98](#d98)** |
| [D59](#d59) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 0 | **Active** |
| [D59a](#d59a) | [3. Diagnostic: sweep and bisection](#3-diagnostic-sweep-and-bisection) | Plan 0.5 | **Active** |
| [D60](#d60) | [2. Mastery model and item models](#2-mastery-model-and-item-models) | Plan 2 (F2) | **Active** |
| [D61](#d61) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan 2 (F2) | **Superseded by [D98](#d98)** |
| [D62](#d62) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | Plan 4 (F3) | **Active** |
| [D63](#d63) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | Plan 4 (F3) | **Active** |
| [D64](#d64) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | Plan 4 (F3) | **Active** |
| [D65](#d65) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | Plan 4 (F3) | **Active** |
| [D66](#d66) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | Plan 4 (F3) | **Active** |
| [D67](#d67) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | Plan 4 (F3) | **Active** |
| [D68](#d68) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | Plan 4 (F3) | **Active** |
| [D69](#d69) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | Plan 4 (F3) | **Active** |
| [D70](#d70) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | Plan 4 (F3) | **Active** |
| [D71](#d71) | [4. Planning: greedy and CP-SAT](#4-planning-greedy-and-cp-sat) | Plan 4 (F3) | **Active** |
| [D72](#d72) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan 4 (F3) | **Superseded by [D98](#d98)** |
| D73–D79 | none | Plan 5 (F4), never assigned | Not in this file |
| [D80](#d80) | [1. Curriculum, content and review gate](#1-curriculum-content-and-review-gate) | Plan 1 (F5), adopted in Plan 1.5 | **Amended by [D91](#d91)** |
| [D81](#d81) | [1. Curriculum, content and review gate](#1-curriculum-content-and-review-gate) | Plan 1 (F5), adopted in Plan 1.5 | **Active** |
| [D82](#d82) | [1. Curriculum, content and review gate](#1-curriculum-content-and-review-gate) | Plan 1 (F5), adopted in Plan 1.5 | **Active** |
| [D83](#d83) | [1. Curriculum, content and review gate](#1-curriculum-content-and-review-gate) | Plan 1 (F5), adopted in Plan 1.5 | **Amended by [D88](#d88)** |
| [D84](#d84) | [1. Curriculum, content and review gate](#1-curriculum-content-and-review-gate) | Plan 1 (F5), adopted in Plan 1.5 | **Historical** |
| [D85](#d85) | [1. Curriculum, content and review gate](#1-curriculum-content-and-review-gate) | Plan 1 (F5), adopted in Plan 1.5 | **Active** |
| [D86](#d86) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan 1 (F5), adopted in Plan 1.5 | **Historical** |
| [D87](#d87) | [1. Curriculum, content and review gate](#1-curriculum-content-and-review-gate) | Plan 1 (F5), adopted in Plan 1.5 | **Amended by [D91](#d91)** |
| [D88](#d88) | [1. Curriculum, content and review gate](#1-curriculum-content-and-review-gate) | Plan 1.5 | **Amended by [D93](#d93)** |
| [D89](#d89) | [6. Interfaces: CLI, store, demo](#6-interfaces-cli-store-demo) | Plan 2.5 | **Active** |
| [D90](#d90) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan 3.5 | **Superseded by [D98](#d98)** |
| [D91](#d91) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan V2 (carried over from Plan 7 T1) | **Active** |
| [D92](#d92) | [6. Interfaces: CLI, store, demo](#6-interfaces-cli-store-demo) | Plan FE | **Amended by [D97](#d97)** |
| [D93](#d93) | [1. Curriculum, content and review gate](#1-curriculum-content-and-review-gate) | Plan FE | **Active** |
| [D94](#d94) | [6. Interfaces: CLI, store, demo](#6-interfaces-cli-store-demo) | Plan FE | **Active** |
| [D95](#d95) | [6. Interfaces: CLI, store, demo](#6-interfaces-cli-store-demo) | Plan FE | **Active** |
| [D96](#d96) | [6. Interfaces: CLI, store, demo](#6-interfaces-cli-store-demo) | Plan FE | **Active** |
| [D97](#d97) | [6. Interfaces: CLI, store, demo](#6-interfaces-cli-store-demo) | Plan FE | **Active** |
| [D98](#d98) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan V2 | **Amended by [D102](#d102)** |
| [D99](#d99) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan V2 | **Active** |
| [D100](#d100) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan V2 | **Active** |
| [D101](#d101) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan V2 | **Active** |
| [D102](#d102) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Plan V2 | **Active** |
| [D103](#d103) | [7. Evaluation and the final study](#7-evaluation-and-the-final-study) | Docs reorganisation (2026-11-21) | **Active** |

Gaps:

- **D19** is reserved and unused (row kept in section 4). The W4 heading announced D11–D19 but only D11–D18 were written. Two archived documents use the number for a feasibility lower bound (`docs/archive/notes/WEEK4_WEEK5_REPORT_PREP.md`, `docs/archive/superseded/FREEZE_RECORD.md`); that rule was never recorded here as D19, and the ID stays unused so later numbering is stable.
- **D73–D79** were never assigned. They were drafted in the Plan 5 file (F4, prerequisite regression handling), which was not implemented ([D91](#d91)). No document in `docs/archive/` mentions them; the only mention is in [D91](#d91).

## History of this file

Until 21 November 2026 this file was organised by week and plan: a summary list ("Methodology & Modeling Decisions"), then sections for D1–D10 (open decisions, defaults applied), D11–D19 (W4), D20–D30 (W5), D31–D34 (October 2026), D35–D40 (W6), D41–D48 (W7, headed "Proposed for W7, awaiting human approval"; all eight were implemented, so the heading was dropped and each row has its own status), D49–D88 (Plans 0–6), D92–D97 (Plan FE) and D91, D98–D102 (Plan V2). On 21 November 2026 it was consolidated by topic: rows were moved, given a Status column and an anchor, and D103 was added; no decision text was changed and no number was changed. The summary list was split across the topic sections. In the D1–D10 table the third column was headed "Default Applied".

Original introduction:

> This document records the finalized architectural and methodological decisions for AdaptEngine, replacing outdated prototype notes with finalized specifications.

Original note above D1–D10:

> The following decisions were flagged for human sign-off; defaults were applied to maintain progress without blocking:

Later on 21 November 2026, at the owner's request: D82 marked **Amended by D91** (its Phase B
`*_16node.json` files were never built), and D91's status lists D82; the test paths in the texts of
D45, D94 and D96 were updated from `frontend/api/tests/test_api.py` to the files that now hold those
tests (`test_parity.py`, `test_health_preset.py`, `test_sessions.py`) after that file was split, and
D94's `docs/FRONTEND_NOTES.md` to its archived path. No other decision text changed.

Also on 21 November 2026, at the owner's request: paths to moved documents inside decision texts were
updated to their new locations (`docs/archive/notes/…`, `docs/archive/preregistration/…`,
`docs/project/…`). Nothing else in those texts changed.
