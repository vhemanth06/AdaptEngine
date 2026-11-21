"""Deterministic process pool: results come back in input order whatever the worker count."""

from __future__ import annotations

import multiprocessing as mp
import os


def default_procs() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


def pmap(fn, units, procs: int = 1) -> list:
    """[fn(u) for u in units], in parallel with `procs` forked workers when procs > 1."""
    units = list(units)
    if procs <= 1 or len(units) <= 1:
        return [fn(u) for u in units]
    with mp.get_context("fork").Pool(min(procs, len(units))) as pool:
        return pool.map(fn, units, chunksize=1)
