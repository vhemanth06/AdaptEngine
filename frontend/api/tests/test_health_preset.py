"""TestClient tests for the demo adapter (T8.2): /api/health and the demo preset. Skipped when the demo extra is not installed."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")


from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from frontend.api import app as app_module  # noqa: E402


def test_health_fields(client):
    """FE-TC2 / FE.3 item 1."""
    from adaptengine.core.config import config_hash

    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["api_version"] == app_module.app.version
    assert "code_hash" not in h
    assert h["config_hash_default"] == config_hash(DEFAULT_CONFIG)
    assert isinstance(h["ortools_available"], bool) and isinstance(h["engine_version"], str)
    assert h["content_review"]["8node_x10"] == "vhemanth06"
    assert h["content_review"]["8node"] == "PENDING_HUMAN_REVIEW"  # still pending (D93)
    assert h["content_review"]["4node"] is None  # no content file
    rows = {r["id"]: r["reviewed"] for r in client.get("/api/curricula").json()}
    assert h["curriculum_review"] == rows and rows["8node_x10"] is True
    assert h["web_build"] in ("fresh", "stale", "missing")


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
