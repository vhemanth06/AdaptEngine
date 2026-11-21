"""V2-TC6: the results schema accepts a valid document and rejects broken ones."""

import copy

import pytest

from experiments.core.results import Run, validate, write


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
    assert len(d["code_hash"]) == len(d["harness_hash"]) == 64
    write(d, str(tmp_path / "x.json"))


@pytest.mark.parametrize(
    "breaker",
    [
        lambda d: d.pop("code_hash"),
        lambda d: d.__setitem__("harness_hash", "abc"),
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
