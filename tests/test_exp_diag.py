import json

from experiments.run_diag import _engines, goal_of, learner_arms, main, summarise


def test_matched_budget():
    for seed in (2001, 2003, 2005):
        r = learner_arms("8node_x10", "S1", seed)
        n = r["product"]["items"]
        assert n > 0
        for arm in ("fixed@n", "random@n", "irt_cat@n"):
            assert r[arm]["items"] == n


def test_state_space_skipped_over_12():
    assert "state_space" not in learner_arms("synth-20-x10", "S0", 2001)
    assert "state_space" in learner_arms("4node_x10", "S0", 2001)


def test_inferred_precision_defined():
    r = learner_arms("4node_x10", "S0", 2001)
    s = summarise([r], ["prior_only"])["prior_only"]
    assert "inferred_precision" in s and s["inferred_precision"] is None


def test_goalpath_stops_scoped_to_path():
    # 8node: goal path (7) is smaller than all concepts (8), so unscoped stops would fail this.
    r = learner_arms("8node_x10", "S0", 2001)
    base = _engines("8node_x10")["product"]
    goal = goal_of(base)
    path = {goal} | base.graph.ancestors(goal)
    rec = r["product_goalpath"]
    assert 0 < sum(rec["stops"].values()) <= len(path) < len(list(base.graph.concepts()))
    assert rec["inferred"][0] <= len(path)


def test_smoke_meta(tmp_path):
    out = main(["--smoke", "--out-dir", str(tmp_path)])
    assert out["meta"]["engine"] == "product" and len(out["cells"]) == 2
    saved = json.load(open(tmp_path / "diag_matrix_smoke.json"))
    for cell in saved["cells"].values():
        assert cell["n"] == 10 and "product_goalpath" in cell["arms"]
