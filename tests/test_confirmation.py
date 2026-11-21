"""Plan 3 (F1-T5 to F1-T7): learner flags, epsilon confirmation, planner confirmation path and
the closed loop (F1-TC7, TC8, TC9)."""

import contextlib
import dataclasses
import io
import json
import os
import sys

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from adaptengine.api import Engine  # noqa: E402
from adaptengine.cli import main  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG, bisection_config  # noqa: E402
from adaptengine.core.schema import Event, EventType, PlanContext  # noqa: E402
from adaptengine.learner.adapter import CustomBKT  # noqa: E402
from adaptengine.learner.evidence import update_concept_evidence  # noqa: E402
from adaptengine.learner.state import (  # noqa: E402
    ExecutionLog,
    LearnerConcept,
    LearnerState,
    is_evidence_mastered,
)
from adaptengine.planner import compute_workload, serialize_plan  # noqa: E402
from adaptengine.session import (  # noqa: E402
    deserialize_learner,
    load_snapshot,
    save_snapshot,
    serialize_learner,
)
from experiments.core.audit import executed_violations as count_executed_prereq_violations  # noqa: E402

CUR = os.path.join(repo_root, "data", "curriculum")
ALL8 = {f"C{i}" for i in range(1, 9)}
CTX = PlanContext(goal="C8", deadline_day=10, budget=15)


def _eng(name="8node_x10", cfg=None):
    return Engine.from_files(
        f"{CUR}/curriculum_{name}.json",
        f"{CUR}/activities_{name}.json",
        config=cfg or bisection_config(),
        allow_unreviewed=name.endswith("x10"),
    )


def _advanced(e):
    return e.diagnose(e.init_learner(), lambda a: a.target_concept in ALL8, session_id="t").state


def _rec(e, st, log, aid, ok, day=1):
    a = e.activities[aid]
    return e.record(
        st,
        log,
        Event(
            day=day,
            kind=EventType.COMPLETED,
            activity_id=aid,
            minutes_elapsed=a.duration,
            correct=ok,
        ),
    )


def _reasons(plan):
    return {
        (t.get("concept_id"), t["reason"])
        for t in plan.trace
        if t.get("decision") in ("OMITTED", "CONFIRMATION")
    }


# ---------------- F1-T5: learner fields and the epsilon test ----------------


def test_flags_default_and_serialization():
    c = LearnerConcept("C1")
    assert c.diag_confident is False and c.confirmed is False
    st = LearnerState(
        concepts={"C1": c, "C2": LearnerConcept("C2", diag_confident=True, confirmed=False)}
    )
    data = serialize_learner(st)
    assert "diag_confident" not in data["concepts"]["C1"]  # unchanged files without F1 flags
    assert data["concepts"]["C2"]["diag_confident"] is True
    assert deserialize_learner(data, ("C1", "C2")) == st
    old = {"schema_version": 1, "concepts": {"C1": {"p": 0.3}}}
    assert deserialize_learner(old, ("C1",)).concepts["C1"].confirmed is False


@pytest.mark.parametrize(
    "p,d,correct", [(0.9, 0.5, True), (0.95, 0.5, True), (0.8, 0.2, True), (0.95, 0.5, False)]
)
def test_epsilon_test_f1_tc7(p, d, correct):
    cfg = bisection_config()
    m = CustomBKT(cfg)
    c = LearnerConcept("C1", p=p, diag_confident=True)
    new, _ = update_concept_evidence(c, d, correct, transition=cfg.t_exercise, model=m, cfg=cfg)
    p_obs = m.update(p, d, correct, 0.0)
    assert new.confirmed == (p_obs >= 1 - cfg.confirm_epsilon)
    off, _ = update_concept_evidence(c, d, correct, transition=0.1, model=m, cfg=DEFAULT_CONFIG)
    assert off.confirmed is False and off.diag_confident is True  # flag off: untouched


def test_failed_check_out_of_reach_clears_diag_confident():
    cfg = bisection_config()
    c = LearnerConcept("C1", p=0.5, diag_confident=True)
    new, _ = update_concept_evidence(c, 0.5, False, transition=0.0, model=CustomBKT(cfg), cfg=cfg)
    assert new.diag_confident is False and new.confirmed is False


def test_mastered_test_with_confirmation():
    c = LearnerConcept("C1", p=0.99, responses=1, correct_responses=1, confirmed=True)
    assert is_evidence_mastered(c, bisection_config()) is True
    assert is_evidence_mastered(c, DEFAULT_CONFIG) is False  # D4 alone: k = 2 answers
    low = dataclasses.replace(c, p=0.5)
    assert is_evidence_mastered(low, bisection_config()) is False  # p < theta revokes


