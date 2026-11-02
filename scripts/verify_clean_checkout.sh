#!/usr/bin/env bash
set -euo pipefail

# verify_clean_checkout.sh
# Verifies installation, tests, quickstart flow, API example, and eval reproducibility
# from an isolated copy of the working tree (working-tree copy avoids needing uncommitted git state).

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "=== Verifying clean copy in $TEMP_DIR ==="
mkdir -p "$TEMP_DIR/AdaptEngine"
rsync -a --exclude .git --exclude .venv --exclude runs --exclude '__pycache__' --exclude '*.pyc' ./ "$TEMP_DIR/AdaptEngine/"
cd "$TEMP_DIR/AdaptEngine"

echo "=== Creating isolated venv and installing ==="
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -r requirements-dev.txt -q
pip install -e . -q

echo "=== Running test suite ==="
pytest -q

echo "=== Running CLI Quickstart flow ==="
python -m adaptengine validate --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json
python -m adaptengine init-learner --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot quick_snap.json --goal C4 --deadline 5 --budget 15
python -m adaptengine plan --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot quick_snap.json
python -m adaptengine update --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot quick_snap.json --activity L-C1 --day 1
python -m adaptengine replan --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json --snapshot quick_snap.json
rm -f quick_snap.json

echo "=== Running API Quickstart ==="
python examples/api_quickstart.py

echo "=== Running quick evaluation twice (TC8.1 byte-identical check) ==="
python experiments/run_evaluation.py --quick
cp experiments/results/evaluation_results.json "$TEMP_DIR/eval1.json"
python experiments/run_evaluation.py --quick
diff "$TEMP_DIR/eval1.json" experiments/results/evaluation_results.json

echo "CLEAN CHECKOUT OK"
