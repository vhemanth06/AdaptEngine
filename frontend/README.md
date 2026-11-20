# AdaptEngine demo frontend (W7 WP8, rebuilt for `redo` in Plan FE)

A thin web demo over the engine. The FastAPI adapter in `api/` only validates input, stores
sessions and reshapes engine output. Every decision (diagnostic items, stop reasons, mastery,
confirmation checks, eligibility, plans, replans, infeasibility advice) comes from
`adaptengine.api.Engine` (decision D45).

## Run the demo: one command

```bash
pip install -e ".[demo,cpsat]"   # once; [cpsat] adds OR-Tools for the CP-SAT and hybrid planners
make demo                        # builds web/dist if src/ is newer, starts uvicorn, prints the URL
```

`make demo` (`scripts/demo.py`) checks that FastAPI and uvicorn are installed and the curriculum
data is present. It rebuilds the web app when needed (`npm ci` the first time) and serves
everything from http://127.0.0.1:8000. `GET /api/health` reports:
- the engine version, the code hash and the default config hash;
- whether OR-Tools is installed;
- whether the web build is fresh, stale or missing;
- the review status of every curriculum and content file.

Everything is local (system fonts, bundled JS), so the demo works offline. For hot reload, run
`make demo-api` and `make demo-web`, then open http://localhost:5173 (Vite proxies `/api` to
port 8000).

Without OR-Tools, Setup disables CP-SAT and hybrid with "needs the [cpsat] extra". The demo
preset uses CP-SAT, so install the extra for the walkthrough.

## Design system and shell

- **Tokens:** in `web/src/styles/tokens.css`, light and dark. Engine states always have a
  colour, an icon and a label:
  - mastered: emerald ✓; in progress: indigo; remediation: amber ↻; locked: zinc 🔒;
  - the bisection badges: inferred ◇ (dashed border), check pending ⧗, confirmed ✓✓.
- **Sidebar groups:**
  - Learner: Overview, Setup, Diagnostic, Curriculum map, Plan + Why?, Study.
  - Adaptation: Disruptions.
  - Evidence: Autopilot.
- **Top bar:**
  - the session chip (id · curriculum · diagnostic · item model · planner);
  - plan status and the day, deadline and budget chips;
  - **Next day →**: ends today, and the engine replans the remaining work from the next day
    (D96). The learner is assumed to keep to the daily budget. A finished day stays on screen as
    "Day N complete" (Study has the same button) until Next day is pressed or a day is marked
    missed. The deadline day is the last day;
  - the demo-mode switch, the theme toggle and Reset demo.
- **⌘K / Ctrl+K:** opens the command palette (jump to a screen, and other actions).
- **Robustness:** loading skeletons, empty states with a next step, inline errors with Retry,
  and an error boundary per screen.
- **Bundle:** the React Flow and Recharts screens are lazy-loaded (about 247 kB of JS gzipped
  in total, 76 kB for the first screen).
- **Removed (D92):** Policy Lab, Authoring Studio, the agent features and the Evaluation tab.
  The `/api/evaluation` route stays.

## The 8 screens

