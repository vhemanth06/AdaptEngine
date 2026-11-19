"""Plan 1 (F5-T5, D84): synthetic generator option exercises_per_concept (F5-TC1, F5-TC6)."""

import hashlib
import json
import os
import sys
from collections import Counter

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from adaptengine.learner.adapter import get_difficulty_class  # noqa: E402
from experiments.synth_curriculum import (  # noqa: E402
    generate_synthetic_curriculum,
    parse_synth_name,
    write_synthetic_curriculum,
)

# sha256 of json.dumps(generate_synthetic_curriculum(n), sort_keys=True), recorded before Plan 1
DEFAULT_PINS = {
    8: "b1fb00a75868c51e797e564c6e047ae48846ecd4335345c58be10278aeaa57ef",
    20: "dfcf4b75c380bee7e6f6e5da9c87be21f5c123776f17300060be5b934f34dd7d",
    50: "a3c052628e00bb274a6f4673c086a8bd146bdc39c8ddb4a1186a0d47bba51850",
}


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize("n", sorted(DEFAULT_PINS))
def test_default_output_unchanged_f5_tc1(n):
    assert _sha(generate_synthetic_curriculum(n)) == DEFAULT_PINS[n]
    assert _sha(generate_synthetic_curriculum(n, exercises_per_concept=4)) == DEFAULT_PINS[n]


def test_x10_spread_and_same_graph_f5_tc6():
    cur4, _ = generate_synthetic_curriculum(20)
    cur10, act10 = generate_synthetic_curriculum(20, exercises_per_concept=10)
    assert cur10 == cur4  # only the catalogue changes
    exercises = [a for a in act10["activities"] if a["type"] == "EXERCISE"]
    assert len(exercises) == 200
    for c in (x["concept_id"] for x in cur10["concepts"]):
        mine = [a for a in exercises if a["target_concept"] == c]
        assert [a["activity_id"] for a in mine] == [f"E-{c}-{i}" for i in range(1, 11)]
        classes = Counter(get_difficulty_class(a["difficulty"]) for a in mine)
        assert (classes["easy"], classes["medium"], classes["hard"]) == (3, 4, 3)
        assert [a["duration"] for a in mine] == [1, 1, 1] + [2] * 7


def test_x10_deterministic_f5_tc6():
    a = generate_synthetic_curriculum(50, exercises_per_concept=10)
    assert a == generate_synthetic_curriculum(50, exercises_per_concept=10)
    assert a != generate_synthetic_curriculum(50, seed=7, exercises_per_concept=10)


def test_names_and_files(tmp_path):
    assert parse_synth_name("synth-20") == (20, 4)
    assert parse_synth_name("synth-50-x10") == (50, 10)
    for bad in ("synth-20-x7", "8-node", "synth-"):
        with pytest.raises(ValueError):
            parse_synth_name(bad)
    with pytest.raises(ValueError):
        generate_synthetic_curriculum(8, exercises_per_concept=6)
    cp, ap = write_synthetic_curriculum(str(tmp_path), 20)
    assert os.path.basename(cp) == "curriculum_synth_20.json"
    cp, ap = write_synthetic_curriculum(str(tmp_path), 20, exercises_per_concept=10)
    assert os.path.basename(ap) == "activities_synth_20_x10.json"


def test_grid_runner_resolves_x10_names():
    from experiments.run_w7_grid import curriculum_paths, engine

    assert curriculum_paths("8-node-x10")[1].endswith("activities_8node_x10.json")
    assert curriculum_paths("synth-20-x10")[1].endswith("activities_synth_20_x10.json")
    assert len(engine("synth-20-x10", "default").activities) == 20 * 11
