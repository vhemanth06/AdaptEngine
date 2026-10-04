#!/bin/bash
set -e

TEMP_DIR=$(mktemp -d)
echo "Running in $TEMP_DIR"

git clone . $TEMP_DIR/AdaptEngine
cd $TEMP_DIR/AdaptEngine

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .

pytest -q

python -m adaptengine validate --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json

python experiments/run_smoke.py > out1.txt
python experiments/run_smoke.py > out2.txt
diff out1.txt out2.txt

echo "CLEAN CHECKOUT OK"
