# Experiment Suite Rewrite and Re-run (Product Engine) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every W6–W8 experiment, except the fitted-parameter experiments, with one small suite that measures the engine as it ships today: the product config. Then re-run the suite and publish the new results.

**Architecture:** The plan works in three phases:
1. Archive and delete the old runners and results (Task 1).
2. Keep the shared simulation harness, which the fits and the web app's `/api/simulate` endpoint also import: `sim.py`, `arms.py`, `checks.py`, `stats.py`, `provenance.py` and `synth_curriculum.py`.
3. Write six focused runners (E1–E6) on top of one new `experiments/common.py`. `common.py` builds the product engine and holds seeds, curricula and the results writer. The suite is pre-registered before any full run. One generator, `experiments/make_results.py`, turns the results into `docs/RESULTS.md`.

**Tech Stack:** Python 3.11 (`.venv`), numpy/pandas (already used), OR-Tools (installed), pytest, multiprocessing (16 cores).

**Spec:** `docs/superpowers/specs/2026-11-14-strict-mastery-and-goal-search-diagnostic-design.md` defines the product (§5) and the evaluation (§6). This plan supersedes:
- `docs/preregistration/FINAL_A5_2026-11-10.md` §4–§7, for new runs only.
- The deleted `docs/superpowers/plans/2026-11-14-w9-rerun-experiments-implementation-plan.md`, which kept W6–W8 and added `--product` flags. This plan deletes them instead.

---

## Part A — What was done before (scraped inventory)

Each row lists one old experiment, its design, its result file, and what this plan does with it. "Ported" means its question survives in a new runner. Seeds use the FINAL_A5 sets: fit = even 2000–2398, select = even 4000–4398, train = even 6000–6398, HLR = even 8000–8398, report = odd 2001–2399, headline = odd 2001–3999. W6 and W7 used the older 100–299 seeds.

