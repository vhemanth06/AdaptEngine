from dataclasses import dataclass
from typing import Optional, Mapping
from types import MappingProxyType
from ..core.errors import ValidationError
from .mastery import entropy
from ..core.config import DEFAULT_CONFIG
from ..core.schema import Event

@dataclass(frozen=True)
class LearnerConcept:
    mastery: float
    uncertainty: float
    assessed: bool = False
    last_practice_day: Optional[int] = None
    n_reviews: int = 0
    half_life_days: Optional[float] = None

    def __post_init__(self):
        if not (0.0 <= self.mastery <= 1.0):
            raise ValidationError(f"Invalid mastery: {self.mastery}")

@dataclass(frozen=True)
class ExecutionLog:
    events: tuple[Event, ...] = ()

    def append(self, event: Event) -> "ExecutionLog":
        return ExecutionLog(events=self.events + (event,))

    def completed_ids(self) -> tuple[str, ...]:
        return tuple(e.activity_id for e in self.events if e.activity_id is not None and e.kind.value == "COMPLETED")

@dataclass(frozen=True)
class LearnerState:
    concepts: Mapping[str, LearnerConcept]

    def __post_init__(self):
        sorted_copy = {k: self.concepts[k] for k in sorted(self.concepts.keys())}
        object.__setattr__(self, 'concepts', MappingProxyType(sorted_copy))

def initial_state(concept_ids: tuple[str, ...], cfg=DEFAULT_CONFIG) -> LearnerState:
    p0 = cfg.p0
    unc = entropy(p0)
    concepts = {cid: LearnerConcept(mastery=p0, uncertainty=unc) for cid in concept_ids}
    return LearnerState(concepts=concepts)
