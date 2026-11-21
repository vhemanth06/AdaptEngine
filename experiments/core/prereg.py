"""Pre-registration guard (D47, D104): a full run starts only from a pre-registration whose status
is "Registered" and that records a registration time. `--smoke` runs are allowed.

The guard reads two lines:
    Status: Registered
    Registered UTC: 2026-11-21T10:00:00+00:00
Pre-registrations written before D104 also carry a "Code hash:" line; it is ignored.
"""

from __future__ import annotations

import glob
import os
import re

from .provenance import HARNESS_ROOT

PREREG_DIR = os.path.join(HARNESS_ROOT, "preregistration")


class NotRegistered(RuntimeError):
    pass


def find(exp: str) -> str:
    """The newest preregistration/<exp>_<date>.md."""
    hits = sorted(glob.glob(os.path.join(PREREG_DIR, f"{exp}_*.md")))
    if not hits:
        raise NotRegistered(f"no pre-registration for {exp} in {PREREG_DIR}")
    return hits[-1]


def read(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read()

    def last(label):
        found = re.findall(rf"^\s*[-*]?\s*\**{label}:\**\s*`?([^`\n]*?)`?\s*$", text, re.M | re.I)
        return found[-1].strip() if found else None

    return {
        "path": os.path.relpath(path, os.path.dirname(HARNESS_ROOT)).replace(os.sep, "/"),
        "status": last("Status"),
        "registered_utc": last("Registered UTC"),
    }


def guard(exp: str, smoke: bool, path: str | None = None) -> dict:
    """Pre-registration fields for the results file; raises NotRegistered for a bad full run."""
    if smoke:
        try:
            info = read(path or find(exp))
        except (NotRegistered, OSError):
            info = {"path": f"experiments/preregistration/{exp}_<date>.md"}
        return {**info, "registered_utc": info.get("registered_utc"), "smoke": True}
    info = read(path or find(exp))
    if (info["status"] or "").lower() != "registered":
        raise NotRegistered(f"{info['path']}: status is {info['status']!r}, not 'Registered'")
    if not info["registered_utc"]:
        raise NotRegistered(f"{info['path']}: no 'Registered UTC' time")
    return info
