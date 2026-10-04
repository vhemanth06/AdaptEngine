import pytest
from adaptengine.core.schema import Concept, Activity, ActivityType, Event, EventType
from adaptengine.core.errors import (
    ValidationError,
    DifficultyError,
    DuplicateIdError,
    UnknownConceptError,
)
from adaptengine.curriculum.loader import load_curriculum, load_activities


# --- Unit tests for Schema Dataclasses ---
def test_concept_validation():
    # Valid
    c = Concept(concept_id="C1", prerequisites=("C2",))
    assert c.concept_id == "C1"

    # Invalid IDs
    with pytest.raises(ValidationError):
        Concept(concept_id="")
    with pytest.raises(ValidationError):
        Concept(concept_id="   ")
    with pytest.raises(ValidationError):
        Concept(concept_id="C 1")


def test_activity_validation():
    # Valid
    Activity("A1", ActivityType.LESSON, "C1", duration=5)
    Activity("A2", ActivityType.EXERCISE, "C1", duration=2, difficulty=0.5)

    # Invalid ID
    with pytest.raises(ValidationError):
        Activity("", ActivityType.LESSON, "C1", duration=5)

    # Invalid Duration
    with pytest.raises(ValidationError):
        Activity("A3", ActivityType.LESSON, "C1", duration=0)
    with pytest.raises(ValidationError):
        Activity("A3", ActivityType.LESSON, "C1", duration=2.5)  # float
    with pytest.raises(ValidationError):
        Activity("A3", ActivityType.LESSON, "C1", duration="5")  # string

    # Difficulty constraints
    with pytest.raises(DifficultyError):
        Activity("A4", ActivityType.LESSON, "C1", duration=5, difficulty=0.5)  # LESSON with diff
    with pytest.raises(DifficultyError):
        Activity(
            "A5", ActivityType.EXERCISE, "C1", duration=5, difficulty=None
        )  # EXERCISE missing diff
    with pytest.raises(DifficultyError):
        Activity("A6", ActivityType.EXERCISE, "C1", duration=5, difficulty=0.01)  # < D_MIN
    with pytest.raises(DifficultyError):
        Activity("A7", ActivityType.EXERCISE, "C1", duration=5, difficulty=0.96)  # > D_MAX


def test_event_validation():
    # Valid
    Event(day=0, kind=EventType.COMPLETED, activity_id="A1", minutes_elapsed=5, correct=True)
    Event(day=1, kind=EventType.MISSED, activity_id=None, minutes_elapsed=0)

    # Invalid day
    with pytest.raises(ValidationError):
        Event(day=-1, kind=EventType.MISSED)
    with pytest.raises(ValidationError):
        Event(day="1", kind=EventType.MISSED)

    # MISSED rules
    with pytest.raises(ValidationError):
        Event(day=0, kind=EventType.MISSED, activity_id="A1")
    with pytest.raises(ValidationError):
        Event(day=0, kind=EventType.MISSED, minutes_elapsed=5)

    # COMPLETED rules
    with pytest.raises(ValidationError):
        Event(day=0, kind=EventType.COMPLETED, activity_id=None, minutes_elapsed=5)
    with pytest.raises(ValidationError):
        Event(day=0, kind=EventType.COMPLETED, activity_id="A1", minutes_elapsed=-1)


# --- Unit tests for Loader and Fixtures ---


# TC1.2: Load valid and invalid curriculum and learner-state schema fixtures.
def test_valid_fixtures_load():
    concepts = load_curriculum("data/curriculum/curriculum_4node.json", allow_unreviewed=True)
    assert len(concepts) == 4

    activities = load_activities(
        "data/curriculum/activities_4node.json", concepts, allow_unreviewed=True
    )
    assert len(activities) == 20

    lessons = [a for a in activities if a.type == ActivityType.LESSON]
    exercises = [a for a in activities if a.type == ActivityType.EXERCISE]

    assert len(lessons) == 4
    assert len(exercises) == 16

    # 4 diffs per concept
    for c in ["C1", "C2", "C3", "C4"]:
        diffs = {a.difficulty for a in exercises if a.target_concept == c}
        assert diffs == {0.2, 0.4, 0.6, 0.8}


@pytest.mark.parametrize(
    "fixture, exc_type",
    [
        ("duplicate_concept", DuplicateIdError),
        ("bad_schema_version", ValidationError),
        ("malformed", ValidationError),
    ],
)
# TC1.2: Invalid types, ranges, unknown references, and missing required fields raise the appropriate typed validation errors.
def test_invalid_curriculum_fixtures(fixture, exc_type):
    path = f"tests/fixtures/invalid/{fixture}.json"
    with pytest.raises(exc_type) as exc_info:
        load_curriculum(path, allow_unreviewed=True)
    # the error message for file problems contains the path
    assert path in str(exc_info.value)


@pytest.mark.parametrize(
    "fixture, exc_type",
    [
        ("duplicate_activity", DuplicateIdError),
        ("exercise_no_difficulty", DifficultyError),
        ("difficulty_low", DifficultyError),
        ("difficulty_high", DifficultyError),
        ("lesson_with_difficulty", DifficultyError),
        ("bad_duration", ValidationError),
        ("unknown_target", UnknownConceptError),
    ],
)
def test_invalid_activity_fixtures(fixture, exc_type):
    concepts = [Concept("C1")]
    path = f"tests/fixtures/invalid/{fixture}.json"
    with pytest.raises(exc_type) as exc_info:
        load_activities(path, concepts, allow_unreviewed=True)
    if exc_type is UnknownConceptError:
        assert "targets unknown concept" in str(exc_info.value)
    elif exc_type in (DuplicateIdError, ValidationError):
        assert path in str(exc_info.value)
