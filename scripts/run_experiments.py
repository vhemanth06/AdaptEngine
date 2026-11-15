#!/usr/bin/env python3
"""Run the pre-registered experiment suite E1-E6, then experiments/make_results.py if present.

  python scripts/run_experiments.py [--smoke] [--only E1 E2 ... | --from EN] [--no-results]
                                    [--out-dir DIR] [--prereg PATH]
Before every step the src/ code hash and the experiment hash (experiments/provenance.py) are
recomputed and compared with the `Code hash (src/, SHA-256): `<hex>`` and
`Experiment hash (SHA-256): `<hex>`` lines of the pre-registration; a mismatch aborts the run.
E1 always gets --resume: its checkpoint is keyed on both hashes, so a rerun of the same code
continues where it stopped. --from EN runs EN and every later step; --only runs the named steps.
make_results runs last in every mode unless --no-results is given.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from experiments.provenance import code_hash, experiment_hash, prereg_hashes  # noqa: E402

PREREG = os.path.join(ROOT, "docs", "preregistration", "PRODUCT_RERUN_2026-11-15.md")
# (id, script, subcommand args)
STEPS = (
    ("E1", "run_grid.py", ["--grid", "both", "--resume"]),
    ("E2", "run_diag.py", []),
    ("E3", "run_sensitivity.py", []),
    ("E4", "run_policy.py", ["train"]),
    ("E4", "run_policy.py", ["eval"]),
    ("E5", "run_extensions.py", ["all"]),
    ("E6", "run_planner_cost.py", ["all"]),
)
IDS = list(dict.fromkeys(s[0] for s in STEPS))


def registered(path: str) -> dict[str, str]:
    h = prereg_hashes(path)
    missing = [k for k, v in h.items() if v is None]
    if missing:
        raise SystemExit(
            f"no registered {' / '.join(missing)} line in {path} (need 'Code hash (src/, "
            "SHA-256): `<hex>`' and 'Experiment hash (SHA-256): `<hex>`')"
        )
    return h


def build_commands(smoke=False, only=None, out_dir=None, start=None):
    cmds = []
    for eid, script, args in STEPS:
        if only and eid not in only:
            continue
        if start and IDS.index(eid) < IDS.index(start):
            continue
        # subcommand must follow the script name directly
        cmd = [sys.executable, os.path.join(ROOT, "experiments", script), *args]
        if smoke:
            cmd.append("--smoke")
        if out_dir:
            cmd += ["--out-dir", out_dir]
            if eid == "E4":
                cmd += ["--frozen-path", os.path.join(out_dir, "policy_frozen.json")]
        cmds.append(cmd)
    return cmds


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    sel = ap.add_mutually_exclusive_group()
    sel.add_argument("--only", nargs="+", choices=IDS)
    sel.add_argument("--from", dest="start", choices=IDS)
    ap.add_argument("--no-results", action="store_true", help="skip make_results.py")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--prereg", default=PREREG)
    a = ap.parse_args(argv)
    expected = registered(a.prereg)
    cmds = build_commands(a.smoke, a.only, a.out_dir, a.start)
    make = os.path.join(ROOT, "experiments", "make_results.py")
    if not a.no_results:
        if os.path.exists(make):
            cmds.append(
                [sys.executable, make]
                + (["--smoke"] if a.smoke else [])
                + (["--out-dir", a.out_dir] if a.out_dir else [])
            )
        else:
            print("skipped: make_results.py not present")
    for cmd in cmds:
        now = {"code_hash": code_hash(), "experiment_hash": experiment_hash()}
        for k, v in now.items():
            if v != expected[k]:
                raise SystemExit(f"REFUSED: {k} {v} != pre-registered {expected[k]}")
        print("+", " ".join(cmd), flush=True)
        rc = subprocess.call(cmd, cwd=ROOT)
        if rc:
            raise SystemExit(rc)


if __name__ == "__main__":
    main()
