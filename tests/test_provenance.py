"""W8 0.3: code_hash() is a deterministic SHA-256 over src/**/*.py that changes with the code."""

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from experiments.provenance import code_hash, stamp  # noqa: E402


def test_code_hash_deterministic_and_sensitive(tmp_path):
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "a.py").write_text("x = 1\n")
    (pkg / "notes.txt").write_text("ignored")
    h1 = code_hash(str(tmp_path))
    assert h1 == code_hash(str(tmp_path)) and len(h1) == 64
    (pkg / "notes.txt").write_text("still ignored")
    assert code_hash(str(tmp_path)) == h1
    (pkg / "a.py").write_text("x = 2\n")
    assert code_hash(str(tmp_path)) != h1
    s = stamp()
    assert set(s) == {"code_hash", "timestamp_utc"} and s["code_hash"] == code_hash()
