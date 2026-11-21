"""V2-TC5: no full run without a registered pre-registration (status and registration time)."""

import pytest

from experiments.core.prereg import NotRegistered, guard


def _write(tmp_path, status, utc="2026-11-21T10:00:00+00:00", extra="Code hash: x\n"):
    # a "Code hash:" line from before D104 may still be present; the guard ignores it
    p = tmp_path / "EX_2026-11-21.md"
    utc_line = f"Registered UTC: {utc}\n" if utc else ""
    p.write_text(f"# EX\n\nStatus: {status}\n{utc_line}{extra}", encoding="utf-8")
    return str(p)


def test_draft_is_refused(tmp_path):
    with pytest.raises(NotRegistered):
        guard("EX", smoke=False, path=_write(tmp_path, "DRAFT"))


def test_registered_runs(tmp_path):
    info = guard("EX", smoke=False, path=_write(tmp_path, "Registered"))
    assert info["registered_utc"].startswith("2026-11-21")


def test_missing_registered_utc_is_refused(tmp_path):
    with pytest.raises(NotRegistered):
        guard("EX", smoke=False, path=_write(tmp_path, "Registered", utc=None))


def test_smoke_is_allowed(tmp_path):
    assert guard("EX", smoke=True, path=_write(tmp_path, "DRAFT"))["smoke"] is True
