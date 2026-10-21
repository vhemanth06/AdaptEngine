import subprocess
import sys
from adaptengine.cli import main


def test_cli_validate(capsys):
    ret = main(
        [
            "validate",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
        ]
    )
    assert ret is None
    out, _ = capsys.readouterr()
    assert "OK:" in out


def test_cli_validate_error(capsys, tmp_path):
    import json

    dummy_act = tmp_path / "dummy_act.json"
    dummy_act.write_text(json.dumps({"schema_version": 1, "activities": []}))
    ret = main(
        [
            "validate",
            "--curriculum",
            "tests/fixtures/invalid/cycle.json",
            "--activities",
            str(dummy_act),
            "--allow-unreviewed",
        ]
    )
    assert ret == 2
    _, err = capsys.readouterr()
    assert "error:" in err
    assert "Cycle detected" in err


def test_cli_validate_unreviewed(capsys):
    ret = main(
        [
            "validate",
            "--curriculum",
            "tests/fixtures/invalid/cycle.json",
            "--activities",
            "data/curriculum/activities_4node.json",
        ]
    )
    assert ret == 2
    _, err = capsys.readouterr()
    assert "error:" in err
    assert "No entry in manifest" in err


def test_cli_show(capsys):
    ret = main(["show", "--curriculum", "data/curriculum/curriculum_4node.json"])
    assert ret is None
    out, _ = capsys.readouterr()
    assert "C1" in out


def test_cli_subprocess():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "adaptengine",
            "validate",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "OK:" in result.stdout


def test_cli_model_flag_selection(capsys, tmp_path):
    snap_path = str(tmp_path / "snap.json")
    ret_init = main(
        [
            "init-learner",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--goal",
            "C4",
            "--deadline",
            "10",
            "--budget",
            "15",
        ]
    )
    assert ret_init is None

    ret_upd = main(
        [
            "update",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--activity",
            "E-C1-0.2",
            "--response",
            "correct",
            "--day",
            "1",
            "--model",
            "pybkt",
        ]
    )
    assert ret_upd is None
    out, _ = capsys.readouterr()
    assert "C1: p" in out

    ret_replan = main(
        [
            "replan",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--model",
            "pybkt",
        ]
    )
    assert ret_replan is None
    out, _ = capsys.readouterr()
    assert "Status: FEASIBLE" in out
