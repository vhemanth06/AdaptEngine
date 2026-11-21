> Archived (21 Nov 2026). Historical record of the project at the time it was written; paths, commands and numbers may no longer match the repository. Current documentation: [docs/README.md](../../README.md).

# Plan 1 notes: F5 Phase A, `8node_x10` (10 exercises per concept)

Baseline: Plans 0 and 0.5 committed (`make check` 241 passed, 9 API tests passed). Recorded
2026-11-20.

## What was added

| Task | Files |
|---|---|
| F5-T1 catalogue | `data/curriculum/curriculum_8node_x10.json` (byte copy of `curriculum_8node.json`), `data/curriculum/activities_8node_x10.json` (40 original activities unchanged + 48 new exercises) |
| F5-T2 content | `data/content/content_8node_x10.json` (40 `content_8node.json` entries verbatim + 48 new exercises, 42 of them marked `"verify": "output"`) |
| F5-T3 checker | `scripts/check_content.py` |
| F5-T5 synth option | `experiments/synth_curriculum.py` (`exercises_per_concept`, `parse_synth_name`), `experiments/run_w7_grid.py::curriculum_paths` (accepts `8-node-x10` and `synth-N-x10`) |
| F5-T6 sanity runner | `experiments/run_f5_baseline.py`, draft `docs/preregistration/F5_2026-11-20.md` |
| Tests | `tests/test_curriculum_x10.py`, `tests/test_check_content.py`, `tests/test_synth.py`, `tests/test_f5_baseline.py`; `tests/test_loader_review_gate.py` gains `PENDING_REVIEW` |
| F5-T12 docs | `data/content/README.md`, `docs/data_manifest.md`, `docs/DECISIONS.md` (D80–D87), `docs/TRACEABILITY.md` (F5-TC1–TC4, TC6, TC7), `README.md` |

New exercises per concept: `E-Cn-0.1`, `0.3` (easy, 1 min), `0.45`, `0.55` (medium, 2 min), `0.7`,
`0.9` (hard, 2 min). With the existing 0.2, 0.4, 0.6, 0.8 this gives 3 easy / 4 medium / 3 hard
under D6. Within each concept, the 10 correct answers are spread 3/3/2/2 over the four positions.
New items stay inside each concept's prerequisites (for example, no loops in C6 items, no
comprehensions in C5 or C8 items).

File hashes (sha256) at the end of Plan 1:

| File | sha256 |
|---|---|
| `curriculum_8node_x10.json` | `f057fe5b41f737d4c660bcabc012780269898c65aa4d0b263d57541ba38adfd7` (same as `curriculum_8node.json`) |
| `activities_8node_x10.json` | `13f309a4362099f00f379b76777a217d90c1be6f031f34406d516f03e12ed8d4` |
| `content_8node_x10.json` | `533a5dd4996dc14c62afa98117fab7c53494af1ba499a6c7ebc8f4b264001784` |

## Unchanged (F5-TC1)

- Original data files match their `data/review_manifest.json` hashes.
- `generate_synthetic_curriculum(n)` for n = 8, 20, 50 has the same sha256 as before Plan 1
  (pinned in `tests/test_synth.py`).
- No `EngineConfig` field was added: `config_hash(DEFAULT_CONFIG)` stays
  `b450f59cc11c1a0179f8a41d864a648166652bbd4efb2a4ca141eac2070afcee`.
- `tests/test_baseline_pins.py` passes unchanged. No engine code changed.
- `experiments/run_w7_grid.py` produces the same engines for `4-node`, `8-node` and `synth-20`
  (same paths, seed and review flags); `curriculum_paths` now raises for an unknown name instead of
  silently returning synth-20.

## Checker calibration

The first near-duplicate rule (prompt similarity ≥ 0.90 alone) flagged four pairs, including an
existing 8-node pair (`E-C3-0.2` / `E-C3-0.4`, 0.93). These are short "what does this print"
prompts that share boilerplate but ask different things. The rule now also requires the same
correct answer. Exact duplicate prompts are always flagged. The highest remaining similarity in
`content_8node_x10.json` is 0.94 (`E-C1-0.3` / `E-C1-0.4`, answers `2.5` and `3`).

## After Plan 1

| Item | Value |
|---|---|
| `make check` | ruff clean; **272 passed**; coverage **90.74%** |
| `pytest frontend/api/tests` | **9 passed** |
| `scripts/check_content.py` | `content_8node.json` OK; `content_8node_x10.json --spread 3,4,3` OK (42 snippets verified) |

## Plan 1.5: Plan 1's open steps, done (2026-11-20)

Plan 1.5 finished the steps Plan 1 left for the owner (ground rule 11). Engine behaviour is
unchanged.

| Task | Done |
|---|---|
| P1.5-T1 review-gate gap | Before, `loader.py::_check_review_gate` rejected only the reviewer `"AI"`, so a `PENDING_HUMAN_REVIEW` entry with a correct hash would have unlocked a file. It is now rejected as "pending human review" (case-insensitive, spaces ignored). `scripts/record_review.py` gained `--pending`, `--ai-assisted` and `--manifest` |
| P1.5-T2 AI review (F5-T4 under D88) | `docs/content_reviews/8node_x10_ai_review.md`: 48 rows, 47 pass and 1 fixed. In `E-C2-0.1` the distractor `return` also ends a loop inside a function, so it was replaced with `end`. 42/42 runnable answers match their code's output. The checker passes with `--spread 3,4,3` |
| P1.5-T3 pending entries | The three `8node_x10` files are recorded as `PENDING_HUMAN_REVIEW`, `ai_assisted: true`, and the curriculum entry has `edges_reviewed: false`. The tests read the pending set from the manifest. The demo API lists `8node_x10` as unreviewed, with "pending human review" |
| P1.5-T4 decisions | D80–D86 adopted (D83 amended by D88); D88 added |
| P1.5-T5 pre-registration | `docs/preregistration/F5_2026-11-20.md` registered at 2026-11-19T23:39:12Z (UTC), code hash `4129b2bf…`, before the run |
| P1.5-T6 full run | `experiments/results/f5_baseline.json` (full design: S0–S4, 250 diagnostics and 2 × 200 episodes per curriculum and world; about 35 s CPU). Its `code_hash` equals the registered one, and it carries the D88 label |

