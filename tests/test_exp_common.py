import hashlib
import json

import pytest

from adaptengine.core.profiles import product_config
from adaptengine.core.schema import ActivityType
from experiments.common import (
    FIT_SEEDS,
    HEADLINE_SEEDS,
    HLR_SEEDS,
    REPORT_SEEDS,
    TRAIN_SEEDS,
    curriculum_paths,
    product_engine,
    run_parallel,
    world_kw,
    write_result,
)
from experiments.synth_curriculum import X10_DIFFICULTIES, write_synthetic_curriculum

# sha256 of the default 20-concept output (seed 2026), pinned before the generator edit
PINNED_C = "09167c5ab9f5a1639457c77116b96ee3b02e4c106285a745a316c808b883edf0"
PINNED_A = "f4f1b8c3b3b6e9b679fa7baed12ec6556cc1f34fd5cf0d237ba28aa6f70ef873"


def _h(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def test_synth_default_unchanged(tmp_path):
    c, a = write_synthetic_curriculum(str(tmp_path), 20, seed=2026)
    assert (_h(c), _h(a)) == (PINNED_C, PINNED_A)


def test_synth_x10_has_ten_exercises():
    e = product_engine("synth-20-x10")
    for cid in e.graph.concepts():
        got = sorted(
            x.difficulty
            for x in e.activities.values()
            if x.target_concept == cid and x.type == ActivityType.EXERCISE
        )
        assert got == list(X10_DIFFICULTIES)


def test_x10_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        curriculum_paths("4node_x10", root=str(tmp_path))
    with pytest.raises(ValueError):
        curriculum_paths("nope")


def test_product_engine_is_product_config():
    assert product_engine("4node_x10").config == product_config()
    assert product_engine("4node_x10", consolidation=True).config.consolidation is True


def test_seeds_disjoint():
    assert not set(REPORT_SEEDS) & set(FIT_SEEDS + TRAIN_SEEDS + HLR_SEEDS)
    assert all(s % 2 for s in HEADLINE_SEEDS) and len(HEADLINE_SEEDS) == 1000


def test_write_result_stamps(tmp_path):
    p = write_result("t", {"meta": {"x": 1}}, out_dir=str(tmp_path))
    meta = json.load(open(p))["meta"]
    assert meta["x"] == 1 and meta["engine"] == "product"
    assert "code_hash" in meta and "timestamp_utc" in meta


def test_world_kw_and_parallel():
    assert world_kw("S1") == ("S1", {})
    assert world_kw("S4F")[0] == "S4" and "bkt_params" in world_kw("S4F")[1]
    assert run_parallel(abs, [-3, 2, -1], processes=2) == [3, 2, 1]


def test_synth_temp_dir_removed_at_exit():
    import os
    import subprocess
    import sys

    code = (
        "from experiments.common import curriculum_paths; import os; "
        "p = curriculum_paths('synth-20-x10')[0]; assert os.path.isfile(p); print(p)"
    )
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert not os.path.exists(os.path.dirname(out.stdout.strip()))
