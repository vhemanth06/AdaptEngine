import pytest
import subprocess
from adaptengine.cli import main

def test_cli_validate(capsys):
    ret = main(["validate", "--curriculum", "data/curriculum/curriculum_4node.json", "--activities", "data/curriculum/activities_4node.json"])
    assert ret is None
    out, _ = capsys.readouterr()
    assert "OK:" in out

def test_cli_validate_error(capsys, tmp_path):
    import json
    dummy_act = tmp_path / "dummy_act.json"
    dummy_act.write_text(json.dumps({"schema_version": 1, "activities": []}))
    ret = main(["validate", "--curriculum", "tests/fixtures/invalid/cycle.json", "--activities", str(dummy_act), "--allow-unreviewed"])
    assert ret == 2
    _, err = capsys.readouterr()
    assert "error:" in err
    assert "Cycle detected" in err

def test_cli_validate_unreviewed(capsys):
    ret = main(["validate", "--curriculum", "tests/fixtures/invalid/cycle.json", "--activities", "data/curriculum/activities_4node.json"])
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
    result = subprocess.run(["python3", "-m", "adaptengine", "validate", "--curriculum", "data/curriculum/curriculum_4node.json", "--activities", "data/curriculum/activities_4node.json"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "OK:" in result.stdout
