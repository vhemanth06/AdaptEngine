import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from .errors import ValidationError, DifficultyError
from .constants import D_MIN, D_MAX
from .validators import (
    check_bool,
    check_positive_int,
    check_non_negative_int,
    check_valid_id,
)


class ActivityType(str, Enum):
    LESSON = "LESSON"
    EXERCISE = "EXERCISE"


class EventType(str, Enum):
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    FAILED_ASSESSMENT = "FAILED_ASSESSMENT"
    DEADLINE_CHANGED = "DEADLINE_CHANGED"
    BUDGET_CHANGED = "BUDGET_CHANGED"


@dataclass(frozen=True)
class Concept:
    concept_id: str
    prerequisites: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self):
        check_valid_id(self.concept_id, "concept_id")
        if not isinstance(self.prerequisites, (tuple, list)):
            raise ValidationError(
                f"prerequisites must be a sequence, got {type(self.prerequisites).__name__}"
            )
        for p in self.prerequisites:
            check_valid_id(p, "prerequisite")
        if not isinstance(self.description, str):
            raise ValidationError(
                f"description must be a string, got {type(self.description).__name__}"
            )


@dataclass(frozen=True)
class Activity:
    activity_id: str
    type: ActivityType
    target_concept: str
    duration: int
    difficulty: Optional[float] = None
    text: str = ""
    d_min: float = D_MIN
    d_max: float = D_MAX

    def __post_init__(self):
        check_valid_id(self.activity_id, "activity_id")
        check_valid_id(self.target_concept, "target_concept")
        check_positive_int(self.duration, "duration")

        if not isinstance(self.type, ActivityType):
            raise ValidationError(f"Invalid activity type: {self.type}")

        if self.type == ActivityType.EXERCISE:
            if self.difficulty is None:
                raise DifficultyError(
                    f"EXERCISE must have difficulty in [{self.d_min}, {self.d_max}]"
                )
            if not isinstance(self.difficulty, (int, float)) or isinstance(self.difficulty, bool):
                raise DifficultyError(
                    f"EXERCISE difficulty must be numeric, got {type(self.difficulty).__name__}"
                )
            diff_float = float(self.difficulty)
            if not math.isfinite(diff_float) or not (self.d_min <= diff_float <= self.d_max):
                raise DifficultyError(
                    f"EXERCISE must have difficulty in [{self.d_min}, {self.d_max}], got {self.difficulty}"
                )
        elif self.type == ActivityType.LESSON:
            if self.difficulty is not None:
                raise DifficultyError("LESSON must not have difficulty")


@dataclass(frozen=True)
class Event:
    day: int
    kind: EventType
    activity_id: Optional[str] = None
    minutes_elapsed: int = 0
    correct: Optional[bool] = None
    attempt_id: Optional[str] = None

    def __post_init__(self):
        check_non_negative_int(self.day, "day")

        if not isinstance(self.kind, EventType):
            raise ValidationError(f"Invalid event kind: {self.kind!r}")

        check_non_negative_int(self.minutes_elapsed, "minutes_elapsed")

        if self.correct is not None:
            check_bool(self.correct, "correct")

        if self.attempt_id is not None:
            if not isinstance(self.attempt_id, str) or not self.attempt_id.strip():
                raise ValidationError(
                    f"attempt_id must be a non-empty string, got {self.attempt_id!r}"
                )

        if self.activity_id is not None:
            check_valid_id(self.activity_id, "activity_id")

        if self.kind == EventType.MISSED:
            if self.minutes_elapsed != 0 or self.activity_id is not None:
                raise ValidationError("MISSED event must have minutes_elapsed=0 and no activity_id")

        if self.kind == EventType.COMPLETED:
            if self.activity_id is None:
                raise ValidationError("COMPLETED event must have activity_id")
