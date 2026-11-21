"""Provenance without git: content hashes of the engine and of this harness, and UTC time."""

from __future__ import annotations

import hashlib
import os
import platform
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
V2_ROOT = os.path.join(REPO_ROOT, "experiments_v2")


def tree_hash(root: str) -> str:
    """SHA-256 over every *.py file under root (sorted relative path, NUL, bytes, NUL)."""
    paths = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        paths += [os.path.join(d, f) for f in files if f.endswith(".py")]
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda p: os.path.relpath(p, root).replace(os.sep, "/")):
        h.update(os.path.relpath(p, root).replace(os.sep, "/").encode())
        h.update(b"\0")
        with open(p, "rb") as f:
            h.update(f.read())
        h.update(b"\0")
    return h.hexdigest()


def code_hash() -> str:
    """The engine's code hash: src/**/*.py (same definition as the rest of the project)."""
    return tree_hash(os.path.join(REPO_ROOT, "src"))


def harness_hash() -> str:
    """This harness: experiments_v2/**/*.py."""
    return tree_hash(V2_ROOT)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def machine() -> dict:
    cpu = platform.processor() or ""
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            cpu = next(
                (ln.split(":", 1)[1].strip() for ln in f if ln.startswith("model name")), cpu
            )
    except OSError:
        pass
    return {"cpu": cpu, "cpu_count": os.cpu_count(), "python": platform.python_version()}


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    print("code_hash", code_hash())
    print("harness_hash", harness_hash())
