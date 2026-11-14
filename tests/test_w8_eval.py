from experiments.run_final_grid import arm_engine, winner_spec


def test_strict_arms_config():
    spec = winner_spec()
    e, run_arm = arm_engine("adapt_strict_gs", "S1", "4-node", spec)
    assert run_arm == "adapt_dx"
    assert (e.config.theta, e.config.k_responses, e.config.selection_scope, e.config.concept_cap) == (0.95, 1, "goal_search", 4)
    assert e.config.consolidation and e.config.diagnostic_scope == "goal_path"
    e2, _ = arm_engine("adapt_strict_dx", "S1", "4-node", spec)
    assert e2.config.selection_scope == "concept_sweep" and e2.config.theta == 0.95


def test_w8_diag_smoke(tmp_path):
    from experiments.run_w8_diag import main
    r = main(str(tmp_path / "d.json"), n=3, curricula=["4-node", "synth-20"])
    assert set(r["curricula"]["synth-20"]["S0"]) >= {"prior_only", "goal_search"}


def test_smoke_name():
    from experiments.run_final_grid import smoke_name
    assert smoke_name("/r/final_grid.json") == "/r/final_grid_smoke.json"
    assert smoke_name("/r/final_grid.ckpt.jsonl") == "/r/final_grid_smoke.ckpt.jsonl"
    assert smoke_name("/r/w8_grid.json") == "/r/w8_grid_smoke.json"
    assert smoke_name("/r/w8_grid.ckpt.jsonl") == "/r/w8_grid_smoke.ckpt.jsonl"
