# experiments_v2 — notes

Baseline record, equivalence-check record, run log and outcomes of the Plan V2 study
(`EXPERIMENTS_V2_IMPLEMENTATION_PLAN.md`).

## V2-T0 — Starting point (2026-11-21)

| Item | Value |
|---|---|
| Code hash (SHA-256 over `src/**/*.py`) | `9a40c4d822397fa019d69ba64ddc7ab58d5baf8fe04ed0d090b1dfebfe66e6ef` |
| `config_hash(DEFAULT_CONFIG)` | `1e26bd7de81c8f56a6e998b33ee531f59470681d78ff71affd05362a910e7b11` |
| `make check` | green: 464 passed, 1 skipped, coverage 92.84% |
| `pytest -q frontend/api/tests` | green: 27 passed |
| CPU | 13th Gen Intel(R) Core(TM) i7-1360P, 16 logical CPUs; default workers 15 |
| `sha256sum -c data/external/CHECKSUMS` | `as.csv: OK`, `assist09_skill_builder.csv: OK`, `ct.csv: OK` (none missing) |

Plans 0–4.5 and Plan FE (with D96, D97) are present on the `redo` branch (last commit `07b8d43`).

## V2-T4 — Equivalence check (2026-11-21, one-off)

A throwaway script outside the repository (sha256
`4898873bae2bcddec95a29789ed06de7716c06f932ec0deb437b72bfb871d21b`) ran v2's harness and compared
it with stored results read as JSON data. The script was deleted afterwards.

| Check | Cells compared | Outcome |
|---|---|---|
| 1a. Episodes: adapt, calm, budget 15, seeds 1000–1199; goal-mastery rate, all-required rate, mean minutes, executed violations vs `experiments/results/f2_grid.json` (heuristic) | 20: worlds S0–S4 × 4-node, 8-node, `8node_x10`, synth-20 | all **equal** |
| 1b. Sweep diagnostic, odd seeds 101–599; diagnostic Brier, AUC, questions asked, next-answer Brier vs `f2_grid.json` | 60: worlds S0–S4, S4-assist09 × 4-node, 8-node, `8node_x10`, synth-20, synth-50 × heuristic, fitted_assist09 | all **equal** |
| 2. Synthetic curricula vs the old generator (run once inside the script) | synth-20, synth-50, synth-20-x10, synth-50-x10 | **byte-identical** |
| 3. Real-data fit vs `bkt_fit_assist09.json`, `bkt_fit_ct.json` | cleaning counts; class-profile parameters; pooled held-out RMSE, Brier, log-loss, AUC, ECE of the three models | cleaning equal; parameters within 4.0e-7 (stored values are rounded to 6 decimals); metrics within 4.8e-7 |

No difference needed a fix. Note: `config_hash(DEFAULT_CONFIG)` differs from the hash stored in
`f2_grid.json` (`a00fdb…`) only because fields were added to `EngineConfig` since (Plans 3–4);
the defaults' behaviour is unchanged, as Check 1 shows.

## V2-T8 — Final checks (2026-11-21)

| Item | V2-T0 | V2-T8 |
|---|---|---|
| Code hash | `9a40c4d822397fa0…` | `9a40c4d822397fa019d69ba64ddc7ab58d5baf8fe04ed0d090b1dfebfe66e6ef` (same) |
| `config_hash(DEFAULT_CONFIG)` | `1e26bd7de81c8f56…` | `1e26bd7de81c8f56a6e998b33ee531f59470681d78ff71affd05362a910e7b11` (same) |
| `git status -- src experiments` | clean | clean (0 entries) |
| `make check` | 464 passed, 1 skipped, 92.84% | 464 passed, 1 skipped, 92.84% |
| `pytest -q frontend/api/tests` | 27 passed | 27 passed |
| `pytest -q experiments_v2/tests` | – | 58 passed |
| `ruff check .`, `ruff format --check .` | – | clean (174 files) |
| Results carry their registered code hash | – | all 7 files (E1–E6 and `E5_latency.json`), none smoke |
| Report | – | `make v2-report`: 38 table files, 20 figure files, no "not run" rows |

## Run log (V2-T6)

All six results carry code hash `9a40c4d822397fa0…` (unchanged from V2-T0) and
`config_hash(DEFAULT_CONFIG)` `1e26bd7de81c8f56…`. Each prereg was set to Registered, with UTC time
and code hash, immediately before its full run, by the driver script (outside the repo).

| Exp | Registered UTC | Run UTC | Wall | Workers | Harness hash |
|---|---|---|---|---|---|
| E3 | 2026-11-20 23:02:50 | 23:02:50 – 23:03:29 | 39 s | 15 | `928630191a0a…` |
| E2 | 2026-11-20 23:03:29 | 23:03:29 – 23:25:31 | 1 321 s | 15 | `928630191a0a…` |
| E1 | 2026-11-20 23:37:19 | 23:37:20 – 00:07:37 | 1 817 s | 15 | `240e95fd4c2c…` |
| E4 | 2026-11-21 00:07:39 | 00:07:39 – 00:11:52 | 253 s | 15 | `240e95fd4c2c…` |
| E5 (cells) | 2026-11-21 00:11:52 | 00:11:52 – 03:57:16 | 13 524 s | 15 | `240e95fd4c2c…` |
| E5 (latency) | (same prereg) | 03:57:17 – 05:56:42 | 7 165 s | 1 | `240e95fd4c2c…` |
| E6 | 2026-11-21 03:36:32 | 03:36:32 – 03:39:47 | 196 s | 13 | `240e95fd4c2c…` |

- **E1 false start.** The driver reached E1 at 23:25:31 and was refused ("refusing to run"),
  on purpose: the E1 prereg had been moved aside to stop the driver after E2 so the code-review
  fixes (below) could land before E1, E4, E5 and E6 were registered. No E1 results were written.
- **Two harness hashes.** E2 and E3 ran on harness `928630…`. The changes before E1 touched only
  `core/episode.py` (θ at confirmation time), `runners/common.py` (confirmation metrics),
  `runners/e4_features.py`, `runners/e5_planners.py`, `report/` and `tests/`. The E2 and E3 code
  paths (`core/diagnostics.py`, `core/realdata.py`, `core/metrics.py`, their runners) are unchanged,
  so E2 and E3 were not re-run.
- **E5 cells.** One hybrid synth-20 cell kept one worker busy for about 1 h 20 min after the
  other 14 had finished; 430 greedy cells were reused from E1 (all three hashes matched).
- **E5 latency.** One worker, quiet machine: load average 1.00 / 1.07 / 1.42 before and
  1.02 / 1.15 / 1.20 after. CP-SAT on synth-50 (31–42 s per call, 155 calls per event set)
  took most of the 2 h.
- **E6 ran beside E5.** While E5's last cell ran on one core, the driver shell was stopped
  (SIGKILL to the shell only; the E5 process was untouched and wrote both its files) so it would
  not re-run E6, and E6 ran on 13 workers at `nice 19`. E6 finished at 03:39:47, before E5's timing
  phase began at 03:57:17, so the timings are unaffected. Results do not depend on the worker count
  (`test_determinism`).

## Outcomes

Every registered hypothesis, held or failed. Numbers are paired differences with 95 % bootstrap CIs
(2 000 resamples), N = 200 learners per arm unless stated. The full evidence strings are in
`report/tables/H.md`; per-cell numbers are in the results files and the report tables.

### Summary

| Exp | Hyp | Held | Key numbers |
|---|---|---|---|
| E1 | H1 | yes | 0 executed prerequisite violations for adapt and no_review over 560 cells |
| E1 | H2 | yes | S1 headline adapt − static goal mastery: 4-node +0.004 [−0.007, +0.015]; `8node_x10` +0.036 [+0.025, +0.048] |
| E1 | H3 | **no** | adapt − no_replan above 0 in only 6 of 40 missed-day cells; below 0 in many (down to −0.230 [−0.285, −0.175], S4 synth-20) |
| E1 | H4 | yes | adapt_h7 ≠ no_review_h7 in 49 of 80 forgetting_21 cells |
| E1 | H5 | yes | 0 plan-level violations over 3 897 198 plans checked |
| E2 | H1 | yes | bisection − sweep Brier from −0.229 [−0.265, −0.192] to −0.475 [−0.496, −0.451], all 6 cells |
| E2 | H2 | – | descriptive |
| E2 | H3 | yes | vs prior_only (Brier CI below 0): sweep 5/15, bisection 0/15, fixed@n 5/15, irt_cat_global@n 1/15, irt_cat_per_concept@n 10/15 |
| E3 | H1 | yes | assist09 Brier 0.1948 vs 0.2252, ECE 0.0086 vs 0.1324; ct Brier 0.2069 vs 0.2452, ECE 0.0112 vs 0.1452 |
| E3 | H2 | yes | next-answer Brier: 4-node −0.0184 [−0.0258, −0.0111], 8-node −0.0117, `8node_x10` −0.0166, synth-20 −0.0079 (all CIs below 0) |
| E3 | H3 | yes | mean extra questions: fitted_assist09 +0.48, fitted_ct +1.30 |
| E4 | H1 | yes | 0 executed violations, all arms, 30 cells |
| E4 | H2 | **no** | total minutes 8-node −1.76 [−4.76, +1.21], `8node_x10` −2.46 [−5.77, +0.76] (CIs include 0); goal mastery +0.110 and +0.040 (that part holds) |
| E4 | H3 | **no** | confirmation false-pass rate 0.60–0.73 in all 40 (cell, arm) pairs in S0–S3; limit was 0.10 |
| E5 | H1 | yes | 0 executed violations, all planners, 434 cells |
| E5 | H2 | yes | 86 800 learner first plans with greedy FEASIBLE, 0 UNKNOWN; 0 verdict mismatches |
| E5 | H3 | **no** | hybrid − greedy goal mastery CI excludes 0 in 2 of 434 cells: S2 `8node_x10` B5 missed_day and deadline_cut, both +0.020 [+0.005, +0.040] (hybrid better) |
| E5 | H4 | yes | 0 plan-level violations over 2 579 083 plans checked |
| E6 | – | – | descriptive; no hypotheses registered |

