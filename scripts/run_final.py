#!/usr/bin/env python3
"""W8 I.4 `make final`: every gate, the final-week runs and the figures, in order.

Steps (stop at the first failure):
  1. make check (lint + tests + coverage)        2. make w3 w4 w5 w6 (acceptance runners)
  3. probes and WP-A gate                       4. B.2 fits, B.3 selection
  5. final grid (resumable)                     6. bandit training + policy evaluation
  7. extensions (D.1, O.1-O.4)                  8. stub agent run   9. FINAL_RESULTS.md + figures
Use --skip-runs to only run the gates and rebuild the results document from existing files.
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = (
    str(REPO / ".venv" / "bin" / "python")
    if (REPO / ".venv" / "bin" / "python").exists()
    else sys.executable
)

GATES = [["make", "check"], ["make", "w3"], ["make", "w4"], ["make", "w5"], ["make", "w6"]]
RUNS = [
    [PY, "experiments/probes/probe_w8_baseline.py"],
    [PY, "experiments/probes/probe_w8_gate.py"],
    [PY, "experiments/fit_bkt_sim.py", "w8"],
    [PY, "experiments/run_calibration_select.py"],
    [PY, "experiments/run_final_grid.py"],
    [PY, "experiments/train_policy.py"],
    [PY, "experiments/run_policy_eval.py"],
    [PY, "experiments/run_extensions.py"],
    [PY, "experiments/run_agent_eval.py", "--provider", "stub"],
]
RESULTS = [[PY, "experiments/make_final_results.py"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-runs", action="store_true")
    a = ap.parse_args()
    for cmd in GATES + ([] if a.skip_runs else RUNS) + RESULTS:
        print("==>", " ".join(cmd), flush=True)
        if subprocess.run(cmd, cwd=REPO).returncode != 0:
            print("FAILED:", " ".join(cmd))
            return 1
    print("make final: all steps passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
