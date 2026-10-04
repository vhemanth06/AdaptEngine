import pytest
from adaptengine.learner.state import initial_state, ExecutionLog
from adaptengine.session import apply_response, save_learner, load_learner, save_log, load_log
from adaptengine.core.schema import Activity, ActivityType, Event, EventType
from adaptengine.core.errors import ValidationError


def test_initial_state():
    state = initial_state(("C1", "C2"))
    assert "C1" in state.concepts
    c = state.concepts["C1"]
    assert c.mastery == 0.20
    assert c.uncertainty == pytest.approx(0.7219, abs=1e-4)
    assert not c.assessed

    with pytest.raises(TypeError):
        state.concepts["C1"] = c


def test_apply_response():
    state = initial_state(("C1",))
    act = Activity("A1", ActivityType.EXERCISE, "C1", duration=2, difficulty=0.5)
    new_state, record = apply_response(state, act, correct=True, day=1)

    assert new_state is not state
    c1_new = new_state.concepts["C1"]
    assert c1_new.mastery > 0.20
    assert c1_new.assessed
    assert c1_new.last_practice_day == 1
    assert record.p_before == 0.20
    assert record.p_after == c1_new.mastery

    act_lesson = Activity("A2", ActivityType.LESSON, "C1", duration=2)
    with pytest.raises(ValidationError):
        apply_response(state, act_lesson, True)


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
