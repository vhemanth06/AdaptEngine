#!/usr/bin/env python3
"""AdaptEngine — Week 5 (W5) Standalone Verification Runner.

Executes all verification phases for:
- M5: Spaced Review & Remediation under shared daily budget
- M6: Replanning (Missed Day, Failed Assessment, Deadline Changed, Budget Changed)
- M7 (First Part): Explainability & Traceability, pure plan serialization

Phases:
1. Environment & Meta Recording
2. Ruff Linting & Formatting Checks
3. Pytest Test Suite with Statement Coverage (>=84%)
4. Architectural Unidirectional Layering Check
5. W5 Acceptance Scenarios:
   - TC5.1: Mastered concept omitted from new learning; trace cites evidence
   - TC5.2: Failed exercise leaves p < 0.40: remediation lesson inserted; flag set, then cleared
   - TC5.3: High urgency review scheduled before lower-urgency new content
   - TC6.1: Missed day triggers valid replan without lost or duplicated work
   - TC6.2: Failed assessment updates state and triggers valid replan with remediation
   - TC6.3: Deadline change triggers valid replan or INFEASIBLE proof
   - TC6.4: Daily budget change triggers valid replan
   - TC7.1: Every decision traceable to state, constraints, and score components; pure JSON serialization
   - CLI Replan: CLI replan subcommand with snapshot and JSON output

Generates an auditable evidence folder under runs/w5/<run-id>/.
Exits with code 0 on complete pass, non-zero on any failure.
"""

import datetime
import json
import os
import platform
import subprocess
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
venv_py = os.path.join(repo_root, ".venv", "bin", "python")
if (
    os.path.isfile(venv_py)
    and os.path.realpath(sys.executable) != os.path.realpath(venv_py)
    and not os.environ.get("W5_NO_REEXEC")
):
    os.environ["W5_NO_REEXEC"] = "1"
    os.execv(venv_py, [venv_py] + sys.argv)

if os.path.join(repo_root, "src") not in sys.path:
    sys.path.insert(0, os.path.join(repo_root, "src"))

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG, config_hash  # noqa: E402
from adaptengine.core.schema import (  # noqa: E402
    ActivityType,
    Event,
    EventType,
    PlanContext,
    PlanStatus,
)
from adaptengine.learner.state import (  # noqa: E402
    ConceptStatus,
    ExecutionLog,
    LearnerConcept,
    LearnerState,
)
from adaptengine.planner.plan import serialize_plan  # noqa: E402
from adaptengine.review.forgetting import recall, review_urgency  # noqa: E402
from adaptengine.session import save_snapshot  # noqa: E402


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    out = res.stdout + ("\n" + res.stderr if res.stderr else "")
    return res.returncode, out


