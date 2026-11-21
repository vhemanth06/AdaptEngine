VENV ?= .venv
PYTHON = $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
PYTEST = $(if $(wildcard $(VENV)/bin/pytest),$(VENV)/bin/pytest,pytest)
RUFF = $(if $(wildcard $(VENV)/bin/ruff),$(VENV)/bin/ruff,ruff)

.PHONY: all w3 w4 w5 poc test lint format check demo demo-api demo-web demo-test demo-figures exp-test exp-smoke exp-run exp-report exp-figures

all: check w3 w4 w5 poc

w3:
	$(PYTHON) scripts/run_w3.py

w4:
	$(PYTHON) scripts/run_w4.py

w5:
	$(PYTHON) scripts/run_w5.py

poc:
	$(PYTHON) scripts/poc_demo.py



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

# The final study (Plan V2, D98; renamed from experiments/, D102) in experiments/ (README there).
# Runs refuse to start unless registered.
EXP_RUNNERS = e3_calibration e2_diagnostic e1_safety_outcomes e4_features e5_planners e6_sensitivity

exp-test:
	$(PYTEST) -q experiments/tests

exp-smoke:
	for r in $(EXP_RUNNERS); do $(PYTHON) -m experiments.runners.$$r --smoke || exit 1; done

exp-run:
	for r in $(EXP_RUNNERS); do $(PYTHON) -m experiments.runners.$$r || exit 1; done

exp-report:
	$(PYTHON) -m experiments.report.extract
	$(PYTHON) -m experiments.report.render_tables
	$(PYTHON) -m experiments.report.render_figures

exp-figures:
	$(PYTHON) -m experiments.report.render_figures