### What the failures mean

- **E1 H3 (adapt vs no_replan after missed days).** Replanning after a missed day does not raise goal
  mastery on its own; on 8-node, synth-20 and in S4 it lowers it. The likely cause is the gating seen
  in the static-wins list below: after a disruption the closed loop re-plans around prerequisites
  that lack evidence, which leaves less of a short budget for the goal. This was not tested per cell
  for no_replan, so it is a candidate explanation, not a finding.
- **E4 H2.** In S0, bisection asks more diagnostic items than the sweep (8-node 7.5 vs 3.0 items,
  13.7 vs 5.2 min) and saves study minutes (64.8 vs 75.0); the two partly cancel, so the
  total-minutes CI includes 0 (`8node_x10`: 7.1 vs 2.9 items, 60.8 vs 71.7 study min).
  Goal mastery is higher with bisection.
- **E4 H3 (confirmation checks are weak in the simulator).** 60–73 % of confirmations happen while
  the simulated learner's θ is below the true-mastery bar 0.70. The code was checked: θ is recorded at
  the moment of confirmation (the learner's initial θ for confirmations made by the diagnostic). Under
  the 2PL simulator (a = 3), an easy check item is answered correctly well below θ = 0.70, so a pass is
  weak evidence. The end-of-episode rate is reported as a secondary metric (`false_confirm_rate_at_end`).
- **E5 H3.** Hybrid differs from greedy only where it calls CP-SAT. The two differing cells are tight
  B5 cells with a disruption, and both differences favour hybrid by +0.020.
- **E2 H3 (reported, not a failure).** In the simulated worlds bisection's Brier is never below
  prior_only's (0 of 15 cells): its advantage is on the scripted learners (H1), not on population-like
  learners whose prior is already close.

### Mechanism check behind the static-wins list (E1)

A throwaway script (outside the repo) re-ran four static-win cells, recording minutes spent on the goal
concept itself. Share of all minutes spent on the goal, adapt vs static: S0 4-node B5 calm 8 % vs 23 %;
S1 8-node B15 missed_day 2 % vs 18 %; S4 4-node B10 missed_day 2 % vs 34 %; S3 synth-20 B30
budget_crash 0 % vs 2.5 %. Adapt holds the goal back until its prerequisites have evidence of mastery
(D46); static walks the curriculum in order regardless. In every one of the 158 cells static broke
prerequisite order for 178–200 of its 200 learners. E6 points the same way: stricter mastery rules
lower adapt's goal mastery (θ = 0.95: down to −0.105; `n_consecutive` 3: down to −0.125;
`k_responses` 4: down to −0.075), because more of the budget goes to prerequisites.

### E6 (descriptive)

- **Scans (S0, S1 × 4-node, 8-node, `8node_x10`, B15, calm).** Largest changes in goal mastery from
  baseline: `mastery_criterion=n_consecutive` 3 (−0.015 to −0.125), `theta` 0.95 (−0.015 to −0.105),
  `k_responses` 4 (−0.015 to −0.075), `half_life_days` 7 (−0.005 to −0.070). `p0`, `t_lesson`,
  `recall_threshold` and `remediation_threshold` move it by at most 0.035. Looser settings (`theta`
  0.70, `k_responses` 1, `n_consecutive` 2, `two_threshold`) change it by at most 0.015.
- **Real-data world S4-assist09 (exploratory).** adapt − static goal mastery: 4-node calm +0.000
  [−0.035, +0.035], 4-node missed_day −0.065 [−0.110, −0.025], `8node_x10` calm +0.100
  [+0.060, +0.140], `8node_x10` missed_day +0.050 [+0.025, +0.080]. adapt − no_replan: +0.040, +0.040,
  +0.020, −0.030 (the last two CIs include 0). Adapt has the highest all-required rate in every cell.

### Per-cell explanations (registered explanation rules)

Generated from the results files; each line cites the numbers it rests on.

### E1: cells where static wins on goal mastery (158)

