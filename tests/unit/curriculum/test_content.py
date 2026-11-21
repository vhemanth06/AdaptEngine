import copy
import json

import pytest

from adaptengine.core.errors import ValidationError
from adaptengine.core.schema import Activity, ActivityType
from adaptengine.curriculum.content import load_content
from adaptengine.curriculum.loader import load_activities, load_curriculum

CONTENT = "data/content/content_8node.json"


def test_real_content_covers_8node_activities():
    concepts = load_curriculum("data/curriculum/curriculum_8node.json")
    activities = load_activities("data/curriculum/activities_8node.json", concepts)
    content = load_content(CONTENT, activities)
    assert set(content) == {a.activity_id for a in activities}
    # correct answers are spread over all four positions
    assert {e["correct"] for e in content.values() if e["type"] == "EXERCISE"} == {0, 1, 2, 3}


ACTS = (
    Activity("L-X", ActivityType.LESSON, "X", 1),
    Activity("E-X", ActivityType.EXERCISE, "X", 1, difficulty=0.5),
)
GOOD = {
    "schema_version": 1,
    "activities": {
        "L-X": {"type": "LESSON", "target_concept": "X", "markdown": "# Hi"},
        "E-X": {
            "type": "EXERCISE",
            "target_concept": "X",
            "prompt": "1 + 1?",
            "options": ["1", "2", "3", "4"],
            "correct": 1,
            "explanation": "One plus one is two.",
        },
    },
}


def _write(tmp_path, doc):
    p = tmp_path / "content.json"
    p.write_text(json.dumps(doc))
    return str(p)


def test_minimal_valid(tmp_path):
    assert set(load_content(_write(tmp_path, GOOD), ACTS)) == {"L-X", "E-X"}


def _mutate(path, value):
    doc = copy.deepcopy(GOOD)
    *parents, key = path
    node = doc
    for k in parents:
        node = node[k]
    if value is None:
        del node[key]
    else:
        node[key] = value
    return doc


@pytest.mark.parametrize(
    "path, value, msg",
    [
        (("activities", "E-X"), None, "missing ids ['E-X']"),
        (("activities", "E-Y"), GOOD["activities"]["E-X"], "unknown ids ['E-Y']"),
        (("activities", "E-X", "type"), "LESSON", "type"),
        (("activities", "L-X", "target_concept"), "Y", "target_concept"),
        (("activities", "E-X", "options"), ["1", "2", "2", "4"], "4 non-empty unique"),
        (("activities", "E-X", "options"), ["1", "2", "3"], "4 non-empty unique"),
        (("activities", "E-X", "correct"), 4, "0..3"),
        (("activities", "L-X", "markdown"), "  ", "markdown"),
    ],
)
def test_invalid_content(tmp_path, path, value, msg):
    with pytest.raises(ValidationError) as exc:
        load_content(_write(tmp_path, _mutate(path, value)), ACTS)
    assert msg in str(exc.value)


def test_unparseable_file(tmp_path):
    p = tmp_path / "content.json"
    p.write_text("{not json")
    with pytest.raises(ValidationError, match="failed to parse"):
        load_content(str(p), ACTS)
