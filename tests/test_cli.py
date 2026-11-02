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


def test_cli_error_cases_exit_code_and_stderr():
    """Verify CLI error cases return exit code 2, single-line message, and no traceback."""
    test_cases = [
        # 1. Missing file
        (
            [
                sys.executable,
                "-m",
                "adaptengine",
                "validate",
                "--curriculum",
                "non_existent.json",
                "--activities",
                "data/curriculum/activities_4node.json",
            ],
            "No entry in manifest for non_existent.json",
        ),
        # 2. Unreviewed content without --allow-unreviewed
        (
            [
                sys.executable,
                "-m",
                "adaptengine",
                "validate",
                "--curriculum",
                "tests/fixtures/invalid/cycle.json",
                "--activities",
                "data/curriculum/activities_4node.json",
            ],
            "No entry in manifest for tests/fixtures/invalid/cycle.json",
        ),
        # 3. Unknown goal
        (
            [
                sys.executable,
                "-m",
                "adaptengine",
                "plan",
                "--curriculum",
                "data/curriculum/curriculum_4node.json",
                "--activities",
                "data/curriculum/activities_4node.json",
                "--goal",
                "UNKNOWN_CONCEPT",
                "--deadline",
                "5",
                "--budget",
                "15",
            ],
            "Goal concept 'UNKNOWN_CONCEPT' not in graph",
        ),
        # 4. Budget not in {5, 10, 15, 30}
        (
            [
                sys.executable,
                "-m",
                "adaptengine",
                "plan",
                "--curriculum",
                "data/curriculum/curriculum_4node.json",
                "--activities",
                "data/curriculum/activities_4node.json",
                "--goal",
                "C4",
                "--deadline",
                "5",
                "--budget",
                "12",
            ],
            "budget must be one of (5, 10, 15, 30), got 12",
        ),
        # 5. Deadline 0
        (
            [
                sys.executable,
                "-m",
                "adaptengine",
                "plan",
                "--curriculum",
                "data/curriculum/curriculum_4node.json",
                "--activities",
                "data/curriculum/activities_4node.json",
                "--goal",
                "C4",
                "--deadline",
                "0",
                "--budget",
                "15",
            ],
            "deadline_day must be a positive integer >= 1, got 0",
        ),
    ]

    for cmd, expected_err in test_cases:
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 2, f"Expected returncode 2 for {cmd}, got {res.returncode}"
        assert "Traceback" not in res.stderr, f"Traceback found in stderr for {cmd}: {res.stderr}"
        err_lines = [line for line in res.stderr.strip().splitlines() if line]
        assert len(err_lines) == 1, f"Expected single-line stderr, got: {res.stderr}"
        assert expected_err in err_lines[0], f"Expected '{expected_err}' in '{err_lines[0]}'"


def test_cli_json_roundtrip(tmp_path):
    """Verify plan --json and replan --json output valid JSON with config_hash and trace."""
    import json

    snap_path = str(tmp_path / "snap.json")

    # 1. init-learner
    ret_init = subprocess.run(
        [
            sys.executable,
            "-m",
            "adaptengine",
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
        ],
        capture_output=True,
        text=True,
    )
    assert ret_init.returncode == 0

    # 2. plan --json
    res_plan = subprocess.run(
        [
            sys.executable,
            "-m",
            "adaptengine",
            "plan",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert res_plan.returncode == 0
    plan_data = json.loads(res_plan.stdout)
    assert "config_hash" in plan_data
    assert "trace" in plan_data
    assert plan_data["status"] == "FEASIBLE"

    # 3. replan --json
    res_replan = subprocess.run(
        [
            sys.executable,
            "-m",
            "adaptengine",
            "replan",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert res_replan.returncode == 0
    replan_data = json.loads(res_replan.stdout)
    assert "config_hash" in replan_data
    assert "trace" in replan_data
    assert replan_data["config_hash"] == plan_data["config_hash"]
    assert replan_data["status"] == "FEASIBLE"
