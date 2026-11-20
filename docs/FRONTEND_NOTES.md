# Plan FE notes: demo UI rebuilt for `redo` (D92–D95)

## FE-T0 baseline (2026-11-20, before any Plan FE change)

| Item | Value |
|---|---|
| Code hash (`python experiments/provenance.py`) | `9a40c4d822397fa019d69ba64ddc7ab58d5baf8fe04ed0d090b1dfebfe66e6ef` |
| `config_hash(DEFAULT_CONFIG)` | `1e26bd7de81c8f56a6e998b33ee531f59470681d78ff71affd05362a910e7b11` |
| `make check` | ruff clean; **464 passed, 1 skipped** (`test_full_results_match_registration_f1_tc10`, Plan 7); coverage **92.84%** |
| `pytest -q frontend/api/tests` | **17 passed** |
| `npm run build` (Week 7 UI) | green; one JS bundle 800.67 kB (237.62 kB gzip), CSS 30.62 kB (6.22 kB gzip) |
| Playwright (Week 7 `e2e/demo.spec.ts`) | first run failed: Chromium was not installed (`chrome-headless-shell` missing). After `npx playwright install chromium` (Chrome Headless Shell 158.0.8127.18, build 1254): **1 passed** |

`frontend/web/node_modules` was present, so `npm ci` was not needed.

## FE-T1 hash check and review record (D93)

| File | sha256 before = D88 entry | Reviewer now |
|---|---|---|
| `data/curriculum/curriculum_8node_x10.json` | yes (`f057fe5b…`) | `vhemanth06`, `ai_assisted`, `edges_reviewed` |
| `data/curriculum/activities_8node_x10.json` | yes (`13f309a4…`) | `vhemanth06`, `ai_assisted` |
| `data/content/content_8node_x10.json` | yes (`96a2db6a…`) | `vhemanth06`, `ai_assisted` |

