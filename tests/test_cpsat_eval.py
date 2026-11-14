"""W8 O.4: CP-SAT evaluation runner (experiments/run_cpsat_eval.py)."""

import pytest

from experiments.run_cpsat_eval import headline, run


def _cell(d_min, c_min, d_last, c_last):
    arm = lambda m, last: {  # noqa: E731
        "status": "FEASIBLE",
        "reason": "X",
        "minutes": m,
        "last_day": last,
        "prereq_violations": 0,
        "budget_violations": 0,
        "solver_note": None,
        "plan_ms_mean": 1.0,
    }
    return {
        "default": arm(d_min, d_last),
        "cpsat": arm(c_min, c_last),
        "same_status": True,
        "cpsat_days_saved": d_last - c_last,
    }


def test_headline_separates_packing_gains_from_dropped_reviews():
    h = headline({"same": _cell(100, 100, 9, 8), "dropped": _cell(177, 119, 46, 26)})
    assert h["cpsat_shorter"] == 2 and h["max_days_saved"] == 20
    assert h["same_workload_cells"] == 1 and h["same_workload_max_days_saved"] == 1
    assert h["cpsat_dropped_review_minutes_cells"] == 1


def test_cpsat_eval_small_grid_passes_audits():
    pytest.importorskip("ortools")
    cells = run(sizes=(20,), budgets=(30,), repeats=1)
    assert set(cells) == {"synth-20|b30|loose", "synth-20|b30|greedy", "synth-20|b30|tight"}
    h = headline(cells)
    assert h["audit_violations_default"] == 0 and h["audit_violations_cpsat"] == 0
    assert h["cpsat_longer"] == 0
