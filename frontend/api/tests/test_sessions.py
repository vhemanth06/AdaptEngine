"""TestClient tests for the demo adapter (T8.2): session lifecycle (create, plan, events, trace, flags, day handling). Skipped when the demo extra is not installed."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")


from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from frontend.api.tests.helpers import KNOWN, _new, _run_diagnostic  # noqa: E402


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


@pytest.mark.parametrize(
    "profile", ["fitted_sim", "config/fitted_assist09.json", "../../etc/passwd"]
)
def test_model_profile_allowlist(client, profile):
    """Only named profiles are accepted: no paths from clients, and never fitted_sim (D60)."""
    body = {"curriculum": "8node", "goal": "C8", "deadline_day": 10, "budget": 10}
    r = client.post("/api/sessions", json=body | {"model_profile": profile})
    assert r.status_code == 422


def test_default_session_flags_false(client):
    """FE-TC3: a sweep session never shows confirmation flags, and its info is empty."""
    sid = _new(client)["session_id"]
    first = client.get(f"/api/sessions/{sid}").json()["diagnostic"]
    assert first["info"] is None and set(first["live_p"].values()) == {DEFAULT_CONFIG.p0}
    view = _run_diagnostic(client, sid)
    assert not any(c["diag_confident"] or c["confirmed"] for c in view["concepts"])
    assert not view["diagnostic"]["info"]


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
