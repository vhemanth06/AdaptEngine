"""TestClient tests for the demo adapter (T8.2): API results equal the engine called directly. Skipped when the demo extra is not installed."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")


from dataclasses import replace  # noqa: E402

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.core.schema import Event, EventType, PlanContext  # noqa: E402
from adaptengine.learner.state import ExecutionLog  # noqa: E402
from adaptengine.planner import serialize_plan  # noqa: E402
from frontend.api import app as app_module  # noqa: E402
from frontend.api.tests.helpers import KNOWN, _engine, _new, _norm, _run_diagnostic  # noqa: E402


def test_diagnostic_stepwise_equals_engine_diagnose(client, engine):
    sid = _new(client)["session_id"]
    first = client.get(f"/api/sessions/{sid}").json()["diagnostic"]["next_item"]
    wrong = {"activity_id": "E-C8-0.2", "correct": True}
    assert client.post(f"/api/sessions/{sid}/diagnostic/answer", json=wrong).status_code == 409
    # choice is graded against the content answer key
    key = client.get("/api/curricula/8node").json()["content"][first["activity_id"]]["correct"]
    body = {"activity_id": first["activity_id"], "choice": key}
    view = client.post(f"/api/sessions/{sid}/diagnostic/answer", json=body).json()
    assert view["diagnostic"]["items"][0]["correct"] is True
    assert view["diagnostic"]["live_p"]["C1"] > 0.2
    view = _run_diagnostic(client, sid)
    direct = engine.diagnose(
        engine.init_learner(), lambda a: a.target_concept in KNOWN, session_id=sid
    )
    api_p = {c["concept_id"]: c["p"] for c in view["concepts"]}
    assert api_p == {c: x.p for c, x in direct.state.concepts.items()}
    reasons = {r["concept_id"]: r["stop_reason"] for r in view["diagnostic"]["concept_results"]}
    assert reasons == {c: r.stop_reason.value for c, r in direct.concept_results.items()}
    assert view["plan"] is not None  # a plan is made as soon as the diagnostic finishes
    done = {"activity_id": first["activity_id"], "correct": True}
    assert client.post(f"/api/sessions/{sid}/diagnostic/answer", json=done).status_code == 409


@pytest.mark.parametrize(
    "profile,method,planner,curriculum",
    [
        ("heuristic", "sweep", "greedy", "8node"),
        ("fitted_assist09", "sweep", "greedy", "8node"),
        ("heuristic", "bisection", "greedy", "8node"),
        ("heuristic", "sweep", "cpsat", "8node"),
        ("heuristic", "sweep", "hybrid", "8node"),
        ("heuristic", "bisection", "cpsat", "8node_x10"),
    ],
)
def test_end_to_end_plan_matches_direct_engine(
    client, engine, profile, method, planner, curriculum
):
    """create -> diagnose -> plan -> answer -> disrupt; the API plan equals a direct Engine call.

    Also with a fitted item model (F2-TC7), the bisection preset (F1-TC11), each planner (F3-TC11)
    and 8node_x10 x bisection x CP-SAT (FE-TC5).
    """
    if planner != "greedy":
        pytest.importorskip("ortools")
    if (profile, method, planner, curriculum) != ("heuristic", "sweep", "greedy", "8node"):
        cfg = (
            replace(DEFAULT_CONFIG, model_profile=f"config/{profile}.json")
            if profile != "heuristic"
            else DEFAULT_CONFIG
        )
        if method == "bisection":
            cfg = replace(cfg, diagnostic_method="bisection", confirm_diag_confident=True)
        if planner != "greedy":
            cfg = replace(cfg, planner_method=planner)
        engine = Engine.from_files(
            str(app_module.DATA / "curriculum" / f"curriculum_{curriculum}.json"),
            str(app_module.DATA / "curriculum" / f"activities_{curriculum}.json"),
            str(app_module.MANIFEST),
            config=cfg,
        )
    extra = {"model_profile": profile} if profile != "heuristic" else {}
    extra["curriculum"] = curriculum
    if method != "sweep":
        extra["diagnostic_method"] = method
    if planner != "greedy":
        extra["planner_method"] = planner
    created = _new(client, **extra)
    assert created["model_profile"] == profile and created["diagnostic_method"] == method
    assert created["planner_method"] == planner
    sid = created["session_id"]
    view = _run_diagnostic(client, sid)
    direct = engine.diagnose(
        engine.init_learner(), lambda a: a.target_concept in KNOWN, session_id=sid
    )
    state, log = direct.state, ExecutionLog()
    ctx = PlanContext(goal="C8", deadline_day=10, budget=10)

    def check(api_view):
        today, plan = engine.next_activities(state, log, ctx)
        assert api_view["plan"] == _norm(serialize_plan(plan, engine.config))
        assert api_view["context"]["current_day"] == ctx.current_day  # the learner's day
        if today is not None and today.day != ctx.current_day:
            today = None  # budget used: that is the next day's work, after "Next day" (D96)
        want = today and {"day": today.day, "activities": list(today.activities)}
        assert api_view["today"] == (want and want | {"duration": today.duration})

    view = client.post(f"/api/sessions/{sid}/plan", json={}).json()
    check(view)
    assert ("model_profile" in view["plan"]) == (profile != "heuristic")
    for correct in (None, False, True):
        if view["today"] is None:  # today's budget used up (fitted profile: two lessons, 8 min)
            break
        aid, d = view["today"]["activities"][0], view["today"]["day"]
        act = engine.activities[aid]
        c = None if act.type.value == "LESSON" else bool(correct)
        body = {"kind": "COMPLETED", "activity_id": aid}
        if c is not None:
            body["correct"] = c
        view = client.post(f"/api/sessions/{sid}/events", json=body).json()["session"]
        ev = Event(
            day=d,
            kind=EventType.COMPLETED,
            activity_id=aid,
            minutes_elapsed=act.duration,
            correct=c,
        )
        state, log = engine.record(state, log, ev)
        check(view)
    day = view["context"]["current_day"]
    view = client.post(f"/api/sessions/{sid}/events", json={"kind": "MISSED"}).json()["session"]
    state, log = engine.record(state, log, Event(day=day, kind=EventType.MISSED))
    ctx = replace(ctx, current_day=day + 1)  # a missed day ends it
    check(view)


def test_bisection_session_info_and_flags(client):
    """FE-TC4 (D45): info, inferred stop reasons and flags are the engine's own."""
    cfg = replace(DEFAULT_CONFIG, diagnostic_method="bisection", confirm_diag_confident=True)
    engine = _engine("8node_x10", cfg)
    sid = _new(client, curriculum="8node_x10", diagnostic_method="bisection")["session_id"]
    first = client.get(f"/api/sessions/{sid}").json()["diagnostic"]
    prior = engine.diagnose(engine.init_learner(), lambda a: True, session_id=sid, item_limit=0)
    assert first["info"] == _norm(dict(prior.info))  # no answer yet: the engine's prior
    assert first["live_p"] == {c: x.p for c, x in prior.state.concepts.items()}
    assert first["live_p"]["C1"] != engine.init_learner().concepts["C1"].p  # not p0
    view = _run_diagnostic(client, sid)
    info = view["diagnostic"]["info"]
    assert {"n_max", "mode", "top_state"} <= set(info) and isinstance(info["top_state"], list)
    direct = engine.diagnose(
        engine.init_learner(), lambda a: a.target_concept in KNOWN, session_id=sid
    )
    assert info == _norm(dict(direct.info))
    reasons = {r["concept_id"]: r["stop_reason"] for r in view["diagnostic"]["concept_results"]}
    assert "INFERRED" in reasons.values()
    assert reasons == {c: r.stop_reason.value for c, r in direct.concept_results.items()}
    flags = {c["concept_id"]: (c["diag_confident"], c["confirmed"]) for c in view["concepts"]}
    assert flags == {c: (x.diag_confident, x.confirmed) for c, x in direct.state.concepts.items()}
    assert any(f[0] for f in flags.values())
