"""V2-TC6: every runner's --smoke completes and writes a schema-valid file."""

import importlib
import os

import pytest

from experiments_v2.core.provenance import code_hash
from experiments_v2.core.results import load, validate

RUNNERS = {
    "e1_safety_outcomes": "E1_safety_outcomes",
    "e2_diagnostic": "E2_diagnostic",
    "e3_calibration": "E3_calibration",
    "e4_features": "E4_features",
    "e5_planners": "E5_planners",
    "e6_sensitivity": "E6_sensitivity",
}


def run_smoke(module: str, out: str, procs: int = 2) -> dict:
    mod = importlib.import_module(f"experiments_v2.runners.{module}")
    mod.main(["--smoke", "--procs", str(procs), "--out", out])
    return load(out)


@pytest.mark.parametrize("module", sorted(RUNNERS))
def test_smoke_writes_valid_results(module, tmp_path):
    out = str(tmp_path / f"{RUNNERS[module]}.json")
    doc = run_smoke(module, out)
    validate(doc)
    assert doc["experiment"] == RUNNERS[module]
    assert doc["code_hash"] == code_hash() and doc["smoke"] is True
    assert doc["cells"] and doc["hypotheses"]
    if module == "e5_planners":
        lat = load(os.path.join(tmp_path, "E5_latency.json"))
        validate(lat)
        kinds = {c["key"]["kind"] for c in lat["cells"]}
        assert kinds == {"cold_start", "replan"}


def test_full_run_refuses_without_registration(tmp_path):
    p = tmp_path / "E1_2026-11-21.md"
    p.write_text("Status: DRAFT\nCode hash: x\n", encoding="utf-8")
    mod = importlib.import_module("experiments_v2.runners.e1_safety_outcomes")
    with pytest.raises(SystemExit):
        mod.main(["--prereg", str(p), "--out", str(tmp_path / "x.json")])
    assert not (tmp_path / "x.json").exists()
