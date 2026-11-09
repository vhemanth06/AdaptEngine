"""TestClient tests for the demo adapter (T8.2). Skipped when the demo extra is not installed."""

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from adaptengine.api import Engine  # noqa: E402
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


def test_end_to_end_plan_matches_direct_engine(client, engine):
    """create -> diagnose -> plan -> answer -> disrupt; the API plan equals a direct Engine call."""
    sid = _new(client)["session_id"]
    view = _run_diagnostic(client, sid)
    direct = engine.diagnose(
        engine.init_learner(), lambda a: a.target_concept in KNOWN, session_id=sid
    )
    state, log = direct.state, ExecutionLog()
    ctx = PlanContext(goal="C8", deadline_day=10, budget=10)

    def check(api_view):
        today, plan = engine.next_activities(state, log, ctx)
        assert api_view["plan"] == _norm(serialize_plan(plan, engine.config))
        want = today and {"day": today.day, "activities": list(today.activities)}
        assert api_view["today"] == (want and want | {"duration": today.duration})

    view = client.post(f"/api/sessions/{sid}/plan", json={}).json()
    check(view)
    for correct in (None, False, True):
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
    day = view["effective"]["current_day"]
    view = client.post(f"/api/sessions/{sid}/events", json={"kind": "MISSED"}).json()["session"]
    state, log = engine.record(state, log, Event(day=day, kind=EventType.MISSED))
    check(view)