The owner ran the three `scripts/record_review.py` commands (the agent was not allowed to
record a human review in the owner's name). No file changed since the AI check.
`content_8node.json` stays pending.

**Historical results:** `f5_baseline.json`, `f2_grid.json` and `f1_grid_run1.json` are untouched.
They were produced before D93, on identical data, so they keep the label "AI-checked, human
review pending (D88)". The tests that read those stored files keep asserting the old label. Fresh
runs (the smoke tests) say "reviewed".

## FE-T3 demo preset record (§FE.6)

`.venv/bin/python -m frontend.api.select_demo_preset` (2026-11-20, about 3.5 min, all 81
candidates evaluated through the `TestClient`).

**Criterion 2 was split into two parts,** so the fallback rule can drop just one:
- **2a:** bisection asks fewer questions than a sweep session;
- **2b:** at least one concept is `INFERRED`.

**Outcome:**
- **2a: no candidate meets it.** The sweep asks 6 questions for every candidate and learner;
  bisection asks 8–9 with the heuristic model and 21 with the fitted models.
- So 2a is dropped (§FE.6: "drop that step from the walkthrough, say so in the notes and README,
  and assert the variant chosen"). `demo.FEWER_QUESTIONS = False`, and `test_demo_preset` asserts
  it.
- Every other criterion is met.

**Chosen preset:**

| Item | Value |
|---|---|
| Known set, item model | {C1, C2, C3, C6}, `heuristic` |
| Deadline, budget | day 10, 10 min/day |
| Fixed values | `8node_x10`, goal C8, bisection, CP-SAT |
| First Setup plan | FEASIBLE |
| Questions: bisection vs sweep | **8 vs 6** (bisection budget `n_max` = 10, mode exact, 18 states, top state {C1, C2, C3, C6} with p 0.83) |
| Inferred concepts | C1, C2, C7, C8 |
| Plan after the diagnostic | FEASIBLE (`CPSAT_OPTIMAL`) |
| Check activities (`CONFIRMATION` records) | `E-C1-0.1` (C1), `E-C2-0.1` (C2), `E-C6-0.1` (C6), all in today's work |
| Too-tight variant | 10 → 5 min/day: INFEASIBLE, `CPSAT_INFEASIBLE`; options "Extend deadline by exactly 2 days to day 12 (proven minimum with CP-SAT)", "Increase daily budget to 10 min (fits by the deadline, CP-SAT)"; back to 10 min: FEASIBLE |

**Rejected before it:** 9 candidates, all with the known set {C1, C2, C3, C6} and model
`fitted_assist09`, at deadlines 10/14/21 × budgets 10/15/30. Each failed criterion **2b**:
bisection used its full 21-question budget and inferred nothing.

**Study step 5 (a wrong answer on a check).** Plan FE says the concept should then no longer be
"check pending / confirmed". The engine does something else for every check. Each check was
answered wrong on a fresh prepared session, after the scripted learner did the earlier cards:

| Check | Moves | `diag_confident` after | `confirmed` after |
|---|---|---|---|
| `E-C1-0.1` | 1 | false | **true**: C1's p was 0.9992; after the wrong answer the observation-only posterior is still ≥ 1 − ε |
| `E-C2-0.1` | 7 | true | false |
| `E-C6-0.1` | 2 | true | false |

A second wrong answer on C2 or C6 does not clear the flag before today's work runs out either.
The walkthrough therefore claims only what the engine shows:
- step 5 answers wrong on **`E-C2-0.1`**, the first check where a wrong answer does not confirm
  the concept (`demo.WRONG_CHECK`);
- the replan toast appears at once (7 moves);
- C2 stays "check pending".

`test_demo_preset` and `e2e/demo.spec.ts` assert exactly this. The C1 case is engine behaviour
(F1, D57), not changed here.

## Web app: taken from the spec, and what was adapted

| File | Source and adaptation |
|---|---|
| `index.html`, `src/main.tsx` | Spec; already identical, unchanged |
| `src/index.css`, `src/shell/CommandPalette.tsx` | Spec verbatim |
| `src/styles/tokens.css` | Spec + `--inferred`, `--check`, `--confirmed` (and `-soft`) tokens in light and dark for the bisection badges |
| `src/components/ui.tsx` | Spec + `STATE` entries inferred ◇ / check ⧗ / confirmed ✓✓; `ARM_COLOR` for sweep and bisection; Chip with a dashed border for inferred; `Segmented` with labels, disabled reasons and test ids; helpers `checkRecords`, `f1Badges`, `conceptStatus`. W8 policy/profile fields removed |
| `src/ctx.ts` | Spec, with the 8 tabs and 3 groups; `useDemoPreset`, `useHealth`; the switch lists (diagnostic, item model, planner) and their labels |
| `src/api/client.ts` | Spec minus the evaluation, policy, agent and authoring calls; adds `health` and `demoPreset` |
| `src/shell/AppShell.tsx` | Spec; the session chip shows curriculum · diagnostic · item model · planner; the honesty badge reads `health.content_review` |
| `src/App.tsx` | Spec minus the removed tabs; Curriculum map and Autopilot lazy-loaded |
| `src/pages/Overview.tsx`, `NoSession.tsx` | Spec B18, B17 |
| `src/pages/Setup.tsx` | Spec B19 + the three switches (CP-SAT and hybrid disabled without OR-Tools), "Use demo preset", the exact options list; a new session when the curriculum or a switch changes |
| `src/pages/Diagnostic.tsx` | Spec B20 + "Question n · budget n_max", stop reasons in plain words with the inferred chip; "Answer right" / "Answer wrong" buttons on every question (owner request, 2026-11-21; replaced the demo-mode scripted answer) |
| `src/pages/CurriculumMap.tsx` | Spec B21 + the inferred / check pending / confirmed badges, explained in the legend and the drawer |
| `src/pages/PlanPage.tsx`, `src/components/WhyPanel.tsx`, `PlanTimeline.tsx` | Spec B22 minus the agent proposer; "Check" badges; Why panel for `CONFIRMATION`, CP-SAT `SELECTED` (earliest day and its reason, placement), review and `CPSAT_SOLVE` records |
| `src/pages/Study.tsx` | Spec B23 minus the strategy chip; "Confirmation check" badge, demo buttons, flags after an answer |
| `src/pages/Disruptions.tsx` | Spec B24, restyled; names the session's planner |
| `src/pages/Autopilot.tsx` | Spec B27 + compare mode (arms or sweep vs bisection with arm, item model and planner), the CP-SAT warning, the `diag-items-*` cells; chart animation off under reduced motion |
| `src/pages/Evaluation.tsx` | Deleted (D92) |

**Removed features (D92):** Policy Lab, Authoring Studio, the agent proposer and strategy chip,
and the Evaluation tab. The `/api/evaluation` route and its test stay.

## Screenshots (`make demo-figures`)

There are 16 files in `docs/figures/`: `ui_<screen>_<theme>.png` for each screen (overview,
setup, diagnostic, map, plan, study, disruptions, autopilot) in light and dark. They are taken
on a seeded preset session after its diagnostic. Autopilot runs 20 learners first. The run uses
reduced motion, so no transition or chart animation is caught half-way. Nothing compares pixels
(`grep -r toHaveScreenshot frontend/web/e2e` finds nothing).

## Final state (FE-T8)

| Item | FE-T0 | FE-T8 |
|---|---|---|
| Code hash | `9a40c4d8…66e6ef` | `9a40c4d822397fa019d69ba64ddc7ab58d5baf8fe04ed0d090b1dfebfe66e6ef` (same) |
| `config_hash(DEFAULT_CONFIG)` | `1e26bd7d…7b11` | `1e26bd7de81c8f56a6e998b33ee531f59470681d78ff71affd05362a910e7b11` (same) |
| `src/` changes | — | none |
| `make check` | 464 passed, 1 skipped, coverage 92.84% | 464 passed, 1 skipped, coverage 92.84% |
| `pytest -q frontend/api/tests` | 17 passed | 25 passed |
| Playwright | 1 passed | 8 passed (walkthrough, light and dark screens, unknown session, API down, ⌘K, theme, keys) |
| JS bundle (gzip) | one file, 237.62 kB | 246.7 kB in total, split: first screen 76.4 kB, CurriculumMap 58.3 kB, Autopilot 105.8 kB, d3 6.3 kB |
| CSS (gzip) | 6.22 kB | 8.27 kB |

**Plan 7 is unaffected,** apart from the label. The F1, F2 and F3 runners now load `8node_x10`
without `allow_unreviewed` and label it "reviewed". The bytes are the same, so the results are
the same. The F1, F2 and F3 pre-registrations each got a dated content-status note.

**CI:** the demo job installs `.[demo]` without the `[cpsat]` extra. The preset uses CP-SAT, so
`e2e/demo.spec.ts` and the screens test need OR-Tools there. Following the plan, the CI was
changed only in the step name. The job is `continue-on-error`. To run the walkthrough in CI,
install `.[demo,cpsat]`.

**D91 (Plans 5 and 6 skipped)** is referenced by Plan FE but has no row in `docs/DECISIONS.md`.
It was not added here, because Plan FE did not ask for it.
