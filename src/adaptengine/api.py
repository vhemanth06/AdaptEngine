from typing import Mapping
from .core.config import EngineConfig, DEFAULT_CONFIG
from .core.schema import Event, EventType, ActivityType, Activity
from .curriculum.loader import load_curriculum, load_activities
from .curriculum.graph import CurriculumGraph
from .learner.state import LearnerState, ExecutionLog, initial_state
from .session import apply_response, apply_lesson
from .core.errors import ValidationError, UnknownConceptError

class Engine:
    def __init__(self, curriculum: tuple, activities: tuple, config: EngineConfig = DEFAULT_CONFIG):
        self.graph = CurriculumGraph.from_concepts(curriculum)
        self.activities: Mapping[str, Activity] = {a.activity_id: a for a in activities}
        self.config = config

    @classmethod
    def from_files(cls, curriculum_path: str, activities_path: str, manifest_path: str = None, config: EngineConfig = DEFAULT_CONFIG, allow_unreviewed: bool = False) -> "Engine":
        concepts = load_curriculum(curriculum_path, manifest_path, allow_unreviewed=allow_unreviewed)
        activities = load_activities(activities_path, concepts, manifest_path, allow_unreviewed=allow_unreviewed)
        return cls(concepts, activities, config)

    def init_learner(self) -> LearnerState:
        return initial_state(self.graph.concepts(), self.config)

    def record(self, state: LearnerState, log: ExecutionLog, event: Event) -> tuple[LearnerState, ExecutionLog]:
        new_log = log.append(event)
        
        if event.kind == EventType.MISSED:
            return state, new_log
            
        if event.kind in (EventType.FAILED_ASSESSMENT, EventType.DEADLINE_CHANGED, EventType.BUDGET_CHANGED):
            raise ValidationError("not supported until Week 5")
            
        if event.kind == EventType.COMPLETED:
            if event.activity_id not in self.activities:
                raise UnknownConceptError(f"Unknown activity {event.activity_id}")
            activity = self.activities[event.activity_id]
            
            if activity.type == ActivityType.EXERCISE:
                if event.correct is None:
                    raise ValidationError("COMPLETED EXERCISE requires correct field")
                new_state, _ = apply_response(state, activity, event.correct, self.config, day=event.day)
                return new_state, new_log
            elif activity.type == ActivityType.LESSON:
                if event.correct is not None:
                    raise ValidationError("COMPLETED LESSON must not have correct field")
                new_state, _ = apply_lesson(state, activity, self.config, day=event.day)
                return new_state, new_log

        return state, new_log