Changed file hashes (sha256):

| File | Plan 1 | Plan 1.5 |
|---|---|---|
| `content_8node_x10.json` | `533a5dd4…` | `96a2db6abade3df691ed254b04253c66a35086f7013c36553d18d47f9d2848fc` (`E-C2-0.1` fix) |
| `data/review_manifest.json` | `ba1c7438…` | `ea3ef7236a33dd330933c5fbd83b8a20fd4a76a6fe15ec6cb6413a748bdb2bc4` (3 pending entries; `curriculum_8node_x10.json` records `edges_reviewed: false`, D88) |

Unchanged: `curriculum_8node_x10.json`, `activities_8node_x10.json`, both pin files,
`config_hash(DEFAULT_CONFIG)` = `b450f59c…`, and every other manifest entry (each original data
file still matches its manifest hash).

### F5-T6 results: 8-node vs 8-node-x10 (baseline engine, `DEFAULT_CONFIG`)

Content: AI-checked, human review pending (D88); `8node_x10` loaded with `allow_unreviewed=True`.
Paired difference x10 − 8-node with 95% bootstrap CI. The diagnostic is identical in S0, S1 and S3,
because those worlds differ only in learning dynamics (S1 prerequisite-gated gains, S3 forgetting),
not in starting knowledge. The same holds in the W7 diagnostic matrix, which ran only S0, S2 and S4.

| World | Diag Brier 8 / x10 (Δ, CI) | Items 8 / x10 (Δ, CI) |
|---|---|---|
| S0, S1, S3 | 0.2038 / 0.2112 (+0.0073, [−0.0047, 0.0193]) | 3.03 / 2.85 (−0.176, [−0.372, 0.024]) |
| S2 | 0.1648 / 0.1611 (−0.0038, [−0.0162, 0.0083]) | 3.02 / 2.82 (−0.208, [−0.404, −0.008]) |
| S4 | 0.1293 / 0.1276 (−0.0017, [−0.0078, 0.0044]) | 2.64 / 2.59 (−0.048, [−0.164, 0.072]) |

| World | Scenario | Goal mastery 8 / x10 (Δ, CI) | Minutes 8 / x10 | Executed violations 8 / x10 |
|---|---|---|---|---|
| S0 | calm | 0.365 / 0.425 (+0.060, [0.020, 0.105]) | 76.6 / 71.9 | 0 / 0 |
| S0 | missed_day | 0.330 / 0.365 (+0.035, [−0.005, 0.070]) | 65.8 / 64.3 | 0 / 0 |
| S1 | calm | 0.315 / 0.325 (+0.010, [−0.010, 0.030]) | 78.2 / 74.2 | 0 / 0 |
| S1 | missed_day | 0.305 / 0.320 (+0.015, [−0.010, 0.040]) | 65.9 / 65.2 | 0 / 0 |
| S2 | calm | 0.370 / 0.435 (+0.065, [0.015, 0.120]) | 74.6 / 70.0 | 0 / 0 |
| S2 | missed_day | 0.280 / 0.345 (+0.065, [0.020, 0.110]) | 64.8 / 63.3 | 0 / 0 |
| S3 | calm | 0.080 / 0.145 (+0.065, [0.020, 0.110]) | 77.4 / 73.7 | 0 / 0 |
| S3 | missed_day | 0.040 / 0.065 (+0.025, [−0.010, 0.060]) | 65.9 / 65.4 | 0 / 0 |
| S4 | calm | 0.235 / 0.260 (+0.025, [0.000, 0.050]) | 80.2 / 81.2 | 0 / 0 |
| S4 | missed_day | 0.225 / 0.230 (+0.005, [−0.010, 0.025]) | 67.1 / 68.2 | 0 / 0 |

Pre-registered expectations:

- **E1 (0 executed violations):** held in every cell, for both curricula.
- **E2 (items within `n_max = 6`):** held; the mean is 2.6–3.0 items, and `n_max` caps every run.
- **E3 (no predicted direction; CIs that exclude 0 explained):**
  - Goal mastery is higher on x10 in S0 calm, S2 calm, S2 missed_day and S3 calm. A likely reason:
    with 10 exercises the closed loop repeats items less often (D41), and it can pick items closer
    to the target success rate. This is an untested explanation, not a measured cause.
  - Diagnostic items are fewer on x10 in S2 (−0.21). A likely reason: the finer difficulty grid
    gives the EIG item choice more informative first items, so the entropy stop comes sooner. Also
    untested. The Brier differences all include 0.

## After Plan 1.5

| Item | Value |
|---|---|
| `make check` | ruff clean; **283 passed**; coverage **90.75%** (272 before; 2 test ids renamed, 13 new, including `test_pending_curricula_record_edges_not_reviewed`) |
| `pytest frontend/api/tests` | **10 passed** (1 new) |
| `config_hash(DEFAULT_CONFIG)` | `b450f59c…` (unchanged) |
| Code hash (`src/**/*.py`) | `4129b2bf…` (was `d887b5f1…`; only `curriculum/loader.py` changed) |
