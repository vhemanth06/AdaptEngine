"""V2-TC6: the results schema accepts a valid document and rejects broken ones."""

import copy

import pytest

import glob
import os

from experiments.core.results import Run, load, validate, write


def _doc():
    run = Run(
        "EX", {"path": "experiments/preregistration/EX_2026-11-21.md", "registered_utc": "t"}, 1
    )
    return run.finish(
        design={"seeds": {"episodes": [1000, 1199]}},
        content_review={"4-node": "reviewed"},
        cells=[{"key": {"world": "S0"}, "arms": {"adapt": {"n": 2, "metrics": {}}}}],
        hypotheses={"H1": {"held": True, "evidence": "0"}},
    )


def test_valid_document(tmp_path):
    d = _doc()
    validate(d)
    assert "code_hash" not in d and "harness_hash" not in d
    assert len(d["config_hash_default"]) == 64
    write(d, str(tmp_path / "x.json"))


@pytest.mark.parametrize(
    "breaker",
    [
        lambda d: d.pop("config_hash_default"),
        lambda d: d.__setitem__("config_hash_default", "abc"),
        lambda d: d["design"].pop("seeds"),
        lambda d: d["cells"][0].pop("key"),
        lambda d: d["cells"][0]["arms"]["adapt"].pop("n"),
        lambda d: d["hypotheses"]["H1"].pop("held"),
        lambda d: d.__setitem__("cells", {}),
    ],
)
def test_broken_documents_rejected(breaker):
    d = copy.deepcopy(_doc())
    breaker(d)
    with pytest.raises(ValueError):
        validate(d)


RESULTS = os.path.join(os.path.dirname(__file__), "..", "..", "results")


def test_existing_results_still_validate():
    # the final results carry the code and harness hashes of the time as extra fields (D104)
    paths = sorted(glob.glob(os.path.join(RESULTS, "*.json")))
    assert paths
    for p in paths:
        validate(load(p))
