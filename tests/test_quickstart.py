"""Tests for examples/api_quickstart.py execution and verification."""

import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_api_quickstart_execution():
    script_path = os.path.join(REPO_ROOT, "examples", "api_quickstart.py")
    res = subprocess.run(
        [sys.executable, script_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"api_quickstart.py failed with stderr: {res.stderr}"
    lines = res.stdout.strip().splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("FEASIBLE [('L-C1'")
    assert lines[1] == "FEASIBLE [3, 4]"
    assert len(lines[2]) == 12  # 12-char config hash prefix