- `S0|4-node|B5|calm` (deadline 9): static 0.330 vs adapt 0.225, diff -0.105 [-0.150, -0.055]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 33.3 vs 40.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.33 of cases.
- `S0|4-node|B5|missed_day` (deadline 9): static 0.330 vs adapt 0.210, diff -0.120 [-0.165, -0.075]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 31.8 vs 35.0 min, and its learners' goal ever reached theta 0.70 in 0.21 vs 0.33 of cases.
- `S0|4-node|B5|deadline_cut` (deadline 9): static 0.255 vs adapt 0.210, diff -0.045 [-0.080, -0.010]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 31.8 vs 36.0 min, and its learners' goal ever reached theta 0.70 in 0.21 vs 0.26 of cases.
- `S0|4-node|B5|missed_2days` (deadline 9): static 0.330 vs adapt 0.190, diff -0.140 [-0.190, -0.095]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 26.9 vs 30.0 min, and its learners' goal ever reached theta 0.70 in 0.19 vs 0.33 of cases.
- `S0|4-node|B10|calm` (deadline 5): static 0.370 vs adapt 0.275, diff -0.095 [-0.145, -0.045]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 39.2 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.28 vs 0.37 of cases.
- `S0|4-node|B10|missed_day` (deadline 5): static 0.370 vs adapt 0.225, diff -0.145 [-0.195, -0.095]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 33.7 vs 32.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.37 of cases.
- `S0|4-node|B10|budget_drop` (deadline 5): static 0.370 vs adapt 0.180, diff -0.190 [-0.240, -0.135]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 23.7 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.18 vs 0.37 of cases.
- `S0|4-node|B10|deadline_cut` (deadline 5): static 0.295 vs adapt 0.225, diff -0.070 [-0.110, -0.030]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 33.7 vs 38.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.29 of cases.
- `S0|4-node|B10|missed_2days` (deadline 5): static 0.370 vs adapt 0.185, diff -0.185 [-0.235, -0.130]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 26.1 vs 23.0 min, and its learners' goal ever reached theta 0.70 in 0.18 vs 0.37 of cases.
- `S0|4-node|B15|missed_day` (deadline 4): static 0.370 vs adapt 0.265, diff -0.105 [-0.155, -0.055]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 37.6 vs 28.0 min, and its learners' goal ever reached theta 0.70 in 0.27 vs 0.37 of cases.
- `S0|4-node|B15|budget_drop` (deadline 4): static 0.370 vs adapt 0.235, diff -0.135 [-0.185, -0.085]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 35.2 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.37 of cases.
- `S0|4-node|B15|deadline_cut` (deadline 4): static 0.370 vs adapt 0.265, diff -0.105 [-0.155, -0.055]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 37.6 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.27 vs 0.37 of cases.
- `S0|4-node|B30|budget_crash` (deadline 3): static 0.370 vs adapt 0.230, diff -0.140 [-0.190, -0.090]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 35.1 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.37 of cases.
- `S0|8-node|B5|calm` (deadline 17): static 0.400 vs adapt 0.305, diff -0.095 [-0.135, -0.055]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 68.1 vs 72.0 min, and its learners' goal ever reached theta 0.70 in 0.30 vs 0.40 of cases.
- `S0|8-node|B5|missed_day` (deadline 17): static 0.400 vs adapt 0.305, diff -0.095 [-0.135, -0.055]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 64.1 vs 67.0 min, and its learners' goal ever reached theta 0.70 in 0.30 vs 0.40 of cases.
- `S0|8-node|B5|deadline_cut` (deadline 17): static 0.355 vs adapt 0.305, diff -0.050 [-0.080, -0.020]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 64.1 vs 68.0 min, and its learners' goal ever reached theta 0.70 in 0.30 vs 0.35 of cases.
- `S0|8-node|B5|missed_2days` (deadline 17): static 0.400 vs adapt 0.290, diff -0.110 [-0.155, -0.070]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 59.9 vs 62.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.40 of cases.
- `S0|8-node|B10|calm` (deadline 8): static 0.445 vs adapt 0.315, diff -0.130 [-0.180, -0.085]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 67.1 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.32 vs 0.45 of cases.
- `S0|8-node|B10|missed_day` (deadline 8): static 0.445 vs adapt 0.295, diff -0.150 [-0.200, -0.105]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 60.1 vs 64.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.45 of cases.
- `S0|8-node|B10|budget_drop` (deadline 8): static 0.445 vs adapt 0.290, diff -0.155 [-0.205, -0.110]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 36.1 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.45 of cases.
- `S0|8-node|B10|deadline_cut` (deadline 8): static 0.355 vs adapt 0.295, diff -0.060 [-0.095, -0.030]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 60.1 vs 68.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.35 of cases.
- `S0|8-node|B10|missed_2days` (deadline 8): static 0.445 vs adapt 0.290, diff -0.155 [-0.205, -0.110]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 52.2 vs 55.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.45 of cases.
- `S0|8-node|B15|calm` (deadline 6): static 0.445 vs adapt 0.365, diff -0.080 [-0.130, -0.035]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 76.6 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.36 vs 0.45 of cases.
- `S0|8-node|B15|missed_day` (deadline 6): static 0.445 vs adapt 0.330, diff -0.115 [-0.165, -0.070]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 65.8 vs 60.0 min, and its learners' goal ever reached theta 0.70 in 0.33 vs 0.45 of cases.
- `S0|8-node|B15|budget_drop` (deadline 6): static 0.445 vs adapt 0.290, diff -0.155 [-0.205, -0.110]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 54.9 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.45 of cases.
- `S0|8-node|B15|deadline_cut` (deadline 6): static 0.400 vs adapt 0.330, diff -0.070 [-0.110, -0.030]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 65.8 vs 72.0 min, and its learners' goal ever reached theta 0.70 in 0.33 vs 0.40 of cases.
- `S0|8-node|B15|missed_2days` (deadline 6): static 0.445 vs adapt 0.290, diff -0.155 [-0.205, -0.110]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 52.6 vs 47.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.45 of cases.
- `S0|8-node|B30|budget_drop` (deadline 4): static 0.445 vs adapt 0.345, diff -0.100 [-0.150, -0.050]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 69.8 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.34 vs 0.45 of cases.
- `S0|8-node|B30|budget_crash` (deadline 4): static 0.445 vs adapt 0.290, diff -0.155 [-0.205, -0.110]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 41.8 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.45 of cases.
- `S0|synth-20|B30|missed_day` (deadline 7): static 0.330 vs adapt 0.275, diff -0.055 [-0.095, -0.020]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 169.8 vs 169.0 min, and its learners' goal ever reached theta 0.70 in 0.28 vs 0.33 of cases.
- `S0|synth-20|B30|budget_drop` (deadline 7): static 0.330 vs adapt 0.240, diff -0.090 [-0.130, -0.055]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 110.0 vs 197.0 min, and its learners' goal ever reached theta 0.70 in 0.24 vs 0.33 of cases.
- `S0|synth-20|B30|missed_2days` (deadline 7): static 0.330 vs adapt 0.240, diff -0.090 [-0.130, -0.055]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 141.5 vs 142.0 min, and its learners' goal ever reached theta 0.70 in 0.24 vs 0.33 of cases.
- `S0|synth-20|B30|budget_crash` (deadline 7): static 0.330 vs adapt 0.240, diff -0.090 [-0.130, -0.055]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 49.6 vs 197.0 min, and its learners' goal ever reached theta 0.70 in 0.24 vs 0.33 of cases.
- `S1|4-node|B5|missed_2days` (deadline 9): static 0.215 vs adapt 0.185, diff -0.030 [-0.055, -0.010]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 26.9 vs 30.0 min, and its learners' goal ever reached theta 0.70 in 0.18 vs 0.21 of cases.
- `S1|4-node|B10|missed_day` (deadline 5): static 0.225 vs adapt 0.200, diff -0.025 [-0.050, -0.005]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 33.8 vs 32.0 min, and its learners' goal ever reached theta 0.70 in 0.20 vs 0.23 of cases.
- `S1|4-node|B10|budget_drop` (deadline 5): static 0.225 vs adapt 0.175, diff -0.050 [-0.080, -0.020]. Static broke prerequisite order for 185/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 23.7 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.17 vs 0.23 of cases.
- `S1|4-node|B10|missed_2days` (deadline 5): static 0.215 vs adapt 0.180, diff -0.035 [-0.060, -0.010]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 26.1 vs 23.0 min, and its learners' goal ever reached theta 0.70 in 0.18 vs 0.21 of cases.
- `S1|4-node|B15|budget_drop` (deadline 4): static 0.225 vs adapt 0.200, diff -0.025 [-0.050, -0.005]. Static broke prerequisite order for 185/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 35.5 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.20 vs 0.23 of cases.
- `S1|8-node|B5|calm` (deadline 17): static 0.335 vs adapt 0.300, diff -0.035 [-0.065, -0.015]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 68.5 vs 72.0 min, and its learners' goal ever reached theta 0.70 in 0.30 vs 0.34 of cases.
- `S1|8-node|B5|missed_day` (deadline 17): static 0.335 vs adapt 0.295, diff -0.040 [-0.070, -0.015]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 64.4 vs 67.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.34 of cases.
- `S1|8-node|B5|deadline_cut` (deadline 17): static 0.315 vs adapt 0.295, diff -0.020 [-0.040, -0.005]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 64.4 vs 68.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.32 of cases.
- `S1|8-node|B5|missed_2days` (deadline 17): static 0.335 vs adapt 0.290, diff -0.045 [-0.075, -0.020]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 60.2 vs 62.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.34 of cases.
- `S1|8-node|B10|calm` (deadline 8): static 0.340 vs adapt 0.305, diff -0.035 [-0.060, -0.010]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 67.5 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.30 vs 0.34 of cases.
- `S1|8-node|B10|missed_day` (deadline 8): static 0.340 vs adapt 0.295, diff -0.045 [-0.075, -0.020]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 60.3 vs 64.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.34 of cases.
- `S1|8-node|B10|budget_drop` (deadline 8): static 0.340 vs adapt 0.290, diff -0.050 [-0.080, -0.025]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 36.2 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.34 of cases.
- `S1|8-node|B10|deadline_cut` (deadline 8): static 0.315 vs adapt 0.295, diff -0.020 [-0.040, -0.005]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 60.3 vs 68.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.32 of cases.
- `S1|8-node|B10|missed_2days` (deadline 8): static 0.340 vs adapt 0.290, diff -0.050 [-0.080, -0.025]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 52.3 vs 55.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.34 of cases.
- `S1|8-node|B15|calm` (deadline 6): static 0.340 vs adapt 0.315, diff -0.025 [-0.045, -0.005]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 78.2 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.32 vs 0.34 of cases.
- `S1|8-node|B15|missed_day` (deadline 6): static 0.340 vs adapt 0.305, diff -0.035 [-0.060, -0.010]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 65.9 vs 60.0 min, and its learners' goal ever reached theta 0.70 in 0.30 vs 0.34 of cases.
- `S1|8-node|B15|budget_drop` (deadline 6): static 0.340 vs adapt 0.290, diff -0.050 [-0.080, -0.025]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 54.9 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.34 of cases.
- `S1|8-node|B15|deadline_cut` (deadline 6): static 0.335 vs adapt 0.305, diff -0.030 [-0.055, -0.010]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 65.9 vs 72.0 min, and its learners' goal ever reached theta 0.70 in 0.30 vs 0.34 of cases.
- `S1|8-node|B15|missed_2days` (deadline 6): static 0.340 vs adapt 0.290, diff -0.050 [-0.080, -0.025]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 52.7 vs 47.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.34 of cases.
- `S1|8-node|B30|missed_day` (deadline 4): static 0.340 vs adapt 0.315, diff -0.025 [-0.045, -0.005]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 83.6 vs 44.0 min, and its learners' goal ever reached theta 0.70 in 0.32 vs 0.34 of cases.
- `S1|8-node|B30|budget_drop` (deadline 4): static 0.340 vs adapt 0.315, diff -0.025 [-0.045, -0.005]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 70.3 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.32 vs 0.34 of cases.
- `S1|8-node|B30|deadline_cut` (deadline 4): static 0.340 vs adapt 0.315, diff -0.025 [-0.045, -0.005]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 83.6 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.32 vs 0.34 of cases.
- `S1|8-node|B30|budget_crash` (deadline 4): static 0.340 vs adapt 0.290, diff -0.050 [-0.080, -0.025]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 41.8 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.34 of cases.
- `S2|4-node|B5|calm` (deadline 9): static 0.400 vs adapt 0.295, diff -0.105 [-0.155, -0.060]. Static broke prerequisite order for 178/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 33.1 vs 40.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.40 of cases.
- `S2|4-node|B5|missed_day` (deadline 9): static 0.400 vs adapt 0.275, diff -0.125 [-0.180, -0.075]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 31.5 vs 35.0 min, and its learners' goal ever reached theta 0.70 in 0.28 vs 0.40 of cases.
- `S2|4-node|B5|missed_2days` (deadline 9): static 0.400 vs adapt 0.225, diff -0.175 [-0.225, -0.125]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 26.8 vs 30.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.40 of cases.
- `S2|4-node|B10|calm` (deadline 5): static 0.435 vs adapt 0.375, diff -0.060 [-0.110, -0.010]. Static broke prerequisite order for 178/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 39.0 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.38 vs 0.43 of cases.
- `S2|4-node|B10|missed_day` (deadline 5): static 0.435 vs adapt 0.290, diff -0.145 [-0.195, -0.095]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 33.5 vs 32.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.43 of cases.
- `S2|4-node|B10|budget_drop` (deadline 5): static 0.435 vs adapt 0.220, diff -0.215 [-0.270, -0.160]. Static broke prerequisite order for 178/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 23.7 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.43 of cases.
- `S2|4-node|B10|deadline_cut` (deadline 5): static 0.370 vs adapt 0.290, diff -0.080 [-0.130, -0.035]. Static broke prerequisite order for 178/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 33.5 vs 38.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.37 of cases.
- `S2|4-node|B10|missed_2days` (deadline 5): static 0.435 vs adapt 0.225, diff -0.210 [-0.265, -0.160]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 26.0 vs 23.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.43 of cases.
- `S2|4-node|B15|missed_day` (deadline 4): static 0.435 vs adapt 0.360, diff -0.075 [-0.130, -0.020]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 37.3 vs 28.0 min, and its learners' goal ever reached theta 0.70 in 0.36 vs 0.43 of cases.
- `S2|4-node|B15|budget_drop` (deadline 4): static 0.435 vs adapt 0.320, diff -0.115 [-0.165, -0.065]. Static broke prerequisite order for 178/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 35.1 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.32 vs 0.43 of cases.
- `S2|4-node|B15|deadline_cut` (deadline 4): static 0.435 vs adapt 0.360, diff -0.075 [-0.130, -0.020]. Static broke prerequisite order for 178/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 37.3 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.36 vs 0.43 of cases.
- `S2|4-node|B30|budget_crash` (deadline 3): static 0.435 vs adapt 0.310, diff -0.125 [-0.175, -0.075]. Static broke prerequisite order for 178/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 34.8 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.31 vs 0.43 of cases.
- `S2|8-node|B5|calm` (deadline 17): static 0.405 vs adapt 0.225, diff -0.180 [-0.235, -0.125]. Static broke prerequisite order for 198/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 67.4 vs 72.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.41 of cases.
- `S2|8-node|B5|missed_day` (deadline 17): static 0.405 vs adapt 0.225, diff -0.180 [-0.235, -0.125]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 63.9 vs 67.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.41 of cases.
- `S2|8-node|B5|missed_2days` (deadline 17): static 0.405 vs adapt 0.210, diff -0.195 [-0.250, -0.140]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 59.7 vs 62.0 min, and its learners' goal ever reached theta 0.70 in 0.21 vs 0.41 of cases.
- `S2|8-node|B10|calm` (deadline 8): static 0.450 vs adapt 0.270, diff -0.180 [-0.235, -0.125]. Static broke prerequisite order for 198/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 65.9 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.27 vs 0.45 of cases.
- `S2|8-node|B10|missed_day` (deadline 8): static 0.450 vs adapt 0.230, diff -0.220 [-0.280, -0.160]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 59.4 vs 64.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.45 of cases.
- `S2|8-node|B10|budget_drop` (deadline 8): static 0.450 vs adapt 0.190, diff -0.260 [-0.320, -0.200]. Static broke prerequisite order for 198/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 36.0 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.19 vs 0.45 of cases.
- `S2|8-node|B10|missed_2days` (deadline 8): static 0.450 vs adapt 0.205, diff -0.245 [-0.305, -0.190]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 51.8 vs 55.0 min, and its learners' goal ever reached theta 0.70 in 0.20 vs 0.45 of cases.
- `S2|8-node|B15|calm` (deadline 6): static 0.450 vs adapt 0.370, diff -0.080 [-0.135, -0.025]. Static broke prerequisite order for 198/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 74.6 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.37 vs 0.45 of cases.
- `S2|8-node|B15|missed_day` (deadline 6): static 0.450 vs adapt 0.280, diff -0.170 [-0.225, -0.115]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 64.8 vs 60.0 min, and its learners' goal ever reached theta 0.70 in 0.28 vs 0.45 of cases.
- `S2|8-node|B15|budget_drop` (deadline 6): static 0.450 vs adapt 0.215, diff -0.235 [-0.295, -0.180]. Static broke prerequisite order for 198/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 54.8 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.21 vs 0.45 of cases.
- `S2|8-node|B15|deadline_cut` (deadline 6): static 0.405 vs adapt 0.280, diff -0.125 [-0.180, -0.070]. Static broke prerequisite order for 198/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 64.8 vs 72.0 min, and its learners' goal ever reached theta 0.70 in 0.28 vs 0.41 of cases.
- `S2|8-node|B15|missed_2days` (deadline 6): static 0.450 vs adapt 0.210, diff -0.240 [-0.300, -0.185]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 52.7 vs 47.0 min, and its learners' goal ever reached theta 0.70 in 0.21 vs 0.45 of cases.
- `S2|8-node|B30|missed_day` (deadline 4): static 0.450 vs adapt 0.385, diff -0.065 [-0.120, -0.010]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 78.7 vs 44.0 min, and its learners' goal ever reached theta 0.70 in 0.39 vs 0.45 of cases.
- `S2|8-node|B30|budget_drop` (deadline 4): static 0.450 vs adapt 0.320, diff -0.130 [-0.185, -0.075]. Static broke prerequisite order for 198/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 68.3 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.32 vs 0.45 of cases.
- `S2|8-node|B30|deadline_cut` (deadline 4): static 0.450 vs adapt 0.385, diff -0.065 [-0.120, -0.010]. Static broke prerequisite order for 198/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 78.7 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.39 vs 0.45 of cases.
- `S2|8-node|B30|budget_crash` (deadline 4): static 0.450 vs adapt 0.190, diff -0.260 [-0.320, -0.200]. Static broke prerequisite order for 198/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 41.4 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.19 vs 0.45 of cases.
- `S2|synth-20|B30|missed_day` (deadline 7): static 0.350 vs adapt 0.235, diff -0.115 [-0.165, -0.070]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 168.4 vs 169.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.35 of cases.
- `S2|synth-20|B30|budget_drop` (deadline 7): static 0.350 vs adapt 0.190, diff -0.160 [-0.210, -0.110]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 110.3 vs 197.0 min, and its learners' goal ever reached theta 0.70 in 0.19 vs 0.35 of cases.
- `S2|synth-20|B30|missed_2days` (deadline 7): static 0.350 vs adapt 0.200, diff -0.150 [-0.200, -0.100]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 141.5 vs 142.0 min, and its learners' goal ever reached theta 0.70 in 0.20 vs 0.35 of cases.
- `S2|synth-20|B30|budget_crash` (deadline 7): static 0.350 vs adapt 0.190, diff -0.160 [-0.210, -0.110]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 49.8 vs 197.0 min, and its learners' goal ever reached theta 0.70 in 0.19 vs 0.35 of cases.
- `S3|4-node|B5|calm` (deadline 9): static 0.030 vs adapt 0.000, diff -0.030 [-0.055, -0.010]. Static broke prerequisite order for 192/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 33.7 vs 40.0 min, and its learners' goal ever reached theta 0.70 in 0.17 vs 0.17 of cases.
- `S3|4-node|B5|missed_day` (deadline 9): static 0.030 vs adapt 0.000, diff -0.030 [-0.055, -0.010]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 32.0 vs 35.0 min, and its learners' goal ever reached theta 0.70 in 0.17 vs 0.17 of cases.
- `S3|4-node|B5|missed_2days` (deadline 9): static 0.030 vs adapt 0.000, diff -0.030 [-0.055, -0.010]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 27.0 vs 30.0 min, and its learners' goal ever reached theta 0.70 in 0.17 vs 0.17 of cases.
- `S3|4-node|B10|calm` (deadline 5): static 0.165 vs adapt 0.100, diff -0.065 [-0.110, -0.020]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 39.7 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.20 vs 0.20 of cases.
- `S3|4-node|B10|missed_day` (deadline 5): static 0.165 vs adapt 0.070, diff -0.095 [-0.140, -0.055]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 33.9 vs 32.0 min, and its learners' goal ever reached theta 0.70 in 0.18 vs 0.20 of cases.
- `S3|4-node|B10|budget_drop` (deadline 5): static 0.165 vs adapt 0.030, diff -0.135 [-0.180, -0.090]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 23.7 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.17 vs 0.20 of cases.
- `S3|4-node|B10|deadline_cut` (deadline 5): static 0.170 vs adapt 0.100, diff -0.070 [-0.110, -0.035]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 33.9 vs 38.0 min, and its learners' goal ever reached theta 0.70 in 0.18 vs 0.20 of cases.
- `S3|4-node|B10|missed_2days` (deadline 5): static 0.165 vs adapt 0.035, diff -0.130 [-0.175, -0.085]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 26.2 vs 23.0 min, and its learners' goal ever reached theta 0.70 in 0.17 vs 0.20 of cases.
- `S3|4-node|B15|budget_drop` (deadline 4): static 0.170 vs adapt 0.100, diff -0.070 [-0.110, -0.035]. Static broke prerequisite order for 185/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 35.5 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.18 vs 0.27 of cases.
- `S3|4-node|B15|deadline_cut` (deadline 4): static 0.255 vs adapt 0.195, diff -0.060 [-0.105, -0.020]. Static broke prerequisite order for 185/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 37.7 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.24 vs 0.27 of cases.
- `S3|4-node|B30|budget_crash` (deadline 3): static 0.230 vs adapt 0.150, diff -0.080 [-0.125, -0.040]. Static broke prerequisite order for 183/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 35.1 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.21 vs 0.30 of cases.
- `S3|8-node|B10|calm` (deadline 8): static 0.100 vs adapt 0.020, diff -0.080 [-0.120, -0.040]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 67.9 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.29 of cases.
- `S3|8-node|B10|missed_day` (deadline 8): static 0.100 vs adapt 0.005, diff -0.095 [-0.140, -0.055]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 60.5 vs 64.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.29 of cases.
- `S3|8-node|B10|budget_drop` (deadline 8): static 0.100 vs adapt 0.000, diff -0.100 [-0.145, -0.060]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 36.2 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.29 of cases.
- `S3|8-node|B10|deadline_cut` (deadline 8): static 0.050 vs adapt 0.015, diff -0.035 [-0.065, -0.005]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 60.5 vs 68.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.29 of cases.
- `S3|8-node|B10|missed_2days` (deadline 8): static 0.100 vs adapt 0.000, diff -0.100 [-0.145, -0.060]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 52.4 vs 55.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.29 of cases.
- `S3|8-node|B15|calm` (deadline 6): static 0.165 vs adapt 0.080, diff -0.085 [-0.135, -0.040]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 77.4 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.33 vs 0.32 of cases.
- `S3|8-node|B15|missed_day` (deadline 6): static 0.165 vs adapt 0.040, diff -0.125 [-0.175, -0.080]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 65.9 vs 60.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.32 of cases.
- `S3|8-node|B15|budget_drop` (deadline 6): static 0.165 vs adapt 0.010, diff -0.155 [-0.205, -0.110]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 55.1 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.32 of cases.
- `S3|8-node|B15|deadline_cut` (deadline 6): static 0.250 vs adapt 0.095, diff -0.155 [-0.205, -0.105]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 65.9 vs 72.0 min, and its learners' goal ever reached theta 0.70 in 0.30 vs 0.32 of cases.
- `S3|8-node|B15|missed_2days` (deadline 6): static 0.165 vs adapt 0.010, diff -0.155 [-0.205, -0.110]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 52.6 vs 47.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.32 of cases.
- `S3|8-node|B30|budget_drop` (deadline 4): static 0.275 vs adapt 0.130, diff -0.145 [-0.195, -0.090]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 70.0 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.33 vs 0.36 of cases.
- `S3|8-node|B30|budget_crash` (deadline 4): static 0.275 vs adapt 0.075, diff -0.200 [-0.255, -0.145]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 41.8 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.29 vs 0.36 of cases.
- `S3|synth-20|B30|missed_day` (deadline 7): static 0.055 vs adapt 0.015, diff -0.040 [-0.075, -0.010]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 170.3 vs 169.0 min, and its learners' goal ever reached theta 0.70 in 0.25 vs 0.24 of cases.
- `S3|synth-20|B30|budget_drop` (deadline 7): static 0.055 vs adapt 0.005, diff -0.050 [-0.085, -0.020]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 109.9 vs 197.0 min, and its learners' goal ever reached theta 0.70 in 0.24 vs 0.24 of cases.
- `S3|synth-20|B30|missed_2days` (deadline 7): static 0.055 vs adapt 0.005, diff -0.050 [-0.085, -0.020]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 141.8 vs 142.0 min, and its learners' goal ever reached theta 0.70 in 0.24 vs 0.24 of cases.
- `S3|synth-20|B30|budget_crash` (deadline 7): static 0.055 vs adapt 0.005, diff -0.050 [-0.085, -0.020]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 49.5 vs 197.0 min, and its learners' goal ever reached theta 0.70 in 0.24 vs 0.24 of cases.
- `S4|4-node|B5|calm` (deadline 9): static 0.480 vs adapt 0.220, diff -0.260 [-0.320, -0.195]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 34.6 vs 40.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.48 of cases.
- `S4|4-node|B5|missed_day` (deadline 9): static 0.480 vs adapt 0.220, diff -0.260 [-0.320, -0.195]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 32.1 vs 35.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.48 of cases.
- `S4|4-node|B5|deadline_cut` (deadline 9): static 0.380 vs adapt 0.220, diff -0.160 [-0.215, -0.110]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 32.1 vs 36.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.38 of cases.
- `S4|4-node|B5|missed_2days` (deadline 9): static 0.480 vs adapt 0.215, diff -0.265 [-0.325, -0.200]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 27.4 vs 30.0 min, and its learners' goal ever reached theta 0.70 in 0.21 vs 0.48 of cases.
- `S4|4-node|B10|calm` (deadline 5): static 0.505 vs adapt 0.260, diff -0.245 [-0.310, -0.180]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 42.8 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.26 vs 0.51 of cases.
- `S4|4-node|B10|missed_day` (deadline 5): static 0.505 vs adapt 0.220, diff -0.285 [-0.350, -0.220]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 34.9 vs 32.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.51 of cases.
- `S4|4-node|B10|budget_drop` (deadline 5): static 0.505 vs adapt 0.210, diff -0.295 [-0.360, -0.230]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 23.8 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.21 vs 0.51 of cases.
- `S4|4-node|B10|deadline_cut` (deadline 5): static 0.460 vs adapt 0.220, diff -0.240 [-0.300, -0.180]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 34.9 vs 38.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.46 of cases.
- `S4|4-node|B10|missed_2days` (deadline 5): static 0.505 vs adapt 0.210, diff -0.295 [-0.360, -0.230]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 26.7 vs 23.0 min, and its learners' goal ever reached theta 0.70 in 0.21 vs 0.51 of cases.
- `S4|4-node|B15|calm` (deadline 4): static 0.505 vs adapt 0.355, diff -0.150 [-0.210, -0.090]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 52.1 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.35 vs 0.51 of cases.
- `S4|4-node|B15|missed_day` (deadline 4): static 0.505 vs adapt 0.245, diff -0.260 [-0.325, -0.195]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 39.6 vs 28.0 min, and its learners' goal ever reached theta 0.70 in 0.24 vs 0.51 of cases.
- `S4|4-node|B15|budget_drop` (deadline 4): static 0.505 vs adapt 0.220, diff -0.285 [-0.350, -0.220]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 38.2 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.51 of cases.
- `S4|4-node|B15|deadline_cut` (deadline 4): static 0.505 vs adapt 0.245, diff -0.260 [-0.325, -0.195]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 39.6 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.24 vs 0.51 of cases.
- `S4|4-node|B30|budget_drop` (deadline 3): static 0.505 vs adapt 0.375, diff -0.130 [-0.190, -0.070]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 53.9 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.38 vs 0.51 of cases.
- `S4|4-node|B30|deadline_cut` (deadline 3): static 0.505 vs adapt 0.375, diff -0.130 [-0.190, -0.070]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 54.8 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.38 vs 0.51 of cases.
- `S4|4-node|B30|budget_crash` (deadline 3): static 0.505 vs adapt 0.235, diff -0.270 [-0.335, -0.205]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 35.9 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.51 of cases.
- `S4|4-node|B30|deadline_halved` (deadline 3): static 0.505 vs adapt 0.375, diff -0.130 [-0.190, -0.070]. Static broke prerequisite order for 188/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 54.8 vs 42.0 min, and its learners' goal ever reached theta 0.70 in 0.38 vs 0.51 of cases.
- `S4|8-node|B5|calm` (deadline 17): static 0.445 vs adapt 0.225, diff -0.220 [-0.280, -0.165]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 69.2 vs 72.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.45 of cases.
- `S4|8-node|B5|missed_day` (deadline 17): static 0.445 vs adapt 0.225, diff -0.220 [-0.280, -0.165]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 65.0 vs 67.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.45 of cases.
- `S4|8-node|B5|deadline_cut` (deadline 17): static 0.370 vs adapt 0.225, diff -0.145 [-0.195, -0.095]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 65.0 vs 68.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.37 of cases.
- `S4|8-node|B5|missed_2days` (deadline 17): static 0.445 vs adapt 0.220, diff -0.225 [-0.285, -0.170]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 60.9 vs 62.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.45 of cases.
- `S4|8-node|B5|forgetting_21` (deadline 21): static 0.465 vs adapt 0.230, diff -0.235 [-0.295, -0.175]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 84.7 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.47 of cases.
- `S4|8-node|B10|calm` (deadline 8): static 0.465 vs adapt 0.225, diff -0.240 [-0.300, -0.180]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 69.8 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.47 of cases.
- `S4|8-node|B10|missed_day` (deadline 8): static 0.465 vs adapt 0.220, diff -0.245 [-0.305, -0.185]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 61.7 vs 64.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.47 of cases.
- `S4|8-node|B10|budget_drop` (deadline 8): static 0.465 vs adapt 0.220, diff -0.245 [-0.305, -0.185]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 36.8 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.47 of cases.
- `S4|8-node|B10|deadline_cut` (deadline 8): static 0.370 vs adapt 0.220, diff -0.150 [-0.200, -0.100]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 61.7 vs 68.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.37 of cases.
- `S4|8-node|B10|missed_2days` (deadline 8): static 0.465 vs adapt 0.220, diff -0.245 [-0.305, -0.185]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 53.4 vs 55.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.47 of cases.
- `S4|8-node|B15|calm` (deadline 6): static 0.465 vs adapt 0.235, diff -0.230 [-0.290, -0.175]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 80.2 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.47 of cases.
- `S4|8-node|B15|missed_day` (deadline 6): static 0.465 vs adapt 0.225, diff -0.240 [-0.300, -0.180]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 67.1 vs 60.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.47 of cases.
- `S4|8-node|B15|budget_drop` (deadline 6): static 0.465 vs adapt 0.220, diff -0.245 [-0.305, -0.185]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 56.9 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.47 of cases.
- `S4|8-node|B15|deadline_cut` (deadline 6): static 0.445 vs adapt 0.225, diff -0.220 [-0.280, -0.165]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 67.1 vs 72.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.45 of cases.
- `S4|8-node|B15|missed_2days` (deadline 6): static 0.465 vs adapt 0.220, diff -0.245 [-0.305, -0.185]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 53.6 vs 47.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.47 of cases.
- `S4|8-node|B30|calm` (deadline 4): static 0.465 vs adapt 0.335, diff -0.130 [-0.200, -0.065]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 111.4 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.34 vs 0.47 of cases.
- `S4|8-node|B30|missed_day` (deadline 4): static 0.465 vs adapt 0.260, diff -0.205 [-0.270, -0.145]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 85.9 vs 44.0 min, and its learners' goal ever reached theta 0.70 in 0.26 vs 0.47 of cases.
- `S4|8-node|B30|budget_drop` (deadline 4): static 0.465 vs adapt 0.225, diff -0.240 [-0.300, -0.180]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 69.4 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.23 vs 0.47 of cases.
- `S4|8-node|B30|deadline_cut` (deadline 4): static 0.465 vs adapt 0.260, diff -0.205 [-0.270, -0.145]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 85.9 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.26 vs 0.47 of cases.
- `S4|8-node|B30|budget_crash` (deadline 4): static 0.465 vs adapt 0.220, diff -0.245 [-0.305, -0.185]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 41.3 vs 74.0 min, and its learners' goal ever reached theta 0.70 in 0.22 vs 0.47 of cases.
- `S4|synth-20|B15|forgetting_21` (deadline 21): static 0.475 vs adapt 0.245, diff -0.230 [-0.290, -0.170]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 286.8 vs 204.0 min, and its learners' goal ever reached theta 0.70 in 0.24 vs 0.47 of cases.
- `S4|synth-20|B30|calm` (deadline 7): static 0.425 vs adapt 0.210, diff -0.215 [-0.270, -0.160]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 200.6 vs 197.0 min, and its learners' goal ever reached theta 0.70 in 0.21 vs 0.42 of cases.
- `S4|synth-20|B30|missed_day` (deadline 7): static 0.425 vs adapt 0.205, diff -0.220 [-0.275, -0.165]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 172.1 vs 169.0 min, and its learners' goal ever reached theta 0.70 in 0.20 vs 0.42 of cases.
- `S4|synth-20|B30|budget_drop` (deadline 7): static 0.425 vs adapt 0.205, diff -0.220 [-0.275, -0.165]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 110.0 vs 197.0 min, and its learners' goal ever reached theta 0.70 in 0.20 vs 0.42 of cases.
- `S4|synth-20|B30|missed_2days` (deadline 7): static 0.425 vs adapt 0.205, diff -0.220 [-0.275, -0.165]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 143.3 vs 142.0 min, and its learners' goal ever reached theta 0.70 in 0.20 vs 0.42 of cases.
- `S4|synth-20|B30|budget_crash` (deadline 7): static 0.425 vs adapt 0.205, diff -0.220 [-0.275, -0.165]. Static broke prerequisite order for 200/200 learners to reach the goal's exercises; adapt (0 violations) waited for evidence on the prerequisites, used 50.4 vs 197.0 min, and its learners' goal ever reached theta 0.70 in 0.20 vs 0.42 of cases.

