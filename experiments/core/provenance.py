"""Provenance of a run: UTC time and machine. Code provenance is the git commit (D104)."""

from __future__ import annotations

import hashlib
import os
import platform
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HARNESS_ROOT = os.path.join(REPO_ROOT, "experiments")


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
