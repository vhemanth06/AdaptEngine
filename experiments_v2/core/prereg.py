"""Pre-registration guard (D47): a full run starts only from a pre-registration whose status is
"Registered" and whose recorded code hash equals the current one. `--smoke` runs are allowed.

The file carries three lines the guard reads:
    Status: Registered
    Registered UTC: 2026-11-21T10:00:00+00:00
    Code hash: <64 hex>
An amendment may update the code hash with a later "Code hash:" line; the last one counts.
"""

from __future__ import annotations

import glob
import os
import re

from .provenance import V2_ROOT, code_hash

PREREG_DIR = os.path.join(V2_ROOT, "preregistration")


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
        "path": os.path.relpath(path, os.path.dirname(V2_ROOT)).replace(os.sep, "/"),
        "status": last("Status"),
        "registered_utc": last("Registered UTC"),
        "code_hash": last("Code hash"),
    }


def guard(exp: str, smoke: bool, path: str | None = None) -> dict:
    """Pre-registration fields for the results file; raises NotRegistered for a bad full run."""
    if smoke:
        try:
            info = read(path or find(exp))
        except (NotRegistered, OSError):
            info = {"path": f"experiments_v2/preregistration/{exp}_<date>.md"}
        return {**info, "registered_utc": info.get("registered_utc"), "smoke": True}
    info = read(path or find(exp))
    if (info["status"] or "").lower() != "registered":
        raise NotRegistered(f"{info['path']}: status is {info['status']!r}, not 'Registered'")
    if info["code_hash"] != code_hash():
        raise NotRegistered(
            f"{info['path']}: code hash {info['code_hash']!r} differs from the current "
            f"{code_hash()!r}; add a dated amendment before running"
        )
    if not info["registered_utc"]:
        raise NotRegistered(f"{info['path']}: no 'Registered UTC' time")
    return info