| Screen | What it shows (data source) |
|---|---|
| **Overview** | Goal-path mastery, minutes used / available, days left, plan status; the Diagnose → Plan → Study → Adapt stepper; recent events |
| **Setup** | Curriculum, goal, deadline, minutes per day, and the three switches (diagnostic, item model, planner). Once the session has a plan, the curriculum and the switches are locked; "New session…" unlocks them, and changing one then starts a new session from day 1 ("Keep current session" goes back). Goal, deadline and budget always replan the current one. Shows the verdict, the shortfall, the plan's options as given (CP-SAT's are exact) and the best-effort plan |
| **Diagnostic** | One question at a time (keys 1–4), belief bars (`live_p`), "Question n · budget n_max" for bisection. When done: each concept's stop reason in plain words; inferred concepts get the inferred chip ("not asked") |
| **Curriculum map** | Prerequisite DAG with the engine's states, plus the inferred / check pending / confirmed badges; a drawer explains each one |
| **Plan + Why?** | Day timeline with "Check" badges; the Why panel shows the engine's trace for the clicked card: confirmation checks ("Short check instead of the full workload"), CP-SAT's earliest day and its reason, review and solve records |
| **Study** | Today's cards. A "Confirmation check" badge on checks. Closed-loop replan after each answer, with the replan toast, the remediation flag and the explanation. When the day's work is done: "Day N complete" with Next day → |
| **Disruptions** | Missed day, budget change, deadline −2: old vs new plan, moved activities, replan time in ms (the session's planner) |
| **Autopilot** | Simulated learners. Compare the four arms (default engine) or the sweep and bisection diagnostics (same arm, item model and planner). Numbers only, no claim text |

## Demo mode and the preset (D94)

With demo mode on (top bar), the "Use demo preset" button in Setup fills in the preset, and the
"Demo learner answers" button in Study answers for a scripted learner. That learner answers
right exactly on the preset's known concepts, with no slips and no guesses. In the Diagnostic,
every question has "Answer right" and "Answer wrong" buttons (demo mode or not), so you play the
learner yourself. Either way the buttons only answer questions; the engine makes every decision.

The preset is served by `GET /api/demo-preset` from `api/demo.py`. It was chosen by the fixed
procedure of Plan FE §FE.6 (`api/select_demo_preset.py`; record in `docs/FRONTEND_NOTES.md`):

| Field | Value |
|---|---|
| Curriculum, goal | `8node_x10`, C8 |
| Deadline, minutes per day | day 10, 10 min |
| Switches | bisection diagnostic, heuristic item model, CP-SAT planner |
| Known concepts | C1, C2, C3, C6 |
| Too-tight variant | 5 min/day (deadline 10) |
| Check answered wrong in step 5 | `E-C2-0.1` |

## Demo walkthrough

Automated in `web/e2e/demo.spec.ts`. Turn on demo mode and press Reset demo first.

| # | Screen | Do | What it shows |
|---|---|---|---|
| 1 | Setup | "Use demo preset" → "Start session and plan" → feasible. Set 5 min/day → Re-plan. Set 10 min/day → Re-plan | CP-SAT's exact answer to the tight variant: "Extend deadline by exactly 2 days to day 12 (proven minimum with CP-SAT)" and "Increase daily budget to 10 min (fits by the deadline, CP-SAT)"; then feasible again |
| 2 | Diagnostic | "Answer right" on C1, C2, C3 and C6 questions, "Answer wrong" on the others, until done | 8 questions (budget 10); C1, C2, C7 and C8 marked **Inferred: not asked** |
| 3 | Curriculum map | Look | Inferred / check pending badges next to the usual states |
| 4 | Plan + Why? | Click a "Check" card, then a lesson card | "Short check instead of the full workload"; then "Earliest possible: day …, because …" |
| 5 | Study | Work through the cards ("Demo learner answers", "Mark lesson done") until `E-C2-0.1`, then "Answer wrong" | Replan toast at once (7 activities moved); C2 stays **check pending**, because confirmation is still within reach of the remaining checks |
| 6 | Disruptions | "Missed day" | Old vs new plan, replan time in ms |
| 7 | Autopilot | Compare: "Diagnostics", planner greedy, 100 learners, Run | Questions asked per learner and outcomes, sweep and bisection side by side |

Two notes on what the preset does **not** show, so the walkthrough does not claim it:

- **Bisection did not ask fewer questions than the sweep.** In step 2 the sweep asks 6 questions
  for the same learner and bisection asks 8. No candidate in the §FE.6 search did better, so that
  claim was dropped.
- **Step 5 uses `E-C2-0.1`, not the first check of the day.** That first check is `E-C1-0.1`.
  C1 was inferred with p = 0.9992, so even after a wrong answer its observation-only posterior
  stays above 1 − ε, and the engine confirms it. Step 5 therefore uses the first check where a
  wrong answer does not confirm.

**Autopilot timings** (this laptop, calm scenario, 15 min/day):
- The four arms take about 2 s for 100 learners.
- The diagnostics comparison with greedy takes about 2 s. It gives 2.75 sweep vs 6.87 bisection
  questions per learner, and a goal-mastered share of 0.41 vs 0.46.
- With CP-SAT the comparison takes about 3 minutes, because every replan is a solver call. The
  screen warns about this, and the test uses 20 learners with greedy.

## Honesty footer

The footer shows:
- "Simulated learners";
- the content status of the active curriculum, read from `data/review_manifest.json` through
  `/api/health`: "content: reviewed by vhemanth06" for `8node_x10` (D93), or "content:
  AI-drafted, human review pending" for a pending file;
- the engine version and the code hash.

## Tests

```bash
make demo-test     # API TestClient tests + build + Playwright
make demo-figures  # build + screenshots of every screen in both themes -> docs/figures/ui_*.png
```

- `api/tests/test_api.py`:
  - one test per route;
  - the end-to-end session checks that the API plan equals a direct `Engine` call, including
    `8node_x10` × bisection × CP-SAT;
  - checks that the Plan FE fields (health, diagnostic info, confirmation flags, the trace
    confirmation record, the simulate switches) come from the engine unchanged;
  - `test_demo_preset` re-checks every step the walkthrough claims.

  It skips when `fastapi` is not installed; the CP-SAT cases skip without OR-Tools.
- `web/e2e/demo.spec.ts`: the walkthrough above.
- `web/e2e/screens.spec.ts`:
  - every screen in light and dark (screenshots saved as pictures, never compared pixel by
    pixel, D95);
  - an unknown stored session;
  - the API being down;
  - ⌘K, the theme toggle, and keys 1–4 in the diagnostic.
- First time only: `cd frontend/web && npx playwright install chromium`.

## Layout

```
api/app.py                 routes -> Engine; stepwise diagnostic = replay with recorded answers
api/schemas.py             pydantic request/response models
api/store.py               sessions in frontend/.sessions/<id>.snapshot.json + .meta.json
api/demo.py                the demo preset (D94)
api/select_demo_preset.py  the §FE.6 selection script (not imported by the app)
web/                       Vite + React + TypeScript, Tailwind, React Flow, Recharts, TanStack Query
web/src/shell/             app shell (sidebar, top bar, footer) and the ⌘K palette
web/src/styles/tokens.css  design tokens (light and dark)
web/src/api/schema.d.ts    generated from the OpenAPI schema: npm run gen:types (also writes openapi.json)
```

Environment: `ADAPTENGINE_SESSIONS_DIR` overrides the session directory (Playwright uses
`frontend/web/test-results/sessions`).