def test_diagnostic_confirms_only_direct_answers():
    e = _eng("8node")
    st = _advanced(e)
    for cid, c in st.concepts.items():
        if c.confirmed:
            assert c.responses >= 1 and c.p >= 0.98
        if c.responses == 0:
            assert not c.confirmed
    assert st.concepts["C5"].confirmed and st.concepts["C7"].confirmed  # F1.4.6
    assert all(st.concepts[c].diag_confident for c in ("C1", "C2", "C3", "C6", "C8"))
    plain = _eng("8node", dataclasses.replace(bisection_config(), confirm_diag_confident=False))
    assert not any(c.diag_confident or c.confirmed for c in _advanced(plain).concepts.values())


# ---------------- F1-T6: planner confirmation path ----------------


def test_worked_example_checks_only_f1_tc8():
    e = _eng("8node")
    plan = e.plan(_advanced(e), CTX)
    acts = [a for d in plan.days for a in d.activities]
    assert {e.activities[a].target_concept for a in acts} == {"C1", "C2", "C3", "C6", "C8"}
    assert all(e.activities[a].type.value == "EXERCISE" for a in acts)  # no lessons
    assert {("C5", "CONFIRMED_BY_DIAGNOSTIC"), ("C7", "CONFIRMED_BY_DIAGNOSTIC")} <= _reasons(plan)
    for c in ("C1", "C2", "C3", "C6", "C8"):
        assert (c, "CONFIRMATION_CHECK") in _reasons(plan)
    assert len(acts) <= 6


def test_dependants_wait_for_checks_f1_tc8():
    e = _eng("8node")
    init = e.init_learner()
    concepts = dict(init.concepts)
    concepts["C1"] = dataclasses.replace(concepts["C1"], p=0.97, diag_confident=True)
    concepts["C2"] = dataclasses.replace(concepts["C2"], p=0.97, diag_confident=True)
    plan = e.plan(
        LearnerState(concepts=concepts), PlanContext(goal="C3", deadline_day=10, budget=15)
    )
    order = [(d.day, i, a) for d in plan.days for i, a in enumerate(d.activities)]
    first_c3 = min(k for k in order if e.activities[k[2]].target_concept == "C3")
    for k in order:
        if e.activities[k[2]].target_concept in ("C1", "C2"):
            assert k < first_c3


def test_routing_prefers_study_when_checks_unlikely_to_pass():
    e = _eng("8node")
    init = e.init_learner()
    mid = dataclasses.replace(init.concepts["C1"], p=0.3, diag_confident=True)
    st = LearnerState(concepts={**init.concepts, "C1": mid})
    wl, trace, _ = compute_workload(e.graph, e.activities, st, "C1", model=e.model, cfg=e.config)
    assert any(a.type.value == "LESSON" for a in wl["C1"])
    assert not any(t.get("reason") == "CONFIRMATION_CHECK" for t in trace)


def test_flag_off_workload_ignores_flags():
    e = _eng("8node", DEFAULT_CONFIG)
    st = _advanced(_eng("8node"))  # carries diag_confident / confirmed flags
    plain = LearnerState(
        concepts={
            c: dataclasses.replace(x, diag_confident=False, confirmed=False)
            for c, x in st.concepts.items()
        }
    )
    assert compute_workload(
        e.graph, e.activities, st, "C8", model=e.model, cfg=e.config
    ) == compute_workload(e.graph, e.activities, plain, "C8", model=e.model, cfg=e.config)


# ---------------- F1-T7: closed loop (8node_x10, plus 8node exercise exhaustion) ----------------


def test_closed_loop_passes_confirm_and_plan_shrinks_f1_tc9():
    e = _eng()
    st, log = _advanced(e), ExecutionLog()
    today, plan = e.next_activities(st, log, CTX)
    n0 = sum(len(d.activities) for d in plan.days)
    for aid in today.activities:
        st, log = _rec(e, st, log, aid, True)
    assert all(st.concepts[c].confirmed for c in ("C1", "C2", "C3", "C6", "C8"))
    _, plan = e.next_activities(st, log, CTX)
    assert sum(len(d.activities) for d in plan.days) < n0
    assert count_executed_prereq_violations(e, _advanced(e), log) == 0


def test_closed_loop_slip_then_failures_return_lessons_f1_tc9():
    e = _eng()
    st, log = _advanced(e), ExecutionLog()
    today, _ = e.next_activities(st, log, CTX)
    c8 = next(a for a in today.activities if "-C8-" in a)
    st, log = _rec(e, st, log, c8, False)
    today, plan = e.next_activities(st, log, CTX)
    assert ("C8", "CONFIRMATION_CHECK") in _reasons(plan)  # one slip: still checking
    c8 = next(a for a in today.activities if "-C8-" in a)
    st, log = _rec(e, st, log, c8, False)
    _, plan = e.next_activities(st, log, CTX)
    assert ("C8", "CONFIRMATION_CHECK") not in _reasons(plan)
    planned = [a for d in plan.days for a in d.activities]
    assert "L-C8" in planned  # repeated failures: the lesson is back
    assert count_executed_prereq_violations(e, _advanced(e), log) == 0


