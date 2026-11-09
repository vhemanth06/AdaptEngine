# AdaptEngine — Week 7 Report (Group 15)

**Version:** 0.3.0 · **Date:** 9 November 2026 · **Evidence file:** `docs/WEEK7_REPORT_NOTES.md` (every number below appears there with its command or results file) · **Full tables:** `docs/WEEK7_RESULTS.md`

Week 7 theme: *make the evaluation honest, close the loop, stress-test, then demo.* Assignment-2 W7 items covered: (1) mismatched simulator variants and stress cases, (2) sensitivity over heuristic parameters, (3) measured improvements with limits. The optional ranking policy is deferred to W8.

---

## 1. Summary of changes and why

| Change | W6 defect it fixes | Notes ref. |
|---|---|---|
| Executed-state prerequisite audit (primary safety metric, D46) | W6 audit assumed every answer was correct, hiding 183 (adapt) / 640 (static) violations in calm | T1.1 |
| Closed loop: `Engine.next_activities` (replan each day and after every wrong answer), mid-day budget, exercise repeats (D41), best-effort plans (D42) | The harness never replanned after outcomes; learners sat idle (50 idle days in calm) | T2.1–T2.4 |
| Reachable spaced review: configurable half-life, maintenance tier, single recall implementation (D43) | Reviews could never fire; adapt = no_review everywhere | T2.6 |
| Diagnostic scored with Brier/log-loss/AUC vs binary truth; flags (min-k, soft pruning, frontier, population prior); pre-registered selection rule applied as written (D44) | MAE of p against θ was an improper metric; W6 overrode its own selection rule | T3.1–T3.3 |
| Simulator worlds S0–S4 and a pre-registered stress grid (D47) | One simulator that rewards raw minutes; results interpreted after the fact | T4.1–T4.4 |
| Exactly-one trace audit; oracle records superseding greedy ones | 45 SELECTED records for 21 activities on the oracle path | T1.4 |
| Real pyBKT parity, BKT fits on ASSISTments 2009 and Cognitive Tutor (D48) | Parity test never used the library; parameters never fitted | T1.5, WP7 |
| Precomputed graph indices | `descendant_count` recomputed by NetworkX in the scheduler's inner loop | T6.1 |
| Demo frontend (FastAPI adapter + React; engine is the sole decision source, D45) | — | WP8 |

## 2. Corrections to W6

