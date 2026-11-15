import json

import pytest

from adaptengine.core.profiles import product_config
from experiments.run_sensitivity import FACTORIAL, SCANS, build_configs, main


@pytest.mark.parametrize("key", list(SCANS))
def test_scans_contain_product_value(key):
    assert getattr(product_config(), key) in SCANS[key]


def test_invalid_combo_skipped_logged():
    configs, index, skipped = build_configs({"skip_threshold": (0.4, 0.8)}, ())
    assert "skip_threshold=0.8" in skipped and "skip_threshold=0.8" not in configs
    assert index["skip_threshold"] == [(0.4, "product"), (0.8, None)]


def test_product_deduped():
    configs, _, _ = build_configs()
    assert list(configs).count("product") == 1 and configs["product"] == {}
    assert "k_responses=2,theta=0.9" in configs and "k_responses=2" in configs


def test_smoke_meta(tmp_path):
    out = main(["--smoke", "--out-dir", str(tmp_path)])
    assert out["meta"]["engine"] == "product" and len(out["cells"]) == 2
    assert out["meta"]["factorial"] == list(FACTORIAL)
    saved = json.load(open(tmp_path / "sensitivity_smoke.json"))
    n = len(out["meta"]["configs"]) + 1  # + static_loop
    assert out["meta"]["episodes_executed"] == 2 * n * 8
    for cell in saved["cells"].values():
        assert (
            "product" in cell["paired_vs_static_loop"]
            and "product" not in cell["paired_vs_product"]
        )
        assert cell["configs"]["product"]["mean_dx_items"] > 0
        for lab, s in cell["configs"].items():
            if lab != "static_loop":
                assert s["executed_prereq_violations"] == 0