| # | Old experiment | Question | Design | Result file | Fate |
|---|---|---|---|---|---|
| 1 | W6 paired baseline (`run_evaluation.py`, `scripts/run_w6.py`) | Does the adaptive diagnostic beat fixed and random order, and does the planner beat the static baselines? | 4-node and 8-node; diagnostic arms adaptive / fixed@{n,4,8} / random@{n,4,8}; planner arms adapt / no_review / no_replan / static; θ 0.85, k 2, n_max 8, cap 3, flat prior | `evaluation_results.json`, `w6_baseline.json` | Ported: E1 (planner), E2 (diagnostic) |
| 2 | W6 diagnostic tuning (`diag_eval.py`) | Matched-budget MAE (all concepts and assessed concepts only) | 4-node, S0 | (feeds #1) | Ported: E2 |
| 3 | W6 replan latency (`run_replan_latency.py`) | Full vs frontier replanning cost | 4-node, 8-node, synth-20, synth-50 × event types | `replan_latency.json` | Ported: E6 |
| 4 | W7 T3.3 diagnostic selection (`run_diag_selection.py`) | Which diagnostic settings to pick (pre-registered) | 648-config grid: min_items {1,2} × pruning {hard,soft,none} × scope {sweep,frontier} × prior {flat,pop} × h_stop {.2,.35,.5} × cap {2,3,4} × n_max {4,6,8}; 4-node, S0; tune = even 100–198, held-out = odd 101–199 | `w7_diag_selection.json` | Dropped as a selection. The product diagnostic is fixed by D62. Its axes become E3 sensitivity scans |
| 5 | W7 T3.7 diagnostic matrix (`run_diag_matrix.py`, `cat_baseline.py`) | Diagnostic accuracy across worlds | S0, S2, S4; arms prior-only, W6 shipped, T3.3 default, min-k, soft prune, frontier, R§7.4 recommendation, state-space, fitted BKT, fixed order, 2PL IRT-CAT | `w7_diag_matrix.json` | Ported: E2 |
| 6 | W7 T4.4 full grid (`run_w7_grid.py`) | Closed-loop outcome across the whole design space | S0–S4 × 4-node / 8-node / synth-20 × B {5,10,15,30} × 8 scenarios × arms adapt / adapt_expected / no_review / no_replan / static; N = 200, headline 1000 | `w7_grid.json` (+ `w7_grid_prereg.json`, `w7_grid_fix1.json`) | Ported: E1 (primary + stress grids) |
| 7 | W7 WP5 sensitivity (`run_sensitivity.py`) | How sensitive is the loop to heuristic parameters? | One-at-a-time scans, θ×k factorial, other mastery criteria; S0, S1 × 4-node, 8-node; B 15 calm; N = 200 | `w7_sensitivity.json` | Ported: E3 (centred on the product) |
| 8 | W7 T7.5 S4-fitted (`run_s4_fitted.py`) | Does the result hold in an ASSISTments-shaped world? | S4 + `fitted_assist09`; 4-node; B 15; calm, missed_day; adapt / no_replan / static; N = 200 | `w7_s4_fitted.json` | Ported: E1 world `S4F` |
| 9 | W7 T6.1 latency (`run_w7_latency.py`) | Planning latency and plan identity with graph indices | 4/8/synth-20/synth-50 × budgets × deadlines × events | `w7_latency.json`, `w8_latency.json` | Ported: E6 |
| 10 | W7 T3.5 / T7 BKT fits (`fit_bkt.py`, `fit_bkt_sim.py`) | Real-data and simulated BKT parameters | ASSISTments09, CT (pyBKT parity); simulated S0 tuning cohort | `bkt_fit_assist09.json`, `bkt_fit_ct.json`, `bkt_fit_ct_pybkt.json`, `bkt_fit_sim.json`, `config/fitted_assist09.json`, `config/fitted_sim.json` | **Kept, not re-run** (fitted parameters) |
| 11 | W8 B.2 per-world profile fits (`fit_bkt_sim.py w8`, `bkt_lessons.py`) | Lesson-aware BKT per world | static_loop + random_eligible episodes; S0, S1, S4 (+ S3 forget); 4-node, 8-node; B 15 calm 14 d; fit seeds; Baum–Welch, 5 restarts | `w8_fits.json`, `w8_bkt_fit_ct.json`, `w8_bkt_fit_assist09.json`, `config/fitted_S{0,1,3,4}.json`, `config/fitted_S3_forget.json` | **Kept, not re-run.** `fitted_S1` is the product profile; refitting it would change the product |
| 12 | W8 probes (`probes/probe_w8*.py`) | Why adapt trailed keep-practising on long horizons | 4-node, B 15, seeds 100–299 | `w8_probe_baseline.json` (others print only) | Dropped: scratch diagnosis, answered by W8 C.1–C.3 |
| 13 | W8 B.3 calibration selection (`run_calibration_select.py`) | C0 vs F1–F5 (θ / k / horizon-aware) | S0, S1, S4 × 4/8-node; select seeds; primary in-loop Brier | `w8_calibration_select.json` (winner F5) | Dropped as a selection. D61 overrides it with θ 0.95, k 1. θ, k and horizon-aware become E3 scans |
| 14 | W8 G final grid (`run_final_grid.py`) | Final engine vs baselines | Arms adapt_w7, adapt_final, adapt_final_dx, adapt_cal, static, static_loop, random_eligible, no_replan; S0, S1, S4, S4F × 4/8-node × B {10,15} × calm / missed_day / missed_2days × horizons {w7,7,14,21} + forgetting_21; N = 200, headline S1·4-node·15·calm·14 at 1000 | `final_grid.json`, `final_grid_smoke.json`, `final_grid.ckpt.jsonl` | Ported: E1 primary grid |
| 15 | W8 J.5/J.6 policy (`train_policy.py`, `run_policy_eval.py`, `policy_runner.py`, `ope.py`) | Does a LinUCB bandit re-ranker help? Can OPE predict its value? | Train on S1, S4 × 4/8-node; eval deterministic / frozen / updating / random; IPS / SNIPS / DR | `w8_policy_train.json`, `w8_policy_eval.json`, `policy_logs/`, `config/policy_frozen.json` | Ported: E4 (retrained on the product) |
| 16 | W8 extensions (`run_extensions.py`) | D.1 review cap, O.1 Elo, O.2 HLR-lite, O.3 BKT forgets | See FINAL_A5 §7 | `w8_extensions.json`, `w8_hlr_fit.json` | Ported: E5. HLR is refit on product episodes because it depends on the engine |
| 17 | W8 O.4 CP-SAT (`run_cpsat_eval.py`) | CP-SAT vs greedy/oracle plan length and latency | synth-20/50, seed 2026, deepest goal | `w8_cpsat_eval.json` | Ported: E6 |
| 18 | W8 agent eval (`run_agent_eval.py`) | LLM agent ranking | Stub provider only (plumbing) | `w8_agent_eval_stub.json` | Dropped: never a real evaluation, and it needs a live model. Out of scope |
| 19 | W8 grid smoke (`run_final_grid.py --arms adapt_strict_*`) | Strict mastery + goal search, first look | S1 · 4-node · 15, N = 20 | `w8_grid_smoke.json` | Superseded by E1 |
| 20 | W8 diagnostic (`run_w8_diag.py`) | Goal search vs prior-only / W6 / T3.3 | — | **never run** (`w8_diag_matrix.json` missing) | Superseded by E2 |
| — | Results builders (`make_w7_results.py`, `make_final_results.py`), `run_smoke.py`, `w8_common.py` | Tables, figures, helpers | — | `docs/WEEK7_RESULTS.md`, `docs/FINAL_RESULTS.md`, `docs/figures/{w7,final}_*.png` | Replaced by `make_results.py` / `common.py`. The old docs stay as history |

### Shared definitions carried over verbatim (EVALUATION_PROTOCOL, FINAL_A5)

- **Worlds** (`experiments/sim.py`):
  - **S0:** θ ~ U(0.10, 0.90) per concept, 2PL a = 3.0.
  - **S1:** S0 + readiness gating sigmoid(10(θ_pre − 0.70)).
  - **S2:** correlated abilities, g ~ U(0.2, 0.8), θ_c = clip(g + N(0, 0.10), 0.05, 0.95).
  - **S3:** per-learner forgetting, h ~ U(5, 30) d.
  - **S4:** the engine's own BKT heuristics: P0 0.20, g(d) = 0.30(1 − d), s(d) = 0.05 + 0.25d, T_lesson 0.20, T_ex 0.05.
  - **S4F:** S4 with `s4_fitted_params("config/fitted_assist09.json")`.
- **True mastery:** θ ≥ `TRUE_MASTERY_CUTOFF` = 0.70.
- **Sim profiles:** nominal (lesson / exercise gain 0.18 / 0.05), high_slip, fast_forgetter (h = 7 d), rapid_learner.
- **Scenarios** (`arms.get_scenario`): calm, missed_day, budget_drop, deadline_cut, missed_2days, budget_crash (30→5), deadline_halved, forgetting_21 (fast_forgetter, 21 days). Horizons are `("w7", 7, 14, 21)`. `w7` is computed from the W7 default engine for every arm.
- **Run modes** (`arms.run_episode`): `adapt`, `adapt_dx`, `no_review` (closed loop); `static`; `static_loop`, `random_eligible` (sequence); any other name, for example `no_replan`, plans once.
- **Statistics:** paired bootstrap 95% CI (2000 resamples, seed 20260), no multiplicity correction, every cell reported.

---

## Part B — Keep / delete manifest

**Keep (fitted-parameter experiments and the harness they import):**
- Fitting code: `experiments/fit_bkt.py`, `experiments/fit_bkt_sim.py`, `experiments/bkt_lessons.py`.
- Harness, imported by the fits, by `frontend/api/app.py` `/api/simulate`, and by the new runners: `experiments/sim.py`, `experiments/arms.py`, `experiments/checks.py`, `experiments/stats.py`, `experiments/provenance.py`, `experiments/synth_curriculum.py`, `experiments/__init__.py` (if present).
- Results: `bkt_fit_assist09.json`, `bkt_fit_ct.json`, `bkt_fit_ct_pybkt.json`, `bkt_fit_sim.json`, `w8_fits.json`, `w8_bkt_fit_ct.json`, `w8_bkt_fit_assist09.json`.
- Config: `config/fitted_*.json` (all 7).
- Tests: `test_arms`, `test_sim`, `test_stats`, `test_eval_checks`, `test_provenance`, `test_bkt_lessons`, `test_agent_policy`, `test_orchestrator`, `test_policy`, `test_planner`, `test_w7_planner`, `test_w8_engine`. These import only harness modules.
- Docs: `docs/preregistration/*.md`, `docs/WEEK*_REPORT*.md`, `docs/WEEK7_RESULTS.md`, `docs/FINAL_RESULTS.md`, `docs/figures/*`. They stay as history, each with a one-line banner (Task 1).

**Delete:**
- Runners and helpers: every other `experiments/*.py`, namely `cat_baseline`, `diag_eval`, `make_final_results`, `make_w7_results`, `ope`, `policy_runner`, `run_*` (all 18), `train_policy`, `w8_common`.
- `experiments/probes/` (whole directory).
- Every other `experiments/results/*` file, including `policy_logs/` and the checkpoints.
- `scripts/run_w6.py`, `scripts/run_final.py`.
- Tests: `test_diag_eval`, `test_evaluation`, `test_cpsat_eval`, `test_ope`, `test_w8_eval`.
- `config/policy_frozen.json` is **regenerated** by E4, not deleted up front, because the web Policy Lab reads it.

**Also edit:** `scripts/verify_clean_checkout.sh` lines 39–42 call `run_evaluation.py`. Point them at the E2 smoke run (Task 3).

---

## Global Constraints

- **Product engine:** `product_config(profile)` = `load_profile(profile, **PRODUCT_OVERRIDES)` from `adaptengine.core.profiles`. That is θ 0.95, k_responses 1, horizon_aware_mastery off, consolidation **off**, verification_probe on, feasibility_warning on, selection_scope `goal_search`, concept_cap 4, n_max 25, diag_budget_min 12, diag_budget_per_concept 1.0, diagnostic_scope `goal_path`.
- **Ruling:** product arms use `fitted_S1` in **every** simulated world, as real users get. The only exception is E5 O.3, which compares `fitted_S3` with `fitted_S3_forget`.
- **Curricula:** `4node_x10`, `8node_x10` (promoted from `data/drafts/`), `synth-20-x10`, `synth-50-x10`. The x10 difficulties are `(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9)`.
- **Seeds:** FINAL_A5 sets, unchanged (Part A header). Reporting uses odd seeds only. Tuning and fitting never touch odd seeds.
- **Outputs:** every new result goes to `experiments/results/<name>.json`, carrying a `provenance.stamp()` (code hash + UTC timestamp) and `"engine": "product"`.
- Executed prerequisite violations must be 0 in every adaptive arm. Static baselines may violate by design.
- **Measurement only:** nothing is selected from report seeds, and results are reported whatever they show.
- Never run `scripts/record_review.py` or edit `data/review_manifest.json`; the owner does that.
- Git: one commit per task, only after the owner approves this plan. The Task 1 deletion happens only after the owner confirms the Part B manifest.

## Review Focus

1. **Unpromoted x10 curriculum:** `common.curriculum_paths("4node_x10")` must raise `FileNotFoundError` when the file is not in `data/curriculum/`. It must never fall back to the 4-exercise file. Test: `test_x10_missing_raises` (Task 2).
2. **Product arm drift:** a runner that builds its engine without `product_engine` would silently measure W7 defaults. Test: `test_product_arm_is_product_config` (Task 3), and every runner test asserts `meta["engine"] == "product"`.
3. **Deleting something the app needs:** `/api/simulate` imports `experiments.arms` and `experiments.sim`, and the Policy Lab reads `config/policy_frozen.json`. Test: `frontend/api/tests` must pass after Task 1.
4. **The kept fits still run:** `fit_bkt_sim.py` imports `arms`, `sim`, `provenance` and `fit_bkt`. Test: `test_fit_bkt_sim_imports` (Task 1).
5. **Diagnostic arms not on a matched budget:** fixed, random and IRT-CAT must use exactly the item count the product diagnostic used for that learner. Test: `test_matched_budget` (Task 4).

---

### Task 0: Owner prerequisites (no code)

- [ ] **Step 1:** The owner confirms the Part B keep/delete manifest, in particular that the HLR fit and the bandit policy are re-run rather than kept.
- [ ] **Step 2:** The owner promotes the x10 drafts: `scripts/record_review.py --promote-draft data/drafts/4node_x10` and the same for `8node_x10`. Check: `ls data/curriculum/*_x10.json` lists 4 files.
- [ ] **Step 3:** Archive tag, so that every deleted file stays reachable: `git tag pre-experiment-rewrite`.

---

### Task 1: Delete old experiments; keep the harness green

**Files:**
- Delete: everything under "Delete" in Part B.
- Modify: `scripts/verify_clean_checkout.sh:39-42`. For now, comment out the block with `# replaced in Task 4`.
- Modify: add a first line to `docs/FINAL_RESULTS.md` and `docs/WEEK7_RESULTS.md`: `> Historical (W7/W8 engine). Source results were removed in the experiment rewrite; see tag pre-experiment-rewrite. Current results: docs/RESULTS.md.`
- Test: `tests/test_harness_kept.py` (new).

- [ ] **Step 1: Failing test.**

```python
def test_fit_bkt_sim_imports():
    import experiments.fit_bkt_sim, experiments.fit_bkt, experiments.bkt_lessons  # noqa

def test_fitted_results_kept():
    for f in ["bkt_fit_assist09", "bkt_fit_ct", "bkt_fit_ct_pybkt", "bkt_fit_sim",
              "w8_fits", "w8_bkt_fit_ct", "w8_bkt_fit_assist09"]:
        assert os.path.exists(f"experiments/results/{f}.json")

def test_old_runners_gone():
    assert not glob.glob("experiments/run_*.py") and not os.path.exists("experiments/probes")
```

- [ ] **Step 2:** `.venv/bin/python -m pytest tests/test_harness_kept.py -v`. The first two tests pass and `test_old_runners_gone` fails.
- [ ] **Step 3:** `git rm` the Part B delete list, then add the doc banners.
- [ ] **Step 4:** `.venv/bin/python -m pytest -q tests frontend/api/tests`. Expected: all pass, with no `ImportError` from `experiments`.
- [ ] **Step 5:** Commit `chore: remove W6–W8 experiment runners and results (fits kept)`.

---

### Task 2: `experiments/common.py` and x10 synthetic curricula

**Files:**
- Create: `experiments/common.py`.
- Modify: `experiments/synth_curriculum.py`. `generate_synthetic_curriculum` (line 14) and `write_synthetic_curriculum` (line 112) gain `difficulties: tuple[float, ...] = (0.20, 0.40, 0.60, 0.80)`. x10 files get the suffix `_x10`.
- Test: `tests/test_exp_common.py`.

**Interfaces (produces):**
- `X10_DIFFICULTIES` in `synth_curriculum`.
- In `common`:
  - Seed tuples `FIT_SEEDS`, `TRAIN_SEEDS`, `HLR_SEEDS`, `REPORT_SEEDS`, `HEADLINE_SEEDS`, with the same values as FINAL_A5 §1.
  - `CURRICULA = ("4node_x10", "8node_x10", "synth-20-x10", "synth-50-x10")`.
  - `curriculum_paths(cur: str) -> tuple[str, str]`: `data/curriculum/{curriculum,activities}_<cur>.json` for x10 hand-written curricula, raising `FileNotFoundError` if missing. `synth-N-x10` is generated once per process into a temp dir (seed 2026).
  - `product_engine(cur: str, profile: str = "fitted_S1", policy=None, **overrides) -> Engine`: config = `product_config(profile)` with `overrides` applied through `dataclasses.replace`, cached by `(cur, profile, sorted overrides)`.
  - `goal_of(engine) -> str`: the deepest concept, with ties broken by id (same rule as the old `w8_common.goal_of`).
  - `world_kw(world: str) -> tuple[str, dict]`: maps `"S4F"` to `("S4", {"bkt_params": s4_fitted_params("config/fitted_assist09.json")})` and any other world to `(world, {})`.
  - `write_result(name: str, payload: dict) -> str`: writes `experiments/results/<name>.json` with `payload["meta"] |= {**stamp(), "engine": "product"}` and returns the path.
  - `run_parallel(fn, units, processes=None) -> list`: a multiprocessing pool, results in the input order.

- [ ] **Step 1: Failing tests.**

```python
def test_synth_default_unchanged(tmp_path):     # pin the hashes BEFORE editing the generator
    c, a = write_synthetic_curriculum(str(tmp_path), 20, seed=2026)
    assert (_h(c), _h(a)) == (PINNED_C, PINNED_A)

def test_synth_x10_has_ten_exercises():
    e = product_engine("synth-20-x10")
    for cid in e.graph.concepts():
        assert sorted(x.difficulty for x in e.activities.values()
                      if x.target_concept == cid and x.type == ActivityType.EXERCISE) == list(X10_DIFFICULTIES)

def test_x10_missing_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        curriculum_paths("4node_x10")

def test_product_engine_is_product_config():
    assert product_engine("4node_x10").config == product_config()
    assert product_engine("4node_x10", consolidation=True).config.consolidation is True

def test_seeds_disjoint():
    assert not set(REPORT_SEEDS) & set(FIT_SEEDS + TRAIN_SEEDS + HLR_SEEDS)
    assert all(s % 2 for s in HEADLINE_SEEDS) and len(HEADLINE_SEEDS) == 1000

def test_write_result_stamps(tmp_path, monkeypatch): ...  # meta has code_hash, timestamp_utc, engine == "product"
```

- [ ] **Step 2:** Run the tests and confirm they fail with `ImportError`.
- [ ] **Step 3:** Implement the interfaces above.
- [ ] **Step 4:** Run the file and the full suite. Expected: PASS.
- [ ] **Step 5:** Commit.

---

### Task 3: E1 closed-loop grid (`experiments/run_grid.py`)

Answers rows #1 (planner), #6, #8, #14 and #19.

**Files:** create `experiments/run_grid.py`; test `tests/test_exp_grid.py`.

**Interfaces:**
- Consumes `common.*`, `arms.get_scenario`, `arms.run_episode`, `sim.PROFILES`, `stats.paired_bootstrap_ci`, `stats.km_median`, `stats.km_rmst`, `stats.brier_score`, `stats.roc_auc`.
- Produces `ARMS: dict[str, tuple[Callable[[str, str], Engine], str]]`, mapping each arm name to an `(engine factory (cur, world), run mode)` pair:

| Arm | Engine | Mode | Purpose |
|---|---|---|---|
| `product` | `product_engine(cur)` | `adapt_dx` | the shipped flow |
| `product_nodx` | `product_engine(cur)` | `adapt` | value of the diagnostic (old D52) |
| `product_consol` | `product_engine(cur, consolidation=True)` | `adapt_dx` | value of consolidation (old D49) |
| `product_norev` | `product_engine(cur)` | `no_review` | value of spaced review (compare with `product_nodx`) |
| `product_noreplan` | `product_engine(cur)` | `no_replan` | value of replanning |
| `w8_final` | `product_engine(cur, profile=f"fitted_{S4 if world=='S4F' else world}", theta=0.85, k_responses=2, horizon_aware_mastery=True, consolidation=True, selection_scope="concept_sweep", concept_cap=2, n_max=6, diag_budget_per_concept=0.0)` | `adapt_dx` | what changed since W8 |
| `static`, `static_loop`, `random_eligible` | `product_engine(cur)` | same name | baselines |

- Grids:
  - `PRIMARY`: worlds S0, S1, S4, S4F × `4node_x10`, `8node_x10` × B {10, 15} × (calm, missed_day, missed_2days × horizons w7/7/14/21, plus forgetting_21 at 21) × all arms; N = 200 report seeds. Headline cell `S1|4node_x10|15|calm|14` uses N = 1000.
  - `STRESS`: worlds S0–S4 × `4node_x10`, `8node_x10`, `synth-20-x10` × B {5, 15, 30} × budget_drop, deadline_cut, budget_crash, deadline_halved (horizon w7) × arms `product`, `product_noreplan`, `static_loop`; N = 200.
- Per cell, the summary covers:
  - goal mastery and all-required mastery, each vs `static_loop` with a paired CI;
  - false-mastery rate, utilisation, diagnostic minutes;
  - items per mastered concept;
  - KM median and RMST (τ = minutes available);
  - in-loop Brier and AUC;
  - executed and plan prerequisite violations, budget violations.
- CLI: `--grid primary|stress|both`, `--smoke` (2 cells, 20 seeds), `--resume`. The checkpoint is `experiments/results/grid.ckpt.jsonl`, one line per (cell, arm, seed). Output: `grid.json` or `grid_smoke.json`.

- [ ] **Step 1: Failing tests.**

```python
def test_product_arm_is_product_config():
    f, mode = ARMS["product"]; assert f("4node_x10", "S0").config == product_config() and mode == "adapt_dx"

@pytest.mark.parametrize("arm,mode,field,val", [
    ("product_nodx", "adapt", "consolidation", False),
    ("product_consol", "adapt_dx", "consolidation", True),
    ("product_norev", "no_review", "theta", 0.95),
    ("w8_final", "adapt_dx", "theta", 0.85)])
def test_arm_variants(arm, mode, field, val): ...

def test_w8_final_uses_world_profile():
    assert ARMS["w8_final"][0]("4node_x10", "S4F").config.profile == "fitted_S4"

def test_smoke_zero_violations(tmp_path):
    out = main(["--smoke", "--out-dir", str(tmp_path)])
    for cell in out["cells"].values():
        for arm, s in cell["arms"].items():
            if arm.startswith(("product", "w8_final")): assert s["executed_prereq_violations"] == 0
    assert out["meta"]["engine"] == "product"

def test_resume_skips_done_units(tmp_path): ...  # second --resume run executes 0 episodes
```

- [ ] **Step 2:** Confirm the tests fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Confirm the tests pass. Then run the smoke: `.venv/bin/python experiments/run_grid.py --smoke`.
- [ ] **Step 5:** Commit.

---

### Task 4: E2 diagnostic matrix (`experiments/run_diag.py`, `experiments/diag_baselines.py`)

Answers rows #1 (diagnostic), #2, #5 and #20.

**Files:**
- Create `experiments/diag_baselines.py`. Port `run_fixed_diagnostic`, the random-order variant and `irt_cat` from `git show pre-experiment-rewrite:experiments/diag_eval.py` and `…:experiments/cat_baseline.py`, cut down to what is listed below.
- Create `experiments/run_diag.py`.
- Test: `tests/test_exp_diag.py`.

**Interfaces:**
- `diag_baselines.fixed_order(engine, learner, n: int) -> dict[str, float]` (topological order, mid-difficulty first); `random_order(engine, learner, n, seed) -> dict[str, float]`; `irt_cat(engine, learner, n) -> dict[str, float]`. Each returns P(mastered) per concept.
- `run_diag.ARMS`:
  - `prior_only`;
  - `product` (`AdaptiveDiagnostic` on `product_engine(cur, diagnostic_scope="all")`, so every concept is scored);
  - `product_goalpath` (the shipped scope, scored on goal-path concepts only);
  - `concept_sweep_w7` (`DEFAULT_CONFIG` diagnostic settings on the fitted_S1 profile);
  - `frontier`;
  - `state_space` (`StateSpaceDiagnostic`, only when there are ≤ 12 concepts);
  - `fixed@n`, `random@n`, `irt_cat@n`, where `n` = the `product` item count for **that learner**.
- Cells: worlds S0, S1, S2, S4 × the 4 `CURRICULA`; N = 200 report seeds. Learners are `make_sim(engine, seed, PROFILES["nominal"], world)` at day 0; the diagnostic does not change θ.
- Metrics, against the truth 1[θ ≥ 0.70]:
  - Brier, AUC, MAE;
  - accuracy of the Known (p ≥ 0.70) and Unknown (p < 0.40) labels;
  - INFERRED precision (share of INFERRED concepts that are truly mastered);
  - items used (mean and p90) and the stop-reason histogram.
- Output: `diag_matrix.json` (`--smoke`: 2 cells, 10 seeds).

- [ ] **Step 1: Failing tests:**
  - `test_matched_budget`: for 3 seeds, the item count of every `@n` arm equals the `product` item count.
  - `test_state_space_skipped_over_12`: `state_space` is absent for `synth-20-x10`.
  - `test_inferred_precision_defined`: the key is present, and its value is `None` when nothing was inferred.
  - `test_smoke_meta`: `meta["engine"] == "product"`.
- [ ] **Step 2:** Confirm the tests fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Confirm the tests pass.
- [ ] **Step 5:** Update `scripts/verify_clean_checkout.sh:39-42` to run `experiments/run_diag.py --smoke` twice and compare the outputs with `meta.timestamp_utc` removed, using a short inline `python -c` (no `jq` dependency).
- [ ] **Step 6:** Commit.

---

### Task 5: E3 sensitivity around the product (`experiments/run_sensitivity.py`)

Answers rows #4, #7 and #13 as measurements, not selections.

**Files:** create `experiments/run_sensitivity.py`; test `tests/test_exp_sensitivity.py`.

**Interfaces:**
- `SCANS: dict[str, tuple]`, one parameter changed at a time from the product; the product value must appear in every scan:
  - `theta` (0.85, 0.90, 0.95, 0.98)
  - `k_responses` (1, 2, 3)
  - `mastery_criterion` ("bkt_threshold", "two_threshold", "n_consecutive")
  - `horizon_aware_mastery` (False, True)
  - `consolidation` (False, True)
  - `concept_cap` (2, 4, 6)
  - `n_max` (12, 25, 40)
  - `diag_budget_per_concept` (0.0, 0.5, 1.0, 2.0)
  - `known_threshold` (0.60, 0.70, 0.80)
  - `skip_threshold` (0.30, 0.40, 0.50)
  - `selection_scope` ("concept_sweep", "frontier", "goal_search")
  - `pruning_mode` ("hard", "soft", "none")
- Factorial: `theta` × `k_responses`.
- Cells: S0, S1, S4 × `4node_x10`, `8node_x10`, B 15, calm, 14 d. Arm `adapt_dx`, with `static_loop` once per cell as reference. N = 200 report seeds.
- Metrics: the E1 per-cell summary plus diagnostic items.
- Output: `sensitivity.json`.

- [ ] **Step 1: Failing tests:**
  - `test_scans_contain_product_value`: for every scan key, `getattr(product_config(), key)` is in the scan.
  - `test_invalid_combo_skipped_logged`: a `skip_threshold` value ≥ `known_threshold` is recorded under `skipped`, not raised.
  - `test_smoke_meta`.
- [ ] **Step 2:** Confirm the tests fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Confirm the tests pass.
- [ ] **Step 5:** Commit.

---

### Task 6: E4 bandit policy on the product (`experiments/policy.py`, `experiments/run_policy.py`)

Answers row #15.

**Files:**
- Create `experiments/policy.py`. Port the closed-loop policy runner and IPS/SNIPS/DR from `pre-experiment-rewrite:experiments/{policy_runner,ope}.py`.
- Create `experiments/run_policy.py` with subcommands `train` and `eval`.
- Test: `tests/test_exp_policy.py`. Restore the old `tests/test_ope.py` assertions for IPS/SNIPS/DR on a known toy log, imported from `experiments.policy`.

**Interfaces:**
- `policy.run_policy_episode(engine, seed, world, cur, policy, log_path=None) -> dict`
- `policy.learning_progress_reward(...)`: rolling success over w = 4, clipped to [−1, 1], 0 on a first attempt; a lesson's reward is assigned at the next exercise on that concept.
- `policy.ope(logs, target, reward_model="ridge") -> dict[str, float]` with keys `ips`, `snips`, `dr`.
- `train`:
  - one `BanditPolicy("updating")`, LinUCB + softmax with λ 1, α 0.3, τ 0.1, zero initial weights;
  - runs sequentially over `TRAIN_SEEDS` × S1, S4 × `4node_x10`, `8node_x10`, B 15, calm, 14 d, on `product_engine`;
  - writes `config/policy_frozen.json` (weights + stamp, replacing the W8 one) and `policy_train.json`.
- `eval`:
  - variants deterministic / frozen / updating / random;
  - same cells as `train`, on `REPORT_SEEDS`, paired;
  - logs to `experiments/results/policy_logs/*.jsonl`;
  - OPE of the frozen policy from the random and updating logs vs its simulated value;
  - output `policy_eval.json`.

- [ ] **Step 1: Failing tests:**
  - the OPE toy log: IPS equals the hand-computed value to within 1e-9;
  - `test_train_smoke` (2 seeds): the frozen file has weights and `meta.engine == "product"`;
  - `test_eval_smoke_zero_violations`;
  - `test_policy_lab_loads_frozen`: the Policy Lab endpoint in `frontend/api/app.py` (the handler that reads `config/policy_frozen.json`, around line 705) returns 200 for the frozen policy after `train`.
- [ ] **Step 2:** Confirm the tests fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Confirm the tests pass.
- [ ] **Step 5:** Commit.

---

### Task 7: E5 extensions (`experiments/run_extensions.py`)

Answers row #16, FINAL_A5 §7, on the product.

**Files:** create `experiments/run_extensions.py`; test `tests/test_exp_extensions.py`.

**Interfaces:** subcommands, each writing one key of `extensions.json`:

| Key | Cells | Arms | Primary metric |
|---|---|---|---|
| `review_cap` (D.1) | `synth-20-x10`, S0, S1, B {10, 15}, forgetting_21 | `product_nodx`; `product_nodx` + `review_cap_fraction=0.25, review_goal_path_only=True`; `product_norev` | goal mastery: capped vs no_review (CI includes or exceeds 0 = pass) |
| `elo` (O.1) | S0, S1, S4 × `4node_x10`, B 15, calm, 14 d | product with `mastery_model="elo"` vs `"bkt"` | in-loop Brier/AUC, goal mastery |
| `hlr` (O.2) | fit: `HLR_SEEDS`, S3, forgetting_21, `4node_x10`, `8node_x10`, product episodes, least squares on recall after gaps; eval: S0, S3 × both curricula, B 15, forgetting_21 | `half_life_model="hlr"` (fitted `hlr_weights`) vs `"fixed"` vs `product_norev` | goal mastery, retention |
| `forgets` (O.3) | S3, `4node_x10`, B 15, forgetting_21 | `product_engine(cur, profile="fitted_S3")` vs `profile="fitted_S3_forget"` | in-loop Brier |

The HLR fit is also written to `hlr_fit.json`.

- [ ] **Step 1: Failing tests:**
  - one smoke per subcommand (2 seeds) asserting its key, `meta.engine`, and 0 violations;
  - `test_hlr_fit_uses_hlr_seeds_only`: the fit unit list ⊆ `HLR_SEEDS`.
- [ ] **Step 2:** Confirm the tests fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Confirm the tests pass.
- [ ] **Step 5:** Commit.

---

### Task 8: E6 planner cost: CP-SAT and latency (`experiments/run_planner_cost.py`)

Answers rows #3, #9 and #17.

**Files:** create `experiments/run_planner_cost.py`; test `tests/test_exp_planner_cost.py`.

**Interfaces:** subcommands:
- `cpsat`:
  - synth-20-x10 and synth-50-x10 (seed 2026), deepest goal, fresh learner;
  - `L` = the last day of the greedy plan under a 1000-day deadline;
  - deadlines {L, ⌈0.9L⌉, ⌈0.8L⌉};
  - compares the greedy `product_config()` with `replace(product_config(), scheduler="cpsat")` and the oracle on plan length, latency (median of 5) and the audits (`checks.count_plan_prereq_violations`, `count_budget_violations`, `count_duplicate_activities`);
  - `maintenance_reviews=False` for both;
  - skipped with a recorded reason if `ortools` is absent.
- `replan`: full vs frontier replanning latency on `CURRICULA` × the event types the old runner used (`git show pre-experiment-rewrite:experiments/run_replan_latency.py`), copied verbatim.
- `plan`: initial planning latency on `CURRICULA` × budgets {5, 15, 30} × deadlines {7, 14, 28}.
- `diag`: wall time of one full product diagnostic per curriculum (median over 50 learners).
- Output: `planner_cost.json`.

- [ ] **Step 1: Failing tests:**
  - `test_cpsat_smoke` (synth-20 only, one deadline; skip if no `ortools`): greedy and cpsat show 0 violations;
  - `test_latency_smoke`: every subcommand returns positive medians;
  - `test_smoke_meta`.
- [ ] **Step 2:** Confirm the tests fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Confirm the tests pass.
- [ ] **Step 5:** Commit.

---

### Task 9: Pre-registration and orchestrator

**Files:**
- Create `docs/preregistration/PRODUCT_RERUN_2026-11-<dd>.md`.
- Create `scripts/run_experiments.py`.
- Test: `tests/test_exp_orchestrator.py`.

- [ ] **Step 1:** Write the pre-registration:
  - the product definition, verbatim from Global Constraints;
  - the ruling;
  - each of E1–E6 with its exact command, cells, arms, seeds, metrics and comparisons;
  - "measurement only";
  - "not re-run: fitted parameters (Part B keep list), agent eval, probes, B.3 and T3.3 selections";
  - the code hash from `.venv/bin/python experiments/provenance.py`.
- [ ] **Step 2:** `scripts/run_experiments.py [--smoke] [--only E1 E2 …]`:
  - runs E1–E6 in order (E4 `train` before `eval`), then `make_results.py`;
  - stops on the first non-zero exit;
  - before each run, checks that the current code hash equals the hash in the pre-registration, and refuses to run if it differs.
- [ ] **Step 3:** Test `test_hash_mismatch_refuses`: monkeypatch `code_hash`, then expect `SystemExit` before any runner starts.
- [ ] **Step 4:** Commit. The code hash is now frozen; do not edit `src/` or `experiments/` until Task 10 finishes.

---

### Task 10: Run everything

- [ ] **Step 1:** `.venv/bin/python scripts/run_experiments.py --smoke`. Expected: all six smoke outputs written, 0 adaptive violations.
- [ ] **Step 2:** `.venv/bin/python scripts/run_experiments.py` (full run). Expected time is roughly 2–4 h on 16 cores; E1 primary dominates, with ~208 cells × 9 arms × 200 seeds.
- [ ] **Step 3:** Verify:
  - every output's `meta.code_hash` equals the pre-registered hash;
  - every adaptive arm in E1, E3, E4 and E5 has `executed_prereq_violations == 0`.
- [ ] **Step 4:** Commit the results.

---

### Task 11: Results document (`experiments/make_results.py` → `docs/RESULTS.md`)

**Files:** create `experiments/make_results.py`; test `tests/test_exp_make_results.py`.

- [ ] **Step 1:** Generate, from the result files only, with each table citing its source file and code hash:
  1. violations;
  2. headline cell;
  3. goal mastery vs `static_loop` by world, curriculum and horizon;
  4. the ablations: diagnostic (`product` − `product_nodx`), consolidation, review, replanning;
  5. `product` vs `w8_final` ("what changed since W8", next to the old `FINAL_RESULTS.md` headline numbers);
  6. the stress grid;
  7. the diagnostic matrix;
  8. sensitivity;
  9. policy + OPE;
  10. extensions;
  11. CP-SAT and latency.

  Figures go to `docs/figures/results_*.png`: KM headline, forest plot vs `static_loop`, reliability, false mastery vs utilisation.
- [ ] **Step 2:** Test `test_make_results_on_smoke`: run on the smoke outputs, check every section header is present, and check that no number appears without a source line.
- [ ] **Step 3:** Run it on the full results.
- [ ] **Step 4:** Commit.