| W6 claim | Corrected |
|---|---|
| 0 prerequisite violations for adapt | 183 (calm), 152 (missed_day) executed violations on W6 code; **0 in W7** |
| static 0 violations in calm | 640 executed violations (87/100 learners) |
| Adaptive diagnostic quality (MAE) | Brier vs truth 0.2425, worse than using no diagnostic (0.2080) |
| "Assessed-only parity" | 0.3852 vs fixed@n 0.2555 — not parity |
| Diagnostic defaults h_stop 0.35, cap 2 | Code was h_stop 0.50, cap 3, N 8 (W7 rule: population prior 0.24, cap 2, N 6) |
| Items ≈ 2.7 | 2.96 |
| Planner BKT "T 0.10, G 0.15, S 0.15" | p0 0.20, g(d) = 0.30(1 − d), s(d) = 0.05 + 0.25d, T_ex 0.05, T_lesson 0.20 |
| Nominal simulator half-life 30 days | Nominal simulator has no forgetting (30 was the planner's value) |
| 100% trace coverage on the oracle path | Duplicated/stale records (fixed, T1.4) |
| Results artifact = 100 seeds | Tests had overwritten it with a 5-seed run (fixed, T1.3) |
| Decision IDs D36/D38/D40 | Mismatched with `DECISIONS.md`; D19 never existed (now recorded as reserved) |
| TC6.x in `tests/test_replanner.py` | Tests live in `tests/test_w5.py` |

## 3. Closed-loop results (S0–S4 matrix)

Pre-registered (`docs/preregistration/W7_T4.1_2026-11-08.md`): 5 worlds × 3 curricula × 4 budgets × 8 scenarios (4 stress) × 5 arms, N = 200 paired learners per cell, headline N = 1000; 420 cells.

**H1 (safety).** The registered run *failed* H1: arms with spaced review still had executed violations (adapt 6192 summed over cells; no_review 0). Cause: due reviews and remediation bypassed the prerequisite gate (Defect 7). After two fixes, each with a regression test that fails on the previous code, the final grid has **0 executed violations for every adapt arm in all 420 cells**, against 1,649,720 for static and 1,229,249 for no_replan. Adapt also has 0 idle days (static 103,074, no_replan 150,429). All three runs are kept (`w7_grid_prereg.json`, `w7_grid_fix1.json`, `w7_grid.json`).

**H2 (headline, S1 prerequisite-gated world, 4-node, B=15, calm, N=1000).** Goal true-mastery 29.0% (adapt) vs 28.7% (static): Δ +0.003 [−0.008, +0.014] — parity, with 0 vs 7200 executed violations and all-required mastery 3.9% vs 1.8%. In S0 the same cell is −0.013 [−0.036, +0.010].

**Across all cells:** adapt is better than static on goal mastery in 35 cells, not significantly different in 226, worse in 159; on mastery of *all* required concepts it is better in 45 and worse in 21.

**Where adapt loses (T4.5).** (a) S0/S2 reward raw minutes on the goal whatever the learner's readiness; static and no_replan buy goal minutes with millions of violations. (b) After disruptions adapt rebuilds prerequisites first, so a 3–5-day horizon leaves fewer goal minutes. (c) In S4 (BKT world) adapt correctly stops practising concepts it has mastered, so goal-only mastery is lower in calm (−0.150) while all-required mastery is higher (+0.125); with a 21-day horizon it wins by +0.405. (d) Goal θ at equal minutes is negative in most cells: safety costs goal minutes.

**H3 (spaced review, fast forgetter, 21 days, h = 7).** Review changes the outcome in 32 of 60 cells: positive in 11 (e.g. 8-node +0.041), negative in 21 (synth-20, where reviews crowd out new content).

**Expected-workload projection** is worse than the optimistic projection in 113 cells and better in 9.

## 4. Diagnostic matrix and calibration

Held-out Brier vs 1[θ ≥ 0.70] (lower is better): prior-only 0.2080, W6 diagnostic 0.2425, pre-registered winner 0.2324 (Δ vs W6 −0.0101 [−0.0210, −0.0015]). Across worlds (250 learners): no BKT diagnostic beats the prior in S0 or S2 (TC2.1's equal-budget clause is **not met** there; fixed-order at the same item count is better), all beat it in S4, where the R§7.4 recommendation (min 2 items, no pruning, frontier) reaches 0.0589 (AUC 0.945). A per-concept IRT CAT is best in S0; a global-ability CAT is best in S2 by AUC. The state-space diagnostic and fitted-sim parameters under-perform. Which diagnostic looks best depends on which world generated the data.

## 5. Sensitivity

Scans of θ, k, half-life, p0, T_lesson, recall and remediation thresholds, a θ×k factorial and alternative mastery criteria (S0/S1, 4-/8-node, N=200): the engine is insensitive to θ in 0.70–0.90, to the thresholds and to h ≥ 14; strict evidence (θ = 0.95: −6.5 points; 3-in-a-row: −12.5 points in S0 4-node) costs goal mastery in a fixed short horizon. Executed violations are 0 in every configuration. Tornado charts: `docs/figures/w7_tornado_*.png`.

## 6. Measured improvements

| Improvement | Before → after |
|---|---|
| Planning latency, identical plans (564/564) | synth-50 60.4 → 22.5 ms (2.69×); oracle cell 24.1 → 9.5 ms (2.55×) |
| Safety (4-node calm, executed violations) | 183 → 0 (static 640) |
| Calibration, held-out RMSE (fitted vs heuristic) | ASSISTments 0.4746 → 0.4414; CT 0.4952 → 0.4549; simulated S0 0.5716 → 0.4586 |
| Diagnostic Brier (S0 held-out) | 0.2425 → 0.2324 |

Limits: fitted parameters are not adopted as defaults (maths data; they hurt the diagnostic), and the diagnostic still does not beat the prior in S0/S2.

## 7. Real-data fitting and provenance

ASSISTments 2009 (297,016 answers, 81 skills) and Cognitive Tutor (15,935 rows, 9 KCs): fitted priors are high (0.74 / 0.63 vs the engine's 0.20), guess falls and slip rises with difficulty (hard-item slip ≈ 0.64 in both), 4.9% / 22.2% of per-skill fits are degenerate. Every simulator parameter now has a provenance entry (`EVALUATION_PROTOCOL.md` §8). Both datasets are maths, not Python: they set ranges, not values. CSEDM 2019 (Python) is deferred to W8 (download failed). An exploratory S4 world driven by the ASSISTments fit gives adapt = static on goal mastery in calm (86.0% each) with 0 vs 1335 violations.

## 8. Demo

`frontend/`: FastAPI adapter (9 endpoints, API plans equal direct engine calls) and a React app with setup, diagnostic, curriculum map, plan timeline, "Why?" trace panel, study mode, disruptions, autopilot and evaluation pages; deterministic demo mode; Playwright run of the 6-minute demo script passes. Run: `make demo-test` (see `frontend/README.md`). Demo content is AI-drafted and awaits human review.

## 9. Limitations and W8 plan

Synthetic evaluation; short horizons; post-hoc scheduler fix (all runs reported); diagnostic not better than the prior in IRT worlds; review effect mixed; reviewed-vs-not retention confounded by selection. W8: ranking policy (ZPDES bandit with logged propensities), Elo/HLR models, CP-SAT scheduler, CSEDM Python fit, longer-horizon evaluation, classroom pilot with the demo.

## 10. Traceability and reproducibility

All 23 TC IDs with test evidence: `docs/TRACEABILITY.md` (W7 changes: TC2.1 clause restored and reported as partly met; TC3.1 now verified for executed episodes; TC3.2 mid-day; TC4.1 library parity; TC7.1 exactly-one audit). Commands, seeds and code hashes: notes §14; each results file records its `code_hash` (SHA-256 over `src/**/*.py`) and timestamp; pre-registrations in `docs/preregistration/`.
