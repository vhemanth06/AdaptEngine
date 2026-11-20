"""Plan 4 (F3-T8): smoke test and result schema of experiments/run_f3_grid.py (full grid: Plan 7)."""

import os
import sys

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

pytest.importorskip("ortools")

from experiments.run_f3_grid import PURE_SUBSET, in_pure_subset, main, reusable_f1_cell, units  # noqa: E402


def test_pure_cpsat_only_on_the_named_subset():
    us = list(units(("S0",), ("4-node", "synth-20"), (1000,)))
    for w, c, b, s, p, _, *f1 in us:
        if p == "cpsat" and not f1:
            assert in_pure_subset(c, b, s)
    assert any(u[4] == "cpsat" for u in us) and any(
        u[4] == "hybrid" and u[1] == "synth-20" for u in us
    )
    assert set(PURE_SUBSET) == {"curricula", "budgets", "scenarios"}


def test_smoke_schema(tmp_path):
    r = main(
        str(tmp_path / "f3.json"),
        n_episodes=1,
        worlds=("S0",),
        curricula=("4-node", "8-node"),
        budgets=(10, 15),
        scenarios=("calm", "deadline_cut"),
        latency_n=1,
    )
    f1x3 = [c for c in r["cells"] if c["f1_bisection"]]
    assert {c["planner"] for c in f1x3} == {"greedy", "hybrid", "cpsat"}
    assert all(c["curriculum"] == "8-node" and c["scenario"] == "calm" for c in f1x3)
    md = r["metadata"]
    assert md["preregistration"].startswith("docs/preregistration/F3_")
    assert {"4-node/greedy", "4-node/hybrid", "4-node/cpsat"} <= set(r["latency"])
    planners = {c["planner"] for c in r["cells"]}
    assert planners == {"greedy", "hybrid", "cpsat"}
    for c in r["cells"]:
        assert c["executed_prereq_violations"] == 0
        assert c["verdict"] in ("FEASIBLE", "INFEASIBLE", "UNKNOWN")
    plain = [c for c in r["cells"] if not c["f1_bisection"]]
    greedy = [c for c in plain if c["planner"] == "greedy"]
    hybrid = {
        (c["curriculum"], c["budget"], c["scenario"]): c for c in plain if c["planner"] == "hybrid"
    }
    for g in greedy:  # hybrid = greedy whenever greedy's first plan met the deadline
        if g["reason"] == "GREEDY_FEASIBLE":
            h = hybrid[(g["curriculum"], g["budget"], g["scenario"])]
            assert (h["verdict"], h["projected_finish_day"]) == (
                g["verdict"],
                g["projected_finish_day"],
            )


def test_reusable_f1_cell():
    f1 = {"closed_loop": {"S0": {"8-node": {"bisect_confirm": {"n": 200}}}}}
    assert reusable_f1_cell(f1, "S0", "8-node", "bisect_confirm") == {"n": 200}
    assert reusable_f1_cell(f1, "S1", "8-node", "bisect_confirm") is None


def test_choose_work_units_rule_p45_tc2():
    from experiments.run_f3_grid import TUNE_THRESHOLD, choose_work_units

    assert TUNE_THRESHOLD == 0.5
    assert choose_work_units({5.0: 0.5, 10.0: 0.79}) == 10.0  # exactly 0.5 is not "most"
    assert choose_work_units({"1.0": 0.0, "2.0": 0.1}) == 2.0  # none above: the largest
    assert choose_work_units({1.0: 0.6, 5.0: 0.9}) == 1.0  # the first above the threshold wins


def test_tuning_file_matches_frozen_value_p45_tc1():
    """P4.5-TC1: the tuning record, the runner's rule and the config agree."""
    import json
    from collections import defaultdict

    from adaptengine.core.config import DEFAULT_CONFIG
    from experiments.run_f3_grid import TUNE_RULE, choose_work_units

    with open(os.path.join(repo_root, "experiments/results/f3_tuning.json"), encoding="utf-8") as f:
        r = json.load(f)
    md = r["metadata"]
    assert md["rule"] == TUNE_RULE and len(md["code_hash"]) == 64
    assert md["chosen"] == DEFAULT_CONFIG.cpsat_max_work_units == 10.0
    assert choose_work_units(r["share_proven"]) == md["chosen"]
    rows = defaultdict(list)
    for p in r["plans"]:
        rows[str(p["work_units"])].append(p["proven"])
    assert {k: round(sum(v) / len(v), 4) for k, v in rows.items()} == r["share_proven"]
