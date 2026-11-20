"""Plan 2.5 (D89): --config / --model-profile on every CLI command (P2.5-TC1 to TC4).

tests/fixtures/cli_default_runs.json holds the stdout and written snapshot files of a fixed set of
CLI runs, recorded before Plan 2.5 changed cli.py. Re-record only on a deliberate CLI change:
python -c "from tests.test_cli_config import record_default_runs; record_default_runs()"
"""

import contextlib
import dataclasses
import io
import json
import os
import subprocess
import sys

import pytest

from adaptengine.api import Engine
from adaptengine.cli import main
from adaptengine.core.config import DEFAULT_CONFIG, config_from_file, config_hash
from adaptengine.core.errors import ValidationError
from adaptengine.core.schema import Event, EventType, PlanContext
from adaptengine.planner import serialize_plan
from adaptengine.session import load_snapshot

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(repo_root, "tests", "fixtures", "cli_default_runs.json")
C4 = ["--curriculum", "data/curriculum/curriculum_4node.json"]
A4 = ["--activities", "data/curriculum/activities_4node.json"]
C8 = ["--curriculum", "data/curriculum/curriculum_8node.json"]
A8 = ["--activities", "data/curriculum/activities_8node.json"]
ASSIST = "config/fitted_assist09.json"


def _call(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        ret = main(argv)
    return ret, out.getvalue(), err.getvalue()


def default_runs(tmp: str, extra=()) -> dict:
    """The P2.5-T0 run set; `extra` is appended to every command (e.g. --model pybkt)."""
    snap = os.path.join(tmp, "snap.json")
    runs = [
        ("validate4", ["validate", *C4, *A4]),
        ("validate8", ["validate", *C8, *A8]),
        ("show4", ["show", *C4, *A4]),
        ("show8", ["show", *C8, *A8]),
        (
            "init8",
            [
                "init-learner",
                *C8,
                *A8,
                "--snapshot",
                snap,
                "--goal",
                "C8",
                "--deadline",
                "10",
                "--budget",
                "15",
            ],
        ),
        (
            "update_correct",
            [
                "update",
                *C8,
                *A8,
                "--snapshot",
                snap,
                "--activity",
                "E-C1-0.2",
                "--response",
                "correct",
                "--day",
                "1",
            ],
        ),
        (
            "update_incorrect",
            [
                "update",
                *C8,
                *A8,
                "--snapshot",
                snap,
                "--activity",
                "E-C2-0.4",
                "--response",
                "incorrect",
                "--day",
                "1",
            ],
        ),
        ("plan_json", ["plan", *C8, *A8, "--snapshot", snap, "--json"]),
        ("plan_text", ["plan", *C8, *A8, "--snapshot", snap]),
        ("missed_day", ["missed-day", *C8, *A8, "--snapshot", snap, "--day", "2"]),
        ("replan_json", ["replan", *C8, *A8, "--snapshot", snap, "--current-day", "3", "--json"]),
    ]
    out = {}
    for name, argv in runs:
        model_ok = argv[0] in ("update", "plan", "replan", "missed-day")
        ret, stdout, _ = _call(argv + (list(extra) if model_ok else []))
        snap_bytes = open(snap, encoding="utf-8").read() if os.path.exists(snap) else None
        out[name] = {
            "ret": ret,
            # config_hash moves whenever a plan adds an EngineConfig field (ground rule 8)
            "stdout": stdout.replace(tmp, "<TMP>").replace(
                config_hash(DEFAULT_CONFIG), "<CONFIG_HASH>"
            ),
            "snapshot": snap_bytes,
        }
    return out


def record_default_runs():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        data = {"custombkt_default": default_runs(tmp)}
    with tempfile.TemporaryDirectory() as tmp:
        data["model_pybkt"] = default_runs(tmp, ["--model", "pybkt"])
    with open(FIXTURE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write("\n")


def _fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


# ---------------- P2.5-TC1 / TC4: defaults and --model alone unchanged ----------------


def test_default_runs_byte_identical_p25_tc1(tmp_path):
    assert default_runs(str(tmp_path)) == _fixture()["custombkt_default"]


def test_model_pybkt_alone_unchanged_p25_tc4(tmp_path):
    assert default_runs(str(tmp_path), ["--model", "pybkt"]) == _fixture()["model_pybkt"]


def test_model_custombkt_alone_equals_default_p25_tc4(tmp_path):
    assert default_runs(str(tmp_path), ["--model", "custombkt"]) == _fixture()["custombkt_default"]


# ---------------- P2.5-T1: config file loader ----------------


def _cfg_file(tmp_path, obj, name="cfg.json"):
    p = tmp_path / name
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj))
    return str(p)


