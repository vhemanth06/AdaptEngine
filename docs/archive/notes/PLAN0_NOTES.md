> Archived (21 Nov 2026). Historical record of the project at the time it was written; paths, commands and numbers may no longer match the repository. Current documentation: [docs/README.md](../../README.md).

# Plan 0 notes: baseline record and sweep default prior (D59)

Baseline (the code before Plan 0): commit `cae9291` (`adaptengine` v0.3.0). Recorded 2026-11-20.

## P0-T1 baseline (before any change)

| Item | Value |
|---|---|
| `make check` | ruff clean; **227 passed, 0 skipped**; coverage **90.53%** |
| `pytest frontend/api/tests` | **9 passed** (1 Starlette deprecation warning) |
| `config_hash(DEFAULT_CONFIG)` | `acaccaeea3a2dd649e043a45cf387f73b0f13e5fcdb2f17b55d3e229f6c28252` |
| Diagnostic matrix | `experiments/run_diag_matrix.py` (n = 250) reproduces the `worlds` block of `experiments/results/w7_diag_matrix.json` exactly |
| PoC demo | `scripts/poc_demo.py` stdout pinned (temp-dir name normalised) |

Regression pins: `tests/fixtures/pins/population_prior.json`, written by `scripts/record_pins.py`
from the baseline defaults. It holds:

- sweep-diagnostic outcomes (per-concept p, responses, status; items asked) on the 4- and 8-node
  curricula for all-wrong, all-right and 10 simulated learners (S0 nominal, odd seeds 101–119);
- the S0 slice of the diagnostic matrix for 5 learners (odd seeds 101–109);
- one closed-loop `Engine.next_activities` episode (4-node, `missed_day`, adapt arm, seed 42);
- serialized plans with full traces (4-node goal C4, 8-node goal C8; 15 min/day, deadline day 14)
  from the cold-start state and after an all-wrong diagnostic;
- the PoC demo output;
- the baseline config as a dict (its hash is the old default hash below).

Recording was deterministic: two runs gave byte-identical files. Before recording, two
behaviour-preserving hooks were added so pins can be computed for any config:
`scripts/poc_demo.py::run_demo(config=...)` and `experiments/run_diag_matrix.py::run_world(base=...)`.
The PoC output with the hook matched a run captured before the edit.

The `plans` and `config` parts were added after the D59 change, following the final review. That
is valid for the baseline: Plan 0 changed no planner code, the plans were computed under
`population_prior_config()`,
and the script first checked that every earlier part still matched the file exactly.

**Do not re-record `population_prior.json`.** It is the baseline reference that
`population_prior_config()` is checked against.

## P0-T2 sweep default prior 0.20 (D59) and `population_prior_config()`

- `EngineConfig.prior_mode` default: `"population"` → `"flat"`. The sweep now starts untouched
  concepts at `p0 = 0.20`.
- New preset `population_prior_config()` in `src/adaptengine/core/config.py`:
  `prior_mode = "population"`, `population_p0 = 0.24`.
- Config hash (ground rule 8):
  - old default (baseline): `acaccaeea3a2dd649e043a45cf387f73b0f13e5fcdb2f17b55d3e229f6c28252`
  - new default: `b450f59cc11c1a0179f8a41d864a648166652bbd4efb2a4ca141eac2070afcee`
  - `config_hash(population_prior_config())` equals the old default hash, so the committed result
    files stay traceable.
- New-default pins: `tests/fixtures/pins/default.json` (`python scripts/record_pins.py default`).
  Compared with `population_prior.json`, the diagnostic, matrix, after-diagnostic plans and PoC
  parts differ (sweep prior). The closed-loop episode and the cold-start plans, which have no diagnostic, are
  identical.
- The hash test checks the pinned baseline config fields, not
  `config_hash(population_prior_config())`, so adding a field in a later plan does not break it.
- **Tests moved to `population_prior_config()`: none.** No existing test pinned the 0.24 default.
  The full suite (227 + 9 API tests) passed unchanged under the new default.
