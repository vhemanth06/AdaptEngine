# AdaptEngine — Week 8 (Final Week) Implementation & Report Notes

This evidence file contains all facts, metrics, and caveats for Week 8. Every number is sourced directly from tool execution outputs or results files. Task IDs follow `WEEK8_IMPLEMENTATION_PLAN.md` (`R§x` = `final_week_report.md`). No git command was run during implementation; all version-control steps are listed in §17 for the human.

---

## 1. Baseline (WP0)

- **Environment:** Linux 7.0.0-43-generic x86_64, Python 3.11.17 (`.venv/bin/python`), pyBKT 1.4.3 installed, FastAPI + matplotlib installed; OR-Tools **not** installed; `anthropic` SDK **not** installed; 16 CPUs.
- **Starting code hash:** `c3cbb8f066c6cc843e611d19149d7f543c91c65afe652df6181b4fa22ca9f0a5` (= the W7 final hash in `w7_grid.json`).
- **Tests:** `make test` → **227 passed** in 41.08 s (pyBKT present here, so the 2 cloud-workspace skips run and pass). **Coverage 90.53%** (2513 statements, 238 missed; threshold 84%).
- **Lint:** clean on the W7 tree. (Copying the review probes verbatim in 0.2 added 33 ruff findings; they are excluded in `pyproject.toml` `extend-exclude` so the copies stay byte-identical — see §16.)
- **`make w3 w4 w5 w6` at baseline:** every acceptance check PASS (W4: TC2.3, TC3.1–TC3.6, TC4.2, 8-node; W5: TC5.1–TC5.3, TC6.1–TC6.4, TC7.1; W6: phases 3–7 PASS). The only FAIL was the lint phase caused by the copied probes (above); re-run after the exclusion, see §2 row 0.4.
- **Key W7 numbers (from `w7_grid.json`, `WEEK7_REPORT_NOTES.md`):** 420 cells; 0 executed prerequisite violations for adapt in every cell; goal mastery vs W7 `static`: 159 cells significantly worse, 35 better.
- **Review probes reproduced (task 0.2, `python experiments/probes/probe_w8_baseline.py` → `experiments/results/w8_probe_baseline.json`, code hash `c3cbb8f0…`, seeds 100–299, 4-node, B = 15, calm, 8-day horizon):**

| World | Minutes used / 120 | Idle days | Goal believed / truly mastered | False-mastery rate | True goal θ at first declared mastery (share < 0.70) |
|---|---|---|---|---|---|
| S0 | 52.7 | 3.77 | 199 / 132 | **39.3%** | 0.735 (34.2%) |
| S1 | 59.8 | 3.29 | 189 / 74 | **50.9%** | 0.627 (61.4%) |

| Cell | static_loop | adapt | Δ adapt − static_loop [95% CI] | Violations static_loop / adapt |
|---|---|---|---|---|
| S0, 4 d | 48.0% | 49.5% | +0.015 [−0.05, +0.075] | 1815 / 0 |
| S0, 8 d | 93.5% | 66.0% | **−0.275 [−0.34, −0.205]** | 2992 / 0 |
| S1, 4 d | 33.5% | 33.0% | −0.005 [−0.04, +0.025] | 1923 / 0 |
| S1, 8 d | 45.0% | 37.0% | **−0.080 [−0.125, −0.04]** | 3556 / 0 |
| S1, 8 d, sweep best (guess .55, T_les .05, T_ex .02, k 3) | 45.0% | 53.5% | **+0.085 [+0.03, +0.14]** (95.8 min used) | 3556 / 0 |

All match the review (R§1.3) exactly.

---

## 2. Change Log