def test_config_from_file_overrides_only_given_fields(tmp_path):
    cfg = config_from_file(_cfg_file(tmp_path, {"theta": 0.9, "allowed_budgets": [5, 15]}))
    assert cfg == dataclasses.replace(DEFAULT_CONFIG, theta=0.9, allowed_budgets=(5, 15))
    assert isinstance(cfg.allowed_budgets, tuple)
    assert config_from_file(_cfg_file(tmp_path, {})) == DEFAULT_CONFIG


@pytest.mark.parametrize(
    "obj,msg",
    [
        ({"thetaa": 0.9}, "unknown"),
        ({"theta": 2}, "theta"),
        ({"model_profile": "config/missing.json"}, "model_profile"),
        ("[1, 2]", "object"),
        ("{not json", "json"),
    ],
)
def test_config_from_file_rejects_bad_files(tmp_path, obj, msg):
    with pytest.raises(ValidationError, match=f"(?i){msg}"):
        config_from_file(_cfg_file(tmp_path, obj))


def test_config_from_file_missing_file(tmp_path):
    with pytest.raises(ValidationError, match="(?i)config file"):
        config_from_file(str(tmp_path / "nope.json"))


# ---------------- P2.5-TC2: CLI results equal the Python Engine ----------------


def _init(tmp_path, *extra):
    snap = str(tmp_path / "snap.json")
    ret, _, _ = _call(
        [
            "init-learner",
            *C8,
            *A8,
            "--snapshot",
            snap,
            "--goal",
            "C8",
            "--deadline",
            "10",
            "--budget",
            "15",
            *extra,
        ]
    )
    assert ret is None
    return snap


def _python_update(cfg, activity="E-C1-0.2", correct=True):
    eng = Engine.from_files(
        os.path.join(repo_root, C8[1]), os.path.join(repo_root, A8[1]), config=cfg
    )
    act = eng.activities[activity]
    ev = Event(
        day=1,
        kind=EventType.COMPLETED,
        activity_id=activity,
        minutes_elapsed=act.duration,
        correct=correct,
    )
    state, _ = eng.record(eng.init_learner(), _empty_log(), ev)
    return state.concepts[act.target_concept].p


def _empty_log():
    from adaptengine.learner.state import ExecutionLog

    return ExecutionLog()


