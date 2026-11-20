# Plan 2 notes: F2, fitted item-model profile

Baseline: Plans 0–1.5 committed (`make check` 283 passed, coverage 90.75%; 10 API tests).
Recorded 2026-11-20.

## What was added

| Task | Files |
|---|---|
| F2-T1 config | `core/config.py`: `model_profile` (default `"heuristic"`), `use_profile_learn` (default `False`), `resolve_profile_path` (working directory first, then the repo root) |
| F2-T2 loader, `ClassBKT` | `learner/profiles.py`: `load_profile`, `Profile`, `ClassBKT`, `build_model`, `profile_config` |
| F2-T3 Cognitive Tutor profile | `config/fitted_ct.json`, written by `python experiments/fit_bkt.py ct-profile` from the class fit stored in `experiments/results/bkt_fit_ct.json` (no refit) |
| F2-T4 engine wiring | `api.py` (`Engine` builds its model from the profile and applies `use_profile_learn`); `planner/plan.py::serialize_plan` adds `"model_profile"` provenance only for a fitted profile |
| F2-T5 demo API | `frontend/api/schemas.py`, `app.py`: optional `model_profile` on session creation (`heuristic`, `fitted_assist09`, `fitted_ct`; no paths, no `fitted_sim`); `SessionOut.model_profile`; `PlanOut` passes extra keys through so plans keep their provenance. `openapi.json` and `schema.d.ts` regenerated; `tsc --noEmit` clean |
| F2-T6 experiments | `experiments/run_f2_grid.py`; `experiments/diag_eval.py::binary_score` gains `sim_kw` (for the ASSISTments-driven S4 world); `experiments/stats.py::ece`; pre-registration `docs/preregistration/F2_2026-11-20.md`; results `experiments/results/f2_grid.json` |
| Tests | `tests/test_profiles.py` (29), `tests/test_f2_grid.py` (3), `frontend/api/tests/test_api.py` (+4: fitted end-to-end, 3 allowlist cases) |
| F2-T7 docs | `docs/MASTERY_MODEL.md` §7, `docs/DECISIONS.md` (D60, D61 adopted), `docs/TRACEABILITY.md` (F2-TC1–TC7), `README.md` |

`experiments/diag_eval.py` and `experiments/arms.py` did not need a `model_profile` argument: the
profile travels in `EngineConfig`, so every experiment that takes an engine already uses it.

## Hashes (ground rule 8)

| Item | Before Plan 2 | After Plan 2 |
|---|---|---|
| `config_hash(DEFAULT_CONFIG)` | `b450f59cc11c1a0179f8a41d864a648166652bbd4efb2a4ca141eac2070afcee` | `a00fdb3161e67097402a7a01021a910f0e609abccced0f8dd9a4cb6f480021ab` |
| `config_hash(population_prior_config())` | `acaccaeea3a2dd649e043a45cf387f73b0f13e5fcdb2f17b55d3e229f6c28252` | `d4f9c4ae900d5df6c428a1d87e02306e44e170d4d22d357f7310e193d973329b` |
| Code hash (`src/**/*.py`) | `4129b2bf…` | `b6259f8470d7d3f971f17119381a946fe987f60426450322a314083e0dbb2b33` |
| `config/fitted_assist09.json` | `197427dd03eedb3f791f95d73c9e08bf7cbdf5fb5601249e28415d8e99127d13` (unchanged) | same |
| `config/fitted_ct.json` | – | `0005cfe4cf5f4e67c26b07016aa493174e9923a0e93c6fa4c31c4ada585463a7` |

The hashes moved only because two fields were added. Behaviour under the defaults is unchanged:
every regression pin in `tests/test_baseline_pins.py` passes unchanged, and the population preset
still reproduces the pre-Plan-0 outputs. A re-run of `experiments/run_evaluation.py` or
`run_diag_matrix.py` now records `config_hash` `d4f9c4ae…` instead of `acaccaee…`, with the same
numbers.

## F2-T6 results (Stage 1, `experiments/results/f2_grid.json`)

Registered 2026-11-20T06:26:13Z with code hash `b6259f84…`; full run finished 06:44:33Z (about
18 min wall on 15 workers), with the registered code hash. 6 worlds × 7 curricula × 3 profiles;
250 diagnostics and 200 calm episodes (adapt, budget 15) per cell. `8node_x10`: content AI-checked,
human review pending (D88).

Paired difference fitted − heuristic, mean over the 7 curricula; the bracket shows, per curriculum
(4-node, 8-node, 8-node-x10, synth-20, synth-20-x10, synth-50, synth-50-x10), whether the 95% CI
is above 0 (+), below 0 (−) or includes 0 (0). Lower Brier is better. S0, S1 and S3 have the same
starting knowledge, so their diagnostic rows are identical.

**fitted_assist09**

| World | Next-answer Brier | Diagnostic Brier | Items | Goal mastery | Minutes |
|---|---|---|---|---|---|
| S0 | −0.0061 [−−−0−+−] | −0.0067 [00−000−] | +0.59 [+++++++] | −0.006 [0000−00] | −5.2 [+++++−−] |
| S1 | −0.0061 [−−−0−+−] | −0.0067 [00−000−] | +0.59 [+++++++] | +0.001 [0000000] | −6.0 [+++++−−] |
| S2 | −0.0059 [−−−−−0−] | −0.0029 [0000000] | +0.64 [+++++++] | −0.024 [00−0−−−] | −4.0 [+++++−−] |
| S3 | −0.0061 [−−−0−+−] | −0.0067 [00−000−] | +0.59 [+++++++] | +0.001 [0+00000] | −6.1 [+++++−−] |
| S4 | +0.0071 [+++++++] | +0.0013 [00000+0] | +0.25 [+++++++] | −0.001 [0000000] | −8.6 [+++0+−−] |
| S4-assist09 | −0.0113 [−−−−−−−] | −0.0215 [−−−−−−−] | +0.65 [+++++++] | −0.006 [00−0000] | −5.3 [+++++−−] |

