"""TestClient tests for the demo adapter (T8.2). Skipped when the demo extra is not installed."""

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from dataclasses import replace  # noqa: E402

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.core.schema import Event, EventType, PlanContext  # noqa: E402
from adaptengine.learner.state import ExecutionLog  # noqa: E402
from adaptengine.planner import serialize_plan  # noqa: E402
from frontend.api import app as app_module  # noqa: E402

KNOWN = {"C1", "C2", "C3", "C6"}  # scripted demo learner: knows these concepts


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADAPTENGINE_SESSIONS_DIR", str(tmp_path / "sessions"))
    return TestClient(app_module.app)


@pytest.fixture(scope="module")
def engine():
    data = app_module.DATA
    return Engine.from_files(
        str(data / "curriculum" / "curriculum_8node.json"),
        str(data / "curriculum" / "activities_8node.json"),
        str(app_module.MANIFEST),
    )


def _new(client, **kw):
    body = {"curriculum": "8node", "goal": "C8", "deadline_day": 10, "budget": 10, **kw}
    r = client.post("/api/sessions", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _run_diagnostic(client, sid):
    view = client.get(f"/api/sessions/{sid}").json()
    while not view["diagnostic"]["done"]:
        item = view["diagnostic"]["next_item"]
        body = {"activity_id": item["activity_id"], "correct": item["concept_id"] in KNOWN}
        r = client.post(f"/api/sessions/{sid}/diagnostic/answer", json=body)
        assert r.status_code == 200, r.text
        view = r.json()
    return view


def _norm(x):
    return json.loads(json.dumps(x))


def test_list_and_get_curricula(client):
    rows = {r["id"]: r for r in client.get("/api/curricula").json()}
    assert rows["8node"]["reviewed"] and rows["8node"]["has_content"]
    assert rows["4node"]["concepts"] == 4 and not rows["4node"]["has_content"]
    d = client.get("/api/curricula/8node").json()
    assert len(d["concepts"]) == 8 and d["content"]["L-C1"]["markdown"]
    assert {c["concept_id"]: c["depth"] for c in d["concepts"]}["C8"] == 4
    assert client.get("/api/curricula/4node").json()["content"] is None


def test_8node_x10_listed_as_reviewed(client):
    """FE-TC1 (D93): the owner reviewed the 8node_x10 files, so the demo lists them as reviewed."""
    row = {r["id"]: r for r in client.get("/api/curricula").json()}["8node_x10"]
    assert row["reviewed"] is True and row["review_error"] is None
    assert row["has_content"] and row["content_reviewer"] == "vhemanth06"
    assert client.get("/api/curricula/nope").status_code == 404


def test_create_session_validates_input(client):
    assert client.post("/api/sessions", json={"curriculum": "8node"}).status_code == 422
    bad_budget = {"curriculum": "8node", "goal": "C8", "deadline_day": 10, "budget": 7}
    assert client.post("/api/sessions", json=bad_budget).status_code == 422
    bad_goal = {**bad_budget, "budget": 10, "goal": "C99"}
    assert client.post("/api/sessions", json=bad_goal).status_code == 422
    bad_id = {**bad_budget, "budget": 10, "curriculum": "../etc"}
    assert client.post("/api/sessions", json=bad_id).status_code == 422
    assert client.get("/api/sessions/../../x").status_code == 404
    assert client.get("/api/sessions/" + "0" * 32).status_code == 404


def test_plan_feasible_then_not_with_best_effort(client):
    sid = _new(client)["session_id"]
    view = client.post(f"/api/sessions/{sid}/plan", json={}).json()
    assert view["plan"]["status"] == "FEASIBLE" and view["today"]["day"] == 1
    assert view["replan_ms"] >= 0
    view = client.post(f"/api/sessions/{sid}/plan", json={"budget": 5, "deadline_day": 5}).json()
    assert view["plan"]["status"] == "INFEASIBLE"
    assert view["plan"]["shortfall_days"] > 0 and view["plan"]["options"]
    assert view["plan"]["best_effort_days"] and view["context"]["budget"] == 5
    assert client.post(f"/api/sessions/{sid}/plan", json={"budget": 7}).status_code == 422


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


def test_events_remediation_diff_and_disruptions(client):
    sid = _new(client)["session_id"]
    view = _run_diagnostic(client, sid)
    for _ in range(6):  # do today's work, answering every exercise wrong
        aid = view["today"]["activities"][0]
        body = {"kind": "COMPLETED", "activity_id": aid}
        if aid.startswith("E-"):
            body["correct"] = False
        res = client.post(f"/api/sessions/{sid}/events", json=body).json()
        view = res["session"]
        if res["update"]["needs_remediation"]:
            break
    assert res["update"]["needs_remediation"] and res["update"]["p_after"] < 0.4
    assert res["update"]["explanation"]
    assert any(c["activity_id"] == aid and c["new_day"] is None for c in res["changes"])
    reasons = {r.get("reason") for r in view["plan"]["trace"]}
    assert "REMEDIATION_INSERTED" in reasons
    day = view["effective"]["current_day"]
    res = client.post(f"/api/sessions/{sid}/events", json={"kind": "MISSED"}).json()
    assert res["session"]["effective"]["current_day"] == day + 1 and res["changes"]
    bad = {"kind": "BUDGET_CHANGED", "value": 7}
    assert client.post(f"/api/sessions/{sid}/events", json=bad).status_code == 422
    res = client.post(f"/api/sessions/{sid}/events", json={"kind": "BUDGET_CHANGED", "value": 5})
    assert res.json()["session"]["effective"]["budget"] == 5
    noans = {"kind": "COMPLETED", "activity_id": "E-C8-0.2"}
    assert client.post(f"/api/sessions/{sid}/events", json=noans).status_code == 422
    unknown = {"kind": "COMPLETED", "activity_id": "E-X"}
    assert client.post(f"/api/sessions/{sid}/events", json=unknown).status_code == 422
    # diagnostic is closed once study events exist
    item = {"activity_id": "E-C1-0.2", "correct": True}
    assert client.post(f"/api/sessions/{sid}/diagnostic/answer", json=item).status_code == 409


def test_trace_filters_one_activity(client):
    sid = _new(client)["session_id"]
    assert client.get(f"/api/sessions/{sid}/trace").status_code == 409
    view = client.post(f"/api/sessions/{sid}/plan", json={}).json()
    aid = view["today"]["activities"][0]
    tr = client.get(f"/api/sessions/{sid}/trace", params={"activity_id": aid}).json()
    sel = [r for r in tr["records"] if r["decision"] == "SELECTED"]
    assert sel and "score_components" in sel[0]
    assert all(r["decision"] == "DEFERRED" for r in tr["deferred_same_day"])
    full = client.get(f"/api/sessions/{sid}/trace").json()
    assert len(full["records"]) == len(view["plan"]["trace"])


def test_simulate(client):
    body = {"curriculum": "4node", "goal": "C4", "budget": 15, "n_seeds": 2, "arm": "static"}
    out = client.post("/api/simulate", json=body).json()
    assert [e["seed"] for e in out["episodes"]] == [100, 101]
    assert out["scenario"]["name"] == "missed_day"
    again = client.post("/api/simulate", json=body).json()
    assert again == out  # deterministic
    out = client.post("/api/simulate", json={**body, "budget": 5, "scenario": "budget_drop"})
    assert out.json()["episodes"] == [] and out.json()["note"]
    assert client.post("/api/simulate", json={**body, "arm": "x"}).status_code == 422


def test_evaluation_tolerates_missing_and_broken_files(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RESULTS_DIR", tmp_path)
    assert client.get("/api/evaluation").json() == {"files": []}
    (tmp_path / "evaluation_results.json").write_text("{not json")
    (tmp_path / "w7_matrix.json").write_text(json.dumps({"a": 1, "per_seed_runs": [1]}))
    files = client.get("/api/evaluation").json()["files"]
    assert files == [{"name": "w7_matrix.json", "data": {"a": 1}}]


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


@pytest.mark.parametrize(
    "profile", ["fitted_sim", "config/fitted_assist09.json", "../../etc/passwd"]
)
def test_model_profile_allowlist(client, profile):
    """Only named profiles are accepted: no paths from clients, and never fitted_sim (D60)."""
    body = {"curriculum": "8node", "goal": "C8", "deadline_day": 10, "budget": 10}
    r = client.post("/api/sessions", json=body | {"model_profile": profile})
    assert r.status_code == 422


# ------------------------------------------------------------------------------ Plan FE


def _engine(curriculum, cfg=DEFAULT_CONFIG):
    return Engine.from_files(
        str(app_module.DATA / "curriculum" / f"curriculum_{curriculum}.json"),
        str(app_module.DATA / "curriculum" / f"activities_{curriculum}.json"),
        str(app_module.MANIFEST),
        config=cfg,
    )


def test_health_fields(client):
    """FE-TC2 / FE.3 item 1."""
    from experiments.provenance import code_hash

    from adaptengine.core.config import config_hash

    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["api_version"] == app_module.app.version
    assert h["code_hash"] == code_hash()
    assert h["config_hash_default"] == config_hash(DEFAULT_CONFIG)
    assert isinstance(h["ortools_available"], bool) and isinstance(h["engine_version"], str)
    assert h["content_review"]["8node_x10"] == "vhemanth06"
    assert h["content_review"]["8node"] == "PENDING_HUMAN_REVIEW"  # still pending (D93)
    assert h["content_review"]["4node"] is None  # no content file
    rows = {r["id"]: r["reviewed"] for r in client.get("/api/curricula").json()}
    assert h["curriculum_review"] == rows and rows["8node_x10"] is True
    assert h["web_build"] in ("fresh", "stale", "missing")


def test_default_session_flags_false(client):
    """FE-TC3: a sweep session never shows confirmation flags, and its info is empty."""
    sid = _new(client)["session_id"]
    first = client.get(f"/api/sessions/{sid}").json()["diagnostic"]
    assert first["info"] is None and set(first["live_p"].values()) == {DEFAULT_CONFIG.p0}
    view = _run_diagnostic(client, sid)
    assert not any(c["diag_confident"] or c["confirmed"] for c in view["concepts"])
    assert not view["diagnostic"]["info"]


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


def test_trace_confirmation_record(client):
    """FE-TC4: /trace returns the plan's CONFIRMATION record for its check activities only."""
    sid = _new(client, diagnostic_method="bisection")["session_id"]
    view = _run_diagnostic(client, sid)
    conf = [r for r in view["plan"]["trace"] if r.get("decision") == "CONFIRMATION"]
    assert conf  # the scripted learner on 8node gets confirmation checks
    for r in conf:
        for aid in r["activity_ids"]:
            tr = client.get(f"/api/sessions/{sid}/trace", params={"activity_id": aid}).json()
            assert tr["confirmation"] == r
    checks = {a for r in conf for a in r["activity_ids"]}
    other = next(a for d in view["plan"]["days"] for a in d["activities"] if a not in checks)
    tr = client.get(f"/api/sessions/{sid}/trace", params={"activity_id": other}).json()
    assert tr["confirmation"] is None


def _direct_episodes(engine, body, diagnose):
    from experiments.arms import get_scenario, run_episode
    from experiments.sim import PROFILES

    sc = get_scenario(
        body.get("scenario", "missed_day"),
        engine,
        engine.init_learner(),
        goal=body["goal"],
        budget=body.get("budget", 15),
    )
    out = []
    for seed in range(100, 100 + body["n_seeds"]):
        ep = run_episode(
            engine,
            seed=seed,
            scenario=sc,
            arm=body.get("arm", "adapt"),
            profile=PROFILES["nominal"],
            diagnose=diagnose,
        )
        ep["executed_minutes_per_day"] = {
            str(d): m for d, m in ep["executed_minutes_per_day"].items()
        }
        out.append(ep)
    return out


def _same(api_eps, direct_eps):
    for a, d in zip(api_eps, direct_eps, strict=True):
        assert {k: v for k, v in a.items() if v is not None} == {
            k: v for k, v in _norm(d).items() if k in a
        }


def test_simulate_default_unchanged(client):
    """FE-TC3: without the new fields /simulate is today's call (default engine, no diagnostic)."""
    body = {"curriculum": "8node", "goal": "C8", "budget": 15, "n_seeds": 2}
    eps = client.post("/api/simulate", json=body).json()["episodes"]
    assert all(e["diag_items"] is None for e in eps)
    _same(eps, _direct_episodes(app_module._bundle("8node").engine, body, diagnose=False))


def test_simulate_diagnostics_compare(client):
    """FE.3 item 6: sweep vs bisection, the diagnostic first; equal to direct run_episode calls."""
    body = {"curriculum": "8node", "goal": "C8", "budget": 15, "n_seeds": 2, "scenario": "calm"}
    for method in ("sweep", "bisection"):
        eps = client.post("/api/simulate", json=body | {"diagnostic_method": method}).json()
        eps = eps["episodes"]
        assert all(isinstance(e["diag_items"], int) and e["diag_items"] > 0 for e in eps)
        engine = app_module._bundle("8node", "heuristic", method, "greedy").engine
        _same(eps, _direct_episodes(engine, body, diagnose=True))


def test_demo_preset(client):
    """FE-TC6 (D94): the stored preset shows every step the walkthrough claims."""
    pytest.importorskip("ortools")
    from frontend.api import demo
    from frontend.api.select_demo_preset import evaluate

    p = client.get("/api/demo-preset").json()
    assert p == demo.PRESET
    passed, d = evaluate(client, p["known"], p["model_profile"], p["deadline_day"], p["budget"])
    assert passed["1"] and passed["2b"] and passed["5"]  # reviewed; something INFERRED; tight
    assert passed["2a"] == demo.FEWER_QUESTIONS  # dropped from the walkthrough when false (§FE.6)
    assert d["tight"]["deadline_day"] == p["tight"]["deadline_day"]
    assert d["tight"]["budget"] == p["tight"]["budget"]
    assert d["tight"]["options"]
    assert (passed["3"] and passed["4"]) == p["has_check"] == demo.HAS_CHECK
    if p["has_check"]:  # Study step 5: a wrong answer on the check replans at once
        step5 = d["study_wrong_on_check"]
        assert step5["activity_id"] == p["wrong_check"] == demo.WRONG_CHECK
        assert step5["changes"] > 0
        assert step5["diag_confident_after"] and not step5["confirmed_after"]  # still pending


# ------------------------------------------------------------------------------ next day (D96)


def test_finished_day_waits_for_next_day(client):
    """A finished day stays complete (no slice), also once its budget is used; only "Next day"
    moves on, and work is recorded on the learner's day (D96)."""
    sid = _new(client)["session_id"]
    view = client.post(f"/api/sessions/{sid}/plan", json={}).json()
    assert view["today"]["day"] == 1
    while view["today"]:
        aid = view["today"]["activities"][0]
        body = {"kind": "COMPLETED", "activity_id": aid}
        if aid.startswith("E-"):
            body["correct"] = aid.split("-")[1] in KNOWN
        view = client.post(f"/api/sessions/{sid}/events", json=body).json()["session"]
        assert view["events"][-1]["day"] == 1
    assert view["context"]["current_day"] == 1 and view["today"] is None  # day 1 complete
    nxt = next(
        d for d in view["plan"]["days"] or view["plan"]["best_effort_days"] if d["activities"]
    )
    view = client.post(f"/api/sessions/{sid}/next-day").json()
    assert view["context"]["current_day"] == 2
    assert view["today"]["day"] == 2 and view["today"]["activities"] == nxt["activities"]
    # a missed day moves on too
    assert client.post(f"/api/sessions/{sid}/events", json={"kind": "MISSED"}).status_code == 200
    view = client.get(f"/api/sessions/{sid}").json()
    assert view["events"][-1]["day"] == 2 and view["context"]["current_day"] == 3
    # a Setup re-plan keeps the day
    view = client.post(f"/api/sessions/{sid}/plan", json={}).json()
    assert view["context"]["current_day"] == 3


def test_next_day_not_past_the_deadline(client):
    sid = _new(client, deadline_day=2)["session_id"]
    client.post(f"/api/sessions/{sid}/plan", json={})
    assert client.post(f"/api/sessions/{sid}/next-day").json()["context"]["current_day"] == 2
    assert client.post(f"/api/sessions/{sid}/next-day").status_code == 409  # day 2 = deadline
    client.post(f"/api/sessions/{sid}/events", json={"kind": "DEADLINE_CHANGED", "value": 4})
    view = client.post(f"/api/sessions/{sid}/next-day").json()
    assert view["context"]["current_day"] == 3 and view["effective"]["deadline_day"] == 4