- The result scripts behind the committed results now run on `population_prior_config()`, so they
  still reproduce the committed result files:
  - `experiments/run_evaluation.py` (and `experiments/diag_eval.py::run_diagnostic_tuning`, which
    gained a `base_config` argument, default `DEFAULT_CONFIG`). A full re-run reproduces
    `experiments/results/evaluation_results.json` exactly, apart from `metadata.git_sha`.
    Its recorded `config_hash` is still `acaccaee…`.
  - `experiments/run_diag_matrix.py`. A full re-run (n = 250) reproduces the `worlds` block of
    `experiments/results/w7_diag_matrix.json` exactly.
- Scripts not changed, because their output does not depend on the sweep prior:
  `run_diag_selection.py` sets `prior_mode` in every config, and `run_w7_grid.py`,
  `run_sensitivity.py`, `run_s4_fitted.py` and `run_w7_latency.py` never run the diagnostic.
  `scripts/run_w3.py` … `run_w6.py` and the demo API (`frontend/api/app.py`) use the new defaults.
  The demo API schema is unchanged, so `openapi.json` / `schema.d.ts` were not regenerated.

## After Plan 0

| Item | Value |
|---|---|
| `make check` | ruff clean; **241 passed**; coverage **90.74%** |
| `pytest frontend/api/tests` | **9 passed** |
| New tests | `tests/test_baseline_pins.py` (14 tests: P0-TC1, P0-TC2) |

## Plan 0.5: rename the population-prior preset (D59a)

A pure rename; no config field, number or pinned output changed.

| Old (added by Plan 0) | New |
|---|---|
| `w7_config()` | `population_prior_config()` |
| `W7_CONFIG` (`experiments/run_diag_matrix.py`) | `POPULATION_PRIOR_CONFIG` |
| `tests/fixtures/pins/w7_redo.json` | `tests/fixtures/pins/population_prior.json` (renamed only) |
| `record_pins.py` argument `w7` | `population` |
| fixture `w7_pins` | `population_pins` |
| `REDO_DEFAULT_HASH` (`tests/test_baseline_pins.py`) | `BASELINE_DEFAULT_HASH` |
| `test_w7_config_reproduces_redo_pins` | `test_population_prior_config_reproduces_baseline_pins` |
| `test_w7_config_matches_redo_config_fields` | `test_population_prior_config_matches_baseline_config_fields` |
| `test_default_differs_from_w7_only_in_sweep_prior` | `test_default_differs_from_population_prior_only_in_sweep_prior` |

No alias for the old name is kept. Section headings added by Plan 0 ("Post-W7 …") in
`DECISIONS.md` and `TRACEABILITY.md` are now "Plan 0–6 …". Earlier W7 comments, file names of
committed results (`experiments/results/w7_*.json`) and W7 scripts are not renamed (out of scope).

Verification, 2026-11-20 (snapshot before the rename vs after, P0.5-T0/T4):

| Check | Result |
|---|---|
| `make check` | ruff clean; **241 passed** before and after; coverage **90.74%** both |
| Test outcomes (`pytest -rA`) | identical apart from the 3 renamed tests (8 ids with parameters) |
| `pytest frontend/api/tests` | **9 passed** before and after |
| `config_hash(DEFAULT_CONFIG)` | `b450f59c…` before and after |
| `config_hash(population_prior_config())` | `acaccaee…` (equals `w7_config()` before) |
| Pin file SHA-256 | `population_prior.json` = old `w7_redo.json` = `3b855a4b…`; `default.json` = `b93579dc…` unchanged |
| Fresh pins (default and population preset) | byte-identical before and after; fresh population pins byte-identical to `population_prior.json` |
| `scripts/poc_demo.py`, CLI `init-learner` + `plan --json` (8-node, C8) | output identical |
| `run_evaluation.py --quick` | output JSON identical |
| `run_diag_matrix.py --n 10` | `worlds` and stdout identical (only `metadata.code_hash` differs, as the code changed) |
| Old-name search in `*.py`, `*.md`, `*.json` | only hit: the D59a rename record in `DECISIONS.md` (and this table) |

The full n = 250 diagnostic matrix was not re-run for Plan 0.5.
