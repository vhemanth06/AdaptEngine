import json
import os

import pytest

from adaptengine.core.profiles import product_config
from experiments.run_grid import ARMS, main


def test_product_arm_is_product_config():
    f, mode = ARMS["product"]
    assert f("4node_x10", "S0").config == product_config() and mode == "adapt_dx"


@pytest.mark.parametrize(
    "arm,mode,field,val",
    [
        ("product_nodx", "adapt", "consolidation", False),
        ("product_consol", "adapt_dx", "consolidation", True),
        ("product_norev", "no_review", "theta", 0.95),
        ("w8_final", "adapt_dx", "theta", 0.85),
    ],
)
def test_arm_variants(arm, mode, field, val):
    f, m = ARMS[arm]
    assert m == mode and getattr(f("4node_x10", "S1").config, field) == val


def test_w8_final_uses_world_profile():
    assert ARMS["w8_final"][0]("4node_x10", "S4F").config.profile == "fitted_S4"


def test_smoke_zero_violations_and_resume(tmp_path):
    out = main(["--smoke", "--out-dir", str(tmp_path)])
    assert len(out["cells"]) == 2 and out["meta"]["episodes_executed"] == 2 * len(ARMS) * 20
    for cell in out["cells"].values():
        for arm, s in cell["arms"].items():
            # product_noreplan plans once, so executing past an unmastered prerequisite is by design
            if arm.startswith(("product", "w8_final")) and arm != "product_noreplan":
                assert s["executed_prereq_violations"] == 0
    assert out["meta"]["engine"] == "product"
    assert "approximate" in out["meta"]["calibration_method"]
    assert os.path.exists(tmp_path / "grid_smoke.json")


def test_resume_skips_done_units(tmp_path):
    first = main(["--smoke", "--out-dir", str(tmp_path)])
    second = main(["--smoke", "--resume", "--out-dir", str(tmp_path)])
    assert second["meta"]["episodes_executed"] == 0
    assert second["cells"] == first["cells"]
    lines = (tmp_path / "grid_smoke.ckpt.jsonl").read_text().splitlines()
    assert len(lines) == first["meta"]["episodes_executed"]
    assert json.loads(lines[0])["code_hash"]


def test_resume_survives_truncated_line(tmp_path):
    first = main(["--smoke", "--out-dir", str(tmp_path)])
    ck = tmp_path / "grid_smoke.ckpt.jsonl"
    lines = ck.read_text().splitlines()
    ck.write_text("\n".join(lines[:-1]) + "\n" + lines[-1][:30])  # last record cut mid-write
    second = main(["--smoke", "--resume", "--out-dir", str(tmp_path)])
    assert second["meta"]["checkpoint_lines_skipped"] == 1
    assert second["meta"]["episodes_executed"] == 1
    assert second["cells"] == first["cells"]
    third = main(["--smoke", "--resume", "--out-dir", str(tmp_path)])
    assert third["meta"]["episodes_executed"] == 0  # half line stays in file, skipped again


@pytest.fixture(scope="module")
def smoke_out(tmp_path_factory):
    return main(["--smoke", "--out-dir", str(tmp_path_factory.mktemp("g"))])


def test_paired_vs_product(smoke_out):
    from experiments.run_grid import ABLATION_ARMS

    for cell in smoke_out["cells"].values():
        assert set(cell["paired_vs_product"]) == set(ABLATION_ARMS)
        for p in cell["paired_vs_product"].values():
            assert p["goal_mastery"]["n"] == 20 and len(p["all_required"]["ci95"]) == 2
        a, b = cell["arms"], cell["paired_vs_product"]["product_nodx"]["goal_mastery"]["diff"]
        assert (
            abs(b - (a["product_nodx"]["goal_mastery_rate"] - a["product"]["goal_mastery_rate"]))
            < 1e-3
        )


