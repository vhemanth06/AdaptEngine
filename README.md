# AdaptEngine

## Quickstart
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .

python -m adaptengine validate --curriculum data/curriculum/curriculum_4node.json --activities data/curriculum/activities_4node.json
```