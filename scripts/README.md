# scripts

Command-line tools around the engine: the demos, content checks, dataset download, regression-pin
recording and the weekly acceptance runners. None of them is imported by `src/`. Run every script
from the repository root.

## `demo/`

| Script | What it does | Command | Writes or changes |
|---|---|---|---|
| `demo.py` | One-command web demo: checks FastAPI and uvicorn, rebuilds `frontend/web/dist` when needed, serves http://127.0.0.1:8000 | `make demo` or `python scripts/demo/demo.py [--port 8000] [--no-build]` | `frontend/web/dist/`, `frontend/.sessions/` (both ignored) |
| `poc_demo.py` | End-to-end command-line proof of concept (diagnose, plan, events, replan) | `make poc` or `python scripts/demo/poc_demo.py` | a temporary folder only; used by `tests/tooling/test_poc_demo.py` and `record_pins.py` |

## `content/`

| Script | What it does | Command | Writes or changes |
|---|---|---|---|
| `check_content.py` | Quality checks for `data/content/content_*.json` (answer keys, difficulty spread, code snippets) | `python scripts/content/check_content.py data/content/content_8node_x10.json --spread 3,4,3` | nothing |
| `record_review.py` | Records a human review (reviewer and SHA-256) in `data/review_manifest.json`. **The only supported way to record a review.** | `python scripts/content/record_review.py --reviewer <name> --source <source> <file>` (see `--help`) | `data/review_manifest.json` |

## `datasets/`

| Script | What it does | Command | Writes or changes |
|---|---|---|---|
| `download_data.py` | Downloads the public datasets into `data/external/` and verifies them against `CHECKSUMS` | `python scripts/datasets/download_data.py --verify-only` (no network) or without the flag to download | `data/external/` |

## `testing/`

| Script | What it does | Command | Writes or changes |
|---|---|---|---|
| `record_pins.py` | Re-records the regression pins checked by `tests/regression/test_baseline_pins.py` | `python scripts/testing/record_pins.py default` | `tests/fixtures/pins/default.json` |

> **Warning.** Run `record_pins.py` only on a deliberate change of the defaults, never to make a
> failing test pass. `tests/fixtures/pins/population_prior.json` was recorded before any Plan 0
> change and must never be re-recorded.

## `acceptance/`

| Script | What it does | Command | Writes or changes |
|---|---|---|---|
| `run_w3.py` | Week 3 acceptance runner (graph, diagnostic, mastery) | `make w3` | `runs/w3/<id>/` (ignored) |
| `run_w4.py` | Week 4 acceptance runner (planning, oracle, bounds) | `make w4` | `runs/w4/<id>/` (ignored) |
| `run_w5.py` | Week 5 acceptance runner (review, replanning, remediation, traces) | `make w5` | `runs/w5/<id>/` (ignored) |

`make_fixtures.py` was removed on 21 Nov 2026: it rewrote the reviewed 4- and 8-node curriculum
files, which the review gate would then refuse to load. The committed files are the reference.
