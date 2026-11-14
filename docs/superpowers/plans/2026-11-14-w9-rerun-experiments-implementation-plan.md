# W9 Re-run of All Experiments on the Current Product — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-measure every W6–W8 experiment against the engine as it stands today (the "product": strict mastery, `fitted_S1`, goal-search diagnostic, goal-path scope, consolidation off, 10-exercise curricula), writing new `w9_*` results without touching any W6–W8 result.

**Architecture:** One helper, `product_engine()` in `experiments/w8_common.py`, builds the product engine (`load_profile("fitted_S1", **PRODUCT_OVERRIDES)` plus per-arm overrides). Every existing runner gets an opt-in `--product` flag (default behaviour unchanged) that swaps its adaptive engine for `product_engine()` and writes to a `w9_*` path. The synthetic curriculum generator gains a 10-exercise variant (`synth-N-x10`). A pre-registration is written before any run; a generator turns the results into `docs/W9_RESULTS.md`.

**Tech Stack:** Python 3.11, pytest, existing `experiments/` simulator and runners.

**Spec:** `docs/superpowers/specs/2026-11-14-strict-mastery-and-goal-search-diagnostic-design.md` (product definition, §5.1) — this plan supersedes Task 8 Steps 2–4 of `docs/superpowers/plans/2026-11-14-strict-mastery-goal-search-implementation-plan.md`.

## Global Constraints

