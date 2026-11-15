import json

import pytest

from experiments.common import HLR_SEEDS, REPORT_SEEDS
from experiments.run_extensions import fit_units, main


def _check(out, key, tmp_path):
    assert key in out and out["meta"]["engine"] == "product"
    saved = json.load(open(tmp_path / "extensions_smoke.json"))
    assert key in saved
    sub = saved[key]
    assert sub["meta"]["episodes_executed"] > 0
    for cell in sub["cells"].values():
        for lab, s in cell["arms"].items():
            assert s["executed_prereq_violations"] == 0, lab
    return sub


@pytest.mark.parametrize("key", ["review_cap", "elo", "forgets"])
def test_smoke(key, tmp_path):
    _check(main([key, "--smoke", "--out-dir", str(tmp_path)]), key, tmp_path)


def test_review_cap_pass_flag(tmp_path):
    out = main(["review_cap", "--smoke", "--out-dir", str(tmp_path)])
    for cell in out["review_cap"]["cells"].values():
        ci = cell["capped_vs_no_review"]["ci95"]
        assert cell["pass"] == (ci[1] >= 0)  # fails only if the upper CI bound is below 0


def test_hlr_smoke(tmp_path):
    out = main(["hlr", "--smoke", "--out-dir", str(tmp_path)])
    _check(out, "hlr", tmp_path)
    fit = json.load(open(tmp_path / "hlr_fit_smoke.json"))
    assert len(fit["weights"]) == 3 and fit["n_observations"] > 0


def test_hlr_fit_uses_hlr_seeds_only():
    seeds = {s for _cur, ss in fit_units() for s in ss}
    assert seeds and seeds <= set(HLR_SEEDS) and not seeds & set(REPORT_SEEDS)
