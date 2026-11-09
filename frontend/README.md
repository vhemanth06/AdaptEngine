# AdaptEngine demo frontend (W7 WP8)

A thin web demo over the engine. The FastAPI adapter in `api/` only validates input, stores
sessions and reshapes engine output. Every decision (diagnostic items, mastery, eligibility,
plans, replans) comes from `adaptengine.api.Engine` (decision D45).

## Run the demo (one command after a one-time setup)

One-time setup, from the repo root:

```bash
pip install -e ".[demo]"                 # or: uv pip install --python .venv/bin/python -e ".[demo]"
(cd frontend/web && npm ci && npm run build)
```

Run:

```bash
make demo-api                            # http://127.0.0.1:8000 serves the API and the built app
```

Everything is served locally (system fonts, bundled JS), so it works offline.

For UI development with hot reload, run `make demo-api` and `make demo-web` together and open
http://localhost:5173 (Vite proxies `/api` to port 8000).

## Tests

```bash
make demo-test     # API TestClient tests + build + Playwright run of the 6-minute demo script
```

- `api/tests/test_api.py` has one test per route and an end-to-end session that checks the
  API plan equals a direct `Engine.next_activities` call after every step. It skips when
  `fastapi` is not installed.
- `web/e2e/demo.spec.ts` runs the demo script below. First time only:
  `cd frontend/web && npx playwright install chromium`.

## Screens and the 6-minute script (report §10.5)

| Tab | What to show |
|---|---|
| 1 Setup | Goal C8, deadline 10, 10 min/day: FEASIBLE. Switch to 5 min/day: not feasible, with the shortfall, options and a best-effort schedule. Switch back. |
| 2 Diagnostic | Answer with keys 1-4 (or "Demo learner answers"). Live p bars, then stop reasons per concept. |
| 3 Map | DAG coloured by engine state: mastered (evidence), remediation, unlocked today, locked (later), not in plan. Colours are colour-blind safe and always carry a text label. |
| 4 Plan + Why? | Day columns with budget bars. Click a card: the trace record, score components (review, unlock, fit) and the alternatives deferred that day. |
| 5 Study | Answer wrong twice: p drops, remediation is flagged and the plan updates at once (closed loop via `next_activities`). |
| 6 Disruptions | Missed day, budget change, deadline -2: old vs new plan, moved activities, replan time measured on the server. |
| 7 Autopilot | Simulated learners (`experiments/arms.py`) through all four arms, fixed seeds. |
| 8 Evaluation | Charts and tables from `experiments/results/*.json` (whatever exists). |

Demo mode (on by default) adds the scripted demo learner buttons. The demo learner knows
C1, C2, C3 and C6. "Reset demo" starts a fresh session. Seeds are fixed, so rehearsals and
the live demo behave the same.

The 4-node curriculum has no content file: the UI then shows "right / wrong" buttons
instead of question text.

## Layout

```
api/app.py        routes -> Engine; stepwise diagnostic = replay with recorded answers (NeedAnswer)
api/schemas.py    pydantic request/response models
api/store.py      sessions in frontend/.sessions/<id>.snapshot.json (adaptengine.session) + .meta.json
web/              Vite + React + TypeScript, Tailwind, React Flow, Recharts, TanStack Query
web/src/api/schema.d.ts   generated from the OpenAPI schema: npm run gen:types (also writes openapi.json)
```

`ADAPTENGINE_SESSIONS_DIR` overrides the session directory.
