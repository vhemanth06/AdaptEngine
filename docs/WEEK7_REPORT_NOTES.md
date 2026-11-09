# AdaptEngine — Week 7 Implementation & Report Notes

This evidence file contains all facts, metrics, and caveats for Week 7. Every number is sourced directly from tool execution outputs or results files. Task IDs (`T0.1` …) refer to `week7_implementation_plan.md`. No git command was run during implementation; all version-control steps are listed in §16 for the human.

---

## 1. Baseline (T0)

- **Execution Environment:** Linux 7.0.0-43-generic x86_64, Python 3.11.17 (`.venv/bin/python`); pyBKT 1.4.3, scikit-learn 1.9.1, numpy 1.26.4, pandas 3.0.6, networkx 3.4.2; Node v22.22.1.
- **Initial code hash:** `b8d35bf7ca6edd368538a6215325f7587c4fbea83ffbd7ced9b1be35057390ee` (SHA-256 over `src/**/*.py`, `python experiments/provenance.py`; no git used). Working tree started clean at HEAD `3141e3a` (from the session's starting git status).
- **Baseline Test Suite:** 171 passed, 1 xfailed in 26.55 s (pytest 8.3.3, ruff 0.8.0) — `make check`.
- **Baseline Coverage:** 89.87% (2151 statements, 218 missed; threshold 84%).
- **Verification Runners (`make w3 w4 w5 w6`):** all `OVERALL RESULT: PASS` (W6: 7/7 phases PASS).
- **Defect seen while taking the baseline:** `make check` (via `tests/test_evaluation.py`) and `make w6` (Phase 5, `--quick`) both overwrite `experiments/results/evaluation_results.json` with a 5/10-seed run (`git status` showed ` M experiments/results/evaluation_results.json` after `make check`). Fixed in T1.3.
- **W6 Baseline Evaluation (`experiments/results/w6_baseline.json`, `make eval`, 100 seeds, 15.1 s wall):**

| Scenario (nominal, budget 15) | adapt rate / θ | no_review | no_replan | static | Prereq viol. (optimistic audit) adapt / static |
|---|---|---|---|---|---|
| calm | 48.0% / 0.6617 | 48.0% / 0.6617 | 43.0% / 0.6697 | 54.0% / 0.7019 | 0 / 0 |
| missed_day | 41.0% / 0.6391 | 41.0% / 0.6391 | 32.0% / 0.5536 | 54.0% / 0.7019 | 0 / 600 |
| budget_drop | 39.0% / 0.6048 | 39.0% / 0.6048 | 43.0% / 0.6697 | 54.0% / 0.7019 | 0 / 0 (budget viol.: no_replan 100, static 200) |
| deadline_cut | 41.0% / 0.6391 | 41.0% / 0.6391 | 43.0% / 0.6697 | 54.0% / 0.7019 | 0 / 0 |

  - Diagnostic (held-out, legacy MAE): adaptive MAE(all) 0.3694, items 3.0, unassessed 48.0%; fixed@n 0.2911; fixed@8 0.2784; random@n 0.3166; random@8 0.3177. Tuning winner `h_stop=0.2, cap=2, N=4`: held-out MAE 0.3443 vs default 0.3694.
  - `metadata.code_hash` = `b8d35bf7…390ee`, `timestamp_utc` = `2026-11-08T17:26:00.690181+00:00`.
- **Executed-State Audit (after T1.1, W6 code):** adapt calm 183 (55/100 learners), static calm 640 (87/100).
- **Diagnostic vs Binary Truth (after T3.1, W6 config):** adaptive Brier 0.2425, prior-only 0.2080 (50 held-out learners).
- **Final state (end of W7):** 227 passed, 0 xfailed, coverage 90.53%; code_hash `c3cbb8f0…`.

---

## 2. Change Log

| Task | What Changed | Files Touched | Tests / Evidence |
|---|---|---|---|
| T0.6 | Created this notes file; recorded baseline (env, code hash, tests, coverage, runners, eval) | `docs/WEEK7_REPORT_NOTES.md`, `experiments/provenance.py` (new: `code_hash()`, `stamp()`) | `make check` 171 passed / 1 xfailed; `make w3 w4 w5 w6` PASS |
| T0.3 | Saved 100-seed baseline evaluation with `code_hash` + timestamp | `experiments/results/w6_baseline.json` (new) | `python experiments/run_evaluation.py` (100 seeds), §1 table |
| T0.1 | No git action; branch/merge checks listed for the human | notes §16 | §16.2 items 1–2 |
| T0.2 | `.gitignore` already covered `graphify-out/`, `learner_session.json`, `test_snapshot.json`; added CI step failing if they (or `data/external/*.csv`) are tracked; `git rm --cached` listed for the human | `.github/workflows/ci.yml`, notes §16 | `git ls-files … | wc -l` = 80 tracked paths today (read-only check) |
| T0.4 | `data/external/*` ignored, `!data/external/CHECKSUMS` re-included; frontend scratch dirs ignored | `.gitignore` | `git check-ignore -v data/external/CHECKSUMS` → negated by line 43 |
| T0.5 | Kept pip + `requirements*.txt` (what README/CI document); deleted `uv.lock` (not referenced anywhere) | `uv.lock` (deleted) | `grep -rn uv.lock` → no references |

| T8.1 | Demo content for all 40 activities of the 8-node curriculum (8 lessons, 32 four-option MCQs; correct index balanced 8/8/8/8); validating loader `load_content(path, activities)`; manifest entry `reviewer: PENDING_HUMAN_REVIEW`, `ai_assisted: true` (sha256 `e153fcbd…2898`). Every "what does this print" snippet was executed to confirm exactly one matching option. | `data/content/content_8node.json`, `data/content/README.md`, `src/adaptengine/curriculum/content.py`, `tests/test_content.py` (new); `data/review_manifest.json` | `pytest -q tests/test_content.py tests/test_loader_review_gate.py tests/test_architecture.py` → 23 passed |
| T1.1 | New primary audit `count_executed_prereq_violations(engine, start_state, log)` replays the real `ExecutionLog` through `engine.record()` and checks `is_evidence_mastered` for each direct prerequisite before every activity; old function renamed `count_plan_prereq_violations`. Episode results/JSON/tables now carry `plan_prereq_violations`, `executed_prereq_violations`, `learners_with_executed_prereq_violations`. | `experiments/checks.py`, `experiments/arms.py`, `experiments/run_evaluation.py`, `scripts/run_w6.py`, `tests/test_eval_checks.py`, `tests/test_arms.py` | New test `test_executed_audit_flags_wrong_answers_plan_audit_does_not` (all-wrong C1 learner: plan audit 0, executed > 0). Reproduces probe numbers on W6 code: adapt calm **183** (55/100 learners), static calm **640** (87/100), adapt missed_day **152** (50/100), static missed_day 600 (100/100) — `python experiments/run_evaluation.py --out <scratch>` |
| T1.2 | Vacuous `>= 0` replaced by `static plan_prereq_violations > 0` (per-seed records are missed_day runs) | `tests/test_evaluation.py` | passes |
| T1.3 | `run_evaluation(out_path=…)` + `--out` CLI flag (default unchanged, `None` = no write); tests write to `tmp_path`; `make w6` Phase 5 writes its quick runs to `runs/w6/<id>/evaluation_results_quick.json` | `experiments/run_evaluation.py`, `tests/test_evaluation.py`, `scripts/run_w6.py` | Test asserts canonical file byte-identical; md5 `6dabdf99…` identical before/after `make check` |
| T1.4 | When the oracle plan is adopted, greedy `SELECTED`/`DEFERRED` records are re-tagged `decision="GREEDY_ATTEMPT", superseded=True, greedy_decision=<old>`. Coverage audits (`stats.selected_coverage`, used by `audit_plan_trace_coverage` and `arms.compute_plan_trace_coverage`) now require exactly one `SELECTED` per planned (day, activity) occurrence and penalise extras. | `src/adaptengine/planner/plan.py`, `experiments/stats.py`, `experiments/arms.py`, `tests/test_planner.py` | Natural case 8-node / B=5 / deadline 12: W6 code 45 SELECTED for 21 activities, new audit 0.4667 on old code; after fix 21 SELECTED, audit 1.0 (`test_oracle_path_trace_natural_case_t1_4`) |
| T1.5 | Real pyBKT parity: per class, an 8-step answer sequence is run through `pyBKT.Model.predict()` and compared step by step with the adapter (`correct_predictions` vs `predict_correct`, `state_predictions` vs adapter state), tol 1e-6; a slip+0.01 perturbation must be detected (> 1e-4). Confirmed for pyBKT 1.4.3: `state_predictions[t]` is the state *before* observing step t (after step t−1's transition). Fallback narrowed to `except ImportError`. | `tests/test_feedback_fixes.py`, `src/adaptengine/learner/adapter.py` | `REQUIRE_PYBKT=1 pytest -k pybkt` → 1 passed; CI `pybkt-parity` job already runs this test |
| T1.6 | Dropped `allow_unreviewed=True` for the 8-node fixture in the evaluation (passes the review gate) | `experiments/run_evaluation.py` | full evaluation ran without the bypass |
| T2.1 | `PlanContext.minutes_used_today` (validated 0 ≤ v ≤ budget); `compute_effective_context` fills it from the log and advances the start day while the day's minutes ≥ the budget in force; scheduler starts day 1 with `budget − minutes_used_today`; feasibility bounds add the used minutes; oracle takes `used_first_day` | `core/schema.py`, `replanner/replan.py`, `planner/schedule.py`, `planner/feasibility.py`, `planner/oracle.py`, `planner/plan.py`, `tests/test_defects_repro.py`, `tests/test_planner.py` | xfail removed: `test_repro_partial_day_replan_budget_overflow` now passes and also checks every plan day; new oracle/validation tests; `pytest -q` 185 passed, 0 xfailed |
| T2.7 | `LearnerConcept.evidence_mastered` now emits `DeprecationWarning` (it always used `DEFAULT_CONFIG`); all internal/test uses switched to `is_evidence_mastered(c, cfg)` | `learner/state.py`, `tests/test_state_session.py`, `tests/test_planner.py`, `tests/test_defects_repro.py` | `pytest -W error::DeprecationWarning:adaptengine` passes; no `src/` caller left (`grep`) |
| T2.6 | (1) `EngineConfig.half_life_days` (default 30) used by `initial_state`, `LearnerConcept` default and snapshot loading (hard-coded 30.0 removed). (2) Single recall implementation: `review/forgetting.recall_at` + `urgency_from_recall`; the scheduler's inline copy deleted. (3) Maintenance tier: `EngineConfig.maintenance_reviews=True` keeps the scheduler running after new content until `deadline_day`, scheduling due reviews only; starvation counter only counts while new content remains. (4) `n_reviews` now increments only on responses to an already evidence-mastered concept (lessons no longer increment); a correct review multiplies the half-life by `half_life_growth` (default 1.0 = unchanged; previously the setting was unused). `arms.get_scenario` sizes the horizon on new-content days only so maintenance days don't stretch it. | `core/config.py`, `learner/state.py`, `learner/evidence.py`, `session.py`, `review/forgetting.py`, `planner/schedule.py`, `experiments/arms.py`, `tests/test_review.py`, `tests/test_planner.py` | `test_review_due_fires_with_short_half_life_t2_6` (h=7, deadline 21 → REVIEW_DUE records; maintenance off → none), `test_n_reviews_counts_review_attempts_only_t2_6`. TC3.1/TC3.3/8-node tests now evaluate new-content slots only (review revisits of mastered prerequisites are post-mastery, not ordering violations). `pytest -q` 187 passed |
| T2.3 | `EngineConfig.allow_exercise_repeats=True` (D41): new-learning workload prefers unseen exercises, then the least-recently-attempted one (recency = position in `done_ids`); attempt IDs keep repeats idempotent. Guard: 200 projected exercises per concept. `False` = W6 behaviour. Workload cache key uses the ordered attempt history when repeats are on. Oracle now packs unique occurrence tokens (`<aid>#<concept>#<i>`) so a repeated id can't corrupt its precedence graph. | `core/config.py`, `planner/workload.py`, `planner/plan.py`, `tests/test_w7_planner.py` | Learner failing 3 of 4 C1 items: repeats → FEASIBLE plan that re-practises C1; repeats off → `INFEASIBLE / CONTENT_INSUFFICIENT`; LRU order test; `test_plan_content_insufficient` (empty bank) still INFEASIBLE |
| T2.5 | `EngineConfig.projection_mode="optimistic"|"expected"` (default optimistic = W6). Expected mode pads each concept to ceil(Σ 1/P(correct)) exercises along the optimistic path. | `core/config.py`, `planner/workload.py`, `tests/test_w7_planner.py` | `test_expected_projection_never_fewer_items_t2_5` (budgets 5/10/15/30: expected > optimistic item count) |
| T2.4 | `Plan.best_effort_days` (D42): `plan()` wraps the goal planner; on INFEASIBLE or UNKNOWN it keeps status/shortfall/options and adds a greedy schedule toward the deepest concept on the goal's path whose workload can be built, truncated at the deadline (trace: `BEST_EFFORT` header + `best_effort: true` records). Greedy records of an abandoned schedule are re-tagged `GREEDY_ATTEMPT` on every oracle exit, not just the feasible one. `replan` and `serialize_plan` carry the field; coverage audits use `best_effort_days` when `days` is empty. | `core/schema.py`, `planner/plan.py`, `replanner/replan.py`, `experiments/stats.py`, `tests/test_w7_planner.py` | `test_best_effort_plan_on_infeasible_t2_4` (C4, deadline 2, B=5: INFEASIBLE + best-effort days ≤ day 2, ≤ 5 min); `test_deadline_cut_episode_never_idle_t2_4` (20 seeds, B=5: 0 idle days) |
| T2.2 | `Engine.next_activities(state, log, ctx) -> (PlanDay | None, Plan)`: replans from the real state (rolling horizon), returns today's slice (best-effort slice when non-FEASIBLE). `arms.run_episode`: `adapt`/`no_review` (`CLOSED_LOOP_ARMS`) call it at the start of each study day and again after every wrong answer; `no_replan`/`static` unchanged. Episodes now report `idle_days` (study day with no work while the goal isn't evidence-mastered) and `minutes_used`. `make w6` Phase 7 now also requires executed violations = 0 for adapt/no_review. | `api.py`, `experiments/arms.py`, `scripts/run_w6.py`, `tests/test_w7_planner.py`, `tests/test_arms.py`, `tests/test_evaluation.py` | `test_wrong_answer_changes_rest_of_day_t2_2`, `test_next_activities_matches_replan_first_day_t2_2`; TC8.2 frontier-equivalence suite still passes. Full 100-seed eval (scratch `--out`): adapt executed violations **0** in all 4 scenarios, all 3 robustness profiles × 3 budgets and the 8-node runs. Paired (100 seeds, nominal, B=15) adapt − static goal θ: calm **−0.0159 [−0.0341, +0.0018]**, missed_day −0.0719 [−0.0905, −0.0534]; adapt idle days 0 in both (W6 harness: 50 calm / 33 missed_day per R§2.2). Expected projection (T2.5) arm: calm +0.0008 [−0.0219, +0.0234], missed_day −0.0661 [−0.0868, −0.0454] (scratch `parity.py`). |
| T4.2 | Simulator worlds S0–S4 (done before WP3 because the diagnostic matrix T3.7 needs S0/S2/S4). `SimLearner(..., world=, prereqs=, bkt_params=)` + `make_sim(engine, seed, profile, world)`; `run_episode(..., world=, sim_kw=)`. S0 = W6 default; S1 readiness-gated gains (K=10, mid 0.70); S2 correlated g~U(0.2,0.8)+N(0,0.10) clipped [0.05,0.95]; S3 forgetting for all profiles, per-learner h~U(5,30) d; S4 BKT world (binary mastery, P0=0.20, engine g(d)/s(d), T_lesson 0.20 / T_ex 0.05, optional fitted `bkt_params`). All keyed-seed deterministic. | `experiments/sim.py`, `experiments/arms.py`, `tests/test_sim.py` | S0 byte-identical: 100-seed eval JSON before vs after the change `cmp` → identical; 3 new world tests (determinism, S1 gating, S2 spread / S3 decay / S4 BKT probabilities) |
| T3.1 | Diagnostic scored with proper scoring rules vs binary truth 1[θ ≥ 0.70]: per-learner Brier (primary), log-loss, AUC, next-response Brier on held-out probe draws (tag `probe`), 10-bin reliability + Murphy decomposition; `prior_only` arm; paired bootstrap on per-learner Brier differences (vs adaptive and vs prior-only); MAE kept as `mae_legacy` with the Pelánek footnote. Added to the evaluation JSON as `diagnostic.binary_truth`. New stats helpers `log_loss`, `reliability_bins`, `brier_decomposition`, `paired_summary`. Diagnostic runners take `world=`. | `experiments/diag_eval.py`, `experiments/stats.py`, `experiments/run_evaluation.py`, `tests/test_diag_eval.py` | Reproduces R§2.6 on the 50 held-out learners: adaptive Brier **0.2425** (AUC 0.5976), prior-only **0.2080** (AUC 0.5), fixed@n 0.2069 (paired vs adaptive −0.0356 [−0.0691, −0.0031]), random@n 0.2119, fixed@4 0.2149, fixed@8 0.2236 (AUC 0.7012); prior-only − adaptive = −0.0345 [−0.0697, +0.0001]. `test_binary_truth_scoring_t3_1` |
| T3.2 | Diagnostic flags (each default = W6 behaviour so the old diagnostic is the ablation): `min_items_per_concept` (responses before an entropy stop), `pruning_mode` hard/soft/none (soft caps undiagnosed descendants' prior at the ancestor's p), `selection_scope` concept_sweep/frontier (frontier: max-EIG unasked item across all open concepts whose in-goal prerequisites are finished; per-concept stops kept), `prior_mode` flat/population with `population_p0`. `DiagnosticResult.concept_results` is now a read-only `MappingProxyType` (T9.1 hygiene item). | `core/config.py`, `diagnostic/engine.py`, `tests/test_diagnostic.py` | Existing diagnostic/CLI/session tests unchanged and passing; 5 new tests (min-k, pruning modes, frontier DAG order + caps + determinism + read-only, population prior, validation) |
| T3.4 | Stopping-rule feasibility table (p and H after 1–2 answers at p0 = 0.20 for d = 0.2/0.5/0.8) and the effect of `min_items_per_concept` added to the diagnostic spec. One wrong answer gives H = 0.204 / 0.282 / 0.337 < h_stop 0.50 → always stops. | `docs/DIAGNOSTIC.md` §3a | values computed with `CustomBKT.update` + `entropy` (inline script, numbers in the doc) |
| T3.3 (pre-registration) | **Logged 2026-11-08T17:57:34Z, before the grid run.** Diagnostic selection rule + 648-config grid registered; code_hash `a2a144aa09daf639634afb8a4c315c515e7d66fe0118e1753a714a2eb987ceaf`. | `docs/preregistration/W7_T3.3_2026-11-08.md` (new), `docs/EVALUATION_PROTOCOL.md` §7.1 | — (run entry follows) |
| T3.3 (run + adoption) | Grid run and rule applied as written (`python experiments/run_diag_selection.py`, 15.8 s). population_p0 = 0.24 (tuning base rate). 648/648 configs eligible (≤ 8 items). **Winner:** `min_items_per_concept=1, pruning_mode=hard, selection_scope=concept_sweep, prior_mode=population, h_stop=0.50, concept_cap=2, n_max=6` (tuning Brier 0.1920, 2.58 items; tied with n_max=8 and with frontier scope, broken by the registered tuple order). Held-out (odd seeds): winner Brier **0.2324** (LL 0.7162, AUC 0.5865, next-resp 0.2970, 2.76 items) vs W6 shipped **0.2425** (AUC 0.5976, 2.96 items) vs prior-only **0.2080**. Paired: winner − shipped **−0.0101 [−0.0210, −0.0015]**; winner − prior-only +0.0244 [−0.0110, +0.0608]; shipped − prior-only +0.0345 [−0.0001, +0.0697]. Adoption condition met → `DEFAULT_CONFIG` now `prior_mode="population", population_p0=0.24, concept_cap=2, n_max=6` (W6 values kept as `experiments.diag_eval.W6_DIAGNOSTIC`). Population prior only replaces a concept still at the flat p0 with no responses (a caller-set p is kept). | `core/config.py`, `diagnostic/engine.py`, `experiments/run_diag_selection.py` (new), `experiments/diag_eval.py`, `experiments/results/w7_diag_selection.json` (new), `tests/test_diag_eval.py`, `tests/test_diagnostic.py` | JSON metadata code_hash `3060acd1…bad4b` (after adoption; grid/winner/held-out identical to the run at the registered code: compared field by field). `pytest -q` 218 passed |
| T3.6 | Stretch done: `StateSpaceDiagnostic` enumerates DAG-consistent mastery patterns (4-node: 6; 8-node: ≤ 256), exact Bayesian posterior with the engine's observation model via `MasteryModel.predict_correct(1|0, d)`, EIG over patterns, per-concept marginals; falls back to the per-concept diagnostic above 12 concepts. | `src/adaptengine/diagnostic/state_space.py` (new), `tests/test_diagnostic.py` | `test_state_space_diagnostic_t3_6` (6 patterns, marginals monotone along the DAG, deterministic, 8-node ≤ 256) |
| T3.7 | Diagnostic matrix in S0/S2/S4 at matched budgets: prior-only, W6 shipped, T3.3 default, min-k 2, soft prune, frontier, R§7.4 recommendation, state-space, fixed@n, IRT CAT global (@n, @8) and per-concept (@8). Fitted-BKT arm is wired (reads `config/fitted_sim.json`) and added once T3.5 produces it. | `experiments/run_diag_matrix.py`, `experiments/cat_baseline.py` (new), `experiments/results/w7_diag_matrix.json` | §6.2 table; runtime ≈ 25 s |
| T6.1 | `CurriculumGraph` precomputes concepts, roots, lexicographic topological order, prerequisite tuples, ancestor/descendant sets, depths and a fingerprint in `__init__` (graph is immutable); scheduler and workload build per-call exercise/activity-by-concept indices instead of scanning the catalogue per candidate; `WorkloadCache` keys include a curriculum + activity-catalogue fingerprint and the cache is bounded (`maxsize=4096`, oldest evicted). | `curriculum/graph.py`, `planner/schedule.py`, `planner/workload.py`, `experiments/run_w7_latency.py` (new), `experiments/results/w7_latency.json` (new), `tests/test_graph.py` | **Identical plans:** 564/564 plan digests unchanged (4-node/8-node/synth-20/synth-50 × B 5/10/15/30 × deadlines 3/6/12/40 + 50 random record/replan walks × 5 days on 4- and 8-node; `--snapshot` before, `--compare` after). Mean full-plan latency (20 repeats, deepest goal, deadline 200, B=15): 4-node 2.905→1.826 ms (1.59×), 8-node 5.218→3.066 (1.70×), synth-20 14.464→7.603 (1.90×), synth-50 60.448→22.496 (**2.69×**); oracle path reported separately (synth-50, B=10, deadline 58, ORACLE_ASSIGNMENT): 24.106→9.463 ms (**2.55×**). code_hash before `58c75a0f…`, after `8ef52d54…`. `pytest -q` 221 passed |
| T4.1 | **Pre-registration logged 2026-11-08T18:05:23Z, before the T4.4 runner was written or run.** Worlds, arms, scenarios (incl. stress), budgets, curricula, N, primary (executed violations; goal true-mastery rate, adapt − static paired CI) and secondary metrics, hypotheses H1–H3. code_hash `8ef52d544d11adc1704cb0a52a61411b686f623f20683c642b7d48c8c53b8e02`. | `docs/preregistration/W7_T4.1_2026-11-08.md` (new), `docs/EVALUATION_PROTOCOL.md` §7.2 | — (run entry follows) |
| T8.2 | FastAPI adapter (D45: no planning/mastery/eligibility logic; all decisions from `Engine.diagnose/next_activities/record`, `serialize_plan`, `load_content`, `experiments.arms` read-only). 9 endpoints + `GET /api/sessions/{sid}`; stepwise diagnostic via replay + `NeedAnswer`; live p bars by re-running the diagnostic with `n_max=k`; persistence `save_snapshot` + meta JSON under `frontend/.sessions/` (32-hex session ids, path-traversal safe); engine `ValidationError` → 422, unknown session → 404, out-of-order → 409; replan latency measured server-side. `demo` extra in `pyproject.toml`. | `frontend/__init__.py`, `frontend/api/{__init__,app,schemas,store}.py`, `frontend/api/tests/{__init__,test_api}.py`, `pyproject.toml` | `pytest -q frontend/api/tests` → 9 passed (end-to-end session: API plan and today's slice equal a direct `Engine` call after every step) |
| T8.3 | Vite 6 + React 18 + TS 5.6 + Tailwind 4 + @xyflow/react 12 + Recharts 2 + TanStack Query 5; TS types generated from the OpenAPI schema (`npm run gen:types`). Seven screens: Setup (status/shortfall/options/best-effort), Diagnostic (keys 1–4, live p bars, stop reasons), Map, Plan timeline, "Why?" panel (score components, deferred alternatives, superseded greedy records), Study, Disruptions (old vs new plan diff + latency). | `frontend/web/**` (see §16.1) | `npm run build` → `tsc --noEmit` clean, vite build OK |
| T8.4 | Autopilot (all 4 arms via `/api/simulate`), Evaluation page (results JSON charts, paired CIs, latency table), deterministic demo mode (scripted learner, reset), Okabe-Ito palette + text labels, 19 px base type, keyboard answers, offline (no CDN). | `frontend/web/src/pages/{Autopilot,Evaluation}.tsx` etc. | visual check by screenshots |
| T8.5 | Playwright e2e of the 6-minute demo script (`e2e/demo.spec.ts`, single uvicorn server on :8765 serving API + `dist`); optional CI `demo` job (`continue-on-error: true`); `make demo-api/demo-web/demo-test`; `frontend/README.md`. | `frontend/web/e2e/demo.spec.ts`, `frontend/web/playwright.config.ts`, `.github/workflows/ci.yml`, `Makefile`, `frontend/README.md` | `npx playwright install chromium` OK; `npm run build && npx playwright test` → 1 passed |
| T5.1 | Allowed budgets come from `EngineConfig.allowed_budgets`: hard-coded `(5, 10, 15, 30)` removed from `PlanContext` and `Event(BUDGET_CHANGED)` (schema keeps positive-int checks); `check_budget(value, allowed)` used by the planner and `load_snapshot(..., cfg=)`; `Engine.record` already checked BUDGET_CHANGED against config. `half_life_days` config was added in T2.6. Error text unchanged ("budget must be one of …"), so the CLI test still matches. | `core/validators.py`, `core/schema.py`, `planner/plan.py`, `session.py`, `tests/test_api.py`, `tests/test_planner.py`, `tests/test_w7_planner.py` | `test_allowed_budgets_from_config_t5_1` (budget 20 plans when configured, rejected by default); `pytest -q` 222 passed |
| T5.4 | `EngineConfig.mastery_criterion` = `bkt_threshold` (D4 default) / `n_consecutive` (last `n_consecutive` responses correct) / `two_threshold` (D4 and H(p) ≤ `certainty_max_entropy`). New `LearnerConcept.correct_streak` (updated in `update_concept_evidence`, serialised in snapshots, default 0 on load). `mastered_by(p, responses, streak, cfg)` is the single criterion used by `is_evidence_mastered`, the workload projection and the plan-level audit. | `core/config.py`, `learner/state.py`, `learner/evidence.py`, `session.py`, `planner/workload.py`, `experiments/checks.py`, `tests/test_mastery.py` | 2 new tests (criteria semantics; streak tracking + FEASIBLE plans under each criterion); `pytest -q` 224 passed |
| T9.1 (docs) | Traceability register: 23 IDs kept; 11 stale test references fixed (e.g. no `test_tc3_1_…`; real names `test_prerequisite_safety_tc31` etc.; every cited test now exists — checked by a grep loop); TC2.1 equal-budget error clause restored and reported as **not met in S0/S2, met in S4**; W7 evidence added to TC3.1/3.2/3.4/4.1/7.1. `DECISIONS.md`: D19 recorded as reserved (never written), D41–D48 added, diagnostic caps updated. `FREEZE_RECORD.md` §2.1 lists D35–D48 as implemented/proposed (not frozen). `ARCHITECTURE.md`: cache key (now includes a curriculum fingerprint), graph indices, `next_activities`. `schema.md`: `PlanDay.activities/duration`, `Event.value`, `PlanContext.minutes_used_today`, `Plan.best_effort_days`, `correct_streak`, `n_reviews`. `EVALUATION_PROTOCOL.md`: §1 provenance claim corrected, N ≈ 2.96 items. `pyproject.toml` version 0.3.0. `AI_USE.md` W6/W7 addendum. | `docs/TRACEABILITY.md`, `docs/DECISIONS.md`, `docs/FREEZE_RECORD.md`, `docs/ARCHITECTURE.md`, `docs/schema.md`, `docs/EVALUATION_PROTOCOL.md`, `docs/AI_USE.md`, `pyproject.toml` | grep loop: 0 missing test references |
| T9.1 (code hygiene) | Loader hashes and parses the **same bytes** (single read; a missing file still reports the review-gate error first); default manifest path raises a clear error when absent (packaged installs must pass `manifest_path`); `concept_results` read-only (done in T3.2); CLI `--allow-unreviewed` on one parent parser (12 duplicate declarations removed); `ExecutionLog.attempt_ids` index gives O(1) duplicate checks in `Engine.record`. | `curriculum/loader.py`, `cli.py`, `learner/state.py`, `api.py` | `pytest -q` 224 passed |
| T9.3 | `IMPLEMENTATION_PLAN.md` W7 row marked done with its deliverables; `TEST_SUITE.md` gained Suites 19–20 and a list of W7 additions per existing suite, with TC/task links. | `docs/IMPLEMENTATION_PLAN.md`, `docs/TEST_SUITE.md` | — |
| T9.2 | D41–D48 registered (see T9.1 docs row). | `docs/DECISIONS.md` §7 | — |
| T7.0 | `data/external/CHECKSUMS` written; prefixes match the inventory (`f22e3fb7872c1784`, `162ef8d2d28bcbfe`, `161e598a609ecdf8`); `data/external/csedm2019/` did not exist (nothing to delete); `.gitignore` covers `data/external/*` (T0.4). | `data/external/CHECKSUMS` (kept by `!data/external/CHECKSUMS`) | `sha256sum` |
| T7.1 | `scripts/download_data.py`: re-downloads `as.csv`/`ct.csv` from `raw.githubusercontent.com/CAHLR/pyBKT-examples/master/data/` (HEAD → 200, sizes equal local), verifies checksums; manual instructions + checksum for the collapsed ASSISTments file; `--verify-only` (no network), `--dest`. | `scripts/download_data.py` | `--verify-only` → 3 × ok, exit 0 (0.30 s); scratch `--dest` download of `ct.csv` → checksum ok |
| T7.2 | `experiments/fit_bkt.py`: `pybkt_pipeline` (pyBKT `Model(seed, num_fits=5).fit` → `crossvalidate(folds=5, ['rmse','auc'])` → `params()`), constraint checks (degenerate: G+S ≥ 1, guess > 0.5 or slip > 0.5; prior < 0.01 flagged separately; fits never altered), `fast_em` (vectorised numpy EM of the same model with pyBKT's init ranges/stopping rule), profile writer refusing G+S ≥ 1. pyBKT on `ct.csv` (12 KCs): fit 127.0 s, fit + CV 1159.6 s; 2/12 degenerate (guess > 0.5), 2 with prior < 0.01. | `experiments/fit_bkt.py`, `tests/test_fit_bkt.py`, `experiments/results/bkt_fit_ct_pybkt.json` | `pytest -q tests/test_fit_bkt.py` → 9 passed (skips cleanly without pyBKT); fast_em vs pyBKT ≤ 1e-6 from the same start (incl. multigs); crafted degenerate case flagged |
| T7.3 | ASSISTments 2009 (`as.csv`): cleaning 525,534 → 449,220 (`original==1`) → 421,318 (has skill) → 300,389 (one row per order_id×skill) → **297,016** rows, 81 skills ≥ 100 students, 4,125 students, correct rate 0.6608. Per-skill BKT medians [IQR]: prior 0.680 [0.583–0.848], learn 0.113 [0.060–0.207], guess 0.164 [0.093–0.337], slip 0.196 [0.136–0.266]; 4/81 degenerate (4.9%). Pooled multigs by D6 class (200 student bootstraps): p0 0.741 [0.721–0.764], learn 0.0725 [0.067–0.080], guess easy/med/hard 0.369/0.147/0.058, slip 0.132/0.342/**0.646** (hard slip > 0.5 recorded as warning). Held-out 5-fold (by student) RMSE / log-loss / AUC: fitted class profile **0.4414 / 0.5753 / 0.7072** vs engine heuristic D6 **0.4746 / 0.6438 / 0.6858** (ECE 0.0086 vs 0.1324); fitted wins in every fold. Runtime 981 s (8 workers). | `experiments/results/bkt_fit_assist09.json`, `config/fitted_assist09.json` (new) | `python experiments/fit_bkt.py assist09 --boot 200` |
| T7.4 | CSEDM 2019 deferred to W8 (0-byte DataShop download). | — | see §15 |
| T7.6 | Cognitive Tutor (`ct.csv`): 9 of 12 KCs ≥ 100 students (15,935 rows, 550 students); 2/9 degenerate (22.2%). Held-out RMSE fitted class 0.4549 vs heuristic D6 0.4952; same shape as ASSISTments (guess falls and slip rises with difficulty; hard slip > 0.5; high priors 0.63–0.74 vs engine p0 0.20). Runtime 311 s. | `experiments/results/bkt_fit_ct.json` | `python experiments/fit_bkt.py ct --boot 200` |
| T7.7 | Data manifest: source URLs, citations (ASSISTments page request: its URL + Feng, Heffernan & Koedinger 2009; ct.csv from KDD Cup 2010 → Stamper et al. 2010 template), access date 8 Nov 2026, layouts, counts, full SHA-256, cleaning counts, maths caveat; verified both ASSISTments files hold the same 346,860 order_ids with identical user/correct. | `docs/data_manifest.md` | — |
| T3.5 | Simulated part: `experiments/fit_bkt_sim.py` fits prior/learn + guess/slip per D6 class (fast_em, best of 5) on the tuning cohort's exercise answers from closed-loop adapt episodes (4-node, B=15, calm; `run_episode` now returns `exercise_log`) and compares fitted vs the heuristic forward filter on held-out learners. **S0** (567 tuning / 544 held-out answers): fitted p0 0.484, learn 0.245, guess easy/med/hard 0.518/0.548/0.026, slip 0.008/0.327/0.241 (easy and medium guess > 0.5 → warnings); held-out fitted vs heuristic RMSE **0.4586 vs 0.5716**, Brier 0.2103 vs 0.3267, log-loss 0.6108 vs 0.8672, AUC 0.5702 vs 0.5436, ECE 0.037 vs 0.336. **S4** recovery check: fitted Brier 0.2411 vs heuristic 0.2710, but AUC 0.6160 vs 0.6314; guess recovered roughly (0.266/0.146/0.103 vs true 0.24/0.15/0.06 at representative d), slips not (hard 0.014 vs 0.25: few hard items), learn absorbs the unmodelled lesson transitions (0.215). Profile `config/fitted_sim.json` written (G+S < 1 enforced). Real-data part: T7.3/T7.6. Heuristic stays the default (D48). | `experiments/fit_bkt_sim.py`, `experiments/arms.py`, `config/fitted_sim.json`, `experiments/results/bkt_fit_sim.json` (new) | `python experiments/fit_bkt_sim.py` (7 s) |
| T3.7 (fitted arm) | Matrix re-run with the `fitted_bkt` arm (PyBKTAdapter with `fitted_sim` class params): worse than the W6 diagnostic in S0/S2/S4 (see §6.2). | `experiments/results/w7_diag_matrix.json` | `python experiments/run_diag_matrix.py` |
| T4.3 | Parameter provenance table: every simulator parameter has its value/range and either a real-data comparison (fitted learn/slip/prior ranges from ASSISTments/CT, with the maths caveat) or the label "synthetic assumption". | `docs/EVALUATION_PROTOCOL.md` §8 | — |
| T7.5 | Fit results fed into: provenance table (T4.3); S4-fitted world (`sim.s4_fitted_params(profile)`: class g/s, prior, learn from `config/fitted_assist09.json`); calibration comparison (§8, T6.3); profile registered under D48. **Exploratory (not pre-registered)** S4-fitted run, 4-node, B=15, N=200: calm adapt goal mastery 86.0% vs static 86.0% (Δ 0.000 [−0.035, +0.035]), all required 74.0% vs 54.5%, executed violations 0 vs 1335; missed_day adapt 79.5% vs static 86.0% (Δ −0.065 [−0.110, −0.025]), all required 61.0% vs 46.0%, violations 0 vs 1200. | `experiments/sim.py`, `experiments/run_s4_fitted.py` (new), `experiments/results/w7_s4_fitted.json` (new), `tests/test_sim.py` | `test_s4_fitted_world_t7_5`; `python experiments/run_s4_fitted.py` |
| T4.4 (as registered) | Full grid run exactly at the registered code_hash `8ef52d54…` (`python experiments/run_w7_grid.py`, 420 cells, 3429 s, 15 processes) → kept as `experiments/results/w7_grid_prereg.json`. **H1 failed:** executed violations summed over all cells — adapt 6192 (138 cells; 90 of them outside forgetting_21), adapt_expected 1149 (95 cells), adapt_h7 25,521 (57 cells), while no_review and no_review_h7 had **0**. Attribution on a replayed episode (8-node, S1, h=7, seed 1000): the violating activity's trace reason was `REVIEW_DUE`. | `experiments/run_w7_grid.py` (new), `experiments/results/w7_grid_prereg.json` (new) | see Defect 7 |
| T4.4 fix | Scheduler prerequisite gate now applies to Tier 0 (remediation) and Tier 1 (reviews) too: no activity for a concept while a direct prerequisite has queued work. Regression test fails on the pre-fix scheduler and passes after (checked by temporarily reverting the line). Full grid, sensitivity and S4-fitted runs re-run at code_hash `eba675d1…` → `w7_grid.json`; both runs are reported. | `planner/schedule.py`, `tests/test_w7_planner.py` | `test_reviews_wait_for_prerequisite_relearning_t4_4_fix`; `pytest -q` passing |
| T4.4 fix 2 | Re-run after fix 1 (`w7_grid_fix1.json`, code_hash `eba675d1…`): residual executed violations adapt 53 (32 cells), adapt_expected 24 (13), adapt_h7 257 (35); no_review still 0. Replayed case (synth-20, S1, B=10, forgetting_21, seed 1110, day 21): plan `INFEASIBLE` → best-effort schedule toward a shallower target whose workload omits prerequisite C2 (p 0.197, needs remediation), so a `REVIEW_DUE` of C4 passed the "in queues" gate. Gate for tiers 0/1 now requires each prerequisite to be evidence-mastered at plan start or completed in the projection. Re-running only the 80 previously violating cell/arm units: **0** violations (8 m 45 s). Final grid + sensitivity + S4-fitted + canonical eval re-run at code_hash `c3cbb8f0…`. | `planner/schedule.py`, `tests/test_w7_planner.py`, `experiments/results/w7_grid_fix1.json` (new) | `test_reviews_wait_for_unmastered_prerequisite_outside_workload_t4_4_fix` fails on fix 1, passes now; `make check` 227 passed, 90.53% |
| T4.4 (final) | Final grid at code_hash `c3cbb8f0…` (`python experiments/run_w7_grid.py`, 420 cells, 3228 s, 15 processes) → `experiments/results/w7_grid.json`; tables/figures generated into `docs/WEEK7_RESULTS.md` §1 and `docs/figures/w7_forest_adapt_vs_static.png` by `python experiments/make_w7_results.py`. **H1 met:** executed violations adapt 0, adapt_expected 0, adapt_h7 0, no_review 0 (no_replan 1,229,249; static 1,649,720). Idle days summed over cells: adapt 0, no_replan 150,429, static 103,074. **H2 (S1 headline, N=1000):** adapt 29.0% vs static 28.7%, Δ +0.003 [−0.008, +0.014] — not lower (met), not higher. **H3:** adapt_h7 ≠ no_review_h7 (goal θ, paired CI excludes 0) in 32 of 60 forgetting_21 cells; positive in 11 (e.g. S0 8-node +0.041 [+0.032, +0.051]), negative in 21 (e.g. S0 synth-20 −0.030 [−0.052, −0.010]). Over all 420 cells adapt vs static goal mastery: better in 35, no significant difference in 226, worse in 159 (§1.4 of the results file); all-required mastery: better 45, ≈ 354, worse 21. | `experiments/run_w7_grid.py`, `experiments/make_w7_results.py` (new), `experiments/results/w7_grid.json` (new), `docs/WEEK7_RESULTS.md` (new), `docs/figures/` (new) | results file + figure |
| T4.5 | Loss explanations written for every adapt-loses pattern (§5.3). | `docs/WEEK7_REPORT_NOTES.md` §5.3, `docs/WEEK7_RESULTS.md` | — |
| T5.2 / T5.3 | One-at-a-time scans (θ, k, h, p0, T_lesson, recall_threshold, remediation_threshold) and the 3×3 θ×k factorial, worlds S0/S1 × 4-/8-node, B=15, calm (horizon fixed from DEFAULT_CONFIG), N=200 → `w7_sensitivity.json` (code_hash `c3cbb8f0…`, 65.3 s). Executed violations 0 for every configuration. | `experiments/run_sensitivity.py` (new), `experiments/results/w7_sensitivity.json` (new) | §7 |
| T5.5 | Tornado charts (one per cell) and full tables with paired CIs vs the baseline config. | `docs/figures/w7_tornado_*.png`, `docs/WEEK7_RESULTS.md` §2 | — |
| T6.2 | Safety improvement (executed-state audit, nominal, 4-node, B=15, 100 seeds): calm **W6 adapt 183 → W7 adapt 0** vs static 640; missed_day 152 → 0 vs static 600 (`make eval`, final `evaluation_results.json`). Over the whole grid: adapt 0 vs static 1,649,720. | `experiments/results/evaluation_results.json` | `make eval` |
| T6.3 | Calibration improvement (held-out, 5-fold by student): ASSISTments fitted class profile vs heuristic D6 RMSE 0.4414 vs 0.4746, log-loss 0.5753 vs 0.6438, AUC 0.7072 vs 0.6858, ECE 0.0086 vs 0.1324; CT 0.4549 vs 0.4952; simulated S0 0.4586 vs 0.5716. Reliability figure `docs/figures/w7_reliability_assist09.png`. | `docs/WEEK7_RESULTS.md` §6 | T3.5, T7.3, T7.6 |
| T6.4 | Diagnostic improvement: pre-registered winner vs W6 shipped, held-out Brier 0.2324 vs 0.2425, paired −0.0101 [−0.0210, −0.0015] (S0). Limits: not better than prior-only in S0/S2; slightly worse than W6 in S4 (+0.0032). | `experiments/results/w7_diag_selection.json`, `w7_diag_matrix.json` | T3.3, T3.7 |
| T7.5 (final) | S4-fitted exploratory run re-run at `c3cbb8f0…` (`w7_s4_fitted.json`). | `experiments/results/w7_s4_fitted.json` | `python experiments/run_s4_fitted.py` |
| T9.4 | W7 report written only from this file: `docs/WEEK7_REPORT.md` (10 sections per plan §T9.4) rendered to `docs/weekly/Week7_report.pdf` (Python `markdown` → HTML → headless Chrome; `markdown` installed into `.venv` for this). Numbers re-checked against the results files (one wrong count found and fixed before rendering: 226 / 159, not 230 / 155). | `docs/WEEK7_REPORT.md`, `docs/weekly/Week7_report.pdf` (new) | visual check of the PDF pages |
| Final fixes | Two regressions found by the final gates: (1) `make w4` TC3.3 counted D43 maintenance-review days → runner now counts new-content days, like the unit test; (2) the demo API accepted budget 7 after T5.1 moved budget membership to config → adapter validates with `core.validators.check_budget(ctx.budget, engine.config.allowed_budgets)` (engine validator, D45 intact). | `scripts/run_w4.py`, `frontend/api/app.py` | `make w4 w5 w6` PASS; `pytest frontend/api/tests` 9 passed |

**WP exit gates:**
- WP0: 2026-11-08 — baseline recorded, runners PASS — gate met.
- WP1: 2026-11-08 — `make check` 184 passed, 1 xfailed, coverage 89.85%; executed audit numbers recorded against the baseline — gate met.
- WP2: 2026-11-08 — `make check` 209 passed, 0 xfailed, coverage 90.28%; `make w6` PASS (Phase 7 includes the executed audit). Adapt executed violations = 0 in every scenario/profile; idle days = 0; calm goal θ at parity with static (paired CI spans 0) — gate met. Missed_day still behind static (see §11).
- WP3: 2026-11-08 — diagnostic flags, proper metrics, pre-registered selection applied as written, matrix S0/S2/S4 incl. fitted and state-space arms — gate met (with the negative results in §11).
- WP4: 2026-11-09 — pre-registered grid run; H1 failed on the registered code (Defect 7), fixed twice, final re-run H1 met (0 executed violations in all 420 cells); H2 met (parity); H3 mixed — gate met with deviation logged.
- WP5: 2026-11-09 — scans, factorial, criteria, tornado charts; 0 executed violations — gate met.
- WP6: 2026-11-09 — latency 1.59–2.69× with 564/564 identical plans; safety 183 → 0; calibration and diagnostic improvements with CIs — gate met.
- WP7: 2026-11-08 — fits with CIs, heuristic vs fitted held-out comparison, provenance table, checksums, manifest — gate met (CSEDM deferred).
- WP8: 2026-11-08 — full demo incl. Playwright pass — gate met.
- WP9 / final: 2026-11-09 — `make check` **227 passed, 0 xfailed, coverage 90.53%**; `make w3 w4 w5 w6` all PASS; `make poc` PASS; `pytest frontend/api/tests` 9 passed; `REQUIRE_PYBKT=1 pytest -k pybkt` passed; `make demo-test` (Playwright) 1 passed; final code_hash `c3cbb8f066c6cc843e611d19149d7f543c91c65afe652df6181b4fa22ca9f0a5`; `evaluation_results.json` byte-identical across `make check` (md5 check) — gate met.

---

## 3. Defects Found and Fixed

1. **Optimistic prerequisite audit hid executed violations (R§2.1):**
   - *Symptom:* W6 tables reported 0 prerequisite violations for adapt in every scenario.
   - *Root Cause:* `count_prerequisite_violations` replayed executed activities assuming every answer was correct.
   - *Fix:* (T1.1) executed-state audit over the real log; plan audit kept as secondary.
   - *Evidence:* adapt calm 183 / static calm 640 executed violations on W6 code (Change Log T1.1).
2. **Tests and `make w6` overwrote the canonical results artifact (R§2.9):**
   - *Symptom:* after `make check`, `evaluation_results.json` held a 5-seed quick run.
   - *Root Cause:* hard-coded output path in `run_evaluation`.
   - *Fix:* (T1.3) `out_path` parameter / `--out` flag.
   - *Evidence:* md5 unchanged across `make check`.
3. **Stale greedy records on the oracle path (R§2.8, TC7.1):**
   - *Symptom:* 45 SELECTED records for 21 planned activities (8-node, B=5, deadline 12); coverage audit still reported 1.0.
   - *Root Cause:* oracle records appended after the abandoned greedy trace; audit only checked "at least one" record.
   - *Fix:* (T1.4) superseded re-tagging + exactly-one audit.
   - *Evidence:* `test_oracle_path_trace_natural_case_t1_4`.
4. **pyBKT parity test was vacuous; any exception silently disabled pyBKT (R§2.7):**
   - *Fix:* (T1.5) stepwise library-vs-adapter test with a perturbation check; `except ImportError` only.
5. **`PyBKTAdapter` model cache ignored `class_params` (found during T1.5):**
   - *Symptom:* an adapter built with custom class parameters reused the pyBKT model fitted with the default parameters.
   - *Root Cause:* cache key held config scalars only.
   - *Fix:* (T1.5) class parameters added to the cache key.
6. **Population prior overwrote caller-set priors (found during T3.3, before adoption):**
   - *Symptom:* `test_surprise_response_and_cap` (C1 deliberately at p = 0.9) failed once `prior_mode="population"` became the default: the diagnostic reset p to 0.24.
   - *Root Cause:* the flag replaced every concept with no responses.
   - *Fix:* (T3.3) only concepts still at the flat cold-start prior (p == p0, no responses) are replaced.
   - *Evidence:* re-running the selection gives a field-identical grid/winner/held-out result; full suite 218 passed.
7. **Spaced reviews and remediation bypassed the prerequisite gate (found by the pre-registered T4.4 audit):**
   - *Symptom:* adapt arms had executed prerequisite violations (adapt 6192, adapt_h7 25,521 summed over cells) while the identical arms without review had 0.
   - *Root Cause:* the scheduler checked "no prerequisite with queued work" only for Tier-2 new content; a due review (Tier 1) or remediation lesson (Tier 0) of a dependent concept could run while a prerequisite that lost its evidence after a wrong review answer was being relearned.
   - *Fix:* (T4.4 fix 1) the same gate for every tier; (fix 2) for reviews/remediation a prerequisite must be evidence-mastered at plan start or completed in the projection, which also covers best-effort schedules whose workload omits an unmastered prerequisite.
   - *Evidence:* two regression tests, each failing on the preceding code; violations 6192 → 53 → 0 on the affected units (§5).

---

## 4. Corrected W6 Results (old vs new, side by side)

All "corrected" values are on the **W6 code** (baseline `code_hash b8d35bf7…`), re-measured with the W7 audits/metrics; sources in brackets.

| W6 claim / number | W6 value | Corrected value | Source |
|---|---|---|---|
| adapt prerequisite violations, calm | 0 | **183** activities, 55/100 learners (executed-state audit) | T1.1 run on W6 code |
| static prerequisite violations, calm | 0 | **640** activities, 87/100 learners | T1.1 |
| adapt prerequisite violations, missed_day / deadline_cut | 0 / 0 | **152** (50 learners) / **152** (50) | T1.1 |
| adapt prerequisite violations, budget_drop | 0 | **28** (10 learners) | T1.1 |
| no_replan prerequisite violations, calm | 0 | **360** (84 learners) | T1.1 |
| "AdaptEngine guarantees 100% prerequisite safety" | executed episodes | true for **plans** only; executed safety achieved in W7 by the closed loop (0 in every cell) | T1.1, T2.2 |
| Diagnostic quality metric | MAE |p − θ| | Brier vs 1[θ ≥ 0.70]: adaptive **0.2425** vs prior-only **0.2080** (diagnostic worse than none) | T3.1 |
| "Assessed-only parity" (W6 §5.2) | parity | adaptive assessed-only MAE 0.3852 vs fixed@n 0.2555 — not parity | `w6_baseline.json` |
| Adaptive diagnostic items | N ≈ 2.7 | **2.96** (50 held-out learners) | `w6_baseline.json`, T3.1 |
| Diagnostic defaults (W6 report §4.2) | h_stop 0.35, cap 2, N 8 | code was h_stop **0.50**, cap **3**, N **8**; W7 T3.3 rule now sets population prior 0.24, cap 2, N 6 | `core/config.py` |
| Planner BKT parameters (W6 PDF §5.3) | L0 0.20, T 0.10, G 0.15, S 0.15 | p0 0.20, g(d) = 0.30(1 − d), s(d) = 0.05 + 0.25d, T_ex 0.05, T_lesson 0.20, T_diag 0 | `core/constants.py` |
| Nominal half-life (W6 PDF §5.4) | "simulator h = 30 days" | nominal **simulator has no forgetting**; 30 days was the planner's hard-coded value | `experiments/sim.py`, T2.6 |
| Oracle trace (TC7.1) | 100% coverage | 45 SELECTED records for 21 activities (8-node, B=5, deadline 12); exactly-one audit 0.4667 | T1.4 |
| Committed `evaluation_results.json` | "100 seeds" | file held a 5-seed quick run (tests overwrote it) | T1.3 |
| D39 diagnostic selection | rule winner overridden | W7 pre-registered rule applied as written | T3.3 |
| Version | reports `v0.2.0-mvp` | `pyproject.toml` said 0.1.0; now 0.3.0 | T9.1 |
| Decision IDs in W6 report | D36 "selection", D38 "cache kept", D40 "mid-day overflow" | `DECISIONS.md`: D36 simulator determinism, D38 oracle trace parity, D40 starvation bound; D19 never written | `docs/DECISIONS.md` |
| Test paths for TC6.1–6.4 | `tests/test_replanner.py` | file doesn't exist; tests are in `tests/test_w5.py` | `docs/TRACEABILITY.md` |
| Spaced review effect | adapt = no_review everywhere | structurally unreachable in W6 (h = 30 hard-coded, scheduler stopped after new content) | T2.6 |

## 5. Closed-Loop Evaluation (S0–S4 Matrix)

Source: `experiments/results/w7_grid.json` (final, code_hash `c3cbb8f0…`); registered run `w7_grid_prereg.json` (`8ef52d54…`) and intermediate `w7_grid_fix1.json` (`eba675d1…`). Full tables: `docs/WEEK7_RESULTS.md` §1.

### 5.1 H1 — executed prerequisite violations summed over all cells

| Arm | Registered run (cells) | After fix 1 (cells) | Final (cells) |
|---|---|---|---|
| adapt | 6192 (138) | 53 (32) | **0 (0)** |
| adapt_expected | 1149 (95) | 24 (13) | 0 (0) |
| adapt_h7 | 25,521 (57) | 257 (35) | 0 (0) |
| no_review / no_review_h7 | 0 / 0 | 0 / 0 | 0 / 0 |
| no_replan | 1,229,249 (400) | same | same |
| static | 1,649,720 (405) | same | same |

### 5.2 Headline cells (4-node, B=15, calm, N=1000)

| World | adapt | static | Δ goal mastery [95% CI] | Δ goal θ | Δ θ at equal minutes | Exec. viol. adapt / static | Minutes adapt / static |
|---|---|---|---|---|---|---|---|
| S1 | 29.0% | 28.7% | +0.003 [−0.008, +0.014] | +0.003 [−0.000, +0.006] | −0.012 [−0.015, −0.009] | 0 / 7200 (926 learners) | 47.0 / 42.0 |
| S0 | 42.6% | 43.9% | −0.013 [−0.036, +0.010] | −0.026 [−0.033, −0.020] | −0.055 [−0.064, −0.047] | 0 / 6710 (916) | 45.5 / 42.0 |

All-required mastery (headline): S1 adapt 3.9% vs static 1.8%; S0 7.3% vs 2.5%. adapt_expected: S1 27.3% (Δ vs static −0.014 [−0.025, −0.003]).

### 5.3 Where adapt loses, and why (T4.5)

- **S0 (independent abilities, unconditional gains), most scenarios:** static spends every planned minute on the goal regardless of prerequisite readiness and S0 rewards raw minutes on the goal concept; adapt first re-practises prerequisites the learner failed. Same reason adapt loses to no_replan in many S0/S2 cells (188 of 420 cells overall) while no_replan has 1.2 M executed violations.
- **missed_day / budget_drop / deadline_cut (S0, S2, S4):** adapt replans the remaining days toward evidence-mastered prerequisites first; with a 3–5 day horizon the goal gets fewer minutes (e.g. S0 4-node missed_day −0.105 [−0.155, −0.055]; static 1200 violations).
- **8-node (S1 calm −0.025 [−0.045, −0.005]):** longer prerequisite chains at B=15 in a fixed short horizon; adapt reaches the goal later. All-required mastery is 0% for both, i.e. the horizon is too short to separate policies on that outcome.
- **S4 (BKT world) calm −0.150 [−0.210, −0.090]:** adapt stops practising a concept once *it believes* it is mastered (p ≥ 0.85, k = 2); in S4 that belief is calibrated, so remaining minutes go to other required concepts — all-required mastery is higher (+0.125 [+0.080, +0.175]) while the goal alone is lower. With a 21-day horizon (forgetting_21) the sign flips: +0.405 [+0.340, +0.475].
- **θ at equal minutes is negative in most cells:** adapt spends minutes on prerequisites/reviews before the goal, so at the same minute count the goal concept has had less practice. This is the cost of the safety guarantee.
- **Spaced review (h = 7):** helps in 11 forgetting cells and hurts in 21 (e.g. synth-20: reviews of 20 concepts crowd out new content in 21 days). Reviewed concepts show *lower* retention than non-reviewed ones (e.g. S0 8-node 0.260 vs 0.341) because reviews are triggered for the concepts that are being forgotten (selection effect), so this column is not a causal estimate.
- **Expected-workload projection:** worse than optimistic in 113 cells, better in 9 — it schedules more items per concept and reaches the goal later.

Wins: stress cases missed_2days and deadline_halved give small positive deltas in every world (e.g. S2 4-node +0.035 [+0.010, +0.060]); S3 4-node calm +0.060 [+0.010, +0.110]; S4 forgetting_21 +0.405; all-required mastery better in 45 cells and worse in 21.

## 6. Diagnostic Matrix & Calibration

### 6.1 Pre-registered selection (T3.3, world S0, 4-node, 50 held-out learners)

| Arm | Brier (↓) | Log-loss | AUC | Next-resp. Brier | Items |
|---|---|---|---|---|---|
| prior only | 0.2080 | 0.6113 | 0.500 | 0.2955 | 0 |
| W6 shipped (flat, cap 3, N 8) | 0.2425 | 0.7386 | 0.5976 | 0.3071 | 2.96 |
| **T3.3 winner (population prior 0.24, cap 2, N 6)** | **0.2324** | 0.7162 | 0.5865 | 0.2970 | 2.76 |

Paired per-learner Brier differences: winner − shipped −0.0101 [−0.0210, −0.0015]; winner − prior-only +0.0244 [−0.0110, +0.0608]. Source: `experiments/results/w7_diag_selection.json`.

### 6.2 Diagnostic matrix across worlds (T3.7; 250 held-out learners, odd seeds 101–599, nominal, 4-node)

Brier vs 1[θ ≥ 0.70] (lower is better). Source: `experiments/results/w7_diag_matrix.json` (`python experiments/run_diag_matrix.py`, code_hash `854912fa…`, includes the `fitted_bkt` arm from `config/fitted_sim.json`). IRT CAT arms use the simulator's true a = 3 (an advantage in the IRT worlds S0/S2).

| Arm | Items (S0) | S0 Brier / AUC | S2 Brier / AUC | S4 Brier / AUC | S4 Δ vs prior-only [95% CI] |
|---|---|---|---|---|---|
| default_t33 | 2.73 | 0.2234 / 0.5913 | 0.1888 / 0.5851 | 0.1139 / 0.7753 | -0.0455 [-0.0569, -0.0343] |
| fitted_bkt | 2.15 | 0.2368 / 0.5943 | 0.2129 / 0.5858 | 0.1266 / 0.772 | -0.0328 [-0.0475, -0.0185] |
| fixed@n_default | 2.73 | 0.2019 / 0.6195 | 0.1673 / 0.6306 | 0.1309 / 0.7724 | -0.0285 [-0.0381, -0.0196] |
| frontier | 2.95 | 0.2282 / 0.5945 | 0.1889 / 0.5922 | 0.1107 / 0.7826 | -0.0487 [-0.0606, -0.0374] |
| irt_cat_global@8 | 8.00 | 0.2298 / 0.5818 | 0.1515 / 0.755 | 0.1619 / 0.7187 | +0.0025 [-0.006, 0.0109] |
| irt_cat_global@n | 2.73 | 0.2170 / 0.5836 | 0.1583 / 0.7092 | 0.1607 / 0.6382 | +0.0013 [-0.0055, 0.008] |
| irt_cat_per_concept@8 | 8.00 | 0.1785 / 0.7174 | 0.1578 / 0.6602 | 0.0771 / 0.9434 | -0.0823 [-0.0922, -0.0723] |
| min_k2 | 5.20 | 0.2244 / 0.6515 | 0.1987 / 0.6389 | 0.0995 / 0.8455 | -0.0599 [-0.0724, -0.0476] |
| prior_only | 0.00 | 0.2050 / 0.5 | 0.1450 / 0.5 | 0.1594 / 0.5 | +0.0000 [0.0, 0.0] |
| r74_recommended | 8.00 | 0.2280 / 0.7025 | 0.2226 / 0.6698 | 0.0589 / 0.9453 | -0.1005 [-0.1148, -0.0854] |
| soft_prune | 5.71 | 0.2390 / 0.6421 | 0.1978 / 0.6458 | 0.0686 / 0.8566 | -0.0908 [-0.105, -0.0766] |
| state_space | 3.12 | 0.2520 / 0.5666 | 0.1925 / 0.6259 | 0.1319 / 0.6105 | -0.0275 [-0.0411, -0.0144] |
| w6_shipped | 2.95 | 0.2282 / 0.5945 | 0.1889 / 0.5922 | 0.1107 / 0.7826 | -0.0487 [-0.0606, -0.0374] |

Reading: (1) No BKT diagnostic beats the prior in S0 or S2; only the per-concept IRT CAT does in S0 (−0.0265). (2) In S4 (the engine's own BKT world) every BKT arm beats the prior; the R§7.4 recommendation (min 2 items, no pruning, frontier, 8 items) is best (0.0589, AUC 0.945) and soft pruning is best among ≤ 6-item arms (0.0686). (3) The T3.3 winner was chosen in S0 and is slightly worse than the W6 diagnostic in S4 (+0.0032): the selection world drives the answer, as R§7.4 predicted. (4) The state-space arm's DAG-consistent prior is misspecified in all three worlds (their initial abilities ignore the DAG) and it under-performs. (5) The global-ability CAT is the best of all in S2 by AUC (0.755) and no better than the prior in S4. (6) The fitted-BKT arm (class g/s fitted on simulated S0 practice data, T3.5) is worse than the W6 diagnostic in every world (S0 +0.0085 [+0.0004, +0.0170], S2 +0.0240, S4 +0.0159): parameters fitted on post-lesson practice answers transfer badly to a cold-start diagnostic, and two of its classes are degenerate (guess > 0.5).

## 7. Sensitivity Analysis

Source: `experiments/results/w7_sensitivity.json` (code_hash `c3cbb8f0…`); tables/tornado figures in `docs/WEEK7_RESULTS.md` §2. Cells S0/S1 × 4-/8-node, B=15, calm, N=200, horizon fixed from DEFAULT_CONFIG. Example (S0, 4-node; baseline goal mastery 38.5%, static 37.0%):

| Setting | Goal mastery (minutes) |
|---|---|
| θ 0.70 / 0.85 / 0.90 / 0.95 | 38.0% (46.5) / 38.5% (46.8) / 38.0% (48.7) / 32.0% (54.1) |
| k 1 / 2 / 3 / 4 | 38.5% / 38.5% / 36.0% (51.5) / 32.5% (54.0) |
| h 7 / 14 / 30 / 60 | 35.5% / 38.5% / 38.5% / 38.5% |
| p0 0.1 / 0.4 | 38.5% (48.3) / 40.0% (45.6) |
| T_lesson 0.1 / 0.3 | 37.5% / 39.0% |
| recall_threshold 0.7–0.9 | 38.5% (no change: reviews rarely due in a 4-day horizon) |
| θ×k: θ 0.95 any k | 32.0%, Δ −0.065 [−0.115, −0.020] |
| criterion n_consecutive 2 / 3; two_threshold | 38.0% / **26.0%** (Δ −0.125 [−0.185, −0.070]) / 38.0% |

Reading: in a fixed short horizon, stricter mastery evidence (θ ≥ 0.95, k ≥ 3, 3-in-a-row) costs goal mastery because more minutes go to prerequisites; the engine is insensitive to θ in 0.70–0.90, to recall/remediation thresholds and to h ≥ 14. Executed violations are 0 in every configuration.

## 8. Measured Improvements (latency, safety, calibration, diagnostic)

| Improvement | Before | After | Evidence |
|---|---|---|---|
| Latency (T6.1), identical plans (564/564) | synth-50 full plan 60.448 ms; oracle cell 24.106 ms | 22.496 ms (2.69×); 9.463 ms (2.55×) | `w7_latency.json` |
| Safety (T6.2), executed violations, 4-node calm, 100 seeds | W6 adapt 183 (static 640) | W7 adapt 0 | `evaluation_results.json`; grid: adapt 0 in 420 cells |
| Calibration (T6.3), held-out RMSE | heuristic 0.4746 (ASSISTments), 0.4952 (CT), 0.5716 (sim S0) | fitted 0.4414, 0.4549, 0.4586 | `bkt_fit_*.json` |
| Diagnostic (T6.4), held-out Brier (S0) | W6 0.2425 | 0.2324, Δ −0.0101 [−0.0210, −0.0015] | `w7_diag_selection.json` |

Limits: the fitted profiles are **not** adopted as defaults (maths data; fitted-sim parameters made the diagnostic worse, §6.2); the diagnostic gain is within S0 and does not beat prior-only.

## 9. Real-Data Parameter Fitting & Provenance

### 9.1 Two-domain comparison (T7.3, T7.6)

| Param | ASSISTments 2009 (81 skills) | Cognitive Tutor (9 KCs) |
|---|---|---|
| prior, per skill median [IQR] | 0.680 [0.583–0.848] | 0.586 [0.278–0.684] |
| learn, per skill | 0.113 [0.060–0.207] | 0.230 [0.134–0.384] |
| guess, per skill | 0.164 [0.093–0.337] | 0.290 [0.081–0.379] |
| slip, per skill | 0.196 [0.136–0.266] | 0.140 [0.114–0.307] |
| % degenerate | 4.9% (4/81) | 22.2% (2/9) |
| pooled class prior / learn (95% CI) | 0.741 (0.721–0.764) / 0.073 (0.067–0.080) | 0.634 (0.347–0.743) / 0.117 (0.091–0.141) |
| guess easy / medium / hard | 0.369 / 0.147 / 0.058 | 0.477 / 0.277 / 0.002 |
| slip easy / medium / hard | 0.132 / 0.342 / 0.646 | 0.111 / 0.366 / 0.634 |
| held-out RMSE fitted class vs heuristic D6 | 0.4414 vs 0.4746 | 0.4549 vs 0.4952 |

Sources: `experiments/results/bkt_fit_assist09.json`, `bkt_fit_ct.json`. **Caveat:** both datasets are school maths, not Python; the parameters give realistic ranges/shapes for the simulator and a calibration benchmark, not values for this project's learners.

## 10. Demo Frontend Status

All of WP8 runs (not only the solo-fallback subset): adapter, 7 screens, autopilot, evaluation page, deterministic demo mode and a passing Playwright run of the demo script. Known points:
- Map "Unlocked (today)" / "Locked (later)" reflect the engine's schedule (today's slice vs later days), not UI-computed eligibility (D45).
- Demo step 1 (5 min/day, deadline 10) currently returns `UNKNOWN / ORACLE_LIMIT_EXCEEDED` with best-effort days, not INFEASIBLE; the UI treats any non-FEASIBLE status the same. A clean INFEASIBLE needs e.g. deadline 5.
- The adapter calls `next_activities` after every event (a superset of the recommended loop).
- Content for the 8-node curriculum is AI-drafted and still `PENDING_HUMAN_REVIEW`.
- Optional src improvement for W8: a stepwise `next_item`/`apply` API on `AdaptiveDiagnostic` to replace the replay trick.

## 11. What Did Not Improve

- **Goal mastery vs static:** adapt is better in 35 of 420 grid cells, not significantly different in 226, worse in 159 (§5.3). The W7 gain is safety (0 vs 1.65 M executed violations), no idle days and all-required mastery (better in 45 cells, worse in 21), not goal mastery.
- **Spaced review:** h = 7 reviews help in 11 forgetting cells and hurt in 21.
- **Expected-workload projection:** worse than optimistic in 113 cells.
- **Fitted parameters in the diagnostic:** worse than the heuristic in S0/S2/S4.
- **Alternative mastery criteria:** none beat D4; 3-in-a-row costs 12.5 points of goal mastery in S0 4-node.

- **Diagnostic vs no diagnostic (S0):** even the pre-registered winner is not better calibrated than the prior alone (winner − prior-only +0.0244 [−0.0110, +0.0608] Brier). In S0 abilities are independent and responses come from a 2PL IRT model with a = 3, so 2–3 BKT-scored items per learner carry little information about 1[θ ≥ 0.70]. See T3.7 for S2/S4.

- **Closed loop vs static under S0 (nominal simulator), missed_day:** adapt −0.0719 [−0.0905, −0.0534] goal θ vs static even with 0 executed violations, because S0 gains ignore prerequisite readiness and static still runs every goal activity after the missed day (static: 600 executed violations). Calm is parity, not a win. (T2.2; addressed by the pre-registered S1 world in WP4, not by tuning.)
- The R§2.3 prototype reported calm +0.0125 [−0.006, +0.031]; the shipped closed loop gives −0.0159 [−0.0341, +0.0018]. Difference: the prototype treated every exercise as re-eligible immediately, the shipped D41 rule prefers unseen exercises first and repeats least-recently-seen ones.

## 12. Acceptance Register (All 23 TC IDs & Milestones)

All 23 IDs are listed with current test evidence in `docs/TRACEABILITY.md`. W7 status changes:

| TC | W7 status | Evidence |
|---|---|---|
| TC2.1 | Stopping: verified. Equal-budget error clause (restored): **not met in S0/S2, met in S4** | `w7_diag_matrix.json` |
| TC3.1 | Verified at plan level **and** for executed episodes (0 executed violations, 420 grid cells, after Defect 7) | `test_eval_checks.py`, `test_arms.py`, `w7_grid.json` |
| TC3.2 | Verified incl. mid-day replans (W6 xfail now passes) | `test_defects_repro.py` |
| TC3.4 | Verified; INFEASIBLE now also carries a best-effort schedule (D42) | `test_w7_planner.py` |
| TC4.1 | Verified; pyBKT parity now stepwise against the library | `test_feedback_fixes.py` |
| TC7.1 | Verified; exactly one SELECTED per planned activity, natural oracle case | `test_planner.py` |
| TC8.1 | Verified; tests no longer overwrite the artifact | `test_evaluation.py` |
| TC8.2 | Verified; 564 plans identical after T6.1 | `w7_latency.json`, `test_replan_frontier.py` |
| Others (TC1.x, 2.2, 2.3, 3.3, 3.5, 3.6, 4.2, 5.x, 6.x) | Unchanged, verified | `docs/TRACEABILITY.md` |

## 13. Limitations

- All closed-loop results are synthetic; worlds S0–S3 use synthetic dynamics (§8 of `EVALUATION_PROTOCOL.md` lists which parameters are assumptions). Real-data fits are school maths, not Python.
- Short horizons (3–6 days in most cells) leave all-required mastery near 0 for 8-node/synth-20, so those cells can't separate policies on that outcome.
- The grid was re-run twice after the registered run because the audit found a real defect; the final numbers are therefore post-hoc with respect to the scheduler fix (both earlier runs are kept).
- The diagnostic is not better than the prior in S0/S2; TC2.1's equal-budget clause is not met there.
- Retention of reviewed vs non-reviewed concepts is confounded by selection (reviews target forgotten concepts).
- The demo content is AI-drafted and awaits human review; the CI `demo` job has never run on GitHub.
- pyBKT runs outside the pinned scikit-learn range locally (1.9.1 vs < 1.6); CI pins < 1.6.
- Fit results carry three different code hashes (src changed between runs; the fits use only constants and class boundaries, which did not change).

## 14. Reproduction Commands

Run from the repo root with `.venv/bin/python` (Python 3.11). Every results file records its `code_hash` and UTC timestamp.

| What | Command | Output |
|---|---|---|
| Tests + lint + coverage | `make check` | — |
| Acceptance runners | `make w3 w4 w5 w6` | `runs/w*/` |
| Canonical 100-seed evaluation (W6 tables + W7 executed audit + binary-truth diagnostic) | `make eval` | `experiments/results/evaluation_results.json` |
| W6 baseline (before any W7 change) | n/a (snapshot) | `experiments/results/w6_baseline.json` |
| Diagnostic selection (pre-registered T3.3) | `python experiments/run_diag_selection.py` | `experiments/results/w7_diag_selection.json` |
| Diagnostic matrix S0/S2/S4 (T3.7) | `python experiments/run_diag_matrix.py` | `experiments/results/w7_diag_matrix.json` |
| Simulated BKT fit (T3.5) | `python experiments/fit_bkt_sim.py` | `experiments/results/bkt_fit_sim.json`, `config/fitted_sim.json` |
| Data check / re-download (T7.1) | `python scripts/download_data.py --verify-only` | — |
| pyBKT pipeline on CT (T7.2) | `python experiments/fit_bkt.py pybkt --data data/external/ct.csv` | `experiments/results/bkt_fit_ct_pybkt.json` |
| ASSISTments fits (T7.3) | `python experiments/fit_bkt.py assist09 --boot 200` (~16 min, 8 workers) | `experiments/results/bkt_fit_assist09.json`, `config/fitted_assist09.json` |
| CT fits (T7.6) | `python experiments/fit_bkt.py ct --boot 200` (~5 min) | `experiments/results/bkt_fit_ct.json` |
| Full grid (T4.4) | `python experiments/run_w7_grid.py` (~57 min, 15 processes) | `experiments/results/w7_grid.json` |
| Sensitivity (WP5) | `python experiments/run_sensitivity.py` | `experiments/results/w7_sensitivity.json` |
| S4-fitted (T7.5, exploratory) | `python experiments/run_s4_fitted.py` | `experiments/results/w7_s4_fitted.json` |
| Latency + plan identity (T6.1) | `python experiments/run_w7_latency.py --snapshot A.json` (before) / `--compare A.json --timing-out B.json` (after) | `experiments/results/w7_latency.json` (assembled before/after) |
| Results tables and figures | `pip install -e .[figures]` then `python experiments/make_w7_results.py` | `docs/WEEK7_RESULTS.md`, `docs/figures/w7_*.png` |
| Demo | `pip install -e .[demo]`; `make demo-test` (see `frontend/README.md`) | — |

Seeds: evaluation 100–199 (tuning even / held-out odd); diagnostic matrix odd 101–599; grid and sensitivity 1000–1199 (headline 1000–1999); fits seed 42; bootstrap CI seed 20260.

## 15. Deviations from Plan

| Task | Planned | Actual | Reason |
|---|---|---|---|
| T4.2 | WP4, Day 4 | Done before WP3 | T3.7 needs the S0/S2/S4 worlds |
| T6.1 | WP6, Day 6 | Done before the WP4 grid | The ~480k-episode grid needed the speed-up; plan identity proven on 564 plans before it ran |
| WP8 | No git commands during implementation | The frontend sub-agent ran one read-only `git diff --stat pyproject.toml Makefile` | Process slip (read-only; nothing changed in git); recorded for transparency |
| T7.3/T7.6 | Fits with pyBKT | Large fits, bootstraps and CV use `fast_em` (same model, parity-tested vs pyBKT); pyBKT itself run on ct.csv (T7.2) | pyBKT 1.4.3 is pure Python here (~66 s per 5k-row skill); fast_em matches pyBKT ≤ 1e-6 from the same start, its log-likelihood ≥ pyBKT's − 0.024 on every CT KC |
| T7.3 | 76 skills | 81 skills | Plan counted one row per order_id; the per-(order_id, skill) rule keeps multi-skill answers |
| T7.3 | Unrated items dropped | Items with < 20 answers get a 4th "unrated" g/s class (fitted, not in the profile) | Keeps student sequences whole |
| T7.4 | CSEDM 2019 fit | Deferred to W8 | DataShop dataset 2865 download returned 0 bytes |
| WP7 | One code_hash for all fit results | `bkt_fit_assist09.json` `e3e519c0…`, `bkt_fit_ct_pybkt.json` `3c3eb761…`, `bkt_fit_ct.json` `854912fa…` | `src/` changed between runs; the fits only use `core/constants.py` and `get_difficulty_class`, which did not change. A re-run at the final hash is listed in §14 |
| T4.4 | One pre-registered grid run | Two runs: the registered one (H1 failed, kept and reported) and a re-run after the Defect-7 fix | The audit found a real scheduler defect; fixing it and re-running is a post-hoc change, so both results are reported and the fix is labelled as such |
| T6.1 | Frontier vs full | Frontier ≈ full latency in this benchmark | With the D43 maintenance tier and deadline 200, scheduling (not workload projection) dominates, so the WorkloadCache saves little; reported as measured |
| T3.2 | `min_items_per_concept` default 2 | Flag default 1 (W6 behaviour); every new flag defaults to the W6 behaviour | Shipped defaults change only through the pre-registered T3.3 rule, so that the change is not a post-hoc choice (the D39 problem) |
| T3.2 | `prior_mode` population "p0 estimated on the tuning cohort" | `population_p0` config value; the T3.3 grid sets it to the tuning-cohort base rate | Keeps the engine free of evaluation data |

## 16. Git Actions for the Human

### 16.1 New and Modified Files Inventory

From `git status --short` (read-only) at the end of W7.

- **Modified (59):** `.github/workflows/ci.yml`, `.gitignore`, `Makefile`, `pyproject.toml`, `data/review_manifest.json`; docs `AI_USE.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `DIAGNOSTIC.md`, `EVALUATION_PROTOCOL.md`, `FREEZE_RECORD.md`, `IMPLEMENTATION_PLAN.md`, `TEST_SUITE.md`, `TRACEABILITY.md`, `data_manifest.md`, `schema.md`; experiments `arms.py`, `checks.py`, `diag_eval.py`, `run_evaluation.py`, `sim.py`, `stats.py`, `results/evaluation_results.json` (100-seed, final code), `results/replan_latency.json` (regenerated by `make w6`); scripts `run_w4.py`, `run_w6.py`; src `api.py`, `cli.py`, `core/{config,schema,validators}.py`, `curriculum/{graph,loader}.py`, `diagnostic/engine.py`, `learner/{adapter,evidence,state}.py`, `planner/{feasibility,oracle,plan,schedule,workload}.py`, `replanner/replan.py`, `review/forgetting.py`, `session.py`; tests `test_{api,arms,defects_repro,diag_eval,diagnostic,eval_checks,evaluation,feedback_fixes,graph,mastery,planner,review,sim,state_session}.py`.
- **Deleted:** `uv.lock`.
- **New:** `config/fitted_assist09.json`, `config/fitted_sim.json`; `data/content/{content_8node.json,README.md}`; `data/external/CHECKSUMS`; `docs/{WEEK7_REPORT.md,WEEK7_REPORT_NOTES.md,WEEK7_RESULTS.md}`, `docs/figures/w7_*.png` (6), `docs/preregistration/{W7_T3.3_2026-11-08.md,W7_T4.1_2026-11-08.md}`, `docs/weekly/Week7_report.pdf`; experiments `cat_baseline.py`, `fit_bkt.py`, `fit_bkt_sim.py`, `make_w7_results.py`, `provenance.py`, `run_diag_matrix.py`, `run_diag_selection.py`, `run_s4_fitted.py`, `run_sensitivity.py`, `run_w7_grid.py`, `run_w7_latency.py`; results `bkt_fit_{assist09,ct,ct_pybkt,sim}.json`, `w6_baseline.json`, `w7_{diag_matrix,diag_selection,grid,grid_fix1,grid_prereg,latency,s4_fitted,sensitivity}.json`; `frontend/` (see T8.2–T8.5; `node_modules/`, `dist/`, `test-results/`, `.sessions/` are ignored); `scripts/download_data.py`; `src/adaptengine/curriculum/content.py`, `src/adaptengine/diagnostic/state_space.py`; tests `test_content.py`, `test_fit_bkt.py`, `test_w7_planner.py`.
- **Do not commit:** `runs/` (already ignored), `frontend/**/__pycache__/`, raw CSVs in `data/external/`.

### 16.2 Commands for the Human (run after verification, in order)

1. Confirm the W6 work is on `main`: `git log --oneline main | head` and `git branch -a --contains <last-week6-commit>`; check `git reflog | grep week6` for the W6 hygiene commits (R§2.9). (T0.1)
2. Create the W7 branch from the current `main`: `git switch -c week7`. (T0.1)
3. Untrack scratch files and raw data (T0.2, T0.4): `git rm -r --cached graphify-out learner_session.json test_snapshot.json data/external/as.csv data/external/assist09_skill_builder.csv data/external/ct.csv`
4. Remove the deleted lock file from the index (T0.5): `git rm --cached uv.lock` (or let `git add -A` record the deletion).
5. Review AI-drafted content before committing it as reviewed: read `data/content/content_8node.json`, then `python scripts/record_review.py data/content/content_8node.json --reviewer <name> --source "ai-drafted, human-reviewed"` and re-add `"ai_assisted": true` to that manifest entry.
6. Verify: `make check && make w3 w4 w5 w6 && pytest -q frontend/api/tests && make demo-test` (expect 227 passed; all runners PASS).
7. Commit in the groups of §16.3 (pre-registration files first, so their history shows they predate the result files): `git add <files>` then `git commit -m "<message>"` per group.
8. Tag the release: `git tag -a v0.3.0 -m "AdaptEngine 0.3.0 (Week 7)"`.
9. Push branch and tag: `git push -u origin week7 && git push origin v0.3.0`; open a PR `week7 → main`.

### 16.3 Suggested Commit Progression (one group per WP)

1. `docs: W7 pre-registrations (T3.3, T4.1)` — `docs/preregistration/`.
2. `chore(W0): baseline, provenance helper, gitignore, CI scratch guard, drop uv.lock` — `.gitignore`, `.github/workflows/ci.yml` (T0.2 step), `experiments/provenance.py`, `experiments/results/w6_baseline.json`, `uv.lock` deletion, `docs/WEEK7_REPORT_NOTES.md`.
3. `fix(WP1): executed-state audit, artifact path, oracle trace, pyBKT parity` — `experiments/{checks,arms,stats,run_evaluation}.py`, `scripts/run_w6.py`, `src/adaptengine/planner/plan.py`, `src/adaptengine/learner/adapter.py`, related tests.
4. `feat(WP2): closed loop, mid-day budget, repeats, best effort, maintenance reviews` — `src/adaptengine/{api,core,learner,planner,replanner,review,session}`, `tests/test_w7_planner.py`, `tests/test_{review,defects_repro,state_session}.py`.
5. `feat(WP3): diagnostic flags, proper scoring, pre-registered selection, state-space` — `src/adaptengine/diagnostic/`, `experiments/{diag_eval,run_diag_selection,run_diag_matrix,cat_baseline,fit_bkt_sim}.py`, `config/fitted_sim.json`, diagnostic results, `docs/DIAGNOSTIC.md`.
6. `feat(WP4/5): simulator worlds, stress grid, sensitivity, Defect-7 fix` — `experiments/{sim,run_w7_grid,run_sensitivity,run_s4_fitted}.py`, `src/adaptengine/planner/schedule.py` (gate), grid/sensitivity results.
7. `perf(WP6): precomputed graph indices` — `src/adaptengine/curriculum/graph.py`, `experiments/run_w7_latency.py`, `experiments/results/w7_latency.json`.
8. `feat(WP7): data checksums, download script, BKT fitting, profiles` — `scripts/download_data.py`, `experiments/fit_bkt.py`, `tests/test_fit_bkt.py`, `config/fitted_assist09.json`, `bkt_fit_*.json`, `docs/data_manifest.md`, `data/external/CHECKSUMS`.
9. `feat(WP8): demo content, API adapter, React app, Playwright` — `data/content/`, `data/review_manifest.json`, `src/adaptengine/curriculum/content.py`, `tests/test_content.py`, `frontend/`, `Makefile`, CI `demo` job, `pyproject.toml` extras.
10. `docs(WP9): reconcile docs, D41–D48, results, W7 report, v0.3.0` — remaining `docs/` files, `docs/figures/`, `docs/WEEK7_*.md`, `docs/weekly/Week7_report.pdf`, `pyproject.toml` version, `experiments/make_w7_results.py`, `experiments/results/evaluation_results.json`, `experiments/results/replan_latency.json`.

Several files span WPs (e.g. `schedule.py`, `config.py`, `arms.py`); if you want exact per-WP commits use `git add -p`, otherwise group 4 can carry all `src/` changes.
