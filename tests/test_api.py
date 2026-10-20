import pytest
from adaptengine.api import Engine
from adaptengine.core.schema import Event, EventType
from adaptengine.core.errors import ValidationError
from adaptengine.learner.state import ExecutionLog
from adaptengine.core.config import EngineConfig, config_hash


def test_api_record():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    log = ExecutionLog()

    event = Event(
        day=1, kind=EventType.COMPLETED, activity_id="E-C1-0.4", minutes_elapsed=1, correct=True
    )
    new_state, new_log = engine.record(state, log, event)

    assert new_state.concepts["C1"].mastery > 0.20
    assert len(new_log.events) == 1


def test_api_missed():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    log = ExecutionLog()
    event = Event(day=1, kind=EventType.MISSED)
    new_state, new_log = engine.record(state, log, event)
    assert new_state is state
    assert len(new_log.events) == 1


def test_api_unsupported():
    engine = Engine.from_files(
        "data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json"
    )
    state = engine.init_learner()
    log = ExecutionLog()
    event = Event(day=1, kind=EventType.FAILED_ASSESSMENT)
    with pytest.raises(ValidationError):
        engine.record(state, log, event)


def test_config_hash():
    c1 = EngineConfig()
    c2 = EngineConfig()
    c3 = EngineConfig(p0=0.3)
    assert config_hash(c1) == config_hash(c2)
    assert config_hash(c1) != config_hash(c3)

    # Hash changes when any planner field changes
    assert config_hash(c1) != config_hash(EngineConfig(target_success=0.80))
    assert config_hash(c1) != config_hash(EngineConfig(w_review=0.5))
    assert config_hash(c1) != config_hash(EngineConfig(w_unlock=2.0))
    assert config_hash(c1) != config_hash(EngineConfig(w_fit=0.5))
    assert config_hash(c1) != config_hash(EngineConfig(allowed_budgets=(5, 10)))
    assert config_hash(c1) != config_hash(EngineConfig(oracle_node_limit=500))


def test_config_planner_validation():
    with pytest.raises(ValidationError):
        EngineConfig(target_success=0.0)
    with pytest.raises(ValidationError):
        EngineConfig(target_success=1.0)
    with pytest.raises(ValidationError):
        EngineConfig(w_review=-0.1)
    with pytest.raises(ValidationError):
        EngineConfig(w_unlock=-1.0)
    with pytest.raises(ValidationError):
        EngineConfig(w_fit=-0.5)
    with pytest.raises(ValidationError):
        EngineConfig(allowed_budgets=())
    with pytest.raises(ValidationError):
        EngineConfig(allowed_budgets=(-5, 10))
    with pytest.raises(ValidationError):
        EngineConfig(oracle_node_limit=0)