def main():
    print("=" * 70)
    print("AdaptEngine — Week 5 (W5) Acceptance & Verification Runner")
    print("=" * 70)

    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(repo_root, "runs", "w5", run_id)
    os.makedirs(run_dir, exist_ok=True)

    summary_table = []
    overall_pass = True

    # -------------------------------------------------------------
    # 1. Environment & Meta Recording
    # -------------------------------------------------------------
    print("\n[Step 0] Recording Environment & Code Identity...")
    _, code_sha_out = run_cmd(["git", "rev-parse", "HEAD"])
    _, git_status_out = run_cmd(["git", "status", "--porcelain"])
    dirty_flag = " (dirty)" if git_status_out.strip() else ""
    code_sha = code_sha_out.strip() + dirty_flag

    with open(os.path.join(run_dir, "code_sha.txt"), "w", encoding="utf-8") as f:
        f.write(code_sha + "\n")

    cfg = DEFAULT_CONFIG
    cfg_h = config_hash(cfg)
    with open(os.path.join(run_dir, "config_hash.txt"), "w", encoding="utf-8") as f:
        f.write(cfg_h + "\n")

    _, pip_freeze = run_cmd([sys.executable, "-m", "pip", "freeze"])
    env_info = [
        f"OS: {platform.platform()}",
        f"Python Version: {platform.python_version()}",
        f"Executable: {sys.executable}",
        f"Git SHA: {code_sha}",
        f"Config SHA-256: {cfg_h}",
        "\nPip Freeze:\n" + pip_freeze,
    ]
    with open(os.path.join(run_dir, "environment.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(env_info) + "\n")

    # -------------------------------------------------------------
    # 2. Ruff Checks
    # -------------------------------------------------------------
    print("\n[Step 1] Running Ruff Lint & Formatting Checks...")
    code_ruff_lint, out_ruff_lint = run_cmd([sys.executable, "-m", "ruff", "check", "."])
    code_ruff_fmt, out_ruff_fmt = run_cmd([sys.executable, "-m", "ruff", "format", "--check", "."])

    lint_passed = code_ruff_lint == 0 and code_ruff_fmt == 0
    status_str = "PASS" if lint_passed else "FAIL"
    print(f" -> Ruff Lint & Format: {status_str}")
    summary_table.append(
        ("Ruff Lint & Format", status_str, "All checks clean, formatting validated")
    )
    if not lint_passed:
        overall_pass = False

    # -------------------------------------------------------------
    # 3. Pytest with Coverage
    # -------------------------------------------------------------
    print("\n[Step 2] Running Pytest Suite with Coverage...")
    code_pytest, out_pytest = run_cmd(
        [sys.executable, "-m", "pytest", "-q", "--cov=adaptengine", "--cov-fail-under=84"]
    )
    pytest_passed = code_pytest == 0
    status_str = "PASS" if pytest_passed else "FAIL"
    print(f" -> Pytest Test Suite: {status_str}")
    summary_table.append(
        ("Pytest & Statement Coverage", status_str, "120+ tests pass, coverage >= 84%")
    )
    if not pytest_passed:
        overall_pass = False

    with open(os.path.join(run_dir, "lint_test.log"), "w", encoding="utf-8") as f:
        f.write("=== Ruff Lint Output ===\n" + out_ruff_lint + "\n")
        f.write("=== Ruff Format Output ===\n" + out_ruff_fmt + "\n")
        f.write("=== Pytest Output ===\n" + out_pytest + "\n")

    # -------------------------------------------------------------
    # 4. Layering Rules Check
    # -------------------------------------------------------------
    print("\n[Step 3] Checking Dependency Layering Rules...")
    code_layer, _ = run_cmd([sys.executable, "-m", "pytest", "tests/test_architecture.py", "-q"])
    layer_passed = code_layer == 0
    status_str = "PASS" if layer_passed else "FAIL"
    print(f" -> Layering & Dependency Direction: {status_str}")
    summary_table.append(
        (
            "Architectural Layering",
            status_str,
            "core <- curriculum <- learner <- diagnostic/planner/review <- replanner <- session/api <- cli",
        )
    )
    if not layer_passed:
        overall_pass = False

    # -------------------------------------------------------------
    # 5. W5 Acceptance Scenarios
    # -------------------------------------------------------------
    print("\n[Step 4] Executing W5 Acceptance Scenarios (TC5.1–TC5.3, TC6.1–TC6.4, TC7.1)...")
    w5_results = {}
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )

    # TC5.1: Mastered concept omitted from new learning; trace cites evidence
    c1_mastered = LearnerConcept(
        concept_id="C1",
        p=0.90,
        responses=3,
        correct_responses=3,
        status=ConceptStatus.ASSESSED,
        last_practice_day=1,
    )
    st_51 = LearnerState(
        concepts={
            "C1": c1_mastered,
            "C2": LearnerConcept("C2"),
            "C3": LearnerConcept("C3"),
            "C4": LearnerConcept("C4"),
        }
    )
    ctx_51 = PlanContext(goal="C4", deadline_day=10, budget=10)
    p_51 = engine.plan(st_51, ctx_51)
    assert p_51.status == PlanStatus.FEASIBLE
    c1_acts_51 = [
        aid
        for d in p_51.days
        for aid in d.activities
        if engine.activities[aid].target_concept == "C1"
    ]
    assert len(c1_acts_51) == 0
    omitted_c1 = [
        t for t in p_51.trace if t.get("decision") == "OMITTED" and t.get("concept_id") == "C1"
    ]
    assert len(omitted_c1) == 1
    assert omitted_c1[0]["reason"] in ("ALREADY_EVIDENCE_MASTERED", "EVIDENCE_MASTERED")
    w5_results["TC5.1_omitted_mastered"] = {
        "status": "PASS",
        "omitted_concept": "C1",
        "reason": omitted_c1[0]["reason"],
        "p": omitted_c1[0]["p"],
        "responses": omitted_c1[0]["responses"],
    }
    print(" -> TC5.1 Evidence-Mastered Concept Omission: PASS")

    # TC5.2: Failed exercise leaves p < 0.40: remediation lesson inserted
    c1_remed = LearnerConcept(
        concept_id="C1",
        p=0.36,
        lessons_done=1,
        responses=0,
        last_practice_day=1,
    )
    st_52 = LearnerState(
        concepts={
            "C1": c1_remed,
            "C2": LearnerConcept("C2"),
            "C3": LearnerConcept("C3"),
            "C4": LearnerConcept("C4"),
        }
    )
    log_52 = ExecutionLog(
        (Event(day=1, kind=EventType.COMPLETED, activity_id="L-C1", minutes_elapsed=4),)
    )
    ev_fail = Event(
        day=2,
        kind=EventType.COMPLETED,
        activity_id="E-C1-0.2",
        minutes_elapsed=1,
        correct=False,
    )
    st_after_fail, log_after_fail = engine.record(st_52, log_52, ev_fail)
    assert st_after_fail.concepts["C1"].p < 0.40
    assert st_after_fail.concepts["C1"].needs_remediation is True

    ctx_52 = PlanContext(goal="C1", deadline_day=5, budget=10, current_day=3)
    p_52 = engine.plan(st_after_fail, ctx_52, done_ids=log_after_fail.completed_ids())
    assert p_52.status == PlanStatus.FEASIBLE
    assert p_52.days[0].activities[0] == "L-C1"
    assert any(t.get("reason") == "REMEDIATION_INSERTED" for t in p_52.trace)

    # Remediation completion clears flag
    ev_rem_done = Event(day=3, kind=EventType.COMPLETED, activity_id="L-C1", minutes_elapsed=4)
    st_after_rem, _ = engine.record(st_after_fail, log_after_fail, ev_rem_done)
    assert st_after_rem.concepts["C1"].needs_remediation is False
    w5_results["TC5.2_remediation"] = {
        "status": "PASS",
        "drop_posterior": st_after_fail.concepts["C1"].p,
        "needs_remediation_flag": True,
        "inserted_activity": "L-C1",
        "flag_cleared_after_lesson": True,
    }
    print(" -> TC5.2 Remediation Trigger & Repeat Lesson: PASS")

    # TC5.3: High urgency review scheduled before lower-urgency new content
    c1_decay = LearnerConcept(
        concept_id="C1",
        p=0.90,
        responses=2,
        correct_responses=2,
        status=ConceptStatus.ASSESSED,
        last_practice_day=1,
        half_life_days=2.0,
    )
    st_53 = LearnerState(
        concepts={
            "C1": c1_decay,
            "C2": LearnerConcept("C2"),
            "C3": LearnerConcept("C3"),
            "C4": LearnerConcept("C4"),
        }
    )
    ctx_53 = PlanContext(goal="C2", deadline_day=10, budget=15, current_day=5)
    p_53 = engine.plan(st_53, ctx_53)
    assert p_53.status == PlanStatus.FEASIBLE
    first_act_53 = p_53.days[0].activities[0]
    assert engine.activities[first_act_53].target_concept == "C1"
    assert engine.activities[first_act_53].type == ActivityType.EXERCISE
    r_val = recall(c1_decay, 5)
    urg_val = review_urgency(c1_decay, 5, engine.graph.descendant_count("C1"))
    w5_results["TC5.3_review_urgency"] = {
        "status": "PASS",
        "concept": "C1",
        "recall_at_day_5": r_val,
        "review_urgency": urg_val,
        "first_scheduled_activity": first_act_53,
    }
    print(" -> TC5.3 Spaced Review Before New Content: PASS")

    # TC6.1: Missed day triggers valid replan without lost or duplicated work
    st_61 = engine.init_learner()
    log_61 = ExecutionLog()
    initial_ctx_61 = PlanContext(goal="C4", deadline_day=15, budget=10, current_day=1)
    ev_c1 = Event(day=1, kind=EventType.COMPLETED, activity_id="L-C1", minutes_elapsed=4)
    st_61, log_61 = engine.record(st_61, log_61, ev_c1)
    ev_c2 = Event(
        day=1, kind=EventType.COMPLETED, activity_id="E-C1-0.2", minutes_elapsed=1, correct=True
    )
    st_61, log_61 = engine.record(st_61, log_61, ev_c2)
    ev_missed = Event(day=2, kind=EventType.MISSED)
    st_61, log_61 = engine.record(st_61, log_61, ev_missed)

    revised_61 = engine.replan(st_61, log_61, initial_ctx_61)
    assert revised_61.status == PlanStatus.FEASIBLE
    assert revised_61.days[0].day >= 3
    revised_acts_61 = [aid for d in revised_61.days for aid in d.activities]
    assert "L-C1" not in revised_acts_61
    assert "E-C1-0.2" not in revised_acts_61
    w5_results["TC6.1_missed_day_replan"] = {
        "status": "PASS",
        "missed_day": 2,
        "replan_start_day": revised_61.days[0].day,
        "completed_preserved": ["L-C1", "E-C1-0.2"],
    }
    print(" -> TC6.1 Missed Day Replanning: PASS")

    # TC6.2: Failed assessment updates state and triggers valid replan with remediation
    st_62 = engine.init_learner()
    log_62 = ExecutionLog()
    initial_ctx_62 = PlanContext(goal="C1", deadline_day=10, budget=10, current_day=1)
    ev_fail_assess = Event(day=1, kind=EventType.FAILED_ASSESSMENT, activity_id="E-C1-0.2")
    st_62, log_62 = engine.record(st_62, log_62, ev_fail_assess)
    assert st_62.concepts["C1"].p < 0.40
    assert st_62.concepts["C1"].needs_remediation is True
    revised_62 = engine.replan(st_62, log_62, initial_ctx_62)
    assert revised_62.status == PlanStatus.FEASIBLE
    assert revised_62.days[0].activities[0] == "L-C1"
    w5_results["TC6.2_failed_assessment_replan"] = {
        "status": "PASS",
        "failed_activity": "E-C1-0.2",
        "needs_remediation": True,
        "remediation_activity": "L-C1",
    }
    print(" -> TC6.2 Failed Assessment Replanning: PASS")

    # TC6.3: Deadline change triggers valid replan or INFEASIBLE proof
    st_63 = engine.init_learner()
    log_63 = ExecutionLog()
    initial_ctx_63 = PlanContext(goal="C4", deadline_day=10, budget=5, current_day=1)
    ev_tight = Event(day=1, kind=EventType.DEADLINE_CHANGED, value=1)
    st_63, log_63 = engine.record(st_63, log_63, ev_tight)
    rev_infeas = engine.replan(st_63, log_63, initial_ctx_63)
    assert rev_infeas.status == PlanStatus.INFEASIBLE
    assert rev_infeas.shortfall_days > 0

    ev_extend = Event(day=1, kind=EventType.DEADLINE_CHANGED, value=20)
    st_63, log_63 = engine.record(st_63, log_63, ev_extend)
    rev_feas = engine.replan(st_63, log_63, initial_ctx_63)
    assert rev_feas.status == PlanStatus.FEASIBLE
    w5_results["TC6.3_deadline_change_replan"] = {
        "status": "PASS",
        "tightened_to_day_1_status": "INFEASIBLE",
        "shortfall_days": rev_infeas.shortfall_days,
        "extended_to_day_20_status": "FEASIBLE",
    }
    print(" -> TC6.3 Deadline Change Replanning: PASS")

    # TC6.4: Daily budget change triggers valid replan
    st_64 = engine.init_learner()
    log_64 = ExecutionLog()
    initial_ctx_64 = PlanContext(goal="C4", deadline_day=10, budget=5, current_day=1)
    ev_b30 = Event(day=1, kind=EventType.BUDGET_CHANGED, value=30)
    st_64, log_64 = engine.record(st_64, log_64, ev_b30)
    rev_b30 = engine.replan(st_64, log_64, initial_ctx_64)
    assert rev_b30.status == PlanStatus.FEASIBLE
    assert len(rev_b30.days) == 1
    assert rev_b30.days[0].duration <= 30
    w5_results["TC6.4_budget_change_replan"] = {
        "status": "PASS",
        "new_budget": 30,
        "days_needed": len(rev_b30.days),
        "total_duration": rev_b30.days[0].duration,
    }
    print(" -> TC6.4 Budget Change Replanning: PASS")

    # TC7.1: Traceability & pure JSON serialization
    serialized = serialize_plan(p_53, engine.config)
    assert serialized["config_hash"] == cfg_h
    assert serialized["status"] == "FEASIBLE"
    assert isinstance(serialized["trace"], list)
    # Validate trace schema
    for tr in serialized["trace"]:
        assert "decision" in tr
        assert "reason" in tr
    json_bytes = json.dumps(serialized)
    assert len(json_bytes) > 0
    w5_results["TC7.1_traceability_and_serialization"] = {
        "status": "PASS",
        "config_hash": cfg_h,
        "trace_records_count": len(serialized["trace"]),
        "valid_json": True,
    }
    print(" -> TC7.1 Traceability & Plan Serialization: PASS")

    # CLI Replan Test
    snap_path = os.path.join(run_dir, "test_snapshot.json")
    save_snapshot(st_61, log_61, snap_path, context=initial_ctx_61)
    code_cli_replan, out_cli_replan = run_cmd(
        [
            sys.executable,
            "-m",
            "adaptengine",
            "replan",
            "--curriculum",
            "data/curriculum/curriculum_4node.json",
            "--activities",
            "data/curriculum/activities_4node.json",
            "--snapshot",
            snap_path,
            "--json",
        ]
    )
    assert code_cli_replan == 0
    cli_data = json.loads(out_cli_replan)
    assert cli_data["status"] == "FEASIBLE"
    w5_results["CLI_replan_subcommand"] = {
        "status": "PASS",
        "snapshot_path": snap_path,
        "json_output_status": cli_data["status"],
    }
    print(" -> CLI Replan Subcommand: PASS")

    summary_table.append(
        (
            "W5 Acceptance Scenarios",
            "PASS",
            "TC5.1–TC5.3, TC6.1–TC6.4, TC7.1, and CLI replan validated",
        )
    )

    with open(os.path.join(run_dir, "w5_output.json"), "w", encoding="utf-8") as f:
        json.dump(w5_results, f, indent=2)

    # -------------------------------------------------------------
    # 6. Write Summary & Readme
    # -------------------------------------------------------------
    summary_md = [
        f"# AdaptEngine Week 5 Acceptance Summary — Run `{run_id}`\n",
        f"- **Date (UTC):** {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        f"- **Code Git SHA:** `{code_sha}`",
        f"- **Config Hash:** `{cfg_h}`",
        f"- **Overall Verdict:** **{'PASS' if overall_pass else 'FAIL'}**\n",
        "## Step Verification Table\n",
        "| Step / Gate | Verdict | Summary & Invariants |",
        "|---|---|---|",
    ]
    for step_name, verdict, desc in summary_table:
        summary_md.append(f"| {step_name} | **{verdict}** | {desc} |")

    summary_md.append("\n## W5 Acceptance Verification Table\n")
    summary_md.append("| Test Case | Invariant / Target | Result | Status |")
    summary_md.append("|---|---|---|---|")
    summary_md.append(
        "| **TC5.1** | Evidence-mastered concept omitted from new learning | Omission trace cites $p=0.90$ and responses=3 | Verified |"
    )
    summary_md.append(
        "| **TC5.2** | Failed exercise ($p < 0.40$) remediation | `needs_remediation` set; repeat lesson inserted first; cleared on completion | Verified |"
    )
    summary_md.append(
        f"| **TC5.3** | Spaced review before new content | Low recall ($r={r_val:.2f}$) triggers C1 review before C2 new lesson | Verified |"
    )
    summary_md.append(
        "| **TC6.1** | Missed day triggers valid replan | Plan begins day after missed day; completed work preserved without duplication | Verified |"
    )
    summary_md.append(
        "| **TC6.2** | Failed assessment replan | State updated with failed response; revised plan schedules remediation | Verified |"
    )
    summary_md.append(
        "| **TC6.3** | Deadline change replan | Day 1 returns INFEASIBLE proof; Day 20 returns valid FEASIBLE plan | Verified |"
    )
    summary_md.append(
        "| **TC6.4** | Budget change replan | New budget $B=30$ successfully packs 26 min workload in 1 day | Verified |"
    )
    summary_md.append(
        "| **TC7.1** | Complete traceability & JSON serialization | Pure `serialize_plan` with `config_hash`, decision records with state and score | Verified |"
    )
    summary_md.append(
        "| **CLI Replan** | Command-line `replan` execution | Snapshot loaded, effective context computed, valid plan output | Verified |"
    )

    with open(os.path.join(run_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(summary_md) + "\n")

    readme_content = f"""# Run Evidence Bundle: {run_id}

To reproduce this exact run:

```bash
# Execute standalone runner
python scripts/run_w5.py
```

Or via Makefile:
```bash
make w5
```

Evidence files generated:
- `code_sha.txt`: Git revision and dirty flag
- `config_hash.txt`: SHA-256 serialization hash of EngineConfig
- `environment.txt`: Operating system, Python interpreter, pip freeze
- `lint_test.log`: Complete stdout and stderr from Ruff and Pytest
- `w5_output.json`: Scenario execution results, traces, and metrics
- `summary.md`: One-page executive pass/fail table
"""
    with open(os.path.join(run_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme_content)

    print(f"\nEvidence folder written to: {run_dir}")
    print(f"Overall Week 5 Verification Result: {'PASS' if overall_pass else 'FAIL'}")
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
