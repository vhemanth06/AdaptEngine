VENV ?= .venv
PYTHON = $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
PYTEST = $(if $(wildcard $(VENV)/bin/pytest),$(VENV)/bin/pytest,pytest)
RUFF = $(if $(wildcard $(VENV)/bin/ruff),$(VENV)/bin/ruff,ruff)

.PHONY: all w3 w4 w5 w6 poc eval eval-quick test lint format check

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

