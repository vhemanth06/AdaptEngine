import json

import pytest

from experiments.run_planner_cost import main


def test_cpsat_smoke(tmp_path):
    pytest.importorskip("ortools")
    out = main(["cpsat", "--smoke", "--out-dir", str(tmp_path)])["cpsat"]
    assert out["cells"]
    for cell in out["cells"].values():
        for arm in ("greedy_or_oracle", "cpsat"):
            c = cell[arm]
            assert c["prereq_violations"] == c["budget_violations"] == 0
        # greedy keeps in-plan reviews (repeat occurrences by design); cpsat packs each once
        assert cell["cpsat"]["duplicate_occurrences"] == 0


def test_latency_smoke(tmp_path):
    out = main(["all", "--smoke", "--out-dir", str(tmp_path)])
    for r in out["replan"]["curricula"].values():
        for row in r["rows"]:
            assert row["median_full_ms"] > 0 and row["median_frontier_ms"] > 0
    assert all(c["median_ms"] > 0 for c in out["plan"]["cells"].values())
    assert all(c["median_ms"] > 0 for c in out["diag"]["curricula"].values())


def test_smoke_meta(tmp_path):
    main(["plan", "--smoke", "--out-dir", str(tmp_path)])
    main(["diag", "--smoke", "--out-dir", str(tmp_path)])
    saved = json.load(open(tmp_path / "planner_cost_smoke.json"))
    assert saved["meta"]["engine"] == "product" and saved["meta"]["smoke"] is True
    assert {"plan", "diag"} <= set(saved)
    for k in ("plan", "diag"):
        assert saved[k]["meta"]["code_hash"] and saved[k]["meta"]["timestamp_utc"]


def test_diag_times_goal_path_flow(tmp_path, monkeypatch):
    from adaptengine.api import Engine

    from experiments.common import goal_of, product_engine

    seen, real = [], Engine.diagnose

    def spy(self, *a, **k):
        seen.append(k.get("goal_concepts"))
        return real(self, *a, **k)

    monkeypatch.setattr(Engine, "diagnose", spy)
    out = main(["diag", "--smoke", "--out-dir", str(tmp_path)])["diag"]
    assert (
        out["scope"] == "goal_path"
        and product_engine("synth-20-x10").config.diagnostic_scope == "goal_path"
    )
    assert seen and all(g == [goal_of(product_engine("synth-20-x10"))] for g in seen)
