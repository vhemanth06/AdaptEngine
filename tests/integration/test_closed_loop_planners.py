"""Plan 4 (F3-T7): every planner in the closed loop, with F1 and F2 options, and from the CLI.

Formerly tests/test_cpsat_closed_loop.py.
"""

import contextlib
import dataclasses
import io
import json
import os
import sys

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

pytest.importorskip("ortools")

from adaptengine.api import Engine  # noqa: E402
from adaptengine.cli import main  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG, bisection_config  # noqa: E402
from adaptengine.core.schema import Event, EventType, PlanContext, PlanStatus  # noqa: E402
from adaptengine.learner.state import ExecutionLog  # noqa: E402
from adaptengine.planner import serialize_plan  # noqa: E402
from adaptengine.session import load_snapshot, save_snapshot  # noqa: E402
from experiments.core.arms import E1_ARMS  # noqa: E402
from experiments.core.audit import executed_violations, plan_violations  # noqa: E402
from experiments.core.episode import run_episode  # noqa: E402
from experiments.core.scenarios import make_scenario  # noqa: E402

CUR = os.path.join(repo_root, "data", "curriculum")
METHODS = ("greedy", "cpsat", "hybrid")


def _eng(method, name="8node", base=DEFAULT_CONFIG, **kw):
    cfg = dataclasses.replace(base, planner_method=method, **kw)
    return Engine.from_files(
        f"{CUR}/curriculum_{name}.json",
        f"{CUR}/activities_{name}.json",
        config=cfg,
        allow_unreviewed=name.endswith("x10"),
    )


def _plan_prereq(e, state, plan, days):
    """Plan-level prerequisite violations of `days` (replaces experiments/checks.py::
    count_plan_prereq_violations); budget and deadline do not affect the prerequisite count."""
    return plan_violations(e, state, plan, budget=10**6, deadline=10**6, days=days)["prereq"]


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("scenario", ["missed_day", "budget_drop", "deadline_cut"])
def test_scripted_episodes_have_no_violations(method, scenario):
    e = _eng(method)
    sc = make_scenario(scenario, e, "C8", 15)
    for seed in (1000, 1001):
        r = run_episode(e, seed, sc, E1_ARMS["adapt"], "S0", "nominal")
        assert r["exec_viol"] == 0
        assert r["plan_checks"]["prereq"] == 0 and r["exec_budget_viol"] == 0


@pytest.mark.parametrize("method", METHODS)
def test_events_and_mid_day_replans(method):
    e = _eng(method)
    st, log = e.init_learner(), ExecutionLog()
    ctx = PlanContext(goal="C8", deadline_day=8, budget=15)
    today, _ = e.next_activities(st, log, ctx)
    first = today.activities[0]
    st, log = e.record(
        st,
        log,
        Event(
            day=1,
            kind=EventType.COMPLETED,
            activity_id=first,
            minutes_elapsed=e.activities[first].duration,
        ),
    )
    today2, plan = e.next_activities(st, log, ctx)  # mid-day: minutes already used today count
    assert today2 is None or today2.duration <= ctx.budget - e.activities[first].duration
    ex = next(
        a for a in e.activities.values() if a.target_concept == "C1" and a.type.value == "EXERCISE"
    )
    for ev in (
        Event(day=1, kind=EventType.FAILED_ASSESSMENT, activity_id=ex.activity_id),
        Event(day=2, kind=EventType.MISSED),
        Event(day=3, kind=EventType.BUDGET_CHANGED, value=10),
        Event(day=3, kind=EventType.DEADLINE_CHANGED, value=12),
    ):
        st, log = e.record(st, log, ev)
        _, plan = e.next_activities(st, log, dataclasses.replace(ctx, current_day=ev.day))
        assert plan.status in (PlanStatus.FEASIBLE, PlanStatus.INFEASIBLE, PlanStatus.UNKNOWN)
        days = plan.days or plan.best_effort_days
        assert _plan_prereq(e, st, plan, days) == 0


@pytest.mark.parametrize("method", ["cpsat", "hybrid"])
def test_with_f1_confirmation_checks_gate_dependants(method):
    e = _eng(method, base=bisection_config())
    st = e.diagnose(e.init_learner(), lambda a: True, session_id="t").state
    plan = e.plan(st, PlanContext(goal="C8", deadline_day=10, budget=15))
    assert plan.status == PlanStatus.FEASIBLE
    acts = [a for d in plan.days for a in d.activities]
    assert all(e.activities[a].type.value == "EXERCISE" for a in acts)  # checks, no lessons
    # the plan-level audit projects D4 only and does not know confirmation, so replay the planned
    # checks as correct answers and audit the executed log with the engine's mastered rule
    log = ExecutionLog()
    for d in plan.days:
        for a in d.activities:
            log = log.append(
                Event(
                    day=d.day,
                    kind=EventType.COMPLETED,
                    activity_id=a,
                    minutes_elapsed=e.activities[a].duration,
                    correct=True,
                    attempt_id=f"{a}-{d.day}-{len(log.events)}",
                )
            )
    assert executed_violations(e, st, log) == 0


@pytest.mark.parametrize("method", ["cpsat", "hybrid"])
def test_with_fitted_profile_plans_are_valid(method):
    e = _eng(method, model_profile="config/fitted_assist09.json")
    for dl in (5, 10):
        plan = e.plan(e.init_learner(), PlanContext(goal="C8", deadline_day=dl, budget=15))
        days = plan.days or plan.best_effort_days
        assert _plan_prereq(e, e.init_learner(), plan, days) == 0


# ---------------- CLI (D89) ----------------


def _cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        ret = main(argv)
    return ret, out.getvalue(), err.getvalue()


@pytest.fixture
def snap(tmp_path):
    e = _eng("greedy")
    path = str(tmp_path / "snap.json")
    save_snapshot(
        e.init_learner(),
        ExecutionLog(),
        path,
        context=PlanContext(goal="C8", deadline_day=5, budget=10),
    )
    return path


ARGS = [
    "plan",
    "--curriculum",
    f"{CUR}/curriculum_8node.json",
    "--activities",
    f"{CUR}/activities_8node.json",
]


@pytest.mark.parametrize("method", ["cpsat", "hybrid"])
def test_cli_planner_via_config_matches_python(tmp_path, snap, method):
    f = tmp_path / "f3.json"
    f.write_text(json.dumps({"planner_method": method}))
    ret, out, err = _cli(ARGS + ["--snapshot", snap, "--json", "--config", str(f)])
    assert ret is None, err
    e = _eng(method)
    st, _ = load_snapshot(snap, tuple(sorted(e.graph.concepts())))
    want = serialize_plan(e.plan(st, PlanContext(goal="C8", deadline_day=5, budget=10)), e.config)
    assert json.loads(out) == json.loads(json.dumps(want))


def test_cli_without_ortools_fails_clearly(tmp_path, snap, monkeypatch):
    monkeypatch.setitem(sys.modules, "ortools.sat.python", None)
    monkeypatch.setitem(sys.modules, "ortools.sat.python.cp_model", None)
    f = tmp_path / "f3.json"
    f.write_text(json.dumps({"planner_method": "cpsat"}))
    ret, _, err = _cli(ARGS + ["--snapshot", snap, "--json", "--config", str(f)])
    assert ret == 2 and "[cpsat]" in err
