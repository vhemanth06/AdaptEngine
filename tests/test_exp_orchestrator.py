import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import run_experiments as ro  # noqa: E402


A = "a" * 64
B = "b" * 64


def _patch(monkeypatch, tmp_path, hash_now=A, exp_now=B):
    pre = tmp_path / "pre.md"
    pre.write_text(f"x\nCode hash (src/, SHA-256): `{A}`\n\nExperiment hash (SHA-256): `{B}`\n")
    calls = []
    monkeypatch.setattr(ro, "code_hash", lambda: hash_now)
    monkeypatch.setattr(ro, "experiment_hash", lambda: exp_now)
    monkeypatch.setattr(ro.subprocess, "call", lambda cmd, **k: calls.append(cmd) or 0)
    return str(pre), calls


@pytest.mark.parametrize("kw,which", [({"hash_now": "f" * 64}, "code_hash"),
                                      ({"exp_now": "f" * 64}, "experiment_hash")])  # fmt: skip
def test_hash_mismatch_refuses(monkeypatch, tmp_path, kw, which):
    pre, calls = _patch(monkeypatch, tmp_path, **kw)
    with pytest.raises(SystemExit) as e:
        ro.main(["--prereg", pre, "--out-dir", str(tmp_path)])
    assert e.value.code not in (0, None) and "REFUSED" in str(e.value.code)
    assert which in str(e.value.code) and calls == []


def test_missing_experiment_hash_line_refuses(monkeypatch, tmp_path):
    pre, calls = _patch(monkeypatch, tmp_path)
    (tmp_path / "pre.md").write_text(f"Code hash (src/, SHA-256): `{A}`\n")
    with pytest.raises(SystemExit) as e:
        ro.main(["--prereg", pre])
    assert "experiment_hash" in str(e.value.code) and calls == []


def test_hash_checked_before_every_step(monkeypatch, tmp_path):
    pre, calls = _patch(monkeypatch, tmp_path)
    seq = iter([B, B, "f" * 64])  # code edited after the second step
    monkeypatch.setattr(ro, "experiment_hash", lambda: next(seq))
    with pytest.raises(SystemExit) as e:
        ro.main(["--prereg", pre, "--out-dir", str(tmp_path)])
    assert "REFUSED" in str(e.value.code) and len(calls) == 2


def test_e1_always_resumes(monkeypatch, tmp_path):
    pre, calls = _patch(monkeypatch, tmp_path)
    ro.main(["--prereg", pre, "--out-dir", str(tmp_path)])
    e1 = [c for c in calls if c[1].endswith("run_grid.py")]
    assert len(e1) == 1 and "--resume" in e1[0] and e1[0][2:5] == ["--grid", "both", "--resume"]


def test_from_runs_rest_then_results(monkeypatch, tmp_path):
    pre, calls = _patch(monkeypatch, tmp_path)
    ro.main(["--prereg", pre, "--from", "E4", "--out-dir", str(tmp_path)])
    names = [os.path.basename(c[1]) for c in calls]
    assert names == ["run_policy.py", "run_policy.py", "run_extensions.py",
                     "run_planner_cost.py", "make_results.py"]  # fmt: skip


def test_only_runs_results_unless_no_results(monkeypatch, tmp_path):
    pre, calls = _patch(monkeypatch, tmp_path)
    ro.main(["--prereg", pre, "--only", "E2", "E6", "--out-dir", str(tmp_path)])
    names = [os.path.basename(c[1]) for c in calls]
    assert names == ["run_diag.py", "run_planner_cost.py", "make_results.py"]
    calls.clear()
    ro.main(["--prereg", pre, "--only", "E2", "--no-results"])
    assert [os.path.basename(c[1]) for c in calls] == ["run_diag.py"]
    with pytest.raises(SystemExit):  # --only and --from are exclusive
        ro.main(["--prereg", pre, "--only", "E2", "--from", "E3"])


def test_command_order(monkeypatch, tmp_path):
    pre, calls = _patch(monkeypatch, tmp_path)
    ro.main(["--prereg", pre, "--out-dir", str(tmp_path), "--smoke"])
    names = [
        os.path.basename(c[1]) + " " + (c[2] if c[2] in ("train", "eval") else "") for c in calls
    ]
    runners = [n.strip() for n in names]
    assert [r for r in runners if r.startswith("run_")] == [
        "run_grid.py",
        "run_diag.py",
        "run_sensitivity.py",
        "run_policy.py train",
        "run_policy.py eval",
        "run_extensions.py",
        "run_planner_cost.py",
    ]
    assert all("--smoke" in c for c in calls if "run_" in c[1])
    pol = [c for c in calls if "run_policy.py" in c[1]]
    assert all(str(tmp_path / "policy_frozen.json") in c for c in pol)


def test_make_results_gets_smoke_only_in_smoke_mode(monkeypatch, tmp_path):
    pre, calls = _patch(monkeypatch, tmp_path)
    ro.main(["--prereg", pre, "--out-dir", str(tmp_path), "--smoke"])
    mk = [c for c in calls if c[1].endswith("make_results.py")]
    assert len(mk) == 1 and "--smoke" in mk[0] and str(tmp_path) in mk[0]
    calls.clear()
    ro.main(["--prereg", pre, "--out-dir", str(tmp_path)])
    mk = [c for c in calls if c[1].endswith("make_results.py")]
    assert len(mk) == 1 and "--smoke" not in mk[0]


def test_only_e2(monkeypatch, tmp_path):
    pre, calls = _patch(monkeypatch, tmp_path)
    ro.main(["--prereg", pre, "--only", "E2", "--out-dir", str(tmp_path)])
    assert [os.path.basename(c[1]) for c in calls[:1]] == ["run_diag.py"]
    assert not any("run_grid" in c[1] for c in calls)


def test_stops_on_failure(monkeypatch, tmp_path):
    pre, calls = _patch(monkeypatch, tmp_path)
    monkeypatch.setattr(ro.subprocess, "call", lambda cmd, **k: calls.append(cmd) or 3)
    with pytest.raises(SystemExit) as e:
        ro.main(["--prereg", pre, "--out-dir", str(tmp_path)])
    assert e.value.code == 3 and len(calls) == 1


def test_smoke_without_out_dir_e4_cannot_target_real_frozen():
    for cmd in ro.build_commands(smoke=True, only=["E4"]):
        assert "--smoke" in cmd and "--frozen-path" not in cmd  # runner defaults to *_smoke.json
        assert not any(a.endswith("config/policy_frozen.json") for a in cmd)
