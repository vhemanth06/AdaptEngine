"""Results provenance without git (W7 §0.2): a content hash over src/**/*.py, an experiment hash
over the runners and their inputs, plus a UTC timestamp.

Never imported from src/.
"""

from __future__ import annotations

import glob
import hashlib
import os
import re
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def code_hash(root: str = REPO_ROOT) -> str:
    """SHA-256 over every src/**/*.py file (sorted relative path + bytes)."""
    src = os.path.join(root, "src")
    h = hashlib.sha256()
    paths = []
    for d, _, files in os.walk(src):
        paths += [os.path.join(d, f) for f in files if f.endswith(".py")]
    for p in sorted(paths, key=lambda p: os.path.relpath(p, src).replace(os.sep, "/")):
        h.update(os.path.relpath(p, src).replace(os.sep, "/").encode())
        h.update(b"\0")
        with open(p, "rb") as f:
            h.update(f.read())
        h.update(b"\0")
    return h.hexdigest()


def experiment_files(root: str = REPO_ROOT) -> list[str]:
    """Repo-relative paths covered by experiment_hash(): experiments/**/*.py,
    scripts/run_experiments.py, config/fitted_*.json, data/curriculum/*_x10.json.
    Excludes config/policy_frozen.json (an E4 output) and experiments/results/."""
    pats = (
        "experiments/**/*.py",
        "scripts/run_experiments.py",
        "config/fitted_*.json",
        "data/curriculum/*_x10.json",
    )
    rels = {
        os.path.relpath(p, root).replace(os.sep, "/")
        for pat in pats
        for p in glob.glob(os.path.join(root, pat), recursive=True)
        if os.path.isfile(p)
    }
    return sorted(
        r
        for r in rels
        if not r.startswith("experiments/results/") and r != "config/policy_frozen.json"
    )


def experiment_hash(root: str = REPO_ROOT) -> str:
    """SHA-256 over experiment_files() (sorted relative path + bytes), same scheme as code_hash."""
    h = hashlib.sha256()
    for rel in experiment_files(root):
        h.update(rel.encode())
        h.update(b"\0")
        with open(os.path.join(root, rel), "rb") as f:
            h.update(f.read())
        h.update(b"\0")
    return h.hexdigest()


PREREG_RES = {
    "code_hash": re.compile(r"^Code hash \(src/, SHA-256\): `([0-9a-f]{64})`\s*$", re.M),
    "experiment_hash": re.compile(r"^Experiment hash \(SHA-256\): `([0-9a-f]{64})`\s*$", re.M),
}


def prereg_hashes(path: str) -> dict[str, str | None]:
    """The registered hashes from a pre-registration file: {"code_hash", "experiment_hash"},
    each the hex of its parseable line, or None if the line is absent (or the file missing).
    The last matching line wins, so an amendment can re-register a hash."""
    txt = open(path).read() if os.path.isfile(path) else ""
    return {k: (m[-1] if (m := r.findall(txt)) else None) for k, r in PREREG_RES.items()}


def stamp() -> dict[str, str]:
    return {
        "code_hash": code_hash(),
        "experiment_hash": experiment_hash(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    print(f"code_hash       {code_hash()}")
    print(f"experiment_hash {experiment_hash()}")
