# AdaptEngine demo frontend (W7 WP8, rebuilt in W8 WP-H)

A thin web demo over the engine. The FastAPI adapter in `api/` only validates input, stores
sessions and reshapes engine output. Every decision (diagnostic items, mastery, eligibility,
plans, replans, policy checks) comes from `adaptengine` (decision D45).

## Run the demo: one command

```bash
pip install -e ".[demo]"     # once
make demo                    # builds web/dist if src/ is newer, starts uvicorn, prints the URL
```

`make demo` checks that FastAPI/uvicorn are installed, rebuilds the web app when needed
(`npm ci` the first time) and serves everything from http://127.0.0.1:8000. `/api/health`
reports the engine version, code hash, profiles, flags and whether the web build is stale; the
footer shows the code hash and the honesty badge. Everything is local (no CDN), so it works
offline. For hot reload: `make demo-api` and `make demo-web`, then http://localhost:5173.

Optional live agent (Policy Lab "LLM agent", plan proposer, strategy chip): set
`ADAPTENGINE_AGENT_PROVIDER=anthropic` (or `ollama:<model>`) after populating the replay cache
(`docs/AGENTS.md`). Without it the agent screens use the offline stub and say so.

## Design system and shell (W8 H.2–H.3)

- Tokens in `web/src/styles/tokens.css` (light and dark; Tailwind's neutral scale is remapped
  so every screen follows the theme). Engine states: mastered emerald, in progress indigo,
  remediation amber, locked zinc, violation rose, always with an icon and a label.
- Sidebar groups: Learner (Overview, Setup, Diagnostic, Map, Plan, Study), Adaptation
  (Disruptions, Policy Lab), Authoring (Authoring Studio), Evidence (Autopilot, Evaluation).
- Top bar: session, plan status, day/deadline/budget chips, demo-mode switch, theme toggle,
  Reset demo. ⌘K / Ctrl+K opens the command palette (jump to a screen, miss a day, reset).
- Loading skeletons, empty states with a call to action, inline errors with Retry and
  "Copy debug info", an error boundary per screen. React Flow and Recharts screens are
  lazy-loaded (JS ≈ 255 kB gzipped in total).
- The planned Radix/lucide/framer-motion packages were not installed (handover item); the
  plan's fallback was used: tokens + Tailwind with the existing dependencies only.

## Tests

```bash
make demo-test     # API TestClient tests + build + Playwright
```

- `api/tests/test_api.py`: every route, including W8 health, profiles, simulate (new arms,
  belief vs reality), policy preview, plan proposer, strategy and the authoring flow; the
  end-to-end session checks the API plan equals a direct `Engine.next_activities` call.
- `web/e2e/demo.spec.ts`: the 8-minute demo script below.
- `web/e2e/screens.spec.ts`: every screen in light and dark (visual snapshots in
  `e2e/screens.spec.ts-snapshots/`), an unknown stored session, and the API being down.
  Refresh the snapshots after an intended UI change with `npx playwright test --update-snapshots`.

## Eight-minute demo script (final report R§3.6) and rehearsal checklist

| # | Screen | Do | What it shows |
|---|---|---|---|
| 1 | Overview → Setup | Goal C8, 10 min/day, deadline 10 → Feasible. 5 min/day → Not feasible with shortfall and a best-effort plan. Back to 10. | Instant feasibility; honest "no" |
| 2 | Diagnostic | Answer 4–6 questions (keys 1–4) or "Skip → plan from the prior". | Belief bars move; the diagnostic is optional (D52) |
| 3 | Plan + Why? | Click a card. | Score breakdown, deferred alternatives, raw trace |
| 4 | Study | Answer wrong twice. | Remediation, instant replan toast, agent strategy chip |
| 5 | Disruptions | "Missed yesterday". | Old vs new plan, replan time in ms |
| 6 | Autopilot | 100 learners, S1, 14 days: adapt (final) vs adapt (W7) vs static_loop. | Belief vs reality: false mastery falls with the calibrated engine |
| 7 | Policy Lab | Deterministic → Bandit frozen → LLM agent → "forced bad output". | Candidates and propensities; "rejected → fallback" |
| 8 | Authoring Studio (optional) | Generate a 3-concept draft (stub), validate, approve with your name. | AI drafts, human approves, engine accepts only reviewed content |
| 9 | Evaluation | Forest plot vs static_loop, violations (log), reliability. | 0 prerequisite violations; wins and losses stated honestly |

Rehearsal checklist: `make demo` on the presentation laptop; Reset demo; theme as projected;
run the script once end to end; `npx playwright test` green; screenshots in
`docs/figures/demo_*.png`.

## Layout

```
api/app.py        routes -> Engine; stepwise diagnostic = replay with recorded answers (NeedAnswer)
api/schemas.py    pydantic request/response models
api/store.py      sessions in frontend/.sessions/<id>.snapshot.json (adaptengine.session) + .meta.json
web/              Vite + React + TypeScript, Tailwind, React Flow, Recharts, TanStack Query
web/src/api/schema.d.ts   generated from the OpenAPI schema: npm run gen:types (also writes openapi.json)
```

`ADAPTENGINE_SESSIONS_DIR` overrides the session directory.
