"""Shared fixtures for the web API tests (formerly in test_api.py).

FastAPI and the app are imported inside the fixtures, so a missing demo extra still skips the tests
(each test file calls pytest.importorskip) instead of breaking collection of this folder.
"""

import pytest

from adaptengine.api import Engine


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from frontend.api import app as app_module

    monkeypatch.setenv("ADAPTENGINE_SESSIONS_DIR", str(tmp_path / "sessions"))
    return TestClient(app_module.app)


@pytest.fixture(scope="module")
def engine():
    from frontend.api import app as app_module

    data = app_module.DATA
    return Engine.from_files(
        str(data / "curriculum" / "curriculum_8node.json"),
        str(data / "curriculum" / "activities_8node.json"),
        str(app_module.MANIFEST),
    )