**fitted_ct** (robustness)

| World | Next-answer Brier | Diagnostic Brier | Items | Goal mastery | Minutes |
|---|---|---|---|---|---|
| S0 | −0.0277 [−−−−−−−] | +0.0147 [+++++++] | +1.52 [+++++++] | +0.006 [+000−00] | +37.0 [+++++++] |
| S1 | −0.0277 [−−−−−−−] | +0.0147 [+++++++] | +1.52 [+++++++] | +0.001 [0000000] | +35.8 [+++++++] |
| S2 | −0.0274 [−−−−−−−] | +0.0293 [+++++++] | +1.64 [+++++++] | −0.024 [+0−0−−−] | +38.1 [+++++++] |
| S3 | −0.0277 [−−−−−−−] | +0.0147 [+++++++] | +1.52 [+++++++] | −0.011 [00−0000] | +36.1 [+++++++] |
| S4 | +0.0184 [+++++++] | +0.0067 [++++0+0] | +1.66 [+++++++] | +0.011 [+000000] | +32.3 [+++++++] |
| S4-assist09 | −0.0370 [−−−−−−−] | −0.0286 [−−−−−−−] | +1.53 [+++++++] | −0.010 [00−0000] | +36.7 [+++++++] |

Pre-registered hypotheses:

- **H1 (F2-TC6, 0 executed violations):** held in all 126 cells.
- **H2 (S4-assist09: fitted_assist09 next-answer Brier below heuristic on every curriculum):**
  held; differences −0.004 to −0.018, every CI below 0. The diagnostic Brier is also lower on every
  curriculum there (−0.022 on average).
- **H3 (S0–S3, no predicted direction):**
  - fitted_assist09 predicts next answers slightly better in most S0–S3 cells (−0.006). One
    curriculum per world, synth-50, goes the other way (+). Diagnostic Brier is mostly unchanged.
    Goal mastery is lower in S2 on 4 curricula (−0.024 on average). A likely reason: S2's
    correlated abilities reward the heuristic's stronger per-answer updates. This explanation is
    untested.
  - fitted_ct predicts next answers clearly better (−0.028) but diagnoses worse (+0.015 to
    +0.029), asks about 1.5 more items, and needs about 36 more minutes per episode. Its easy-class
    guess 0.48 makes easy items weak evidence, so mastery takes more exercises. Again an untested
    explanation.
  - In the default S4 world, which generates answers with its own BKT numbers rather than the
    fitted ones, both fitted profiles predict next answers worse than the heuristic (+0.007,
    +0.018).
- **H4 (fitted profiles ask at least as many items):** held in every cell: +0.25 to +0.65 items
  (fitted_assist09) and +1.5 to +1.7 (fitted_ct).

Minutes: fitted_assist09 uses more minutes on the five smaller curricula and fewer on synth-50
and synth-50-x10. The mean over curricula is negative only because of the two synth-50 curricula.

Reading: a fitted profile helps where the learners behave like the data it was fitted on
(S4-assist09) and is not a free win elsewhere. The heuristic stays the default (D48). Stage 2
(sweep vs bisection × heuristic vs fitted) runs in Plan 3.

## After Plan 2

| Item | Value |
|---|---|
| `make check` | ruff clean; **315 passed**; coverage **91.10%** (283 before; +32) |
| `pytest frontend/api/tests` | **14 passed** (10 before; +4) |

## Plan 2.5: CLI access to config options (D89)

Before, the CLI could not use a fitted profile or any other config option: every
`Engine.from_files` call got `DEFAULT_CONFIG`, and `--model` (default `custombkt`) always passed an
explicit model built from `DEFAULT_CONFIG`.

| Change | Where |
|---|---|
| `config_from_file(path, base)`: JSON object of `EngineConfig` overrides, unknown keys rejected, lists to tuples for tuple fields, validated by `EngineConfig` | `core/config.py` |
| `--config` and `--model-profile` on the shared parent parser (every command); `_effective_config` (defaults < `--config` < `--model-profile`); `config=cfg` on all 12 `Engine.from_files` calls; `--model` default `None` on all 7 commands that have it; `_resolve_model(name, cfg)` returns `None` when `--model` is not given; `--model` + fitted profile → `ValidationError` (exit 2); stderr info line for a non-default config | `cli.py` |
| 23 tests | `tests/test_cli_config.py`, golden outputs `tests/fixtures/cli_default_runs.json` |

Before/after comparison (P2.5-T0 / T5): 11 CLI runs with no new options (validate and show on
4-node and 8-node, init-learner, update correct and incorrect, plan text and `--json`, missed-day,
replan `--json` on one 8-node snapshot), plus the same runs with `--model pybkt`, were recorded with
the unchanged CLI. After the change, stdout and snapshot bytes are identical for all of them, and
`--model custombkt` gives the default output. `config_hash(DEFAULT_CONFIG)` is unchanged
(`a00fdb31…`; no field was added), the regression pins pass, and the 14 API tests pass.

| Item | Value |
|---|---|
| `make check` | ruff clean; **338 passed**; coverage **91.32%** (315 before; +23) |
| `pytest frontend/api/tests` | **14 passed** |
