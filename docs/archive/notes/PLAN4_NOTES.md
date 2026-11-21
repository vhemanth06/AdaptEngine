> Archived (21 Nov 2026). Historical record of the project at the time it was written; paths, commands and numbers may no longer match the repository. Current documentation: [docs/README.md](../../README.md).

# Plan 4 notes: F3, greedy / pure CP-SAT / hybrid planners

Baseline: Plans 0–3.5 committed (`make check` 406 passed, 1 skipped; coverage 92.44%; 15 API
tests). Recorded 2026-11-20.

## What was added

| Task | Files |
|---|---|
| F3-T1 config, dispatch, extra | `core/config.py` (`planner_method`, `cpsat_seed`, `cpsat_max_work_units` = 10.0, `cpsat_use_greedy_hint`, `cpsat_max_reviews_per_concept`, `cpsat_review_lateness_penalty`), `planner/plan.py` (dispatch after the shared workload and greedy steps; best effort with the selected planner), `pyproject.toml` (`[cpsat]` extra, `ortools==9.14.6206`) |
| F3-T2–T4 model | `planner/cpsat_model.py` (items, budget, order, prerequisites, deadline, reviews, five lexicographic levels, deterministic solver settings; lazy `ortools` import with the clear error) |
| F3-T5 trace | `planner/cpsat_trace.py` |
| F3-T6 hybrid / pure planners | `planner/cpsat_planner.py` (problem building, greedy hint, exact minimum days and smallest working budget, `UNKNOWN` at the limit, best effort) |
| F3-T7 closed loop, CLI | tests only (`tests/test_cpsat_closed_loop.py`); the planner is reachable through `--config` (D89) |
| F3-T8 runner, tuning, smoke | `experiments/run_f3_grid.py` (grid, pure-CP-SAT subset, F1 × F3 subset with reuse of F1 greedy cells, latency, `--tune`), `experiments/results/f3_tuning.json`, draft `docs/preregistration/F3_2026-11-20.md` |
| F3-T9 demo API | `frontend/api/schemas.py`, `app.py`: optional `planner_method`; `openapi.json` / `schema.d.ts` regenerated, `tsc --noEmit` clean |
| F3-T10 docs | `docs/PLANNER_CPSAT.md` (new), `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (D62–D72), `docs/TRACEABILITY.md` (F3-TC1–TC11), `README.md` |
| Tests | `tests/test_cpsat_planner.py` (26), `tests/test_cpsat_reviews.py` (8), `tests/test_cpsat_closed_loop.py` (19), `tests/test_f3_grid.py` (3); API end-to-end cases for `cpsat` and `hybrid` |

`planner/schedule.py` and `planner/oracle.py` are unchanged.

## Hashes (ground rule 8)

| Item | Before Plan 4 | After Plan 4 |
|---|---|---|
| `config_hash(DEFAULT_CONFIG)` | `3f921797214d55341eb3e6bcd4a94bb66537348ddd09d17a106cb1e7fa2b13bd` | `1e26bd7de81c8f56a6e998b33ee531f59470681d78ff71affd05362a910e7b11` |
| `config_hash(population_prior_config())` | `1a318779db17…` | `3d8c023cb724…` |
| Code hash (`src/**/*.py`) | `54119df5…` | `9a40c4d822397fa019d69ba64ddc7ab58d5baf8fe04ed0d090b1dfebfe66e6ef` |

Only fields were added; with `planner_method = "greedy"` every regression pin, the CLI golden runs
and the API tests are unchanged.

## Work-unit tuning (F3-T8)

`python experiments/run_f3_grid.py --tune` (20 min single process): cold-start plans on 8-node and
synth-20, budgets 5/10/15/30 × deadlines {greedy finish − 1, finish, finish + 2}, for work units
1, 2, 5, 10, 20. Share of plans with every objective level proven (or infeasibility proven):

| Work units | 1 | 2 | 5 | 10 | 20 |
|---|---|---|---|---|---|
| Proven | 0% | 0% | 50% | 79% | 87.5% |

At 1–2 units not even the first level finishes (all `UNKNOWN`); at 20 units 8-node is always proven
and synth-20 is proven in 9 of 12 plans. One synth-20 plan takes about 5 s at 1 unit and up to about
57 s at 20 units.

- **Ruling (tuning rule):** the plan's rule is "the smallest value that reaches proven optimality on
  most plans". The runner as first written used ≥ 90%, which no value met, so its file records the
  fallback 20.0. By the plan's rule (a majority) the smallest value is **10.0**, the existing
  default, which also keeps latency down; it stays frozen. The runner now uses the plan's rule (> 50%).
  Cost if wrong: with 10 units about 1 in 5 tuning plans keeps a level unproven (still valid and
  deterministic, but possibly not optimal on the lower levels).
- **Plan 4.5 (2026-11-20, file regenerated 15:00Z):** the first tuning file still recorded the
  ≥ 90% rule and `chosen` 20.0. The runner now holds the rule in one place (`TUNE_RULE`,
  `TUNE_THRESHOLD`, `choose_work_units`), and `python experiments/run_f3_grid.py --tune` was re-run.
  The code hash was unchanged since tuning (`9a40c4d8…`), and the regenerated file is identical in
  all 120 plan rows and in `share_proven` (which also confirms the solver's determinism on the
  tuning set); it records the plan's rule and `chosen` 10.0, equal to the frozen
  `cpsat_max_work_units`. `tests/test_f3_grid.py::test_tuning_file_matches_frozen_value_p45_tc1`
  and `::test_choose_work_units_rule_p45_tc2` keep the record, the runner and the config in step.

## Implementation notes and rulings

- **Review due day:** the plan writes Δ = ⌈h · log2(1/recall_threshold)⌉. Greedy reviews when
  recall drops strictly below the threshold, so the model uses ⌊h · log2(1/threshold)⌋ + 1 (the same
  value except when the product is an integer, where it is one day later, as greedy).
- **Level 5 (even load):** minimises the maximum daily load; idle days before the finish day are not
  modelled separately.
- **Review urgency:** greedy computes urgency on the day; the model uses greedy's formula at
  r = `recall_threshold` (one constant per concept) and greedy's `review_urgency` override (0 = no
  reviews, as the `no_review` arm).
- **Reviews of a concept with work in the plan** are modelled only after its work (greedy may also
  review it earlier if due).
- **Hybrid best effort and pure CP-SAT best effort** both use the CP-SAT fastest schedule truncated
  at the deadline ("the selected planner", D42).
- **Plan-level audit and F1:** `experiments/checks.count_plan_prereq_violations` projects D4 only,
  so it reports confirmation-check plans (Plan 3) as violations for greedy too; the F1 × F3 test uses
  the executed audit with the engine's mastered rule instead.
- **Latency:** cold-start CP-SAT plans take about 0.3–3 s on 8-node and 5–60 s on synth-20, so the
  full grid runs pure CP-SAT only on the pre-registered subset (D72). The test suite now takes about
  3.5 min (was about 1.5 min).

## After Plan 4

| Item | Value |
|---|---|
| `make check` | ruff clean; **462 passed, 1 skipped** (`test_full_results_match_registration_f1_tc10`, Plan 7); coverage **92.84%** |
| `pytest frontend/api/tests` | **17 passed** |
| Pending for Plan 7 (D90) | the full F3 grid (`experiments/results/f3_grid.json`), F3-TC9 |

**Plan V2 (D98):** the full F3 grid is superseded by the experiments_v2 study (E5) and not run; see `experiments_v2/README.md` and `experiments_v2/NOTES.md`.
