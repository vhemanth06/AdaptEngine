"""V2-TC5: no full run without a registered pre-registration carrying the current code hash."""

import pytest

from experiments.core.prereg import NotRegistered, guard
from experiments.core.provenance import code_hash


def _write(tmp_path, status, h, utc="2026-11-21T10:00:00+00:00"):
    p = tmp_path / "EX_2026-11-21.md"
    p.write_text(
        f"# EX\n\nStatus: {status}\nRegistered UTC: {utc}\nCode hash: {h}\n", encoding="utf-8"
    )
    return str(p)


def test_draft_is_refused(tmp_path):
    with pytest.raises(NotRegistered):
        guard("EX", smoke=False, path=_write(tmp_path, "DRAFT", code_hash()))


def test_other_hash_is_refused(tmp_path):
    with pytest.raises(NotRegistered):
        guard("EX", smoke=False, path=_write(tmp_path, "Registered", "0" * 64))


def test_registered_with_current_hash_runs(tmp_path):
    info = guard("EX", smoke=False, path=_write(tmp_path, "Registered", code_hash()))
    assert info["registered_utc"].startswith("2026-11-21")


def test_smoke_is_allowed(tmp_path):
    assert guard("EX", smoke=True, path=_write(tmp_path, "DRAFT", "x"))["smoke"] is True


def test_amendment_hash_counts(tmp_path):
    p = _write(tmp_path, "Registered", "0" * 64)
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"\n## Amendment 1\nCode hash: {code_hash()}\n")
    assert guard("EX", smoke=False, path=p)["code_hash"] == code_hash()
