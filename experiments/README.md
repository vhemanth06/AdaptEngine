# experiments — the final study (Plan V2, D98–D102)

One self-contained study on the final engine: its own simulator, arms, statistics and runners,
six pre-registered experiments, and a report pipeline where restyling never re-runs an experiment.
It imports only the engine (`adaptengine`), the standard library, numpy, pandas, matplotlib and
ortools. Until 21 Nov 2026 this folder was `experiments_v2/`, next to an older harness in
`experiments/`; the older harness was removed after the final study (archived outside the
repository) and this folder was renamed.

## The experiments

| # | Runner | Question | Report |
|---|---|---|---|
| E1 | `e1_safety_outcomes` | Does the engine ever teach out of order, and does adapting pay off compared with not adapting? | 5.1, 5.4, 5.6 |
| E2 | `e2_diagnostic` | How well does each diagnostic estimate what the learner knows, and at what question cost? | 5.2 |
| E3 | `e3_calibration` | Are the engine's probabilities trustworthy, and do fitted guess/slip numbers make them more trustworthy? | 5.3 |
| E4 | `e4_features` | Does bisection with confirmation reach the goal as often as the sweep, in fewer total minutes, safely? | 5.4 |
| E5 | `e5_planners` | When does CP-SAT change outcomes, verdicts or advice compared with greedy, and at what planning time? | 5.5 |
| E6 | `e6_sensitivity` | How much do the results depend on the hand-set numbers, and on the simulator? (descriptive) | 5.6 |

Every experiment uses `DEFAULT_CONFIG` and changes only the setting it studies (D99). The exact
arms, cells, seeds, metrics and hypotheses are in `preregistration/E*_2026-11-21.md`; outcomes and
the run log are in `NOTES.md`.

## Running

From the repository root:

```bash
make exp-test                                  # pytest -q experiments/tests
make exp-smoke                                 # every runner with --smoke (1-2 learners, temp output)
python -m experiments.runners.e1_safety_outcomes [--smoke] [--procs N] [--out PATH]
make exp-run                                   # E3, E2, E1, E4, E5, E6 in order
```

Tests in `experiments/tests/` are grouped by kind: `unit/` (simulator, scenarios, audit, metrics,
diagnostic arms, real-data fits), `integration/` (closed-loop episodes, every runner end to end in
smoke mode, determinism across worker counts) and `tooling/` (report pipeline, pre-registration
guard, results schema). `make exp-test` runs all three.

- A full run refuses to start unless its pre-registration says `Status: Registered` with the
  current code hash (SHA-256 over `src/**/*.py`). `--smoke` is always allowed.
- `--procs` defaults to CPU count − 1. Results do not depend on it.
- E5 reuses E1's adapt cells for greedy (same config and seeds) when E1 ran with the same code hash,
  so run E1 first. E5 also writes `results/E5_latency.json` (timing, not deterministic).
- To keep the machine usable: `nice -n 19 python -m … --procs 4` (about 3× slower).

## Layout

- `core/` — provenance, curricula (review gate; synthetic generator writing `data/synthetic/`),
  the simulated learners (`simulator.py`, §V2.3), scenarios, arms, episodes, audits (executed and
  plan-level), diagnostics, real data (BKT EM, CV by student), metrics, parallel map, results schema,
  pre-registration guard.
- `runners/` — one runner per experiment plus `common.py`.
- `preregistration/` — E1–E6.
- `results/` — one JSON per experiment (format: Plan V2 §V2.6; `per_learner` keeps the paired vectors).
- `report/` — `extract.py`, `style.py`, `render_tables.py`, `render_figures.py`; outputs in
  `report/data/`, `report/tables/`, `report/figures/` (see `report/README.md`).
- `tests/` — V2-TC1 … V2-TC12.

## The report pipeline (D100)

```bash
make exp-report   # results/*.json -> report/data/*.csv -> report/tables/*.{tex,md}, report/figures/*.{pdf,png}
make exp-figures  # re-render figures only
```

**Restyling:** edit `report/style.py` (colours, fonts, sizes, widths), then `make exp-figures`. Table
formats live in `report/render_tables.py`. Neither reads results JSON, so no experiment re-runs.
