"""Results provenance without git (W7 §0.2): a content hash over src/**/*.py plus a UTC timestamp.

Never imported from src/.
"""

from __future__ import annotations

import hashlib
import os
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


def stamp() -> dict[str, str]:
    return {"code_hash": code_hash(), "timestamp_utc": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    print(code_hash())
