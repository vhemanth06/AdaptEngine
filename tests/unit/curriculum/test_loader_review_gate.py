import pytest
import os
import json
from adaptengine.core.errors import UnreviewedContentError
from adaptengine.curriculum.loader import load_curriculum, load_activities
from adaptengine.core.schema import Concept


def test_live_fixtures_with_manifest():
    concepts = load_curriculum("data/curriculum/curriculum_4node.json")
    assert len(concepts) == 4
    activities = load_activities("data/curriculum/activities_4node.json", concepts)
    assert len(activities) == 20


def test_live_fixtures_with_explicit_manifest():
    concepts = load_curriculum(
        "data/curriculum/curriculum_4node.json", manifest_path="data/review_manifest.json"
    )
    assert len(concepts) == 4
    activities = load_activities(
        "data/curriculum/activities_4node.json", concepts, manifest_path="data/review_manifest.json"
    )
    assert len(activities) == 20


# TC-X6.1: A live curriculum file has no matching review-manifest entry... The loader raises UnreviewedContentError
def test_manifest_missing(tmp_path):
    with open(tmp_path / "curriculum.json", "w") as f:
        json.dump({"schema_version": 1, "concepts": [{"concept_id": "C1"}]}, f)
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(
            str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json")
        )
    assert "Cannot read manifest" in str(exc.value)


def test_no_entry_in_manifest(tmp_path):
    with open(tmp_path / "curriculum.json", "w") as f:
        json.dump({"schema_version": 1, "concepts": [{"concept_id": "C1"}]}, f)
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump({}, f)
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(
            str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json")
        )
    assert "No entry in manifest" in str(exc.value)


def test_missing_reviewer(tmp_path):
    import hashlib

    content = b'{"schema_version": 1, "concepts": [{"concept_id": "C1"}]}'
    with open(tmp_path / "curriculum.json", "wb") as f:
        f.write(content)
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(
            {
                "curriculum.json": {
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "date": "2024-01-01",
                }
            },
            f,
        )
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(
            str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json")
        )
    assert "Missing reviewer or date" in str(exc.value)


def test_ai_reviewer_rejected(tmp_path):
    import hashlib

    content = b'{"schema_version": 1, "concepts": [{"concept_id": "C1"}]}'
    with open(tmp_path / "curriculum.json", "wb") as f:
        f.write(content)
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(
            {
                "curriculum.json": {
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "date": "2024-01-01",
                    "reviewer": "AI",
                    "edges_reviewed": True,
                }
            },
            f,
        )
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(
            str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json")
        )
    assert "AI" in str(exc.value)


def test_edges_not_reviewed(tmp_path):
    import hashlib

    content = b'{"schema_version": 1, "concepts": [{"concept_id": "C1"}]}'
    with open(tmp_path / "curriculum.json", "wb") as f:
        f.write(content)
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(
            {
                "curriculum.json": {
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "date": "2024-01-01",
                    "reviewer": "Human Reviewer",
                    "edges_reviewed": False,
                }
            },
            f,
        )
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(
            str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json")
        )
    assert "edges_reviewed not true" in str(exc.value)


def test_hash_mismatch(tmp_path):
    content = b'{"schema_version": 1, "concepts": [{"concept_id": "C1"}]}'
    with open(tmp_path / "curriculum.json", "wb") as f:
        f.write(content)
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(
            {
                "curriculum.json": {
                    "sha256": "badhash",
                    "date": "2024-01-01",
                    "reviewer": "Human Reviewer",
                    "edges_reviewed": True,
                }
            },
            f,
        )
    with pytest.raises(UnreviewedContentError) as exc:
        load_curriculum(
            str(tmp_path / "curriculum.json"), manifest_path=str(tmp_path / "manifest.json")
        )
    assert "Hash mismatch" in str(exc.value)


# Curriculum files recorded as PENDING_HUMAN_REVIEW (D88). They must fail the gate until a named
# human review is recorded; that review removes them from this set, so the scan below checks them.
def _pending_curriculum_files():
    with open("data/review_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    return {
        os.path.basename(path)
        for path, entry in manifest.items()
        if path.startswith("data/curriculum/")
        and str(entry.get("reviewer", "")).strip().upper() == "PENDING_HUMAN_REVIEW"
    }


PENDING_REVIEW = _pending_curriculum_files()


X10 = (
    "data/curriculum/curriculum_8node_x10.json",
    "data/curriculum/activities_8node_x10.json",
    "data/content/content_8node_x10.json",
)


