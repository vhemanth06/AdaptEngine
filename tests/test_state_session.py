import pytest
from unittest.mock import patch
from adaptengine.learner.state import initial_state, ExecutionLog, ConceptStatus
from adaptengine.session import (
    apply_response,
    apply_lesson,
    save_learner,
    load_learner,
    save_log,
    load_log,
    save_snapshot,
    load_snapshot,
)
from adaptengine.core.schema import Activity, ActivityType, Event, EventType
from adaptengine.core.errors import ValidationError


def test_initial_state():
    state = initial_state(("C1", "C2"))
    assert "C1" in state.concepts
    c = state.concepts["C1"]
    assert c.mastery == 0.20
    assert c.uncertainty == pytest.approx(0.7219, abs=1e-4)
    assert not c.assessed
    assert c.status == ConceptStatus.UNASSESSED
    assert not c.evidence_mastered

    with pytest.raises(TypeError):
        state.concepts["C1"] = c


def test_apply_response():
    state = initial_state(("C1",))
    act = Activity("A1", ActivityType.EXERCISE, "C1", duration=2, difficulty=0.5)
    new_state, record = apply_response(state, act, correct=True, day=1, attempt_id="att-1")

    assert new_state is not state
    c1_new = new_state.concepts["C1"]
    assert c1_new.mastery > 0.20
    assert c1_new.assessed
    assert c1_new.status == ConceptStatus.ASSESSED
    assert c1_new.last_practice_day == 1
    assert "att-1" in c1_new.seen_attempt_ids
    assert record.p_before == 0.20
    assert record.p_after == c1_new.mastery

    # Idempotency: duplicate attempt_id is a no-op
    dup_state, dup_rec = apply_response(new_state, act, correct=True, day=1, attempt_id="att-1")
    assert dup_state is new_state
    assert dup_rec.p_before == dup_rec.p_after

    act_lesson = Activity("A2", ActivityType.LESSON, "C1", duration=2)
    with pytest.raises(ValidationError):
        apply_response(state, act_lesson, True)


def test_apply_lesson_exposure_semantics():
    state = initial_state(("C1",))
    act = Activity("L1", ActivityType.LESSON, "C1", duration=5)
    for i in range(8):
        state, _ = apply_lesson(state, act, attempt_id=f"lesson-{i}")

    c = state.concepts["C1"]
    assert c.p > 0.85
    assert not c.assessed
    assert c.status == ConceptStatus.UNASSESSED
    assert not c.evidence_mastered
    assert c.lessons_done == 8
    assert c.responses == 0


def test_last_practice_day_monotonic():
    state = initial_state(("C1",))
    act = Activity("L1", ActivityType.LESSON, "C1", duration=5)
    state, _ = apply_lesson(state, act, day=20, attempt_id="l-1")
    assert state.concepts["C1"].last_practice_day == 20
    state, _ = apply_lesson(state, act, day=5, attempt_id="l-2")
    assert state.concepts["C1"].last_practice_day == 20


def test_learner_log_roundtrip(tmp_path):
    state = initial_state(("C1", "C2"))
    log = ExecutionLog((Event(day=1, kind=EventType.MISSED),))

    s_path = str(tmp_path / "state.json")
    l_path = str(tmp_path / "log.json")

    save_learner(state, s_path)
    save_log(log, l_path)

    s_loaded = load_learner(s_path, ("C1", "C2"))
    l_loaded = load_log(l_path)

    assert s_loaded.concepts["C1"].mastery == state.concepts["C1"].mastery
    assert len(l_loaded.events) == 1


def test_snapshot_roundtrip_and_atomic_failure(tmp_path):
    state = initial_state(("C1", "C2"))
    log = ExecutionLog((Event(day=1, kind=EventType.MISSED, attempt_id="m-1"),))

    snap_path = str(tmp_path / "snapshot.json")
    save_snapshot(state, log, snap_path)

    loaded_state, loaded_log = load_snapshot(snap_path, ("C1", "C2"))
    assert loaded_state.concepts["C1"].p == state.concepts["C1"].p
    assert len(loaded_log.events) == 1

    # Injected failure test during atomic write:
    # If os.replace fails, the original file stays intact and no .tmp remains
    original_content = open(snap_path, "r", encoding="utf-8").read()
    with patch("os.replace", side_effect=OSError("Injected write failure")):
        with pytest.raises(OSError):
            save_snapshot(state, ExecutionLog(), snap_path)

    # Verify original file untouched
    assert open(snap_path, "r", encoding="utf-8").read() == original_content
    # Verify no .tmp file left behind
    assert not (tmp_path / "snapshot.json.tmp").exists()
