import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (ROOT, os.path.join(ROOT, "src")) if p not in sys.path]

# run_extensions / run_sensitivity names are reused by later tasks, so not listed here.
OLD = [
    "cat_baseline",
    "diag_eval",
    "make_final_results",
    "make_w7_results",
    "ope",
    "policy_runner",
    "train_policy",
    "w8_common",
    "run_agent_eval",
    "run_calibration_select",
    "run_cpsat_eval",
    "run_diag_matrix",
    "run_diag_selection",
    "run_evaluation",
    "run_final_grid",
    "run_policy_eval",
    "run_replan_latency",
    "run_s4_fitted",
    "run_smoke",
    "run_w7_grid",
    "run_w7_latency",
    "run_w8_diag",
]


def test_fit_bkt_sim_imports():
    import experiments.bkt_lessons
    import experiments.fit_bkt
    import experiments.fit_bkt_sim  # noqa: F401


def test_fitted_results_kept():
    for f in [
        "bkt_fit_assist09",
        "bkt_fit_ct",
        "bkt_fit_ct_pybkt",
        "bkt_fit_sim",
        "w8_fits",
        "w8_bkt_fit_ct",
        "w8_bkt_fit_assist09",
    ]:
        assert os.path.exists(os.path.join(ROOT, "experiments", "results", f"{f}.json"))


def test_old_runners_gone():
    for n in OLD:
        assert not os.path.exists(os.path.join(ROOT, "experiments", f"{n}.py")), n
    assert not os.path.exists(os.path.join(ROOT, "experiments", "probes"))
    for n in ("run_w6", "run_final"):
        assert not os.path.exists(os.path.join(ROOT, "scripts", f"{n}.py")), n


def test_fit_bkt_sim_standalone():
    import experiments.fit_bkt_sim as m

    assert "w8_common" not in open(m.__file__).read()
    eps = m._w8_episodes(("S0", "4-node", "static_loop", "calm", 14, (2000,)))
    assert len(eps) == 1 and eps[0]["activity_log"]
