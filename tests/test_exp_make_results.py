import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

HEADERS = (
    "Violations",
    "Headline cell",
    "Goal mastery vs static_loop",
    "Ablations",
    "What changed since W8",
    "Stress grid",
    "Diagnostic matrix",
    "Sensitivity",
    "Policy and OPE",
    "Extensions",
    "CP-SAT and latency",
)


@pytest.fixture(scope="session")
def smoke_dir(tmp_path_factory):
    from experiments import (
        run_diag,
        run_extensions,
        run_grid,
        run_planner_cost,
        run_policy,
        run_sensitivity,
    )

    d = str(tmp_path_factory.mktemp("smoke"))
    run_grid.main(["--smoke", "--out-dir", d])
    run_diag.main(["--smoke", "--out-dir", d])
    run_sensitivity.main(["--smoke", "--out-dir", d])
    run_policy.main(["train", "--smoke", "--out-dir", d])
    run_policy.main(["eval", "--smoke", "--out-dir", d])
    run_extensions.main(["all", "--smoke", "--out-dir", d])
    run_planner_cost.main(["all", "--smoke", "--out-dir", d])
    return d


def test_make_results_on_smoke(smoke_dir):
    from experiments import make_results

    make_results.main(["--smoke", "--out-dir", smoke_dir])
    text = open(os.path.join(smoke_dir, "RESULTS_smoke.md")).read()
    for h in HEADERS:
        assert re.search(rf"^## \d+\. {re.escape(h)}", text, re.M), h
    assert "not run (file missing)" not in text
    for h in ("diagnostic min", "items per mastered concept", "reach rate"):
        assert text.count(h) >= 2, h  # headline table and per-cell companion
    assert "not stored" not in text and "no CI on these bars" not in text
    assert "| n/a |" in text  # E4 plan prereq is not recorded, never shown as 0
    assert "Kaplan-Meier curves" in text and "10 equal-width bins" in text
    assert "−" in text and "point difference" not in text.lower()
    figs = [f for f in os.listdir(os.path.join(smoke_dir, "figures")) if f.startswith("results_")]
    assert len(figs) == 4
    # every table and every figure is followed by a Source line
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if (ln.startswith("|") and not nxt.startswith("|")) or ln.startswith("!["):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            assert lines[j].startswith("Source: `"), (i, ln[:60])
    assert re.search(r"code hash `[0-9a-f]{12}`", text)


def test_missing_files_do_not_crash(tmp_path):
    from experiments import make_results

    make_results.main(["--smoke", "--out-dir", str(tmp_path)])
    text = (tmp_path / "RESULTS_smoke.md").read_text()
    assert text.count("not run (file missing)") >= 8


def test_make_results_reports_registered_extras(smoke_dir):
    from experiments import make_results

    make_results.main(["--smoke", "--out-dir", smoke_dir])
    text = open(os.path.join(smoke_dir, "RESULTS_smoke.md")).read()
    for h in ("INFERRED precision", "n inferred", "stop reasons", "≤ 12 concepts",
              "not budget-matched", "informative censoring", "already mastered at day 0",
              "state distribution"):  # fmt: skip
        assert h in text, h
    assert text.count("diagnostic items") >= 2
    # deterministic E4 variant makes no policy decisions: agreement is "—", never 0.000
    det = [ln for ln in text.splitlines() if ln.startswith("| S1\\|4node_x10 | deterministic |")]
    assert det and all(ln.split(" | ")[7:9] == ["0", "—"] for ln in det), det


def test_provenance_warning(smoke_dir, tmp_path, monkeypatch):
    import shutil

    from experiments import make_results
    from experiments.provenance import code_hash, experiment_hash

    pre = tmp_path / "pre.md"
    monkeypatch.setattr(make_results, "PREREG", str(pre))
    reg = f"Code hash (src/, SHA-256): `{code_hash()}`\n"
    pre.write_text(reg + f"Experiment hash (SHA-256): `{experiment_hash()}`\n")
    make_results.main(["--smoke", "--out-dir", smoke_dir])
    text = open(os.path.join(smoke_dir, "RESULTS_smoke.md")).read()
    assert "WARNING: INPUTS DO NOT MATCH" not in text and "Provenance: every input" in text

    pre.write_text(reg + f"Experiment hash (SHA-256): `{'0' * 64}`\n")
    d = tmp_path / "copy"
    shutil.copytree(smoke_dir, d)
    os.remove(d / "hlr_fit_smoke.json")
    make_results.main(["--smoke", "--out-dir", str(d)])
    top = (d / "RESULTS_smoke.md").read_text().split("## Approximations")[0]
    assert "WARNING: INPUTS DO NOT MATCH" in top and "`hlr_fit_smoke.json` missing" in top
    assert "`grid_smoke.json` experiment_hash" in top and "code_hash" not in top
    assert "`planner_cost_smoke.json`[cpsat] experiment_hash" in top
