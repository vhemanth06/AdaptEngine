"""The one results format of every experiment (Plan V2 §V2.6): build, validate, write."""

from __future__ import annotations

import json
import os
import time

from adaptengine.core.config import DEFAULT_CONFIG, config_hash

from .provenance import REPO_ROOT, code_hash, harness_hash, machine, utc_now

TIMING_FIELDS = ("started_utc", "finished_utc", "wall_s")
REQUIRED = {
    "experiment": str,
    "preregistration": str,
    "registered_utc": (str, type(None)),
    "code_hash": str,
    "harness_hash": str,
    "config_hash_default": str,
    "started_utc": str,
    "finished_utc": str,
    "wall_s": (int, float),
    "procs": int,
    "design": dict,
    "content_review": dict,
    "cells": list,
    "hypotheses": dict,
    "reused": dict,
}


class Run:
    """Collects provenance at the start of a run; `finish` builds the results document."""

    def __init__(self, experiment: str, prereg: dict, procs: int):
        self.experiment, self.prereg, self.procs = experiment, prereg, procs
        self.started, self.t0 = utc_now(), time.time()
        self.code, self.harness = code_hash(), harness_hash()

    def finish(self, design, content_review, cells, hypotheses, reused=None, **extra) -> dict:
        doc = {
            "experiment": self.experiment,
            "preregistration": self.prereg.get("path", ""),
            "registered_utc": self.prereg.get("registered_utc"),
            "code_hash": self.code,
            "harness_hash": self.harness,
            "config_hash_default": config_hash(DEFAULT_CONFIG),
            "started_utc": self.started,
            "finished_utc": utc_now(),
            "wall_s": round(time.time() - self.t0, 1),
            "procs": self.procs,
            "machine": machine(),
            "smoke": bool(self.prereg.get("smoke")),
            "design": design,
            "content_review": content_review,
            "cells": cells,
            "hypotheses": hypotheses,
            "reused": reused or {},
            **extra,
        }
        validate(doc)
        return doc


def validate(doc: dict) -> None:
    """Raise ValueError if the document does not follow the schema."""
    for k, t in REQUIRED.items():
        if k not in doc:
            raise ValueError(f"results: missing field {k!r}")
        if not isinstance(doc[k], t):
            raise ValueError(f"results: field {k!r} has type {type(doc[k]).__name__}")
    for k in ("code_hash", "harness_hash", "config_hash_default"):
        if len(doc[k]) != 64:
            raise ValueError(f"results: {k} is not a SHA-256 hex digest")
    if "seeds" not in doc["design"]:
        raise ValueError("results: design.seeds missing")
    for i, c in enumerate(doc["cells"]):
        if not isinstance(c, dict) or "key" not in c or "arms" not in c:
            raise ValueError(f"results: cell {i} needs 'key' and 'arms'")
        for name, a in c["arms"].items():
            if not isinstance(a, dict) or "n" not in a or "metrics" not in a:
                raise ValueError(f"results: cell {i} arm {name!r} needs 'n' and 'metrics'")
    for h, v in doc["hypotheses"].items():
        if not isinstance(v, dict) or "held" not in v or "evidence" not in v:
            raise ValueError(f"results: hypothesis {h} needs 'held' and 'evidence'")


def write(doc: dict, path: str) -> str:
    validate(doc)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=True, allow_nan=False)
        f.write("\n")
    return path


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def strip_timing(doc: dict) -> dict:
    """The document without fields that depend on when or how fast it ran."""
    out = {k: v for k, v in doc.items() if k not in TIMING_FIELDS + ("procs", "machine")}
    return out


def default_out(name: str) -> str:
    return os.path.join(REPO_ROOT, "experiments", "results", f"{name}.json")
