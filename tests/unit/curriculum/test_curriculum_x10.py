"""Plan 1 (F5 Phase A): the 8node_x10 curriculum (F5-TC1, F5-TC2, F5-TC7)."""

import hashlib
import json
import os
from collections import Counter

import pytest

from adaptengine.core.config import DEFAULT_CONFIG
from adaptengine.core.errors import UnreviewedContentError
from adaptengine.curriculum.loader import load_activities, load_curriculum
from adaptengine.learner.adapter import get_difficulty_class

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CUR = os.path.join(repo_root, "data/curriculum/curriculum_8node_x10.json")
ACT = os.path.join(repo_root, "data/curriculum/activities_8node_x10.json")
NEW_DIFFICULTIES = (0.1, 0.3, 0.45, 0.55, 0.7, 0.9)


def _json(rel):
    with open(os.path.join(repo_root, rel), encoding="utf-8") as f:
        return json.load(f)


def test_originals_unchanged_f5_tc1():
    """The 4-node / 8-node files and content_8node.json still match their recorded hashes."""
    manifest = _json("data/review_manifest.json")
    for rel in (
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        "data/curriculum/curriculum_8node.json",
        "data/curriculum/activities_8node.json",
        "data/content/content_8node.json",
    ):
        with open(os.path.join(repo_root, rel), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == manifest[rel]["sha256"], rel


def test_graph_identical_to_8node_f5_tc2():
    assert _json("data/curriculum/curriculum_8node_x10.json") == _json(
        "data/curriculum/curriculum_8node.json"
    )


def test_existing_activities_unchanged_f5_tc2():
    old = _json("data/curriculum/activities_8node.json")["activities"]
    new = {
        a["activity_id"]: a
        for a in _json("data/curriculum/activities_8node_x10.json")["activities"]
    }
    for a in old:
        assert new[a["activity_id"]] == a


def test_ten_exercises_with_3_4_3_spread_f5_tc2():
    concepts = load_curriculum(CUR, allow_unreviewed=True)
    acts = load_activities(ACT, concepts, allow_unreviewed=True, cfg=DEFAULT_CONFIG)
    assert len({a.activity_id for a in acts}) == len(acts) == 88
    for c in (x.concept_id for x in concepts):
        mine = [a for a in acts if a.target_concept == c]
        lessons = [a for a in mine if a.type.value == "LESSON"]
        exercises = [a for a in mine if a.type.value == "EXERCISE"]
        assert len(lessons) == 1 and len(exercises) == 10
        classes = Counter(get_difficulty_class(a.difficulty) for a in exercises)
        assert (classes["easy"], classes["medium"], classes["hard"]) == (3, 4, 3)
        assert all(DEFAULT_CONFIG.d_min <= a.difficulty <= DEFAULT_CONFIG.d_max for a in exercises)
        for d in NEW_DIFFICULTIES:
            assert any(a.activity_id == f"E-{c}-{d}" and a.difficulty == d for a in exercises)


@pytest.mark.parametrize("path", [CUR, ACT])
def test_review_gate_follows_manifest_f5_tc7(path):
    """F5-TC7 (D88): while the manifest entry is PENDING_HUMAN_REVIEW the file loads only with
    allow_unreviewed=True; once a named human review is recorded it loads without it."""
    with open(os.path.join(repo_root, "data/review_manifest.json"), encoding="utf-8") as f:
        entry = json.load(f)[os.path.relpath(path, repo_root)]
    pending = entry["reviewer"].strip().upper() == "PENDING_HUMAN_REVIEW"
    concepts = load_curriculum(CUR, allow_unreviewed=True)
    load = (
        (lambda: load_curriculum(CUR)) if path == CUR else (lambda: load_activities(ACT, concepts))
    )
    if pending:
        with pytest.raises(UnreviewedContentError, match="pending human review"):
            load()
    else:
        load()
