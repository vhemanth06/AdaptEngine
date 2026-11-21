"""Shared helpers for the web API tests (formerly in test_api.py)."""

import json

from adaptengine.api import Engine
from adaptengine.core.config import DEFAULT_CONFIG

KNOWN = {"C1", "C2", "C3", "C6"}  # scripted demo learner: knows these concepts


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


def _engine(curriculum, cfg=DEFAULT_CONFIG):
    from frontend.api import app as app_module

    return Engine.from_files(
        str(app_module.DATA / "curriculum" / f"curriculum_{curriculum}.json"),
        str(app_module.DATA / "curriculum" / f"activities_{curriculum}.json"),
        str(app_module.MANIFEST),
        config=cfg,
    )
