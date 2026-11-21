"""TestClient tests for the demo adapter (T8.2): curriculum list and detail. Skipped when the demo extra is not installed."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")


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