def _cli_update_p(tmp_path, *opts, activity="E-C1-0.2", response="correct"):
    snap = _init(tmp_path, *opts)
    ret, _, err = _call(
        [
            "update",
            *C8,
            *A8,
            "--snapshot",
            snap,
            "--activity",
            activity,
            "--response",
            response,
            "--day",
            "1",
            *opts,
        ]
    )
    assert ret is None, err
    state, _ = load_snapshot(snap, ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"))
    return state.concepts["C" + activity.split("-")[1][1:]].p, err


def test_update_with_model_profile_equals_python_p25_tc2(tmp_path):
    p_cli, err = _cli_update_p(tmp_path, "--model-profile", ASSIST)
    cfg = dataclasses.replace(DEFAULT_CONFIG, model_profile=ASSIST)
    assert p_cli == _python_update(cfg)
    assert p_cli != _python_update(DEFAULT_CONFIG)
    assert "INFO: config: model_profile=config/fitted_assist09.json" in err


def test_update_with_config_file_naming_profile_p25_tc2(tmp_path):
    f = _cfg_file(tmp_path, {"model_profile": ASSIST})
    p_cli, _ = _cli_update_p(tmp_path, "--config", f)
    assert p_cli == _python_update(dataclasses.replace(DEFAULT_CONFIG, model_profile=ASSIST))


def test_use_profile_learn_via_config_p25_tc2(tmp_path):
    f = _cfg_file(tmp_path, {"model_profile": ASSIST, "use_profile_learn": True})
    p_cli, _ = _cli_update_p(tmp_path, "--config", f)
    with_learn = dataclasses.replace(DEFAULT_CONFIG, model_profile=ASSIST, use_profile_learn=True)
    assert p_cli == _python_update(with_learn)
    assert p_cli != _python_update(dataclasses.replace(DEFAULT_CONFIG, model_profile=ASSIST))


def _plan_json(tmp_path, *opts):
    snap = _init(tmp_path, *opts)
    ret, out, err = _call(["plan", *C8, *A8, "--snapshot", snap, "--json", *opts])
    assert ret is None, err
    return json.loads(out)


def _python_plan(cfg):
    eng = Engine.from_files(
        os.path.join(repo_root, C8[1]), os.path.join(repo_root, A8[1]), config=cfg
    )
    ctx = PlanContext(goal="C8", deadline_day=10, budget=15)
    return json.loads(json.dumps(serialize_plan(eng.plan(eng.init_learner(), ctx), eng.config)))


def test_plan_json_with_profile_equals_python_p25_tc2(tmp_path):
    got = _plan_json(tmp_path, "--model-profile", ASSIST)
    assert got == _python_plan(dataclasses.replace(DEFAULT_CONFIG, model_profile=ASSIST))
    assert "model_profile" in got


def test_other_fields_via_config_reach_engine_p25_tc2(tmp_path):
    f = _cfg_file(tmp_path, {"theta": 0.95, "k_responses": 3})
    got = _plan_json(tmp_path, "--config", f)
    want = _python_plan(dataclasses.replace(DEFAULT_CONFIG, theta=0.95, k_responses=3))
    assert got == want and got != _python_plan(DEFAULT_CONFIG)


def test_init_learner_uses_p0_from_config(tmp_path):
    snap = _init(tmp_path, "--config", _cfg_file(tmp_path, {"p0": 0.3}))
    state, _ = load_snapshot(snap, ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"))
    assert {c.p for c in state.concepts.values()} == {0.3}


def test_model_profile_overrides_config_file(tmp_path):
    f = _cfg_file(tmp_path, {"model_profile": "config/fitted_ct.json"})
    p_cli, err = _cli_update_p(tmp_path, "--config", f, "--model-profile", ASSIST)
    assert p_cli == _python_update(dataclasses.replace(DEFAULT_CONFIG, model_profile=ASSIST))
    assert "model_profile=config/fitted_assist09.json" in err


# ---------------- P2.5-TC3: errors ----------------


def test_model_with_profile_is_an_error_p25_tc3(tmp_path):
    snap = _init(tmp_path)
    ret, _, err = _call(
        [
            "update",
            *C8,
            *A8,
            "--snapshot",
            snap,
            "--activity",
            "E-C1-0.2",
            "--response",
            "correct",
            "--day",
            "1",
            "--model",
            "custombkt",
            "--model-profile",
            ASSIST,
        ]
    )
    assert ret == 2
    assert "error: --model cannot be combined with a fitted model profile" in err


@pytest.mark.parametrize("obj", [{"bogus": 1}, {"theta": 2}, "{not json"])
def test_bad_config_file_cli_error_p25_tc3(tmp_path, obj):
    ret, _, err = _call(["validate", *C4, *A4, "--config", _cfg_file(tmp_path, obj)])
    assert ret == 2 and err.startswith("error:")


def test_missing_config_file_cli_error_p25_tc3(tmp_path):
    ret, _, err = _call(["validate", *C4, *A4, "--config", str(tmp_path / "nope.json")])
    assert ret == 2 and "config file" in err


def test_subprocess_plan_with_profile_prints_info_line(tmp_path):
    snap = _init(tmp_path)
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "adaptengine",
            "plan",
            *C8,
            *A8,
            "--snapshot",
            snap,
            "--model-profile",
            ASSIST,
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert r.returncode == 0, r.stderr
    assert "INFO: config: model_profile=config/fitted_assist09.json, config_hash=" in r.stderr
    assert json.loads(r.stdout)["model_profile"]["profile"] == "fitted_assist09"
