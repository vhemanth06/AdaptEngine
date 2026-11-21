VENV ?= .venv
PYTHON = $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
PYTEST = $(if $(wildcard $(VENV)/bin/pytest),$(VENV)/bin/pytest,pytest)
RUFF = $(if $(wildcard $(VENV)/bin/ruff),$(VENV)/bin/ruff,ruff)

.PHONY: all w3 w4 w5 w6 poc eval eval-quick test lint format check demo demo-api demo-web demo-test demo-figures v2-test v2-smoke v2-run v2-report v2-figures

all: check w3 w4 w5 w6 poc eval

w3:
	$(PYTHON) scripts/run_w3.py

w4:
	$(PYTHON) scripts/run_w4.py

w5:
	$(PYTHON) scripts/run_w5.py

w6:
	$(PYTHON) scripts/run_w6.py

poc:
	$(PYTHON) scripts/poc_demo.py

eval:
	$(PYTHON) experiments/run_evaluation.py

eval-quick:
	$(PYTHON) experiments/run_evaluation.py --quick



test:
	$(PYTEST) -q --cov=adaptengine --cov-fail-under=84

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) format .
	$(RUFF) check --fix .

check: lint test


# Plan FE: one command (builds web/dist if src is newer, starts uvicorn, prints the URL)
demo:
	$(PYTHON) scripts/demo.py

# Demo frontend (W7 WP8). Needs: pip install -e ".[demo]" and npm ci in frontend/web.
demo-api:
	$(PYTHON) -m uvicorn frontend.api.app:app --port 8000

demo-web:
	cd frontend/web && npm run dev

demo-test:
	$(PYTEST) -q frontend/api/tests
	cd frontend/web && npm run build && npx playwright test

# Plan FE (D95): screenshots of every screen in both themes -> docs/figures/ui_<screen>_<theme>.png
demo-figures:
	cd frontend/web && npm run build && npm run figures

# Plan V2 (D98): the final study in experiments_v2/ (README there). Runs refuse to start unless registered.
V2_RUNNERS = e3_calibration e2_diagnostic e1_safety_outcomes e4_features e5_planners e6_sensitivity

v2-test:
	$(PYTEST) -q experiments_v2/tests

v2-smoke:
	for r in $(V2_RUNNERS); do $(PYTHON) -m experiments_v2.runners.$$r --smoke || exit 1; done

v2-run:
	for r in $(V2_RUNNERS); do $(PYTHON) -m experiments_v2.runners.$$r || exit 1; done

v2-report:
	$(PYTHON) -m experiments_v2.report.extract
	$(PYTHON) -m experiments_v2.report.render_tables
	$(PYTHON) -m experiments_v2.report.render_figures

v2-figures:
	$(PYTHON) -m experiments_v2.report.render_figures