def test_low_p_after_failures_triggers_remediation():
    e = _eng()
    st, log = _advanced(e), ExecutionLog()
    hard = [a for a in e.activities if a.startswith("E-C8-")]
    for aid in hard[:4]:
        st, log = _rec(e, st, log, aid, False)
    assert st.concepts["C8"].p < e.config.remediation_threshold
    assert st.concepts["C8"].needs_remediation


def test_replan_events_keep_working_with_flags():
    e = _eng()
    st, log = _advanced(e), ExecutionLog()
    for ev in (
        Event(day=1, kind=EventType.MISSED),
        Event(day=2, kind=EventType.BUDGET_CHANGED, value=10),
        Event(day=2, kind=EventType.DEADLINE_CHANGED, value=6),
    ):
        st, log = e.record(st, log, ev)
        today, plan = e.next_activities(st, log, dataclasses.replace(CTX, current_day=2))
        assert plan.status.value in ("FEASIBLE", "INFEASIBLE", "UNKNOWN")


def test_original_8node_checks_repeat_items_when_exhausted():
    """D41: once a concept's 4 exercises are used, a check repeats the least recently seen one."""
    e = _eng("8node")
    st, log = _advanced(e), ExecutionLog()
    for aid in [a for a in e.activities if a.startswith("E-C8-")]:
        st, log = _rec(e, st, log, aid, aid.endswith("0.2"))  # 4 answers, mixed
    # below theta, so D4 does not hold yet, but a couple of checks could confirm it
    c8 = dataclasses.replace(
        st.concepts["C8"], p=0.8, diag_confident=True, confirmed=False, needs_remediation=False
    )
    st = LearnerState(concepts={**st.concepts, "C8": c8})
    done = tuple(ev.activity_id for ev in log.events if ev.activity_id)
    wl, trace, _ = compute_workload(
        e.graph, e.activities, st, "C8", done_ids=done, model=e.model, cfg=e.config
    )
    assert any(t.get("reason") == "CONFIRMATION_CHECK" and t["concept_id"] == "C8" for t in trace)
    assert wl["C8"] and set(a.activity_id for a in wl["C8"]) <= set(done)


def test_cli_plan_with_confirmation_config_matches_python(tmp_path):
    e = _eng("8node")
    st = _advanced(e)
    snap = str(tmp_path / "snap.json")
    save_snapshot(st, ExecutionLog(), snap, context=CTX)
    cfg_file = tmp_path / "f1.json"
    cfg_file.write_text(json.dumps({"confirm_diag_confident": True}))
    args = [
        "plan",
        "--curriculum",
        f"{CUR}/curriculum_8node.json",
        "--activities",
        f"{CUR}/activities_8node.json",
        "--snapshot",
        snap,
        "--json",
    ]
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        assert main(args + ["--config", str(cfg_file)]) is None
    py = _eng("8node", dataclasses.replace(DEFAULT_CONFIG, confirm_diag_confident=True))
    loaded, _ = load_snapshot(snap, tuple(sorted(ALL8)))
    want = json.loads(json.dumps(serialize_plan(py.plan(loaded, CTX), py.config)))
    assert json.loads(out.getvalue()) == want
    out2 = io.StringIO()
    with contextlib.redirect_stdout(out2):
        assert main(args) is None
    plain = _eng("8node", DEFAULT_CONFIG)
    assert json.loads(out2.getvalue()) == json.loads(
        json.dumps(serialize_plan(plain.plan(loaded, CTX), plain.config))
    )


def test_unconfirmed_concept_always_gets_a_check_regression():
    """F1 grid H1 failure (seed 1060): an inferred concept slipped on its first check; its p after
    learning (0.981) was already >= 1 - epsilon with one direct answer, so the planner planned zero
    checks, the empty workload counted as done, and dependants started while it was unconfirmed."""
    e = _eng("8node")
    init = e.init_learner()
    c1 = dataclasses.replace(
        init.concepts["C1"], p=0.981, responses=1, correct_responses=0, diag_confident=True
    )
    st = LearnerState(concepts={**init.concepts, "C1": c1})
    assert not is_evidence_mastered(c1, e.config)
    wl, trace, _ = compute_workload(e.graph, e.activities, st, "C3", model=e.model, cfg=e.config)
    assert len(wl["C1"]) >= 1  # never an empty, "done" workload for an unconfirmed concept
    plan = e.plan(st, PlanContext(goal="C3", deadline_day=10, budget=15))
    order = [a for d in plan.days for a in d.activities]
    first_c3 = next(i for i, a in enumerate(order) if e.activities[a].target_concept == "C3")
    assert any(e.activities[a].target_concept == "C1" for a in order[:first_c3])