### E4: cells where bisect_confirm loses to sweep (18)

- `S0|4-node`: all-required -0.040 [-0.070, -0.015]: bisection confirmed prerequisites at the diagnostic (false-pass rate 0.60) and skipped them, studying 37.8 vs 44.3 min. Goal mastery +0.070 [+0.025, +0.120].
- `S0|synth-20`: total minutes +14.52 [+10.77, +17.98]: bisection asked 15.0 vs 3.1 diagnostic items (35.7 vs 7.8 min) and saved only 13.4 study min. Goal mastery +0.130 [+0.080, +0.180].
- `S0|synth-20-x10`: total minutes +4.38 [+0.10, +8.70]: bisection asked 13.6 vs 2.9 diagnostic items (26.1 vs 5.4 min) and saved only 16.3 study min. Goal mastery +0.100 [+0.050, +0.145].
- `S1|synth-20`: total minutes +22.18 [+19.42, +24.59]: bisection asked 15.0 vs 3.1 diagnostic items (35.7 vs 7.8 min) and saved only 5.7 study min. Goal mastery +0.005 [+0.000, +0.015].
- `S1|synth-20-x10`: total minutes +12.64 [+9.09, +16.16]: bisection asked 13.6 vs 2.9 diagnostic items (26.1 vs 5.4 min) and saved only 8.1 study min. Goal mastery +0.015 [+0.000, +0.035].
- `S2|4-node`: all-required -0.085 [-0.130, -0.045]: bisection confirmed prerequisites at the diagnostic (false-pass rate 0.69) and skipped them, studying 33.6 vs 41.9 min. Goal mastery -0.015 [-0.060, +0.030].
- `S2|8-node`: all-required -0.075 [-0.115, -0.035]: bisection confirmed prerequisites at the diagnostic (false-pass rate 0.66) and skipped them, studying 59.9 vs 72.9 min. Goal mastery +0.090 [+0.040, +0.145].
- `S2|8node_x10`: all-required -0.040 [-0.075, -0.010]: bisection confirmed prerequisites at the diagnostic (false-pass rate 0.66) and skipped them, studying 58.8 vs 69.0 min. Goal mastery +0.025 [-0.015, +0.065].
- `S2|synth-20`: all-required -0.030 [-0.060, -0.005]: bisection confirmed prerequisites at the diagnostic (false-pass rate 0.66) and skipped them, studying 126.3 vs 150.0 min. Goal mastery +0.180 [+0.130, +0.235].
- `S2|synth-20-x10`: all-required -0.055 [-0.095, -0.015]: bisection confirmed prerequisites at the diagnostic (false-pass rate 0.63) and skipped them, studying 120.6 vs 144.8 min. Goal mastery +0.080 [+0.035, +0.125].
- `S3|synth-20`: total minutes +17.34 [+13.99, +20.48]: bisection asked 15.0 vs 3.1 diagnostic items (35.7 vs 7.8 min) and saved only 10.5 study min. Goal mastery +0.035 [+0.010, +0.060].
- `S3|synth-20-x10`: total minutes +7.34 [+3.15, +11.46]: bisection asked 13.6 vs 2.9 diagnostic items (26.1 vs 5.4 min) and saved only 13.4 study min. Goal mastery +0.025 [+0.005, +0.050].
- `S4|4-node`: total minutes +3.50 [+2.11, +4.88]: bisection asked 5.1 vs 2.5 diagnostic items (9.5 vs 4.5 min) and saved only 1.5 study min; all-required -0.045 [-0.080, -0.010]: bisection confirmed prerequisites at the diagnostic (false-pass rate 0.27) and skipped them, studying 50.0 vs 51.5 min. Goal mastery +0.020 [-0.020, +0.060].
- `S4|8-node`: total minutes +8.12 [+7.33, +8.82]: bisection asked 6.8 vs 2.7 diagnostic items (12.6 vs 4.8 min) and saved only -0.3 study min. Goal mastery +0.010 [-0.010, +0.030].
- `S4|8node_x10`: total minutes +8.24 [+7.23, +9.17]: bisection asked 6.6 vs 2.5 diagnostic items (12.8 vs 4.7 min) and saved only -0.1 study min. Goal mastery +0.005 [-0.025, +0.035].
- `S4|synth-20`: total minutes +26.62 [+25.68, +27.55]: bisection asked 13.6 vs 2.6 diagnostic items (33.0 vs 7.1 min) and saved only -0.7 study min. Goal mastery +0.005 [+0.000, +0.015].
- `S4|synth-20-x10`: total minutes +19.32 [+18.43, +20.21]: bisection asked 12.1 vs 2.6 diagnostic items (23.4 vs 4.9 min) and saved only -0.8 study min. Goal mastery +0.000 [+0.000, +0.000].
- `S4-assist09|synth-20`: total minutes +14.82 [+10.46, +18.80]: bisection asked 15.0 vs 3.1 diagnostic items (35.5 vs 8.1 min) and saved only 12.6 study min. Goal mastery +0.055 [+0.025, +0.090].