| Task | What Changed | Files Touched | Tests / Evidence |
|---|---|---|---|
| 0.1 | Created this notes file; baseline recorded | `docs/WEEK8_REPORT_NOTES.md` | §1 |
| 0.2 | Review probes copied verbatim; new `probe_w8_baseline.py` re-runs their procedures and writes JSON | `experiments/probes/{__init__,probe_w8,probe_w8_calib,probe_w8_sweep,probe_w8_baseline}.py`, `experiments/results/w8_probe_baseline.json` | §1 tables reproduced exactly |
| 0.3 | `code_hash()` already existed (`experiments/provenance.py`, W7); reused by every new runner; unit test added | `tests/test_provenance.py` | test passes |
| 0.4 | `.gitignore`: `data/drafts/`, `experiments/results/policy_logs/`, `experiments/results/agent_cache/*` (caches kept local; demo cache re-included), `frontend/.sessions/` and `frontend/web/test-results/` were already ignored; ruff excludes the three verbatim probe copies | `.gitignore`, `pyproject.toml` | `ruff check .` clean |
| A.1 | `static_loop` (static's order, then cycles required exercises to the deadline; next-fit) and `random_eligible` (keyed-uniform among required activities whose direct prerequisites are evidence-mastered in the recorded state and that fit the day) arms in `run_episode` | `experiments/arms.py` | `tests/test_arms.py`: determinism (3 arms), static_loop uses every study day (14 calm / 13 missed_day, 0 idle), random_eligible 0 executed violations over 40 episodes |
| A.2 | `get_scenario(..., horizon="w7" | int ≥ 3)`: fixed horizons are policy-independent; "w7" keeps the W7 rule; forgetting_21 keeps its fixed 21 days | `experiments/arms.py` | `test_fixed_horizon_does_not_depend_on_policy` (W7 rule differs between configs, 7/14/21 do not) |
| A.3 | Episode metrics: `false_mastered` / `believed_mastered` / `false_mastery_rate`, `minutes_available` (budget on non-missed days), `minute_utilisation`, `idle_days_total`, `idle_days_unmastered` (old meaning, F.2). Kaplan–Meier `kaplan_meier`, `km_median`, `km_rmst` (censored at the episode's minutes) replace the survivorship-biased mean | `experiments/arms.py`, `experiments/stats.py` | `test_kaplan_meier_hand_computed` (curve, median 5, RMST(6) = 4.3, all-censored case), `test_w8_episode_metrics_are_consistent` |
| A.4 | `adapt_dx` arm: `engine.diagnose` first (answers tagged `diag`, never change θ), item minutes charged to day 1 (spilling to later days if > budget), then the closed loop from the diagnosed state; audit starts from the diagnosed state | `experiments/arms.py` | `test_adapt_dx_charges_diagnostic_minutes_to_day_one` (dx + day-1 ≤ 15, minutes_used includes dx) |
| WP-A gate | Probe numbers reproduced through the new arms/metrics: `python experiments/probes/probe_w8_gate.py` → S0 8 d Δ −0.275 [−0.34, −0.205], S1 8 d −0.080 [−0.125, −0.04], S0/S1 4 d +0.015 / −0.005; adapt minutes 52.7 / 59.8; pooled false mastery 39.3% / 50.9%; violations static_loop 2992/3556, adapt 0 | `experiments/probes/probe_w8_gate.py` | **gate met**; 236 tests pass |
| B.1 | Named profiles in the planner: `EngineConfig.class_params` (per-class guess/slip replace g(d)/s(d) in `learner/mastery.guess/slip`), `profile` name; `core/profiles.load_profile(name, **overrides)` (w7_default = `DEFAULT_CONFIG`, bit-identical); validation guess + slip < 1, 0 < T < 1, finite | `core/config.py`, `core/profiles.py` (new), `learner/mastery.py` | `tests/test_w8_engine.py`: default profile plans identical (4 budgets), fitted_sim values loaded, 3 invalid class cases + 3 invalid transition cases rejected |
| C.1 | Consolidation tier (D49, flag `consolidation`): Tier 3 after all required new work, until `deadline_day`; unseen hardest exercises first, lowest projected p first, then repeats of the hardest; also when every required concept is already believed mastered (plan reason `CONSOLIDATION`). Trace reason `CONSOLIDATION` | `planner/schedule.py`, `planner/plan.py`, `core/config.py` | only after all new work; 0 plan-audit violations; utilisation higher than W7 in a fixed-seed S0 and S1 episode with 0 executed violations |
| C.2 | Verification probe (D50, flag `verification_probe`, `probe_easy_share` = 0.5): exercise evidence (completed + projected) > 50% easy and no hard item → one hard exercise appended (trace `VERIFICATION_PROBE`); an evidence-mastered concept that needs it stays required so dependents stay gated | `planner/workload.py` | probe inserted with easy-heavy evidence, not with hard/balanced evidence, dependants locked until the probe, cleared after it is answered; 0 executed violations (10 S1 episodes) |
| C.3 | Horizon-aware strictness (D51, flag `horizon_aware_mastery`): slack = 1 − optimistic days needed / days left; above `strict_slack` 0.5 the plan uses `two_threshold` with k = 3 and H ≤ 0.35 (trace `HORIZON_AWARE_STRICT`) | `planner/plan.py`, `core/config.py` | same plan as W7 at slack 0.5 (deadline 4); stricter at deadline 21 (more items; a concept mastered by W7's rule is required again) |
| D.1 | `review_cap_fraction` (1.0 = off; reviews limited to that share of the day while new content is pending, trace `REVIEW_CAP`) and `review_goal_path_only` (goal + prerequisites of pending new content) | `planner/schedule.py`, `core/config.py` | cap respected on days with pending new content; off-path concept not reviewed |
| E.1 | `diagnostic_scope = "goal_path"`: `Engine.diagnose(goal_concepts=[goal])` probes only the goal's ancestor path minus evidence-mastered concepts; `adapt_dx` passes the goal in that mode | `api.py`, `core/config.py`, `experiments/arms.py` | items ⊆ path; mastered C1 not probed |
| F.1 | `Plan.feasibility_warning` (flag `feasibility_warning`): expected-projection days needed vs days left; schedule unchanged; serialized and carried through replan | `core/schema.py`, `planner/plan.py`, `replanner/replan.py` | days identical with the flag on/off; warning present at deadline 4 / B = 10, absent at deadline 40 |
| F.2 | `idle_days` split into `idle_days_unmastered` (old meaning) and `idle_days_total` in episodes; W7 grid runner/report and the W7 test renamed | `experiments/arms.py`, `experiments/run_w7_grid.py`, `experiments/make_w7_results.py`, `tests/test_w7_planner.py` | tests pass |
| J.1–J.4 | `policy` package: `RankingPolicy` protocol, `DeterministicPolicy`, keyed SHA-256 uniform; `features.extract` (17 features); `BanditPolicy` LinUCB + softmax (exact propensities), Sherman–Morrison ridge update, save/load, modes frozen/updating/random. Scheduler hook `_policy_pick` on the top-K (5) Tier 2 candidates; trace `POLICY_SELECTED` (candidates, propensities, features, chosen, deterministic choice, version) / `POLICY_FALLBACK` (single candidate, error, unknown id, does not fit). `Engine(policy=...)` passed through plan/replan/next_activities; config `ranking_policy` (default deterministic) | `src/adaptengine/policy/*` (new), `planner/schedule.py`, `planner/plan.py`, `replanner/replan.py`, `api.py`, `core/config.py` | `tests/test_policy.py` (15): DeterministicPolicy bit-identical plans (4-node, 8-node, 4 budgets) and episodes; propensities sum to 1; choices follow propensities; ridge update = closed form (numpy); fallback on error/unknown id; candidates ⊆ eligible and 0 executed violations for every variant in S1/S4 |
| K.1 | Provider interface: `StubProvider` (offline templates), `AnthropicProvider` (official SDK, default model `claude-opus-5-5`, server-side refusal fallback on, no sampling params), `OllamaProvider` (HTTP, temperature 0), `CachedProvider` (prompt-hash disk cache, replay-only mode); optional extras `[agents]` (anthropic), `[solver]` (ortools) | `src/adaptengine/authoring/providers.py`, `pyproject.toml` | architecture test: core never imports authoring/agents or network clients; only `providers.py` imports `anthropic` |
| K.2 | Draft generation to the three schemas, written only to `data/drafts/<name>/` with `draft_meta.json` (ai_assisted, PENDING reviewer, provider, model, prompt hash, timestamp); retry with the validator's error, max 2 | `authoring/draft.py` | `tests/test_authoring.py`: stub draft passes the loaders, live loader rejects it unreviewed, retry recovers from malformed JSON then a cycle, gives up after 3 attempts, bad names rejected |
| K.3 | Typed validation report: schema (loaders + DAG), duplicate/near-duplicate questions, answer-position bias, difficulty spread, reading length | `authoring/checks.py` | one failing fixture per check |
| K.4 | CLI `adaptengine author draft|validate`; `scripts/record_review.py` now rejects empty/PENDING/AI-model reviewer names and has `--promote-draft NAME` (copies the draft into `data/curriculum` + `data/content`, records all three, refuses to overwrite) | `cli.py`, `scripts/record_review.py` | 9 rejected reviewer names; promotion with a human name records hashes; CLI draft/validate exit codes |
| L.1–L.3 | `AgentRankingPolicy` (non-learning: no reward/update/memory), prompt template `policy/agent_prompt.md`, strict validator `parse_ranking`, propensity 1.0, trace `AGENT_FALLBACK` on any failure | `policy/agent.py`, `policy/agent_prompt.md`, `planner/schedule.py` | `tests/test_agent_policy.py`: unknown id, duplicates, out-of-set id, malformed JSON, empty ranking, timeout → fallback with plans equal to deterministic and 0 executed violations; valid answer logged with rationale; cache hit identical (`test_authoring.py`) |
| M.1–M.2 | `agents/plan_proposer.propose_plan` + engine validator `planner/validate_proposal` (MALFORMED, UNKNOWN_ACTIVITY, DUPLICATE_ACTIVITY, OUTSIDE_HORIZON, DEADLINE_EXCEEDED, OVER_BUDGET, PREREQUISITE_ORDER, GOAL_NOT_REACHED); rejection → deterministic plan + `PROPOSAL_REJECTED` | `agents/plan_proposer.py`, `planner/validate_proposal.py` | `tests/test_plan_proposer.py`: valid accepted (SELECTED per activity), each rule rejected with its reason, unordered days malformed |
| N.1–N.2 | `planner/options.build_options` (continue / remediate / review / rediagnose / consolidate, only when valid) + `default_option` (tier order); `agents/orchestrator.choose_option` / `orchestrated_next` (engine re-checks the slice; fallback to continue) | `planner/options.py`, `agents/orchestrator.py`, `experiments/arms.py` (`next_fn`, `on_execute` hooks) | `tests/test_orchestrator.py`: conditional option set, outside-set/garbage → fallback, 0 violations with first/last/bogus picks |
| O.1 | `EloModel` (1PL logit ability, K = 0.4, a = 1.7) behind `MasteryModel`; `make_model(cfg)` picks it with `mastery_model = "elo"` | `learner/elo.py`, `learner/adapter.py`, `api.py` | monotonicity, update direction, closed-loop episode with 0 violations |
| O.2 | HLR-lite `h = 2^(w0 + w1 √(1+correct) + w2 √(1+wrong))`, flag `half_life_model = "hlr"`, weights `hlr_weights` | `review/hlr.py`, `planner/schedule.py` | ordering of half-lives; reviews fire with short HLR half-lives |
| O.3 | `forget` in profiles; exercise transition p'' = p'(1 − F) + (1 − p') T | `learner/mastery.py`, `core/profiles.py` | formula test |
| O.4 | `planner/cpsat.py` (OR-Tools CP-SAT, min makespan, deterministic single worker); `scheduler = "cpsat"` tries it first, else trace `CPSAT_UNAVAILABLE_USING_GREEDY` and greedy + oracle | `planner/cpsat.py`, `planner/plan.py` | fallback test passes; parity test with the oracle **skipped** (OR-Tools not installed here) |
| A.5 | Pre-registration written **before** any B/G/J/O run, code hash `f09fb8e2…` | `docs/preregistration/FINAL_A5_2026-11-10.md` (sha256 `b7ff229d8ebaccba…`) | this row precedes every run row below |
| A.5a | Amendment 1 to the pre-registration (before any fit): B.2 data = static_loop **+ random_eligible** episodes, because the EM recovery test showed p0 and T_lesson are not separately identifiable when the lesson always comes first | `docs/preregistration/FINAL_A5_2026-11-10.md`, `tests/test_bkt_lessons.py` | recovery test with lessons at random positions recovers p0, T_lesson, T_ex, guess/slip within tolerance; forgets recovered (0.04–0.2 for F = 0.1, < 0.05 without) |
| B.2 | Lesson-aware BKT EM (numpy Baum–Welch, padded sequences; optional forgets); runner `python experiments/fit_bkt_sim.py w8` (2 min) fits S0, S1, S4 (and S3 ± forgets for O.3) on even fit seeds; episodes now carry an `activity_log` | `experiments/bkt_lessons.py` (new), `experiments/fit_bkt_sim.py`, `experiments/arms.py`, `config/fitted_S0.json`, `fitted_S1.json`, `fitted_S4.json`, `fitted_S3.json`, `fitted_S3_forget.json`, `experiments/results/w8_fits.json` | §5 table; S4 recovers its generating parameters; degenerate check: easy-class guess > 0.5 in S0/S1/S3 (warning, valid); no guess + slip ≥ 1 |
| B.3 | Pre-registered selection run (`python experiments/run_calibration_select.py`, 130 s, 8,400 episodes, even seeds 4000–4398): candidates within 0.002 of the minimum Brier = F3, F4, F5; highest secondary = **F5 (fitted profile, k = 2, θ = 0.85, horizon-aware strictness)** — named before any odd-seed run | `experiments/run_calibration_select.py` (new), `experiments/w8_common.py` (new), `experiments/results/w8_calibration_select.json` | §5 tables; 0 executed violations in all 36 candidate-cells |
| G.1 | Final-grid runner: parallel (Pool), resumable (per-unit JSONL checkpoint keyed by code hash), exact Brier sums + 20-bin calibration histograms (AUC, reliability), KM median/RMST, paired CIs vs static_loop and between adapt arms; smoke run (`--smoke`: S1, 4-node, B = 15, h14, 4 scenarios × 8 arms × 20 seeds) in 5.5 s | `experiments/run_final_grid.py` (new) | `experiments/results/final_grid_smoke.json` |
| G.2 | Pre-registered final grid run: `python experiments/run_final_grid.py --procs 14` → 208 cells × 8 arms, 200 odd seeds per cell (headline 1000), 6,784 units, **2327.5 s**, code hash `f09fb8e2…` | `experiments/results/final_grid.json` (22.9 MB), checkpoint `final_grid.ckpt.jsonl` | §8 |
| G.3 / B.4 | `experiments/make_final_results.py` → `docs/FINAL_RESULTS.md` and 5 figures (forest vs static_loop, violations log scale, false mastery + utilisation, KM headline, reliability per world); B.4 table = pooled in-loop Brier/AUC adapt-W7 vs adapt-final per world | `experiments/make_final_results.py` (new), `docs/FINAL_RESULTS.md`, `docs/figures/final_*.png` | tested on the smoke grid first; every number read from results files |
| J.5 | Frozen bandit trained (`python experiments/train_policy.py`, 234 s): 800 sequential episodes, 17,775 updates, 0 executed violations | `experiments/train_policy.py`, `experiments/policy_runner.py`, `experiments/ope.py` (new), `config/policy_frozen.json`, `experiments/results/w8_policy_train.json` | `tests/test_ope.py` (IPS/SNIPS/DR recover a known value 0.8 within 0.05; learning-progress reward) |
| J.6 | Policy evaluation (`python experiments/run_policy_eval.py`): 4 variants × 4 cells × 200 odd seeds; decision logs in `experiments/results/policy_logs/` | `experiments/run_policy_eval.py`, `experiments/results/w8_policy_eval.json` | §9 |
| D.1 / O.1–O.3 | Extension runner (`python experiments/run_extensions.py`): HLR-lite fit on HLR seeds, D.1 synth-20 forgetting cells, Elo vs BKT, HLR vs fixed vs no_review, forgets in S3 | `experiments/run_extensions.py`, `experiments/results/w8_extensions.json`, `w8_hlr_fit.json` | §6, §10 |
| E.2 | D52 decided from the grid; Diagnostic screen has "Skip → plan from the prior" and an item progress bar | `docs/DECISIONS.md` §8, `frontend/web/src/pages/Diagnostic.tsx` | §7 |
| K.5 / L.4 / M.3 / N.3 | Stub plumbing run of the agent evaluations (`python experiments/run_agent_eval.py --provider stub`); live-model runs **not run** (no API key or local model here) | `experiments/run_agent_eval.py`, `experiments/results/w8_agent_eval_stub.json` | §9 |
| H.0 | No failing step was reported to triage; the W7 app built and its Playwright run passed here before the rebuild (`test-results/.last-run.json`); the rebuild removes the R§3.2 failure modes (one command, health endpoint, freshness check, error screens) | — | — |
| H.1 | `make demo` (`scripts/demo.py`: dependency and data checks, rebuilds `web/dist` when `src/` is newer, `npm ci` if needed, starts uvicorn, prints the URL); `/api/health` (engine version, code hash, profiles, flags, web build fresh/stale/missing, content reviewer) | `Makefile`, `scripts/demo.py` (new), `frontend/api/app.py`, `frontend/api/schemas.py` | `test_health` |
| H.2–H.3 | Design tokens (light/dark, Tailwind neutral scale remapped so every screen themes), app shell (grouped collapsible sidebar, top bar with session/status/day/deadline/budget chips, demo-mode switch, theme toggle, Reset), ⌘K palette, footer with code hash and honesty badge; restyled UI kit + Skeleton, EmptyState, ErrorBoundary, Toast, Segmented, Chip | `web/src/styles/tokens.css` (new), `web/src/index.css`, `web/src/shell/{AppShell,CommandPalette}.tsx` (new), `web/src/components/ui.tsx`, `web/src/App.tsx`, `web/src/ctx.ts` | Playwright screens light/dark |
| H.4–H.14 | New screens Overview, Policy Lab, Authoring Studio; rebuilt Curriculum map (custom nodes with mastery ring, hover-highlighted edges, minimap, concept drawer with lock reasons), Autopilot (5 arms, world, horizon, 1/20/100 learners, goal-θ curves, belief vs reality), Evaluation (final grid: forest plot, log-scale violations, reliability, headline, CSV export); Setup (profile, segmented budget, goal description, F.1 warning), Diagnostic (skip, progress), Plan + Why? (new trace reasons, "Ask the agent for a plan" with accept/reject reasons), Study (agent-strategy chip); API: profiles, simulate (new arms, world, horizon, final p vs θ, trajectories), evaluation (final grid + W8 files), policy preview, propose-plan, strategy, authoring draft/get/edit/validate/approve | `web/src/pages/*.tsx`, `web/src/components/{PlanTimeline,WhyPanel}.tsx`, `web/src/api/{client.ts,schema.d.ts}`, `frontend/api/{app.py,schemas.py}` | `frontend/api/tests/test_api.py` 16 passed; `npm run build` OK |
| H.15–H.16 | Skeletons, empty states with a CTA, inline errors with Retry + "Copy debug info", per-screen error boundary, "API not reachable" message; keyboard (palette, digits, focus-visible), labelled colour states; React Flow and Recharts screens lazy-loaded; JS **≈ 254 kB gzipped** in total (budget 600 kB) | `web/src/**` | build output |
| H.17 | Playwright: demo script updated to 9 steps (adds belief vs reality, Policy Lab with forced bad output, plan proposer rejection); `screens.spec.ts`: 11 screens × light/dark visual snapshots, unknown session, API down; OpenAPI types regenerated (`npm run gen:types`) | `web/e2e/demo.spec.ts`, `web/e2e/screens.spec.ts` (new), `web/e2e/screens.spec.ts-snapshots/*.png` (22) | **5/5 passed** here (`npx playwright test`, 50 s) |
| H.18 | CI `demo` job: OpenAPI type drift check, build, Playwright (demo + screens + failure states), report upload on failure (file edit only) | `.github/workflows/ci.yml` | 🧑 runs after push |
| H.19 | Demo README: one command, design system, tests, 8-minute script table and rehearsal checklist; screenshot script; 11 screenshots | `frontend/README.md`, `web/scripts/demo-screenshots.mjs` (new), `docs/figures/demo_*.png` | screenshots taken against a local server |
| I.4 | `make final` (`scripts/run_final.py`: gates → runs → results), version **1.0.0** (pyproject, API), W8 traceability links | `scripts/run_final.py` (new), `Makefile`, `pyproject.toml`, `docs/TRACEABILITY.md` | — |
| D49–D60 | Registered | `docs/DECISIONS.md` §8, `docs/FREEZE_RECORD.md` | — |
| F.3 | Re-ran at the final hash `f09fb8e2…`: W8 fits (B.2, O.3), ASSISTments and CT fits (`fit_bkt.py assist09|ct --out w8_bkt_fit_*.json`; class fits **identical** to W7, `config/fitted_assist09.json` rewritten with the new hash only), latency (`run_w7_latency.py --timing-out w8_latency.json`). Every final result carries code hash `f09fb8e2…` | `experiments/results/w8_{bkt_fit_assist09,bkt_fit_ct,latency}.json`, `config/fitted_assist09.json` | latency note in §16 |
| I.1 / I.2 / I.5 | Final report (built from these notes; W7 corrections: "0 idle days" qualified, static_loop result, premature-mastery motivation), presentation outline | `docs/FINAL_REPORT.md`, `docs/PRESENTATION_OUTLINE.md` | — |
| I.3 | 🧑 Human review of `data/content/content_8node.json` still pending (`PENDING_HUMAN_REVIEW`); command in §17.2 | — | not done |

**WP exit gates:**
- WP-A: met (row "WP-A gate").
- WP-C: all flags off → W7 behaviour (all 227 W7 tests unchanged and passing; TC8.2 frontier equivalence suite passing); executed violations 0 with every flag on (`test_all_flags_on_keep_executed_safety`, 8-node, missed_day, S1/S4). **Met.**
- Code freeze for the runs: 329 passed, 1 skipped (OR-Tools), `ruff` clean, code hash `f09fb8e2f6126c98c5a81cddf0a840a3936509111cbbbdb064fd2e8d5a881b66`.
- WP-G: grid complete, 0 executed violations for every adapt arm. **Met.**
- WP-H: `make demo`, 11 screens, light/dark, loading/empty/error states; API 16 passed; Playwright 5 passed here (🧑 still to confirm on the presentation machine). **Met here.**
- Final state: `pytest tests frontend/api/tests` 350 passed, 1 skipped; `make check` coverage 89%; ruff clean; `tsc` + `npm run build` OK; code hash unchanged since the freeze.

---

## 3. Defects Found and Fixed

| Symptom | Root cause | Fix (task) | Evidence |
|---|---|---|---|
| Logged bandit propensities summed to 1.000001 | Propensities rounded to 6 decimals in the trace | Log exact values (J.3) | `tests/test_policy.py::test_propensities_sum_to_one_and_choice_is_reproducible` |
| A draft with a prerequisite cycle passed validation | `validate_draft` used the loaders only; cycles are detected when the graph is built | Build `CurriculumGraph` in `validate_draft` (K.3) | `tests/test_authoring.py::test_retry_on_validation_error_then_success` |
| API plan lost `feasibility_warning` | Pydantic `PlanOut` had no such field | Field added (F.1/H.5) | `test_end_to_end_plan_matches_direct_engine` |
| A proposed day 0 raised inside `PlanDay` instead of a rule violation | `parse_days` built `PlanDay` without catching its validation | MALFORMED with the message (M.1) | `tests/test_plan_proposer.py` |
| p0 and T_lesson not separately identifiable in the planned B.2 data | Lessons always precede exercises in `static_loop` | Pre-registration Amendment 1 (random_eligible added) before any fit | `tests/test_bkt_lessons.py` |
| "Not in plan" map node unreadable in dark mode | Hard-coded white background | Token-based node styles (H.7) | `e2e/screens.spec.ts-snapshots/map-dark-*.png` |
| Copying the review probes broke `ruff check .` (33 findings), which failed the lint phase of `make w3`–`w6` | Verbatim third-party copies | Excluded from ruff (0.2) | `ruff check .` clean |


## 4. Evaluation Validity (WP-A)

See §1 and the WP-A rows in §2. The new arms and metrics reproduce every review probe exactly. In the final grid (odd seeds, `final_grid.json`):

- **Policy-independent horizons matter.** adapt-final vs static_loop, goal mastery, cells better / n.s. / worse: W7 horizon 0 / 5 / 43 (mean −0.101); 7 days 2 / 8 / 38 (−0.087); 14 days 11 / 19 / 18 (−0.019); 21 days 25 / 32 / 7 (**+0.040**). At short horizons the stricter, calibrated engine has less time than a state-blind loop that starts practising at once; at 21 days it wins.
- **static vs static_loop** shows how flattering the W7 baseline was: static is worse than static_loop in 48/48 cells at 14 days (mean −0.224) and 56/64 at 21 days.
- `random_eligible` (prerequisite-safe random) has 0 executed violations by construction; it loses to static_loop in 47/48 cells at 14 days.

## 5. Calibration (WP-B)

### 5.1 B.2 fitted profiles (`experiments/results/w8_fits.json`, code hash `f09fb8e2…`, even seeds 2000–2398, static_loop + random_eligible, 4-node + 8-node)

| Profile | p0 | T_lesson | T_exercise | F | guess easy / med / hard | slip easy / med / hard | Flags |
|---|---|---|---|---|---|---|---|
| fitted_S0 | 0.053 | 0.278 | 0.097 | — | 0.672 / 0.487 / 0.268 | 0.116 / 0.252 / 0.450 | easy guess > 0.5 |
| fitted_S1 | 0.171 | 0.294 | 0.057 | — | 0.616 / 0.426 / 0.219 | 0.123 / 0.265 / 0.465 | easy guess > 0.5 |
| fitted_S4 | 0.238 | 0.194 | 0.050 | — | 0.248 / 0.151 / 0.064 | 0.101 / 0.180 / 0.251 | none |
| fitted_S3 (O.3) | 0.112 | 0.318 | 0.0004 | — | 0.670 / 0.428 / 0.261 | 0.245 / 0.434 / 0.657 | easy guess > 0.5, hard slip > 0.5 |
| fitted_S3_forget (O.3) | 0.072 | 0.405 | 0.010 | 0.078 | 0.676 / 0.435 / 0.266 | 0.204 / 0.358 / 0.609 | easy guess > 0.5, hard slip > 0.5 |
| W7 default (D6) | 0.20 | 0.20 | 0.05 | — | 0.24 / 0.15 / 0.06 (representative d) | 0.10 / 0.175 / 0.25 | — |

S4 is generated by the D6 heuristics (p0 0.20, T_lesson 0.20, T_ex 0.05), and the fit recovers them, which validates the fitter. In the IRT worlds (S0, S1, S3) easy items are answered correctly well below mastery (guess 0.62–0.68), which is the cause of premature mastery identified in R§1.3.

### 5.2 B.3 selection (`experiments/results/w8_calibration_select.json`, even seeds 4000–4398, C.1 + C.2 on)

| Candidate | Mean in-loop Brier (primary) | Mean Δ goal mastery vs static_loop (secondary) |
|---|---|---|
| C0 W7 default | 0.2544 | +0.034 |
| F1 fitted, k2, θ .85 | 0.2203 | +0.054 |
| F2 fitted, k3, θ .85 | 0.2202 | +0.052 |
| F3 fitted, k2, θ .95 | **0.2126** | +0.009 |
| F4 fitted, k3, θ .95 | **0.2126** | +0.009 |
| F5 fitted, k2, θ .85, horizon-aware | 0.2146 | **+0.053** |

Rule: minimum 0.2126; within 0.002: F3, F4, F5; highest secondary → **F5 wins**. Per cell (Brier / goal mastery / Δ vs static_loop): F5 S0 4-node 0.220 / 1.000 / 0.000; S0 8-node 0.209 / 0.870 / −0.080; S1 4-node 0.223 / 0.940 / +0.180; S1 8-node 0.217 / 0.565 / +0.070; S4 4-node 0.201 / 0.985 / +0.125; S4 8-node 0.218 / 0.710 / +0.025. C0 for comparison: S0 8-node 0.272 / 0.895 / −0.055; S1 4-node 0.283 / 0.775 / +0.015. Utilisation with C.1 is 0.91–0.95 for every candidate. These are tuning (even-seed) numbers; the reported results are the odd-seed final grid (§8).

## 6. Using the Whole Budget (WP-C) and Review (WP-D)

From `final_grid.json` (odd seeds), mean over cells:

| Arm | 7 d util. / false m. / idle days | 14 d | 21 d |
|---|---|---|---|
| adapt_w7 | 0.79 / 0.252 / 0.49 | 0.55 / 0.255 / 4.42 | 0.41 / 0.321 / 10.24 |
| adapt_cal (calibration only) | 0.89 / 0.125 / 0.06 | 0.75 / 0.088 / 2.03 | 0.60 / 0.176 / 6.49 |
| adapt_final (+ C.1, C.2) | 0.91 / 0.121 / 0.00 | 0.92 / 0.068 / 0.00 | 0.93 / 0.145 / 0.00 |
| static_loop | 0.96 / 0.172 / 0.00 | 0.98 / 0.085 / 0.00 | 0.99 / 0.157 / 0.00 |

- Consolidation + probe (adapt_final vs adapt_cal), goal mastery: 42 cells better, 166 n.s., **0 worse** (mean +0.019); headline +0.196 [+0.173, +0.221], all-required +0.360 [+0.331, +0.390].
- Calibration alone (adapt_cal vs adapt_w7): 61 better, 109 n.s., 38 worse (mean +0.046).
- C.1 and C.2 are evaluated together (one ablation arm); their separate effects are not measured.

**D.1 review cap** (`w8_extensions.json`, synth-20, forgetting_21, odd seeds): the cap and goal-path relevance change nothing measurable: adapt_cap vs adapt goal θ 0.128 / 0.128 (S0 B10), 0.148 / 0.147 (S0 B15), 0.128 / 0.128 (S1 B10, B15). Goal mastery is 0–0.5% for every arm (21 days with a 7-day power-law half-life), so the pre-registered criterion (capped not worse than no_review on goal mastery: CI includes 0) is met only trivially. On mean goal θ, no_review is far better in S0 B15 (0.283 vs 0.148): reviews still crowd out new work there, and the cap does not fix it. Reported under §12.
## 7. Diagnostic Decision (WP-E)

- adapt_final_dx − adapt_final (goal-path diagnostic, item minutes charged to day 1): headline −0.017 [−0.027, −0.007]; over all 208 cells 1 better, 191 n.s., 16 worse; mean over the 192 non-forgetting cells −0.005; all-required headline −0.031.
- The pre-registered D52 condition ("CI includes 0 and |mean| ≤ 0.02 → optional") is not met because the diagnostic is slightly but significantly **worse** in the headline cell; the rule did not cover this case. Decision D52: the diagnostic becomes optional in the product flow (Skip → plan from the prior), which follows the rule's intent; logged as a deviation (§16).
- E.1 goal-path scope: on the 4-node and 8-node curricula the goal's ancestor path covers almost every concept, so the item saving is small (tests show items ⊆ path and mastered concepts skipped).
## 8. Final Grid Results (WP-G)

Full tables: `docs/FINAL_RESULTS.md` (generated). Headline cell **S1 | 4-node | B = 15 | calm | 14 days, N = 1000 odd seeds**:

| Arm | Goal mastery | All required | False mastery | Utilisation | KM median min | Brier | Δ goal vs static_loop |
|---|---|---|---|---|---|---|---|
| adapt_final | **0.939** | **0.896** | 0.033 | 0.95 | 104 | 0.224 | **+0.234 [+0.207, +0.261]** |
| adapt_final_dx | 0.922 | 0.865 | 0.042 | 0.95 | 107 | 0.224 | +0.217 [+0.190, +0.244] |
| adapt_cal | 0.743 | 0.536 | 0.165 | 0.56 | 104 | 0.214 | +0.038 [+0.007, +0.067] |
| adapt_w7 | 0.368 | 0.088 | 0.522 | 0.29 | 129 | 0.250 | −0.337 [−0.366, −0.308] |
| static_loop | 0.705 | 0.657 | 0.071 | 0.99 | 138 | 0.235 | — |
| static | 0.303 | 0.021 | 0.427 | 0.20 | censored | 0.264 | −0.402 |
| random_eligible | 0.660 | 0.651 | 0.047 | 1.00 | 170 | 0.215 | −0.045 |
| no_replan | 0.295 | 0.019 | 0.409 | 0.16 | censored | 0.261 | −0.410 |

adapt_final vs adapt_w7 (headline): goal **+0.571 [+0.541, +0.601]**, all-required **+0.808 [+0.784, +0.832]**.

- **Safety (primary):** executed prerequisite violations = **0 for all four adapt arms and random_eligible in all 208 cells**; static_loop 997,126 (42,400 learners), static 451,900, no_replan 273,169. Budget violations 0 everywhere.
- **Goal mastery vs static_loop (primary):** depends on the horizon (§4): worse at the W7 and 7-day horizons, mixed at 14 days (11 better / 19 n.s. / 18 worse), better at 21 days (25 / 32 / 7). By world at 14 days, B = 15: S1 wins in 5/6 cells (up to +0.300), S4 in 2/6, S4-fitted in 1/6, S0 8-node loses 2/3 (−0.075, −0.080).
- **All-required mastery vs static_loop (primary):** adapt_final 118 better / 85 n.s. / 5 worse (mean +0.104); adapt_w7 65 / 88 / 55 (−0.061).
- **adapt_final vs adapt_w7:** 66 better / 105 n.s. / 37 worse (mean +0.065); the losses are concentrated at the W7 and 7-day horizons, where stricter evidence needs more time.
- **B.4 calibration (pooled in-loop):** Brier S0 0.254 → 0.219, S1 0.252 → 0.224, S4 0.234 → 0.210; AUC S0 0.535 → 0.646, S1 0.566 → 0.644, S4 0.636 → 0.688. **S4-fitted got worse** (Brier 0.248 → 0.283, AUC 0.587 → 0.485): the pre-registered rule used `fitted_S4` (fitted on the D6-generated S4 world) in the ASSISTments-driven S4-fitted world, a profile mismatch.
## 9. Agentic Layer (WP-J to WP-N): specs, tests, evaluations

Specs: `docs/POLICY_SPEC.md` (D53), `docs/AGENTS.md`, `docs/AUTHORING.md`. All agent tests run offline with the stub provider.

**Bandit (J.6, `w8_policy_eval.json`, odd seeds, N = 200 paired, adapt_final, 14 days):**

| Cell | Deterministic goal / all-req | Frozen Δ goal vs det. | Updating Δ | Random Δ | Executed violations |
|---|---|---|---|---|---|
| S1, 4-node | 0.950 / 0.900 | +0.005 [0.000, +0.015] | +0.005 | +0.005 | 0 for every variant |
| S1, 8-node | 0.485 / 0.180 | +0.010 [−0.015, +0.035] | +0.010 | +0.005 | 0 |
| S4, 4-node | 0.960 / 0.950 | 0.000 | 0.000 | 0.000 | 0 |
| S4, 8-node | 0.710 / 0.645 | +0.010 [−0.010, +0.030] | +0.010 | +0.020 [−0.005, +0.045] | 0 |

- No variant differs from the deterministic ranking (all CIs include 0), as the plan's risk table expected with ≤ 5 near-equivalent candidates. Agreement with the deterministic choice: frozen 0.41–0.50, random 0.51–0.52.
- **Updating = frozen in every cell.** Checked directly: an updating learner makes 43 updates in a 14-day 8-node episode; against 17,775 training updates its weights move by ≤ 0.0017 and propensities by ≤ 0.0007, so the keyed draws select the same items. Per-learner updating is too weak to matter at this scale.
- **OPE of the frozen policy** (value = mean learning progress per decision): from the random logs, |error| IPS/SNIPS/DR 0.0013/0.0013/0.0018 (S1 4-node), 0.0000/0.0000/0.0001 (S1 8-node), 0.0036/0.0039/0.0049 (S4 4-node), 0.0069/0.0067/0.0056 (S4 8-node), against simulated values −0.0043 to 0.0299. From the updating logs the error is ≤ 0.0006 because the logging policy is effectively the target policy.

**LLM ranker, plan proposer, orchestrator (L.4, M.3, N.3):** **not run with a model** (no Anthropic key or local model in this environment). The stub plumbing run (`w8_agent_eval_stub.json`, labelled "not an agent evaluation") confirms: ranker 0 fallbacks and agreement 1.0 with the deterministic choice (the stub echoes it), proposer acceptance 1.0 (the stub echoes the engine plan), orchestrator agreement with the tier order 0.457 (the stub always picks the first option, "continue"), 0 executed violations. Adversarial behaviour is covered by the offline tests (§2 L.1–L.3, M.1–M.2, N.1–N.2).

**Authoring aid (K.5):** stub drafts pass the loaders on the first attempt (6-concept "Python dictionaries": 30 activities, 0 errors). The stub template produces near-duplicate questions, which the checker flags (276 warnings), as it should. The real-model draft, human edit count and time to review are **not run** (🧑).
## 10. Model and Planner Extensions (WP-O)

From `w8_extensions.json` (odd seeds, N = 200):

| Extension | Result |
|---|---|
| O.1 Elo vs BKT (adapt_final, 4-node, B = 15, calm, 14 d) | Elo has higher AUC (S0 0.675 vs 0.637, S1 0.683 vs 0.637, S4 0.708 vs 0.656), better Brier only in S1 (0.216 vs 0.224), and **lower goal mastery**: S0 −0.015 [−0.035, 0.000], S1 −0.145 [−0.205, −0.090], S4 −0.200 [−0.255, −0.145]. The θ = 0.85 threshold means something different on the Elo scale (harder to reach), so it drills longer. Stays off (D59). |
| O.2 HLR-lite | Fitted weights (1.75, −0.25, 0.0) on 48,515 post-gap answers; Brier 0.270, **worse** than a constant-rate baseline 0.241. In forgetting_21 cells HLR lowers goal mastery (8-node −0.105 [−0.155, −0.065]). Fixed half-life ≈ no_review (+0.005, +0.010, n.s.). S3 and S0 cells are identical: with the fast_forgetter profile (own half-life) S3 adds nothing, so the pre-registered S3 cells duplicate S0. |
| O.3 BKT forgets | Fitted F = 0.078 on S3 data. With it, p plateaus near 0.76 under repeated correct answers, below θ = 0.85, so mastery is unreachable and the planner returns CONTENT_INSUFFICIENT (0 attempts in the forget arm; goal θ 0.131 vs 0.373 without). A threshold criterion and a forgetting transition are incompatible without a lower θ or time-based decay. |
| O.4 CP-SAT | Implemented and fallback-tested; **not run** (OR-Tools not installed, 🧑 `pip install -e ".[solver]"`). |
| O.5 Junyi | **Not done**: dataset not downloaded (🧑). |
| O.6 CSEDM retry | **Not done**: raw ITAP export not available (🧑). |
| O.7 Pilot | **Not run** (needs consent and participants, 🧑). |
## 11. Frontend (WP-H): fix, redesign, test results, screenshots

- Rebuilt on the existing stack with design tokens and Tailwind only (the planned Radix, lucide, fonts and framer-motion packages were not installed: handover item; plan fallback used). System font stack with Inter/JetBrains Mono first when installed locally.
- 11 screens in the shell (Overview, Setup, Diagnostic, Map, Plan + Why?, Study, Disruptions, Policy Lab, Authoring Studio, Autopilot, Evaluation), light and dark.
- `npm run build`: JS 77 kB (main) + lazy Map 58 kB + Autopilot/Recharts 108 kB + Evaluation 3 kB gzipped ≈ 254 kB total.
- Tests: API 16 passed; Playwright 5 passed (demo script, 22 visual snapshots, unknown session, API down).
- Screenshots: `docs/figures/demo_{overview,setup,diagnostic,map,plan_why,study,disruptions,policy_lab,authoring,autopilot,evaluation}.png`.
## 12. What Did Not Improve

- Goal mastery vs static_loop at the W7 and 7-day horizons: adapt-final is worse in 43/48 and 38/48 cells.
- S0 8-node at 14 days: adapt-final loses to static_loop (−0.075, −0.080 in two scenarios).
- Calibration in the S4-fitted world (Brier 0.248 → 0.283) because the selected world profile did not match it.
- The diagnostic is slightly harmful (headline −0.017).
- The bandit (frozen, updating) and random rankings do not differ from the deterministic ranking; per-learner updating does not change choices.
- Review cap and goal-path relevance (D.1) do not fix review crowding on synth-20.
- Elo lowers goal mastery; HLR-lite fits worse than a constant and lowers goal mastery; BKT forgets makes θ unreachable.
## 13. Acceptance Register (23 TC IDs, Milestones, D49–D60)

All 23 TC IDs stay **Verified** as in W7 (`docs/TRACEABILITY.md`), with W8 tests linked in its new section; TC2.1's error clause keeps its W7 status. M1–M8 frozen and verified. D49–D60 registered (proposed) in `docs/DECISIONS.md` §8 and `docs/FREEZE_RECORD.md`. Final test state: `make check` 334 passed, 1 skipped (CP-SAT parity, OR-Tools absent), coverage 89%, ruff clean; API tests 16 passed; Playwright 5 passed.
## 14. Limitations

- All learners are simulated (S0, S1, S4, S4-fitted); the pilot (O.7) did not run. The headline gain is largest in S1, the world whose prerequisite-gated learning matches the engine's assumptions.
- The gain depends on the horizon; at short horizons a state-blind loop beats the stricter engine.
- Profiles are fitted per world on that world's data (the deployment analogue is fitting on a population); a mismatched profile hurts (S4-fitted).
- C.1 and C.2 are evaluated together; D50's separate effect is unknown.
- Agent evaluations need a live model and were not run; only offline tests and stub plumbing exist.
- O.2's S3 cells duplicate S0 because of how S3 interacts with the fast_forgetter profile (pre-registration oversight).
- Frontend: Radix/lucide packages not installed; visual snapshots are machine-specific (regenerate on another OS).
## 15. Reproduction Commands

```bash
make check                                              # lint + tests + coverage
python experiments/probes/probe_w8_baseline.py          # 0.2 probe numbers          (~1 min)
python experiments/probes/probe_w8_gate.py              # WP-A exit gate              (~1 min)
python experiments/fit_bkt_sim.py w8                    # B.2 fits                    (~2 min)
python experiments/run_calibration_select.py            # B.3 selection               (~2 min)
python experiments/run_final_grid.py --procs 14         # G.2 final grid              (~39 min, resumable)
python experiments/train_policy.py                      # J.5 frozen bandit           (~4 min)
python experiments/run_policy_eval.py                   # J.6 + OPE
python experiments/run_extensions.py                    # D.1, O.1-O.4
python experiments/run_agent_eval.py --provider stub    # agent plumbing (live: see docs/AGENTS.md)
python experiments/make_final_results.py                # docs/FINAL_RESULTS.md + figures
make final                                              # all of the above in order
make demo                                               # demo app
cd frontend/web && npx playwright test                  # demo + screens + failure states
```

## 16. Deviations from Plan

| What | Why | Consequence |
|---|---|---|
| Verbatim review probes excluded from ruff | They must stay byte-identical to the review's copies | Lint stays clean; the probes are not reformatted |
| "two_part" mastery criterion = the existing `two_threshold` criterion | Same definition (θ and entropy); no new name needed | C.3 switches to `two_threshold` with k = 3, H ≤ 0.35 |
| Review cap applies only while new content is pending | A cap after new content ends would only leave minutes unused, against WP-C | Maintenance/consolidation days are not capped |
| Due reviews (Tier 1) are scheduled before consolidation (Tier 3), not after | Keeps the existing tier order; reviews are already prerequisite-gated | Consolidation fills the time left after due reviews |
| Bandit: LinUCB scores + softmax (not Thompson sampling) | Exact propensities without a Gaussian sampler; pure Python (no numpy in the core) | Spec D53 documents LinUCB |
| "Minutes since practice" feature uses days | The planner's clock is days | Documented in `POLICY_SPEC.md` |
| Claude provider: no temperature 0 | Current Claude models reject sampling parameters (Claude API reference) | Reproducibility comes from the prompt-hash cache |
| `adapt_cal` ablation arm added to the final grid | Separates calibration from C.1/C.2 effects | Evaluation only; pre-registered |
| B.2 data source amended (static_loop + random_eligible) | p0 and T_lesson not identifiable from static_loop alone | Amendment 1, written before any fit |
| D52: diagnostic made optional although the rule's condition (CI includes 0) was not met | The diagnostic was significantly *worse*; the rule did not define that case; "optional" follows its intent | Recorded in D52 and §7 |
| O.2 S3 cells duplicate S0 | S3 adds forgetting only when the profile has none; forgetting_21 uses fast_forgetter | Reported, not re-run (the pre-registered design is kept) |
| WP-H: Radix/lucide/@fontsource/framer-motion/react-markdown not installed | Package installs are a human handover; plan fallback "tokens and Tailwind only" | Same screens and behaviour; shadcn-style components hand-written |
| H.0: no failing step was reported | The user did not send a symptom; the old app built and its Playwright run passed here | The rebuild targets the R§3.2 failure modes instead |
| Live agent evaluations (L.4, M.3, N.3, K.5 real draft), O.4 CP-SAT run, O.5 Junyi, O.6 CSEDM, O.7 pilot, I.3 content review | Need an API key / local model, OR-Tools, datasets, participants or a human reviewer | Marked "not run"; code, tests and runners are ready |
| F.3 latency: W8 code (flags off) is ~20–27% slower than W7 after T6.1 (`w8_latency.json`: 4-node 2.18 vs 1.83 ms, synth-50 28.7 vs 22.5 ms) | Scheduler bookkeeping (required set, recency map) now runs on every call even with W8 flags off | Not changed (would change the code hash after the final runs); follow-up: compute them only when a flag needs them |
| `make check` / `make w6` rewrite `experiments/results/replan_latency.json` | Existing W6 runner behaviour | The human decides whether to keep or restore the file (§17.2) |

## 17. Git Actions for the Human

No git command was run by me. The existing W3–W6 runners (`make w3`–`w6`) call `git rev-parse` / `git status` read-only, unchanged from W7.

### 17.1 New and Modified Files Inventory

- **Engine (`src/adaptengine/`)** — new: `core/profiles.py`, `learner/elo.py`, `review/hlr.py`, `planner/{cpsat,options,validate_proposal}.py`, `policy/{__init__,base,features,bandit,agent}.py`, `policy/agent_prompt.md`, `authoring/{__init__,providers,draft,checks}.py`, `agents/{__init__,plan_proposer,orchestrator}.py`; modified: `api.py`, `cli.py`, `core/{config,schema}.py`, `learner/{adapter,mastery}.py`, `planner/{plan,schedule,workload}.py`, `replanner/replan.py`.
- **Tests** — new: `test_w8_engine.py`, `test_policy.py`, `test_agent_policy.py`, `test_authoring.py`, `test_plan_proposer.py`, `test_orchestrator.py`, `test_bkt_lessons.py`, `test_ope.py`, `test_provenance.py`; modified: `test_arms.py`, `test_stats.py`, `test_architecture.py`, `test_w7_planner.py`.
- **Experiments** — new: `w8_common.py`, `bkt_lessons.py`, `run_calibration_select.py`, `run_final_grid.py`, `make_final_results.py`, `policy_runner.py`, `train_policy.py`, `run_policy_eval.py`, `ope.py`, `run_extensions.py`, `run_agent_eval.py`, `probes/{__init__,probe_w8,probe_w8_calib,probe_w8_sweep,probe_w8_baseline,probe_w8_gate}.py`; modified: `arms.py`, `stats.py`, `fit_bkt_sim.py`, `run_w7_grid.py`, `make_w7_results.py`.
- **Results** — new: `experiments/results/{final_grid.json,w8_probe_baseline.json,w8_fits.json,w8_calibration_select.json,w8_policy_train.json,w8_policy_eval.json,w8_extensions.json,w8_hlr_fit.json,w8_agent_eval_stub.json,w8_latency.json,w8_bkt_fit_assist09.json,w8_bkt_fit_ct.json}`; config `config/{fitted_S0,fitted_S1,fitted_S3,fitted_S3_forget,fitted_S4,policy_frozen}.json`; `config/fitted_assist09.json` (re-fitted at the final hash, F.3); modified by `make w6`: `replan_latency.json`. Ignored (regenerated): `final_grid.ckpt.jsonl` (79 MB), `final_grid_smoke.json`, `policy_logs/`, `agent_cache/`, `data/drafts/`.
- **Frontend** — `frontend/api/{app,schemas}.py`, `frontend/api/tests/test_api.py`, `frontend/README.md`; `frontend/web/src/**` (new `styles/tokens.css`, `shell/*`, pages `Overview`, `PolicyLab`, `AuthoringStudio`; rewritten `App.tsx`, `ctx.ts`, `components/ui.tsx`, `pages/{CurriculumMap,Autopilot,Evaluation,PlanPage,NoSession}.tsx`; edited Setup, Diagnostic, Study, PlanTimeline, WhyPanel, `api/client.ts`, regenerated `api/schema.d.ts`), `openapi.json`, `e2e/{demo,screens}.spec.ts`, `e2e/screens.spec.ts-snapshots/*.png` (22), `scripts/demo-screenshots.mjs`.
- **Docs** — new: `docs/WEEK8_REPORT_NOTES.md`, `docs/FINAL_RESULTS.md`, `docs/FINAL_REPORT.md`, `docs/PRESENTATION_OUTLINE.md`, `docs/POLICY_SPEC.md`, `docs/AGENTS.md`, `docs/AUTHORING.md`, `docs/preregistration/FINAL_A5_2026-11-10.md`, `docs/figures/final_*.png` (5), `docs/figures/demo_*.png` (11); modified: `docs/DECISIONS.md`, `docs/FREEZE_RECORD.md`, `docs/TRACEABILITY.md`.
- **Build/CI/scripts** — `Makefile` (`demo`, `final`), `pyproject.toml` (1.0.0, `[agents]`, `[solver]`, package data, ruff excludes), `.gitignore`, `.github/workflows/ci.yml`, `scripts/{demo,run_final}.py` (new), `scripts/record_review.py`.

### 17.2 Commands for the Human (run after verification, in order)

```bash
git status                                    # review; .VSCodeCounter/ was untracked before W8
git switch -c week8-final                     # work on a branch
git checkout -- experiments/results/replan_latency.json   # only if you do not want make w6's rewrite
.venv/bin/python scripts/record_review.py data/content/content_8node.json --reviewer "Your Name" --source "ai-drafted demo content" --ai-assisted   # I.3, after reading the content
git add -A src tests experiments config docs frontend scripts Makefile pyproject.toml .gitignore .github data/review_manifest.json
git status                                    # confirm no checkpoint/draft/cache files are staged
git commit -m "Week 8: final improvements, agentic layer, frontend rebuild, final results"
git push -u origin week8-final                # then open a PR; CI runs the demo job
git tag -a v1.0.0 -m "AdaptEngine 1.0.0 (final)"   # after merging
git push origin v1.0.0
```

Optional human steps before tagging: `.venv/bin/pip install -e ".[agents,solver]"`, then `.venv/bin/python experiments/run_agent_eval.py --provider anthropic --populate`, `.venv/bin/pytest -q tests/test_w8_engine.py -k cpsat`; Junyi / CSEDM downloads (O.5, O.6).

### 17.3 Suggested Commit Progression (one group per WP)

1. WP0 + WP-A: `experiments/probes/`, `experiments/{arms,stats}.py`, `tests/test_{arms,stats,provenance}.py`, `.gitignore`, `pyproject.toml` (ruff excludes), notes.
2. WP-B/C/D/E/F engine flags: `src/adaptengine/{core,learner,planner,replanner,review}/`, `api.py`, `tests/test_w8_engine.py`, `tests/test_bkt_lessons.py`, `experiments/{bkt_lessons,fit_bkt_sim,w8_common,run_calibration_select}.py`, `config/fitted_S*.json`, prereg file, `w8_fits.json`, `w8_calibration_select.json`.
3. WP-J/K/L/M/N agentic layer: `src/adaptengine/{policy,authoring,agents}/`, `cli.py`, `scripts/record_review.py`, related tests, `experiments/{policy_runner,train_policy,run_policy_eval,ope,run_agent_eval}.py`, `config/policy_frozen.json`, `docs/{POLICY_SPEC,AGENTS,AUTHORING}.md`.
4. WP-O extensions: `learner/elo.py`, `review/hlr.py`, `planner/cpsat.py`, `experiments/run_extensions.py`, results.
5. WP-G results: `experiments/{run_final_grid,make_final_results}.py`, `final_grid.json`, `docs/FINAL_RESULTS.md`, `docs/figures/final_*.png`.
6. WP-H frontend: `frontend/**`, `scripts/demo.py`, `Makefile`, `.github/workflows/ci.yml`, `docs/figures/demo_*.png`.
7. WP-I docs and release: `docs/{FINAL_REPORT,PRESENTATION_OUTLINE,DECISIONS,FREEZE_RECORD,TRACEABILITY,WEEK8_REPORT_NOTES}.md`, `scripts/run_final.py`, version 1.0.0.