- **Do not run any git commands.** Leave changes uncommitted; the owner commits.
- **Never overwrite an existing result or config file.** All new outputs are `experiments/results/w9_*` (policy: `config/policy_frozen_w9.json`, logs: `experiments/results/policy_logs_w9/`). New checkpoints use `w9_*` names.
- `EngineConfig` defaults and every runner's default (no `--product`) behaviour stay unchanged, so W6–W8 still reproduce.
- **Product engine (verbatim):** `load_profile("fitted_S1", **PRODUCT_OVERRIDES)` from `adaptengine.core.profiles` — θ 0.95, k_responses 1, horizon_aware off, consolidation **off**, verification_probe on, feasibility_warning on, selection_scope `goal_search`, concept_cap 4, n_max 25, diag_budget_min 12, diag_budget_per_concept 1.0, diagnostic_scope `goal_path`.
- **Ruling (exact product in every world):** simulation arms use `fitted_S1` in every simulated world, as real users get; the W8 practice of matching each world's own fitted profile is not used for product arms.
- **Curricula:** `4node_x10`, `8node_x10` (require the owner's promotion of `data/drafts/*_x10` first — see Task 6), `synth-20-x10`, `synth-50-x10` (10 exercises per concept at d = 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9).
- **Seeds:** reporting `REPORT_SEEDS` / `HEADLINE_SEEDS`; policy training `TRAIN_SEEDS`; HLR fit `HLR_SEEDS` (all in `experiments/w8_common.py`).
- 0 executed prerequisite violations in every adaptive arm (static baselines violate by design).
- No agent runs `scripts/record_review.py` or edits `data/review_manifest.json`.
- The runs measure; they select nothing. Results are reported whatever they show.

## Review Focus

1. **Default synthetic curricula unchanged:** `synth-20` / `synth-50` must generate byte-identical files after the generator change — Task 1 test `test_synth_default_unchanged`.
2. **Unpromoted `_x10` curricula fail loudly**, never silently falling back to 4-exercise files — Task 1 test `test_x10_missing_raises`.
3. **Default runner output unchanged** with `--product` absent — Task 2 test `test_default_arms_unchanged`, Task 3 test `test_w9_diag_default_unchanged`.
4. **No W8 artefact overwritten** (results, checkpoints, `config/policy_frozen.json`) — every Task 4/5 smoke test asserts its output path starts with `w9_` / ends `_w9` and that the W8 file's mtime is unchanged.
5. **Product arms really are the product** — Task 2 test `test_product_arm_is_product_config`.

---

### Task 1: Product engine helper and 10-exercise synthetic curricula

**Files:**
- Modify: `experiments/w8_common.py` (`engine` ~line 56, `curriculum_paths` ~line 32)
- Modify: `experiments/synth_curriculum.py` (`difficulties` ~line 80, `generate_synthetic_curriculum`, `write_synthetic_curriculum` ~line 112)
- Test: `tests/test_w9_rerun.py` (new)

**Interfaces:**
- Produces: `X10_DIFFICULTIES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9)` in `synth_curriculum`; `generate_synthetic_curriculum(n_concepts, seed, difficulties=(0.20, 0.40, 0.60, 0.80))` and `write_synthetic_curriculum(out_dir, n_concepts, seed=2026, difficulties=...)` (x10 files get a `_x10` suffix); `curriculum_paths("synth-N-x10")`; `product_engine(cur: str, policy=None, **extra) -> Engine` in `w8_common` = `engine(cur, PRODUCT_PROFILE, policy, **{**PRODUCT_OVERRIDES, **extra})`.

- [ ] **Step 1: Write the failing tests**

```python
import hashlib, os, pytest
from adaptengine.core.profiles import product_config
from experiments.synth_curriculum import X10_DIFFICULTIES, write_synthetic_curriculum
from experiments.w8_common import curriculum_paths, product_engine

def _h(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

def test_synth_default_unchanged(tmp_path):
    # pinned hashes: compute ONCE from the pre-change generator and paste them in
    c, a = write_synthetic_curriculum(str(tmp_path), 20, seed=2026)
    assert (_h(c), _h(a)) == (PINNED_SYNTH20_CUR, PINNED_SYNTH20_ACT)

def test_synth_x10_has_ten_exercises(tmp_path):
    c, a = curriculum_paths("synth-20-x10")
    e = product_engine("synth-20-x10")
    for cid in e.graph.concepts():
        ds = sorted(x.difficulty for x in e.activities.values() if x.target_concept == cid and x.difficulty is not None)
        assert ds == list(X10_DIFFICULTIES)

def test_x10_missing_raises(monkeypatch):
    # until the owner promotes 4node_x10, loading it must fail, not fall back
    if os.path.exists("data/curriculum/curriculum_4node_x10.json"):
        pytest.skip("already promoted")
    with pytest.raises(Exception):
        product_engine("4node_x10")

def test_product_engine_is_product_config():
    assert product_engine("4-node").config == product_config()
    assert product_engine("4-node", consolidation=True).config.consolidation is True
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest tests/test_w9_rerun.py -v` → FAIL (ImportError `X10_DIFFICULTIES` / `product_engine`). Before editing the generator, compute and paste the two pinned hashes.
- [ ] **Step 3: Implement** the interfaces above; `curriculum_paths` parses `synth-<N>-x10` (cache key separate from `synth-<N>`). Durations for the 6 new exercises copy the existing exercise duration pattern.
- [ ] **Step 4: Run** `tests/test_w9_rerun.py` and the full suite → PASS.

---

### Task 2: Final-grid product arms (re-runs W6 benchmark, W7 grid/review/projection/S4-fitted, W8 final grid, D49/D52 ablations)

**Files:**
- Modify: `experiments/run_final_grid.py` (`arm_engine` ~lines 49–90; `--arms` choices)
- Test: `tests/test_w9_rerun.py`

**Interfaces:**
- Consumes: `product_engine` (Task 1).
- Produces arms (name → engine, run mode):
  - `adapt_product` → `product_engine(cur)`, `"adapt_dx"` (the product: diagnostic then plan)
  - `adapt_product_nodx` → `product_engine(cur)`, `"adapt"` (diagnostic value, old D52)
  - `adapt_product_consol` → `product_engine(cur, consolidation=True)`, `"adapt_dx"` (consolidation value, old D49)
  - `adapt_product_norev` → `product_engine(cur)`, `"no_review"` (spaced-review value, old W7 §1.5; compare with `adapt_product_nodx`)
  - `adapt_product_expected` → `product_engine(cur, projection_mode="expected")`, `"adapt"` (projection, old W7 §1.6; compare with `adapt_product_nodx`)
  - existing `adapt_final`, `static_loop`, `static`, `random_eligible`, `no_replan` unchanged.

- [ ] **Step 1: Failing tests**

```python
from experiments.run_final_grid import arm_engine, winner_spec, ARMS
from adaptengine.core.profiles import product_config

def test_product_arm_is_product_config():
    e, mode = arm_engine("adapt_product", "S0", "4-node", winner_spec())
    assert e.config == product_config() and mode == "adapt_dx"

@pytest.mark.parametrize("arm,mode,field,val", [
    ("adapt_product_nodx", "adapt", "consolidation", False),
    ("adapt_product_consol", "adapt_dx", "consolidation", True),
    ("adapt_product_norev", "no_review", "theta", 0.95),
    ("adapt_product_expected", "adapt", "projection_mode", "expected"),
])
def test_product_variants(arm, mode, field, val):
    e, m = arm_engine(arm, "S1", "4-node", winner_spec())
    assert m == mode and getattr(e.config, field) == val

def test_default_arms_unchanged():
    assert "adapt_product" not in ARMS  # default run keeps the W8 arm set
```

- [ ] **Step 2: Run → FAIL.** **Step 3: Implement** the branches; add the five names to `--arms` choices. **Step 4: Run** tests + a smoke: `python experiments/run_final_grid.py --smoke --arms adapt_product adapt_product_nodx static_loop --out experiments/results/w9_grid.json --checkpoint experiments/results/w9_grid.ckpt.jsonl` → `w9_grid_smoke.json`, 0 executed violations in adaptive arms.

---

### Task 3: Diagnostic matrix on the product (re-runs W6 matched-budget, W7 T3.3 selection and T3.7 matrix)

**Files:**
- Modify: `experiments/run_w9_diag.py`
- Modify (only if no random-order helper exists): `experiments/diag_eval.py` — add `run_random_diagnostic` mirroring `run_fixed_diagnostic`
- Test: `tests/test_w9_rerun.py`

**Interfaces:**
- Consumes: `product_engine`, `curriculum_paths` (Task 1); `diag_eval.summarize`, `binary_score`, `run_fixed_diagnostic`; `cat_baseline.irt_cat`; `StateSpaceDiagnostic`.
- Produces: `run_w9_diag.main(out_path, n, curricula, worlds=("S0","S1","S2","S4"))`; arms per world × curriculum: `prior_only`, `goal_search_product` (= `product_engine(cur, diagnostic_scope="all")` — whole-curriculum accuracy), `concept_sweep_w8` (W8 product diagnostic: `DEFAULT_CONFIG`), `w6_shipped`, `frontier`, `state_space` (only when ≤ 12 concepts), `fixed@n` and `random@n` (n = `goal_search_product`'s item count per learner), `irt_cat_per_concept@n`. Default curricula `4node_x10, 8node_x10, synth-20-x10, synth-50-x10`; default output `experiments/results/w9_diag_matrix.json`.

- [ ] **Step 1: Failing tests** — `test_w9_diag_arms` (n=2, curricula `["4-node", "synth-20-x10"]`: every listed arm present for 4-node; `state_space` absent for synth-20-x10); `test_w9_diag_default_unchanged` (the pre-existing `goal_search` behaviour of the file for `curricula=["4-node"]` still produces the same `goal_search` numbers as before this task — pin from a run before editing).
- [ ] **Step 2–4:** fail → implement → pass; smoke `--n 3`.

---

### Task 4: `--product` for the sensitivity, policy and extension runners (re-runs W7 sensitivity + W8 B.3, A2 bandit + OPE, D.1/O.1–O.3)

**Files:**
- Modify: `experiments/run_sensitivity.py` (base config ~line 74; worlds S0, S1, S4; curricula `4node_x10`, `8node_x10` under `--product`) → `w9_sensitivity.json`. Its θ / k scans replace the B.3 selection as a measurement.
- Modify: `experiments/train_policy.py` → `config/policy_frozen_w9.json`, `w9_policy_train.json`
- Modify: `experiments/run_policy_eval.py` → `w9_policy_eval.json`, logs `policy_logs_w9/`, reads `policy_frozen_w9.json`
- Modify: `experiments/run_extensions.py` → `w9_extensions.json`, `w9_hlr_fit.json` (HLR refit on product episodes)
- Test: `tests/test_w9_rerun.py`

**Interfaces:** each script gains `--product` (argparse) and, under it, builds adaptive engines with `product_engine(cur, **its_own_arm_overrides)` instead of `engine(cur, prof, **{**ov, **FINAL_FLAGS})` / `DEFAULT_CONFIG`; output metadata records `"engine": "product"`.

- [ ] **Step 1: Failing tests** — one smoke per script at the smallest size it supports (a `--smoke`/`--n` flag may be added): output written under the `w9_` name, metadata `engine == "product"`, and the corresponding W8 file's mtime unchanged.
- [ ] **Step 2–4:** fail → implement → pass.

---

### Task 5: `--product` for CP-SAT, latency, probe and agent-stub runners (re-runs O.4, W6/W7/W8 latency, W8 probe, agent plumbing)

**Files:**
- Modify: `experiments/run_cpsat_eval.py` (`BASE_CFG` ~line 46 → `replace(product_config(), maintenance_reviews=False)`; curricula `synth-20-x10`, `synth-50-x10`) → `w9_cpsat_eval.json`
- Modify: `experiments/run_replan_latency.py` → `w9_replan_latency.json`; `experiments/run_w7_latency.py` → `w9_latency.json` (include `synth-50-x10`)
- Modify: `experiments/probes/probe_w8_baseline.py` → `w9_probe_baseline.json` (its overrides applied on top of the product config)
- Modify: `experiments/run_agent_eval.py` (stub provider only) → `w9_agent_eval_stub.json`
- Test: `tests/test_w9_rerun.py`

- [ ] **Steps 1–4:** same pattern as Task 4 (smoke per script, `w9_` path, `engine == "product"`, W8 file untouched). CP-SAT test skips if OR-Tools is absent.

---

### Task 6: Pre-registration (before any full run)

**Files:** Create `docs/preregistration/W9_RERUN_<date>.md`

- [ ] **Step 1 — OWNER PREREQUISITE:** `4node_x10` and `8node_x10` promoted (`scripts/record_review.py --promote-draft …`). Without it, stop here.
- [ ] **Step 2:** Write the pre-registration: the product definition (verbatim from Global Constraints), every run below with its exact command, arms, cells, seeds, metrics, the comparisons listed in Task 2's arm list, "measurement only", and the code hash from `python experiments/provenance.py`.

**Not re-run (stated in the pre-registration):** BKT fits on ASSISTments / Cognitive Tutor / simulated worlds (`bkt_fit_*`, `w8_fits`, `w8_bkt_fit_*`) — properties of the data, not the engine; `fitted_S1` itself is unchanged. The W6 benchmark, W7 grid and W7 S4-fitted run are covered by Task 2's grid (same arm classes, scenarios, worlds incl. `S4F`).

---

### Task 7: Run everything

- [ ] **Step 1:** Run, in order (each writes only `w9_*`):

```bash
python experiments/run_final_grid.py --arms adapt_product adapt_product_nodx adapt_product_consol adapt_product_norev adapt_product_expected adapt_final static_loop static random_eligible no_replan --curricula 4node_x10 8node_x10 --out experiments/results/w9_grid.json --checkpoint experiments/results/w9_grid.ckpt.jsonl
python experiments/run_w9_diag.py
python experiments/run_sensitivity.py --product
python experiments/train_policy.py --product && python experiments/run_policy_eval.py --product
python experiments/run_extensions.py --product
python experiments/run_cpsat_eval.py --product
python experiments/run_replan_latency.py --product && python experiments/run_w7_latency.py --product
python experiments/probes/probe_w8_baseline.py --product
python experiments/run_agent_eval.py --product
```

- [ ] **Step 2:** Check every output's `code_hash` equals the pre-registered hash and every adaptive arm has 0 executed violations.

---

### Task 8: W9 results document

**Files:** Create `experiments/make_w9_results.py` (pattern: `experiments/make_final_results.py`) → `docs/W9_RESULTS.md`

- [ ] **Step 1:** Generate tables mirroring `docs/FINAL_RESULTS.md` sections: violations; goal mastery vs `static_loop` by horizon; headline cell; `adapt_product` vs `adapt_final`; the four ablations (diagnostic, consolidation, review, projection); diagnostic matrix; sensitivity; policy + OPE; extensions; CP-SAT; latency; probe; agent stub. Each table cites its source file and code hash.
- [ ] **Step 2:** Add a short "What changed since W8" section: for each W8 headline, the W9 number next to it.
- [ ] **Step 3:** Test `test_make_w9_results` runs the generator on the smoke outputs from Tasks 2–5 and checks every section header is present.
