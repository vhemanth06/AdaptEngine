import json

import pytest

from adaptengine.planner.workload import _difficulty_class

DIFFS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9]


def _acts(path):
    d = json.load(open(path))
    return d["activities"] if isinstance(d, dict) else d


@pytest.mark.parametrize("name,base", [("4node_x10", "4node"), ("8node_x10", "8node")])
def test_x10_drafts(name, base):
    d = f"data/drafts/{name}"
    cur = json.load(open(f"{d}/curriculum_{name}.json"))
    assert cur["concepts"] == json.load(open(f"data/curriculum/curriculum_{base}.json"))["concepts"]
    acts = _acts(f"{d}/activities_{name}.json")
    for c in cur["concepts"]:
        ex = sorted(
            a["difficulty"]
            for a in acts
            if a["target_concept"] == c["concept_id"] and a["type"] == "EXERCISE"
        )
        assert ex == DIFFS
        assert [_difficulty_class(x) for x in ex].count("hard") == 4
    by_id = {a["activity_id"]: a for a in acts}
    assert all(by_id[a["activity_id"]] == a for a in _acts(f"data/curriculum/activities_{base}.json"))
    content = json.load(open(f"{d}/content_{name}.json"))["activities"]
    assert set(content) == set(by_id)
    meta = json.load(open(f"{d}/draft_meta.json"))
    assert meta["ai_assisted"] is True and meta["reviewer"] == "PENDING_HUMAN_REVIEW"
