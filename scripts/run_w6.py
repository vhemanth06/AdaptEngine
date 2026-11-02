#!/usr/bin/env python3
"""AdaptEngine — Week 6 (W6) Standalone Verification Runner.

Executes all verification phases for:
- M8: Paired Baseline Evaluation & Simulator
- TC8.1: Evaluation Rerun Byte-Identical
- TC8.2: Frontier Replanning Equivalence & Latency Benchmark
- Audit Totals: Zero prerequisite & budget violations, 100% trace coverage for adaptive arms
- Code Quality: Ruff lint/format, Architecture layering, Statement coverage >= 84%

Generates an auditable evidence folder under runs/w6/<run-id>/.
Exits with code 0 on complete pass, non-zero on any failure.
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import shutil
import subprocess
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
venv_py = os.path.join(repo_root, ".venv", "bin", "python")
if (
    os.path.isfile(venv_py)
    and os.path.realpath(sys.executable) != os.path.realpath(venv_py)
    and not os.environ.get("W6_NO_REEXEC")
):
    os.environ["W6_NO_REEXEC"] = "1"
    os.execv(venv_py, [venv_py] + sys.argv)

if os.path.join(repo_root, "src") not in sys.path:
    sys.path.insert(0, os.path.join(repo_root, "src"))

from adaptengine.core.config import DEFAULT_CONFIG, config_hash  # noqa: E402


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    out = res.stdout + ("\n" + res.stderr if res.stderr else "")
    return res.returncode, out


def main():
    print("=" * 70)
    print("AdaptEngine — Week 6 (W6) MVP Final Acceptance & Verification Runner")
    print("=" * 70)

    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(repo_root, "runs", "w6", run_id)
    os.makedirs(run_dir, exist_ok=True)

    summary_table = []
    overall_pass = True

    # -------------------------------------------------------------
    # Phase 1: Environment & Meta Recording
    # -------------------------------------------------------------
    print("\n[Phase 1] Recording Environment & Meta...")
    _, code_sha_out = run_cmd(["git", "rev-parse", "HEAD"])
    _, git_status_out = run_cmd(["git", "status", "--porcelain"])
    dirty_flag = " (dirty)" if git_status_out.strip() else ""
    code_sha = code_sha_out.strip() + dirty_flag

    cfg = DEFAULT_CONFIG
    cfg_h = config_hash(cfg)

    env_meta = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit": code_sha,
        "python_version": sys.version,
        "platform": platform.platform(),
        "config_hash": cfg_h,
    }
    with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(env_meta, f, indent=2)

    print(f"  Platform:    {env_meta['platform']}")
    print(f"  Python:      {sys.version.split()[0]}")
    print(f"  Git Commit:  {code_sha}")
    print(f"  Config Hash: {cfg_h}")
    summary_table.append(("Phase 1: Environment & Meta", "PASS", f"SHA: {code_sha[:10]}"))

    # -------------------------------------------------------------
    # Phase 2: Ruff Linting & Formatting Checks
    # -------------------------------------------------------------
    print("\n[Phase 2] Running Ruff Lint & Format Checks...")
    rc_lint, out_lint = run_cmd([sys.executable, "-m", "ruff", "check", "."])
    rc_fmt, out_fmt = run_cmd([sys.executable, "-m", "ruff", "format", "--check", "."])

    if rc_lint == 0 and rc_fmt == 0:
        print("  ✓ Ruff lint and format checks clean.")
        summary_table.append(("Phase 2: Ruff Lint & Format", "PASS", "0 errors"))
    else:
        print("  ✗ Ruff checks failed:")
        if rc_lint != 0:
            print(out_lint)
        if rc_fmt != 0:
            print(out_fmt)
        summary_table.append(("Phase 2: Ruff Lint & Format", "FAIL", "Lint/Format violations"))
        overall_pass = False

    # -------------------------------------------------------------
    # Phase 3: Pytest Test Suite & Coverage Gate (>=84%)
    # -------------------------------------------------------------
    print("\n[Phase 3] Running Pytest Suite with Coverage (>=84%)...")
    rc_test, out_test = run_cmd(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--cov=adaptengine",
            "--cov-fail-under=84",
            "--cov-report=term-missing",
        ]
    )
    with open(os.path.join(run_dir, "pytest_coverage.log"), "w", encoding="utf-8") as f:
        f.write(out_test)

    if rc_test == 0:
        print("  ✓ Pytest suite and coverage threshold (>=84%) passed.")
        summary_table.append(("Phase 3: Test Suite & Coverage", "PASS", "Coverage >= 84%"))
    else:
        print("  ✗ Pytest failed:")
        print(out_test)
        summary_table.append(
            ("Phase 3: Test Suite & Coverage", "FAIL", "Test failure or cov < 84%")
        )
        overall_pass = False

    # -------------------------------------------------------------
    # Phase 4: Architecture Layering Test
    # -------------------------------------------------------------
    print("\n[Phase 4] Checking Architectural Layering Guardrails...")
    rc_arch, out_arch = run_cmd(
        [sys.executable, "-m", "pytest", "-q", "tests/test_architecture.py"]
    )
    if rc_arch == 0:
        print("  ✓ Architectural layering validated (unidirectional import rules strictly held).")
        summary_table.append(("Phase 4: Architecture Layering", "PASS", "Zero layer violations"))
    else:
        print("  ✗ Architecture test failed:")
        print(out_arch)
        summary_table.append(("Phase 4: Architecture Layering", "FAIL", "Layer violation detected"))
        overall_pass = False

    # -------------------------------------------------------------
    # Phase 5: TC8.1 Byte-Identical Quick Evaluation Rerun
    # -------------------------------------------------------------
    print("\n[Phase 5] TC8.1: Running Evaluation Quick Mode Twice (Byte-Identical Check)...")
    eval_script = os.path.join(repo_root, "experiments", "run_evaluation.py")
    eval_res_path = os.path.join(repo_root, "experiments", "results", "evaluation_results.json")

    rc_eval1, out_eval1 = run_cmd([sys.executable, eval_script, "--quick"])
    if rc_eval1 != 0:
        print("  ✗ Eval run 1 failed:\n", out_eval1)
        summary_table.append(("Phase 5: TC8.1 Evaluation Rerun", "FAIL", "Run 1 failed"))
        overall_pass = False
    else:
        with open(eval_res_path, "rb") as f:
            eval_bytes1 = f.read()

        rc_eval2, out_eval2 = run_cmd([sys.executable, eval_script, "--quick"])
        if rc_eval2 != 0:
            print("  ✗ Eval run 2 failed:\n", out_eval2)
            summary_table.append(("Phase 5: TC8.1 Evaluation Rerun", "FAIL", "Run 2 failed"))
            overall_pass = False
        else:
            with open(eval_res_path, "rb") as f:
                eval_bytes2 = f.read()

            if eval_bytes1 == eval_bytes2:
                print("  ✓ TC8.1 Verified: Evaluation rerun is byte-identical.")
                summary_table.append(
                    ("Phase 5: TC8.1 Byte-Identical Eval", "PASS", "Exact match across 2 runs")
                )
            else:
                print("  ✗ TC8.1 Failed: Non-deterministic evaluation outputs detected.")
                summary_table.append(
                    ("Phase 5: TC8.1 Byte-Identical Eval", "FAIL", "Byte mismatch")
                )
                overall_pass = False

    # -------------------------------------------------------------
    # Phase 6: TC8.2 Frontier Replanning Equivalence & Latency Pass
    # -------------------------------------------------------------
    print("\n[Phase 6] TC8.2: Frontier Replanning Equivalence & Latency Pass...")
    rc_equiv, out_equiv = run_cmd(
        [sys.executable, "-m", "pytest", "-q", "tests/test_replan_frontier.py"]
    )
    if rc_equiv != 0:
        print("  ✗ Frontier replan equivalence test failed:\n", out_equiv)
        summary_table.append(("Phase 6: TC8.2 Equivalence", "FAIL", "Plan mismatch"))
        overall_pass = False
    else:
        print("  ✓ Frontier replan equivalence verified across curricula, budgets, and events.")

        lat_script = os.path.join(repo_root, "experiments", "run_replan_latency.py")
        rc_lat, out_lat = run_cmd([sys.executable, lat_script, "--quick"])
        if rc_lat != 0:
            print("  ✗ Latency pass failed:\n", out_lat)
            summary_table.append(("Phase 6: TC8.2 Latency Benchmark", "FAIL", "Script error"))
            overall_pass = False
        else:
            print("  ✓ Latency pass complete.")
            summary_table.append(
                ("Phase 6: TC8.2 Frontier Replan", "PASS", "Equivalence & Latency verified")
            )

    # -------------------------------------------------------------
    # Phase 7: Audit Totals (Prereq & Budget Violations = 0, Trace Cov = 1.0)
    # -------------------------------------------------------------
    print("\n[Phase 7] Auditing Evaluation Results (Zero Violations & Full Coverage)...")
    try:
        with open(eval_res_path, "r", encoding="utf-8") as f:
            eval_data = json.load(f)

        violations_clean = True
        coverage_clean = True

        per_seed_planner = eval_data.get("per_seed_runs", {}).get("planner", [])
        for rec in per_seed_planner:
            for arm_name in ("adapt", "no_review", "no_replan"):
                arm_res = rec.get(arm_name, {})
                prereq_v = arm_res.get("prerequisite_violations", 0)
                budget_v = arm_res.get("budget_violations", 0)
                cov = arm_res.get("plan_trace_coverage", 0.0)

                if prereq_v != 0 or budget_v != 0:
                    violations_clean = False
                    print(
                        f"  ✗ Violation found in seed {rec.get('seed')}/{arm_name}: prereq={prereq_v}, budget={budget_v}"
                    )

                if arm_name in ("adapt", "no_review"):
                    if abs(cov - 1.0) > 1e-6:
                        coverage_clean = False
                        print(
                            f"  ✗ Incomplete trace coverage in seed {rec.get('seed')}/{arm_name}: cov={cov} (expected 1.0)"
                        )

        # Also audit main_table for adapt and no_review
        main_table = eval_data.get("planner", {}).get("main_table", {})
        for scenario_name, arms in main_table.items():
            if not isinstance(arms, dict):
                continue
            for arm_name in ("adapt", "no_review"):
                metrics = arms.get(arm_name, {})
                prereq_v = metrics.get("prerequisite_violations", 0)
                budget_v = metrics.get("budget_violations", 0)
                cov = metrics.get("plan_trace_coverage", 0.0)

                if prereq_v != 0 or budget_v != 0:
                    violations_clean = False
                    print(
                        f"  ✗ Violation found in {scenario_name}/{arm_name}: prereq={prereq_v}, budget={budget_v}"
                    )

                if abs(cov - 1.0) > 1e-6:
                    coverage_clean = False
                    print(
                        f"  ✗ Incomplete trace coverage in {scenario_name}/{arm_name}: cov={cov} (expected 1.0)"
                    )

        if violations_clean and coverage_clean:
            print(
                "  ✓ Audit passed: 0 prerequisite and 0 budget violations across all adaptive runs."
            )
            print("  ✓ Audit passed: 100% explanation coverage for all adaptive arms.")
            summary_table.append(
                ("Phase 7: Plan & Trace Audit", "PASS", "0 violations, 100% adaptive coverage")
            )
        else:
            summary_table.append(
                (
                    "Phase 7: Plan & Trace Audit",
                    "FAIL",
                    "Violations detected or incomplete coverage",
                )
            )
            overall_pass = False
    except Exception as e:
        print(f"  ✗ Could not audit evaluation_results.json: {e}")
        summary_table.append(("Phase 7: Plan & Trace Audit", "FAIL", str(e)))
        overall_pass = False

    # -------------------------------------------------------------
    # Phase 8: Copy Evidence Artifacts & Write Summary Table
    # -------------------------------------------------------------
    print("\n[Phase 8] Finalizing Evidence Artifacts...")
    lat_res_path = os.path.join(repo_root, "experiments", "results", "replan_latency.json")

    if os.path.isfile(eval_res_path):
        shutil.copy2(eval_res_path, os.path.join(run_dir, "evaluation_results.json"))
    if os.path.isfile(lat_res_path):
        shutil.copy2(lat_res_path, os.path.join(run_dir, "replan_latency.json"))

    summary_file = os.path.join(run_dir, "summary.txt")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write(f"AdaptEngine W6 Verification Summary — Run ID: {run_id}\n")
        f.write("=" * 70 + "\n\n")
        for name, status, detail in summary_table:
            f.write(f"{name:<35} : [{status}] {detail}\n")
        f.write("\n" + "=" * 70 + "\n")
        f.write(f"OVERALL RESULT: {'PASS' if overall_pass else 'FAIL'}\n")
        f.write("=" * 70 + "\n")

    print(f"\nEvidence stored in: {run_dir}")
    print("-" * 70)
    for name, status, detail in summary_table:
        print(f"{name:<35} : [{status}] {detail}")
    print("-" * 70)
    print(f"OVERALL RESULT: {'PASS' if overall_pass else 'FAIL'}")
    print("-" * 70)

    if not overall_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
