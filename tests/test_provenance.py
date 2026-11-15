"""W8 0.3: code_hash() is a deterministic SHA-256 over src/**/*.py that changes with the code."""

import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from experiments.provenance import (  # noqa: E402
    code_hash,
    experiment_files,
    experiment_hash,
    prereg_hashes,
    stamp,
)


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
    assert set(s) == {"code_hash", "experiment_hash", "timestamp_utc"}
    assert s["code_hash"] == code_hash() and s["experiment_hash"] == experiment_hash()


def _touch(root, rel, text="x"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_experiment_hash_scope(tmp_path):
    for rel in ("experiments/run_x.py", "experiments/sub/y.py", "scripts/run_experiments.py",
                "config/fitted_S1.json", "data/curriculum/curriculum_4node_x10.json"):  # fmt: skip
        _touch(tmp_path, rel)
    covered = experiment_files(str(tmp_path))
    assert len(covered) == 5
    h1 = experiment_hash(str(tmp_path))
    for rel in ("config/policy_frozen.json", "experiments/results/grid.json",
                "experiments/results/x.py", "scripts/other.py", "src/a.py",
                "data/curriculum/curriculum_4node.json", "experiments/notes.md"):  # fmt: skip
        _touch(tmp_path, rel)
    assert experiment_files(str(tmp_path)) == covered and experiment_hash(str(tmp_path)) == h1
    for rel in covered:
        _touch(tmp_path, rel, "changed")
        h2 = experiment_hash(str(tmp_path))
        assert h2 != h1
        h1 = h2


def test_prereg_hashes(tmp_path):
    p = tmp_path / "pre.md"
    assert prereg_hashes(str(p)) == {"code_hash": None, "experiment_hash": None}
    p.write_text(f"Code hash (src/, SHA-256): `{'a' * 64}`\ntext\n"
                 f"Experiment hash (SHA-256): `{'b' * 64}`\n"
                 f"Experiment hash (SHA-256): `{'c' * 64}`\n")  # fmt: skip
    assert prereg_hashes(str(p)) == {"code_hash": "a" * 64, "experiment_hash": "c" * 64}