### E5: cells where pure CP-SAT loses to greedy (56)

- `S0|4-node|B10|calm`: minutes +0.45 [+0.20, +0.72] (39.6 vs 39.2); both first plans finish on day 3; CP-SAT's order leads to more exercise attempts (1972 vs 1951 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S0|4-node|B15|missed_day`: minutes +0.61 [+0.30, +0.94] (38.2 vs 37.6); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (1898 vs 1868 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.010 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S0|4-node|B15|deadline_cut`: minutes +0.61 [+0.30, +0.94] (38.2 vs 37.6); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (1898 vs 1868 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.010 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S0|8-node|B10|calm`: minutes +2.47 [+1.98, +2.98] (69.6 vs 67.1); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3394 vs 3287 over 200 learners), i.e. more retries. Goal mastery +0.010, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S0|8-node|B10|missed_day`: minutes +2.13 [+1.67, +2.63] (62.2 vs 60.1); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3043 vs 2957 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S0|8-node|B10|deadline_cut`: minutes +2.13 [+1.67, +2.63] (62.2 vs 60.1); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3043 vs 2957 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S0|8node_x10|B10|calm`: minutes +1.07 [+0.61, +1.55] (65.1 vs 64.0); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3580 vs 3516 over 200 learners), i.e. more retries. Goal mastery +0.015, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S0|8node_x10|B10|missed_day`: minutes +1.03 [+0.60, +1.47] (59.7 vs 58.7); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3297 vs 3239 over 200 learners), i.e. more retries. Goal mastery +0.010, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S0|8node_x10|B10|deadline_cut`: minutes +1.03 [+0.60, +1.47] (59.7 vs 58.7); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3297 vs 3239 over 200 learners), i.e. more retries. Goal mastery +0.010, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S1|4-node|B10|calm`: minutes +0.51 [+0.26, +0.80] (40.4 vs 39.9); both first plans finish on day 3; CP-SAT's order leads to more exercise attempts (1980 vs 1959 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S1|4-node|B15|missed_day`: minutes +0.62 [+0.33, +0.93] (38.9 vs 38.3); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (1908 vs 1877 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S1|4-node|B15|deadline_cut`: minutes +0.62 [+0.33, +0.93] (38.9 vs 38.3); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (1908 vs 1877 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S1|8-node|B10|calm`: minutes +2.67 [+2.17, +3.17] (70.1 vs 67.5); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3336 vs 3234 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S1|8-node|B10|missed_day`: minutes +2.12 [+1.64, +2.60] (62.4 vs 60.3); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (2981 vs 2892 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S1|8-node|B10|deadline_cut`: minutes +2.12 [+1.64, +2.60] (62.4 vs 60.3); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (2981 vs 2892 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S1|8node_x10|B10|calm`: minutes +1.09 [+0.61, +1.57] (66.5 vs 65.4); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3573 vs 3509 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S1|8node_x10|B10|missed_day`: minutes +1.09 [+0.68, +1.52] (60.4 vs 59.3); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3268 vs 3213 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S1|8node_x10|B10|deadline_cut`: minutes +1.09 [+0.68, +1.52] (60.4 vs 59.3); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3268 vs 3213 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|4-node|B10|calm`: minutes +0.26 [+0.07, +0.48] (39.2 vs 39.0); both first plans finish on day 3; CP-SAT's order leads to more exercise attempts (1973 vs 1959 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|4-node|B15|calm`: minutes +0.38 [+0.14, +0.63] (45.0 vs 44.6); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (2219 vs 2204 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|4-node|B15|missed_day`: minutes +0.24 [+0.01, +0.51] (37.6 vs 37.3); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (1893 vs 1877 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|4-node|B15|deadline_cut`: minutes +0.24 [+0.01, +0.51] (37.6 vs 37.3); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (1893 vs 1877 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|8-node|B10|calm`: minutes +2.54 [+2.02, +3.06] (68.5 vs 65.9); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3360 vs 3239 over 200 learners), i.e. more retries. Goal mastery +0.020, all-required +0.010 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|8-node|B10|missed_day`: minutes +2.37 [+1.93, +2.83] (61.8 vs 59.4); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3042 vs 2926 over 200 learners), i.e. more retries. Goal mastery +0.010, all-required +0.010 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|8-node|B10|deadline_cut`: minutes +2.37 [+1.93, +2.83] (61.8 vs 59.4); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3042 vs 2926 over 200 learners), i.e. more retries. Goal mastery +0.010, all-required +0.010 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|8-node|B15|calm`: minutes +0.66 [+0.32, +1.01] (75.3 vs 74.6); both first plans finish on day 4; CP-SAT's order leads to more exercise attempts (3671 vs 3640 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|8-node|B15|missed_day`: minutes +0.53 [+0.13, +0.94] (65.3 vs 64.8); both first plans finish on day 4; CP-SAT's order leads to more exercise attempts (3218 vs 3196 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|8-node|B15|deadline_cut`: minutes +0.53 [+0.13, +0.94] (65.3 vs 64.8); both first plans finish on day 4; CP-SAT's order leads to more exercise attempts (3218 vs 3196 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|8node_x10|B10|calm`: minutes +1.15 [+0.67, +1.68] (63.9 vs 62.7); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3541 vs 3476 over 200 learners), i.e. more retries. Goal mastery +0.025, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|8node_x10|B10|missed_day`: minutes +1.36 [+0.84, +1.84] (58.8 vs 57.5); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3267 vs 3195 over 200 learners), i.e. more retries. Goal mastery +0.015, all-required +0.010 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S2|8node_x10|B10|deadline_cut`: minutes +1.36 [+0.84, +1.84] (58.8 vs 57.5); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3267 vs 3195 over 200 learners), i.e. more retries. Goal mastery +0.015, all-required +0.010 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S3|4-node|B10|calm`: minutes +0.41 [+0.17, +0.66] (40.1 vs 39.7); both first plans finish on day 3; CP-SAT's order leads to more exercise attempts (1985 vs 1960 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S3|4-node|B15|calm`: minutes +0.40 [+0.10, +0.71] (47.6 vs 47.2); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (2306 vs 2290 over 200 learners), i.e. more retries. Goal mastery +0.010, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S3|4-node|B15|missed_day`: minutes +0.60 [+0.30, +0.92] (38.5 vs 37.9); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (1907 vs 1880 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.005 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S3|4-node|B15|deadline_cut`: minutes +0.59 [+0.28, +0.92] (38.3 vs 37.7); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (1900 vs 1874 over 200 learners), i.e. more retries. Goal mastery -0.005, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S3|8-node|B10|calm`: minutes +2.13 [+1.62, +2.68] (70.0 vs 67.9); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3355 vs 3258 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S3|8-node|B10|missed_day`: minutes +2.09 [+1.61, +2.57] (62.5 vs 60.5); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (2985 vs 2888 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S3|8-node|B10|deadline_cut`: minutes +1.93 [+1.44, +2.42] (62.4 vs 60.5); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (2991 vs 2907 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S3|8node_x10|B10|calm`: minutes +1.33 [+0.79, +1.90] (66.7 vs 65.4); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3612 vs 3534 over 200 learners), i.e. more retries. Goal mastery +0.015, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S3|8node_x10|B10|missed_day`: minutes +1.18 [+0.69, +1.64] (60.7 vs 59.5); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3291 vs 3238 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S3|8node_x10|B10|deadline_cut`: minutes +1.30 [+0.81, +1.79] (60.7 vs 59.4); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3299 vs 3233 over 200 learners), i.e. more retries. Goal mastery +0.005, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|4-node|B10|missed_day`: minutes +0.32 [+0.14, +0.51] (35.2 vs 34.9); both first plans finish on day 3; CP-SAT's order leads to more exercise attempts (1606 vs 1582 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|4-node|B10|deadline_cut`: minutes +0.32 [+0.14, +0.51] (35.2 vs 34.9); both first plans finish on day 3; CP-SAT's order leads to more exercise attempts (1606 vs 1582 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|4-node|B15|calm`: minutes +1.00 [+0.62, +1.38] (53.1 vs 52.1); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (2359 vs 2313 over 200 learners), i.e. more retries. Goal mastery +0.015, all-required +0.015 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|4-node|B15|missed_day`: minutes +1.00 [+0.63, +1.39] (40.6 vs 39.6); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (1827 vs 1777 over 200 learners), i.e. more retries. Goal mastery +0.010, all-required +0.010 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|4-node|B15|deadline_cut`: minutes +1.00 [+0.63, +1.39] (40.6 vs 39.6); both first plans finish on day 2; CP-SAT's order leads to more exercise attempts (1827 vs 1777 over 200 learners), i.e. more retries. Goal mastery +0.010, all-required +0.010 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|8-node|B10|calm`: minutes +2.33 [+1.81, +2.84] (72.1 vs 69.8); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3176 vs 3072 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|8-node|B10|missed_day`: minutes +2.10 [+1.63, +2.55] (63.8 vs 61.7); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (2826 vs 2748 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|8-node|B10|deadline_cut`: minutes +2.10 [+1.63, +2.55] (63.8 vs 61.7); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (2826 vs 2748 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|8-node|B15|calm`: minutes +1.32 [+0.70, +1.93] (81.6 vs 80.2); both first plans finish on day 4; CP-SAT's order leads to more exercise attempts (3564 vs 3486 over 200 learners), i.e. more retries. Goal mastery +0.010, all-required +0.005 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|8-node|B15|missed_day`: minutes +1.39 [+0.89, +1.88] (68.5 vs 67.1); both first plans finish on day 4; CP-SAT's order leads to more exercise attempts (3040 vs 2960 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|8-node|B15|deadline_cut`: minutes +1.39 [+0.89, +1.88] (68.5 vs 67.1); both first plans finish on day 4; CP-SAT's order leads to more exercise attempts (3040 vs 2960 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|8node_x10|B10|calm`: minutes +0.98 [+0.49, +1.49] (71.7 vs 70.7); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3402 vs 3317 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.005 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|8node_x10|B10|missed_day`: minutes +0.78 [+0.32, +1.25] (63.7 vs 62.9); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3000 vs 2966 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S4|8node_x10|B10|deadline_cut`: minutes +0.78 [+0.32, +1.25] (63.7 vs 62.9); CP-SAT's first plan finishes on day 5 vs greedy's 6; CP-SAT's order leads to more exercise attempts (3000 vs 2966 over 200 learners), i.e. more retries. Goal mastery +0.000, all-required +0.000 (CP-SAT not worse); the extra minutes buy no measurable gain.
- `S0|8-node|B15|calm|confirm`: goal mastery -0.020 [-0.040, -0.005] (0.480 vs 0.500). The diagnostic is identical (7.46 items in both), so the gap comes from plan order after it: CP-SAT studied 64.1 vs 64.8 min; a narrow loss (CI upper end -0.005) in 1 of 56 listed contrasts.

## Rename (after the final study, 2026-11-21)

The old evaluation harness (`experiments/`: Week 6 – Plan 4.5 runners and `experiments/results/`)
was deleted from the working tree and this folder, `experiments_v2/`, was renamed `experiments/`
(D102). No experiment was re-run. The results JSONs were not touched: they still name
`experiments_v2/…` paths and carry the harness hash they were produced with (`928630…` for E2 and
E3, `240e95fd…` for the rest). The harness hash changed only because harness files were edited for
the rename (paths, imports, one deleted test); `tree_hash` hashes paths relative to the folder, so
the folder name itself is not part of it. The earlier sections of this file are left as written.

Archive of the old folder (outside the repository, and in git history):
`../AdaptEngine_archive/experiments_old_20261121.tgz`, sha256
`4a64554d6c7432e2b2960c7a240d01e2a39942c7dc183cd4f4d22d895fdfdc13`.

| Item | Before (R0) | After |
|---|---|---|
| Code hash | `9a40c4d822397fa019d69ba64ddc7ab58d5baf8fe04ed0d090b1dfebfe66e6ef` | same |
| Config hash | `1e26bd7de81c8f56a6e998b33ee531f59470681d78ff71affd05362a910e7b11` | same |
| Harness hash | `240e95fd4c2cf5a8c1751d8cac5ae555bfd8f74a7be51e35092e57aae68c75d3` | `752a73171c093a402b96ce540b132106b381fb7836ee1c6b956d55cefd65f5be` (files edited; results keep the old one; was `b40baaf5…` until the `make exp-figures` docstring fix in `report/style.py` and `report/render_figures.py`) |
| `make check` | 464 passed, 1 skipped, coverage 92.84 % | 403 passed, 0 skipped, coverage 92.64 % (gate 84 %) |
| API tests | 27 passed | 23 passed |
| Study tests | 58 passed | 57 passed |
| `make exp-smoke` | – | all 6 runners pass |
| Web build, Playwright | – | build ok, 11 passed |
| `ruff check .`, `ruff format --check .` | clean | clean |
| Results JSON sha256 (7 files) | recorded | identical |
| Tables / CSVs | – | differ only in the source path (`experiments_v2/results/…` → `experiments/results/…`) and the generator header |
| Figures (20 files) | – | byte-identical |

**Deleted test files** (tests of code that no longer exists): `tests/test_f1_grid.py` (5),
`test_f2_grid.py` (3), `test_f3_grid.py` (5), `test_f5_baseline.py` (2), `test_evaluation.py` (1),
`test_arms.py` (3), `test_sim.py` (9), `test_stats.py` (4), `test_diag_eval.py` (5),
`test_eval_checks.py` (5), `test_synth.py` (5), `test_fit_bkt.py` (8; tested the old
`experiments/fit_bkt.py`, found by `make check` in R8), and `experiments/tests/test_independence.py`
(1; V2-TC2 retired). Counts are test functions; parametrised cases add more.

**Ported test files** (every assertion kept): `tests/test_bisection.py` (simulator from
`core/simulator.py`; synthetic curriculum from `core/curricula.py`), `test_confirmation.py`
(`core/audit.executed_violations`), `test_cpsat_closed_loop.py` (`core/scenarios`, `core/episode`,
`core/audit`), `test_cpsat_planner.py` (`core/audit.budget_violations`, `plan_violations`),
`test_knowledge_space.py` (`core/curricula.generate_synthetic`, written to a temp folder),
`test_planner.py` (private `_trace_coverage`, replacing `experiments/stats.py::audit_plan_trace_coverage`),
`test_w7_planner.py` (`core/scenarios`, `core/episode`).

**Removed assertions:** `tests/test_profiles.py::test_ct_profile_matches_results_file`: the three
assertions that compared `config/fitted_ct.json` with the deleted `experiments/results/bkt_fit_ct.json`
(the checks on the profile's own fields stay).

**Removed pin parts** (`scripts/record_pins.py`, `tests/test_baseline_pins.py`; pin JSON files
untouched): `diag_matrix_S0` (computed by the old `run_diag_matrix.run_world` with the W7 arms; the
new harness has no equivalent) and `episode` (the old `arms.run_episode` record layout; the new
`run_episode` returns different fields), including the dependent assertion
`default_pins["episode"] == baseline["episode"]`. The `diagnostic` part was ported to the new
simulator and matches both pin files exactly; `plans`, `config` and `poc_demo` are unchanged.

**Removed API endpoints** (`frontend/api/app.py`): `/api/simulate`, `/api/evaluation` (with
`_compact`, `RESULTS_DIR` and the schemas `SimulateRequest`, `SimEpisode`, `SimulateOut`,
`EvaluationFile`, `EvaluationOut`), and their tests `test_simulate`,
`test_evaluation_tolerates_missing_and_broken_files`, `test_simulate_default_unchanged`,
`test_simulate_diagnostics_compare` (helpers `_direct_episodes`, `_same`). `/api/health` now takes the
code hash from `experiments.core.provenance`. `frontend/web/openapi.json` and `src/api/schema.d.ts`
were regenerated (`npm run gen:types`).

**Removed Makefile targets and scripts:** `eval`, `eval-quick`, `w6` (and their place in `all`);
`scripts/run_w6.py` and `scripts/verify_clean_checkout.sh` (both ran the old harness; deleted at the
owner's choice). `v2-*` targets renamed `exp-test`, `exp-smoke`, `exp-run`, `exp-report`,
`exp-figures`.

## Test files moved into unit/integration/tooling (2026-11-21)

`experiments/tests/` is now `unit/` (simulator, scenarios, audit, metrics, diagnostics, realdata),
`integration/` (episode, runners_smoke, determinism) and `tooling/` (report, prereg_guard,
results_schema). No test or harness logic changed: the only edits are two imports of
`test_runners_smoke` (now `experiments.tests.integration.test_runners_smoke`) and the depth of the
`REPORT` path in `tooling/test_report.py`. 57 tests collected before and after, with identical IDs;
`make exp-test` 57 passed. Code hash unchanged (`9a40c4d8…`). Harness hash
`752a73171c093a402b96ce540b132106b381fb7836ee1c6b956d55cefd65f5be` →
`68b8ee80ecac0694c328cd5f339011ad76cc9c7dc468fffee69882b73423b68c` (it includes relative file
paths). Results JSONs are not touched and keep the hash they were produced with.
