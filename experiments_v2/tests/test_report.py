"""V2-TC10 to V2-TC12: the report pipeline (extract -> CSV -> tables and figures)."""

import ast
import csv
import filecmp
import json
import os

import pytest

from experiments_v2.report import extract, render_figures, render_tables
from experiments_v2.tests.test_runners_smoke import RUNNERS, run_smoke

REPORT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "report"))


@pytest.fixture(scope="module")
def smoke_results(tmp_path_factory):
    d = tmp_path_factory.mktemp("results")
    for module, name in RUNNERS.items():
        run_smoke(module, str(d / f"{name}.json"), procs=1)
    return str(d)


@pytest.fixture(scope="module")
def data_dir(smoke_results, tmp_path_factory):
    d = str(tmp_path_factory.mktemp("data"))
    extract.main(smoke_results, d)
    return d


def _csv(data_dir, name):
    with open(os.path.join(data_dir, f"{name}.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_every_csv_has_columns_and_provenance(data_dir, smoke_results):
    hashes = {
        json.load(open(os.path.join(smoke_results, f)))["code_hash"]
        for f in os.listdir(smoke_results)
    }
    for name, (_, cols, _) in extract.TABLES.items():
        with open(os.path.join(data_dir, f"{name}.csv"), encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == extract.PROV + cols, name
            for r in reader:
                assert r["source_file"].startswith("experiments_v2/results/"), name
                assert r["code_hash"] in hashes and r["status"] == "ok", name


def test_spot_checks_equal_results_json(data_dir, smoke_results):
    def doc(f):
        return json.load(open(os.path.join(smoke_results, f)))

    e1, e2, e3, e4, e5 = (doc(f"{n}.json") for n in ("E1_safety_outcomes", "E2_diagnostic", "E3_calibration",
                                                      "E4_features", "E5_planners"))  # fmt: skip
    head = next(c for c in e1["cells"] if c["key"]["headline"])
    t7 = {(r["world"], r["curriculum"], r["arm"]): r for r in _csv(data_dir, "t7_headline")}
    k = (head["key"]["world"], head["key"]["curriculum"])
    checks = [
        (t7[k + ("adapt",)]["goal_mastery"], head["arms"]["adapt"]["metrics"]["goal_mastery_rate"]),
        (t7[k + ("static",)]["minutes"], head["arms"]["static"]["metrics"]["mean_minutes"]),
        (
            t7[k + ("static",)]["adapt_minus_arm_goal"],
            head["contrasts"]["adapt_minus_static"]["goal_mastered"]["diff"],
        ),
    ]
    sc = next(c for c in e2["cells"] if c["key"]["part"] == "scripted")
    t4 = next(r for r in _csv(data_dir, "t4_scripted") if r["profile"] == sc["key"]["profile"])
    checks += [
        (t4["bisection_brier"], sc["arms"]["bisection"]["metrics"]["brier"]),
        (t4["brier_diff_hi"], sc["contrasts"]["bisection_minus_sweep"]["brier"]["ci95"][1]),
    ]
    t5 = {(r["dataset"], r["model"]): r for r in _csv(data_dir, "t5_realdata")}
    if e3["realdata"]["ct"]["status"] == "run":
        x = e3["realdata"]["ct"]["heldout"]["pooled_oof"]["fitted_class_profile"]
        checks += [
            (t5[("ct", "fitted_class_profile")]["brier"], x["brier"]),
            (t5[("ct", "fitted_class_profile")]["ece"], x["ece"]),
        ]
    c4 = e4["cells"][0]
    t9 = _csv(data_dir, "t9_bisect_vs_sweep")[0]
    checks += [
        (
            t9["total_minutes_diff"],
            c4["contrasts"]["bisect_confirm_minus_sweep"]["total_minutes"]["diff"],
        ),
        (t9["sweep_total_minutes"], c4["arms"]["sweep"]["metrics"]["mean_total_minutes"]),
    ]
    t1 = {(r["experiment"], r["arm"]): r for r in _csv(data_dir, "t1_violations")}
    checks.append(
        (
            t1[("E5_planners", "cpsat")]["executed_violations"],
            sum(c["arms"]["cpsat"]["metrics"]["executed_prereq_violations"] for c in e5["cells"]),
        )
    )
    assert len(checks) >= 10
    for got, want in checks:
        assert float(got) == float(want)


def test_missing_results_give_not_run_rows(tmp_path):
    d = str(tmp_path / "data")
    extract.main(str(tmp_path / "empty"), d)
    for name, (needed, _, _) in extract.TABLES.items():
        rows = _csv(d, name)
        assert rows and all(r["status"] == "not_run" for r in rows), name
        assert {r["source_file"] for r in rows} == {
            f"experiments_v2/results/{extract.FILES[k]}" for k in needed
        }
    render_tables.main(d, str(tmp_path / "t"))  # renders "not run" instead of numbers
    assert "not run" in open(tmp_path / "t" / "T1.md", encoding="utf-8").read()


@pytest.mark.parametrize("module", [render_tables, render_figures])
def test_render_scripts_never_open_results(module):
    tree = ast.parse(open(module.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "results" not in node.value, node.value
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
            assert not any("extract" in n or "results" in n or n == "json" for n in names), names


def test_rendering_twice_is_byte_identical(data_dir, tmp_path):
    for module in (render_tables, render_figures):
        a, b = str(tmp_path / f"{module.__name__}_a"), str(tmp_path / f"{module.__name__}_b")
        files = module.main(data_dir, a)
        module.main(data_dir, b)
        assert files
        names = sorted(os.listdir(a))
        assert names == sorted(os.listdir(b))
        match, mismatch, errors = filecmp.cmpfiles(a, b, names, shallow=False)
        assert not mismatch and not errors
    assert {
        os.path.splitext(n)[1]
        for n in os.listdir(tmp_path / "experiments_v2.report.render_figures_a")
    } == {".pdf", ".png"}