def test_8node_x10_review_recorded_d93():
    """FE-TC1 (D93): the owner's review of the three 8node_x10 files is recorded (reviewer
    vhemanth06, ai_assisted, edges reviewed), the hashes match the files, and both curriculum files
    pass the gate without allow_unreviewed. PENDING_REVIEW stays derived from the manifest."""
    import hashlib

    with open("data/review_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    for path in X10:
        entry = manifest[path]
        assert entry["reviewer"] == "vhemanth06" and entry["ai_assisted"] is True
        with open(path, "rb") as f:
            assert entry["sha256"] == hashlib.sha256(f.read()).hexdigest()
    assert manifest[X10[0]]["edges_reviewed"] is True
    assert not {"curriculum_8node_x10.json", "activities_8node_x10.json"} & PENDING_REVIEW
    assert manifest["data/content/content_8node.json"]["reviewer"] == "PENDING_HUMAN_REVIEW"
    assert len(load_activities(X10[1], load_curriculum(X10[0]))) == 88


def test_pending_curricula_record_edges_not_reviewed():
    """D88: a pending curriculum entry says so explicitly with edges_reviewed: false."""
    with open("data/review_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    for filename in PENDING_REVIEW:
        if filename.startswith("curriculum_"):
            assert manifest[f"data/curriculum/{filename}"].get("edges_reviewed") is False


def test_pending_review_files_blocked_until_recorded():
    for filename in sorted(PENDING_REVIEW):
        path = os.path.join("data/curriculum", filename)
        with pytest.raises(UnreviewedContentError, match="pending human review"):
            if filename.startswith("curriculum_"):
                load_curriculum(path)
            else:
                load_activities(
                    path,
                    load_curriculum(
                        path.replace("activities", "curriculum"), allow_unreviewed=True
                    ),
                )


def test_ci_scan_all_data():
    manifest_path = "data/review_manifest.json"
    assert os.path.exists(manifest_path)
    for filename in os.listdir("data/curriculum"):
        if filename.endswith(".json") and filename not in PENDING_REVIEW:
            path = os.path.join("data/curriculum", filename)
            if "activities" in filename:
                curr_file = path.replace("activities", "curriculum")
                if os.path.exists(curr_file):
                    concepts = load_curriculum(curr_file)
                else:
                    concepts = [Concept("C1"), Concept("C2"), Concept("C3"), Concept("C4")]
                load_activities(path, concepts)
            else:
                load_curriculum(path)


# D88 / P1.5-TC1: a PENDING_HUMAN_REVIEW entry with a correct hash must not pass the gate.
_CUR = b'{"schema_version": 1, "concepts": [{"concept_id": "C1"}]}'
_ACT = (
    b'{"schema_version": 1, "activities": ['
    b'{"activity_id": "L-C1", "type": "LESSON", "target_concept": "C1", "duration": 4},'
    b' {"activity_id": "E-C1-0.2", "type": "EXERCISE", "target_concept": "C1", "duration": 1,'
    b' "difficulty": 0.2}]}'
)


def _write_reviewed(tmp_path, reviewer):
    import hashlib

    (tmp_path / "curriculum.json").write_bytes(_CUR)
    (tmp_path / "activities.json").write_bytes(_ACT)
    entry = {"date": "2026-11-20", "reviewer": reviewer}
    manifest = {
        "curriculum.json": {
            **entry,
            "sha256": hashlib.sha256(_CUR).hexdigest(),
            "edges_reviewed": True,
        },
        "activities.json": {**entry, "sha256": hashlib.sha256(_ACT).hexdigest()},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return (
        str(tmp_path / "curriculum.json"),
        str(tmp_path / "activities.json"),
        str(tmp_path / "manifest.json"),
    )


@pytest.mark.parametrize(
    "reviewer", ["PENDING_HUMAN_REVIEW", " pending_human_review ", "Pending_Human_Review"]
)
def test_pending_reviewer_blocked_even_with_correct_hash(tmp_path, reviewer):
    cur, act, man = _write_reviewed(tmp_path, reviewer)
    with pytest.raises(UnreviewedContentError, match="pending human review"):
        load_curriculum(cur, manifest_path=man)
    concepts = load_curriculum(cur, manifest_path=man, allow_unreviewed=True)
    with pytest.raises(UnreviewedContentError, match="pending human review"):
        load_activities(act, concepts, manifest_path=man)
    assert len(load_activities(act, concepts, manifest_path=man, allow_unreviewed=True)) == 2


def test_named_reviewer_unblocks(tmp_path):
    cur, act, man = _write_reviewed(tmp_path, "test-reviewer")
    concepts = load_curriculum(cur, manifest_path=man)
    assert len(load_activities(act, concepts, manifest_path=man)) == 2


def test_ai_reviewer_still_rejected_with_correct_hash(tmp_path):
    cur, _, man = _write_reviewed(tmp_path, "AI")
    with pytest.raises(UnreviewedContentError, match="'AI'"):
        load_curriculum(cur, manifest_path=man)


def _record_review_main():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "record_review", "scripts/content/record_review.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


def test_record_review_pending_ai_assisted(tmp_path):
    import hashlib
    import shutil

    record_review = _record_review_main()
    man = tmp_path / "manifest.json"
    shutil.copy("data/review_manifest.json", man)
    before = json.loads(man.read_text())
    path = "data/curriculum/curriculum_8node_x10.json"
    record_review([path, "--pending", "--ai-assisted", "--source", "test", "--manifest", str(man)])
    after = json.loads(man.read_text())
    entry = after.pop(path)
    assert entry["reviewer"] == "PENDING_HUMAN_REVIEW" and entry["ai_assisted"] is True
    assert entry["sha256"] == hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert entry["source"] == "test" and "edges_reviewed" not in entry and entry["date"]
    before.pop(path, None)
    assert after == before  # no other entry touched


def test_record_review_needs_reviewer_or_pending(tmp_path):
    record_review = _record_review_main()
    with pytest.raises(SystemExit):
        record_review(["data/curriculum/curriculum_4node.json", "--source", "x"])
    with pytest.raises(SystemExit):
        record_review(
            [
                "data/curriculum/curriculum_4node.json",
                "--source",
                "x",
                "--pending",
                "--reviewer",
                "a",
            ]
        )


def test_8node_x10_loads_with_and_without_allow_unreviewed():
    """F5-TC7 (D93): after the owner's review the real files load with and without
    allow_unreviewed, and give the same 88 activities."""
    cur, act = X10[0], X10[1]
    gated = load_activities(act, load_curriculum(cur))
    opened = load_activities(
        act, load_curriculum(cur, allow_unreviewed=True), allow_unreviewed=True
    )
    assert len(gated) == len(opened) == 88 and gated == opened
