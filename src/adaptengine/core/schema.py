from dataclasses import dataclass
from enum import Enum
from typing import Optional
from .errors import ValidationError, DifficultyError
from .constants import D_MIN, D_MAX

class ActivityType(Enum):
    LESSON = "LESSON"
    EXERCISE = "EXERCISE"

class EventType(Enum):
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
        if not isinstance(self.concept_id, str) or not self.concept_id.strip() or any(c.isspace() for c in self.concept_id):
            raise ValidationError(f"Invalid concept_id: {self.concept_id}")

@dataclass(frozen=True)
class Activity:
    activity_id: str
    type: ActivityType
    target_concept: str
    duration: int
    difficulty: Optional[float] = None
    text: str = ""

    def __post_init__(self):
        if not isinstance(self.activity_id, str) or not self.activity_id.strip() or any(c.isspace() for c in self.activity_id):
            raise ValidationError(f"Invalid activity_id: {self.activity_id}")
        
        if type(self.duration) is not int or self.duration < 1:
            raise ValidationError(f"Invalid duration: {self.duration}")
            
        if self.type == ActivityType.EXERCISE:
            if self.difficulty is None or not (D_MIN <= self.difficulty <= D_MAX):
                raise DifficultyError(f"EXERCISE must have difficulty in [{D_MIN}, {D_MAX}]")
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

    def __post_init__(self):
        if type(self.day) is not int or self.day < 0:
            raise ValidationError(f"Invalid day: {self.day}")
        
        if self.kind == EventType.MISSED:
            if self.minutes_elapsed != 0 or self.activity_id is not None:
                raise ValidationError("MISSED event must have minutes_elapsed=0 and no activity_id")
                
        if self.kind == EventType.COMPLETED:
            if self.activity_id is None:
                raise ValidationError("COMPLETED event must have activity_id")
            if type(self.minutes_elapsed) is not int or self.minutes_elapsed < 0:
                raise ValidationError("COMPLETED event must have minutes_elapsed >= 0")