def test_km_curve_only_in_headline(smoke_out):
    from experiments.stats import kaplan_meier  # noqa: F401

    head = smoke_out["meta"]["headline_cell"]
    for cid, cell in smoke_out["cells"].items():
        for s in cell["arms"].values():
            assert ("km_curve" in s) == (cid == head)
            if cid == head:
                assert s["km_curve"][0] == [0.0, 1.0]
                ts = [t for t, _ in s["km_curve"]]
                assert ts == sorted(ts) and all(0 <= v <= 1 for _, v in s["km_curve"])
                med = s["km_median_minutes"]
                first = next((t for t, v in s["km_curve"] if v <= 0.5), None)
                assert first == med


def test_reliability_bins(smoke_out):
    for cell in smoke_out["cells"].values():
        for s in cell["arms"].values():
            rb = s["reliability"]
            assert len(rb) == 10 and sum(b["n"] for b in rb) == s["n_attempts"]
            for i, b in enumerate(rb):
                assert b["lo"] == i / 10
                if b["n"]:
                    assert b["lo"] - 1e-9 <= b["mean_p"] <= b["hi"] + 1e-9 and 0 <= b["freq"] <= 1


def test_cell_counts_and_skipped_stress_cells():
    from experiments.run_grid import grid_cells, skip_reason

    assert len(list(grid_cells("primary"))) == 208
    stress = list(grid_cells("stress"))
    assert len(stress) == 180 and len(list(grid_cells("both"))) == 388
    skipped = [c for c in stress if skip_reason(c[4], c[2], c[3], c[5])]
    assert len(skipped) == 45 and len(stress) - len(skipped) == 135
    assert {(c[4], c[3]) for c in skipped} == {
        ("budget_drop", 5),
        ("budget_crash", 5),
        ("budget_crash", 15),
    }


def test_prewarm_both_builds_only_each_cells_arms():
    from experiments.run_grid import grid_cells, prewarm

    prewarm(list(grid_cells("both")))  # used to raise: w8_final asked for fitted_S2


def test_stress_one_seed_run(tmp_path, monkeypatch):
    import experiments.run_grid as rg

    real = rg.grid_cells
    pick = lambda g: [  # noqa: E731  one primary cell + the 4node_x10 S2 stress cells
        c for c in real(g)
        if c[1:6] == ("S1", "4node_x10", 15, "calm", 7)
        or (c[0] == "stress" and c[1] == "S2" and c[2] == "4node_x10")
    ]  # fmt: skip
    monkeypatch.setattr(rg, "grid_cells", pick)
    monkeypatch.setattr(rg, "REPORT_SEEDS", (2001,))
    out = main(["--grid", "both", "--out-dir", str(tmp_path), "--processes", "4"])
    m = out["meta"]
    assert len(m["skipped_cells"]) == 3 and all("S2|4node_x10" in k for k in m["skipped_cells"])
    stress = {k: v for k, v in out["cells"].items() if v["grid"] == "stress"}
    assert len(stress) == 9 and len(out["cells"]) == 10
    assert m["episodes_executed"] == 9 * 3 + len(ARMS)
    for c in stress.values():
        assert set(c["arms"]) == {"product", "product_noreplan", "static_loop"}
        assert c["arms"]["product"]["executed_prereq_violations"] == 0


def test_checkpoint_other_hash_lines_not_mixed(tmp_path):
    first = main(["--smoke", "--out-dir", str(tmp_path)])
    ck = tmp_path / "grid_smoke.ckpt.jsonl"
    recs = [json.loads(x) for x in ck.read_text().splitlines()]
    assert all(r["code_hash"] and r["experiment_hash"] for r in recs)
    for r in recs[:10]:
        r["experiment_hash"] = "0" * 64
    ck.write_text("".join(json.dumps(r) + "\n" for r in recs))
    second = main(["--smoke", "--resume", "--out-dir", str(tmp_path)])
    assert second["meta"]["checkpoint_lines_other_hash"] == 10
    assert second["meta"]["episodes_executed"] == 10
    assert second["cells"] == first["cells"]
