import pytest
import os
import json
from adaptengine.core.errors import UnreviewedContentError, ValidationError
from adaptengine.curriculum.loader import load_curriculum, load_activities
from adaptengine.core.schema import Concept

def test_live_fixtures_with_manifest():
    concepts = load_curriculum("data/curriculum/curriculum_4node.json")
    assert len(concepts) == 4
    activities = load_activities("data/curriculum/activities_4node.json", concepts)
    assert len(activities) == 20

# TC-X6.1: A live curriculum file has no matching review-manifest entry... The loader raises UnreviewedContentError
def test_manifest_missing(tmp_path):
    with open(tmp_path / "curriculum.json", "w") as f:
        json.dump({"schema_version": 1, "concepts": [{"concept_id": "C1"}]}, f)
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json"))
    assert "Cannot read manifest" in str(exc.value)

def test_no_entry_in_manifest(tmp_path):
    with open(tmp_path / "curriculum.json", "w") as f:
        json.dump({"schema_version": 1, "concepts": [{"concept_id": "C1"}]}, f)
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump({}, f)
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json"))
    assert "No entry in manifest" in str(exc.value)

def test_missing_reviewer(tmp_path):
    import hashlib
    content = b'{"schema_version": 1, "concepts": [{"concept_id": "C1"}]}'
    with open(tmp_path / "curriculum.json", "wb") as f:
        f.write(content)
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump({"curriculum.json": {"sha256": hashlib.sha256(content).hexdigest(), "date": "2024-01-01"}}, f)
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json"))
    assert "Missing reviewer or date" in str(exc.value)

def test_edges_not_reviewed(tmp_path):
    import hashlib
    content = b'{"schema_version": 1, "concepts": [{"concept_id": "C1"}]}'
    with open(tmp_path / "curriculum.json", "wb") as f:
        f.write(content)
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump({"curriculum.json": {"sha256": hashlib.sha256(content).hexdigest(), "date": "2024-01-01", "reviewer": "AI"}}, f)
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json"))
    assert "edges_reviewed not true" in str(exc.value)

def test_hash_mismatch(tmp_path):
    content = b'{"schema_version": 1, "concepts": [{"concept_id": "C1"}]}'
    with open(tmp_path / "curriculum.json", "wb") as f:
        f.write(content)
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump({"curriculum.json": {"sha256": "badhash", "date": "2024-01-01", "reviewer": "AI", "edges_reviewed": True}}, f)
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json"))
    assert "Hash mismatch" in str(exc.value)

def test_ci_scan_all_data():
    manifest_path = "data/review_manifest.json"
    assert os.path.exists(manifest_path)
    for filename in os.listdir("data/curriculum"):
        if filename.endswith(".json"):
            path = os.path.join("data/curriculum", filename)
            if "activities" in filename:
                load_activities(path, [Concept("C1"), Concept("C2"), Concept("C3"), Concept("C4")])
            else:
                load_curriculum(path)
