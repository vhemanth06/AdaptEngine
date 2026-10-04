import json
from dataclasses import dataclass
from .core.errors import ValidationError, UnknownConceptError
from .core.schema import Activity, ActivityType, Event, EventType
from .learner.state import LearnerState, LearnerConcept, ExecutionLog
from .learner.mastery import update_mastery, learn, entropy
from .core.config import DEFAULT_CONFIG


@dataclass(frozen=True)
class UpdateRecord:
    concept_id: str
    p_before: float
    p_after: float
    h_before: float
    h_after: float


def apply_response(
    state: LearnerState, activity: Activity, correct: bool, cfg=DEFAULT_CONFIG, T=None, day=None
) -> tuple[LearnerState, UpdateRecord]:
    if activity.type != ActivityType.EXERCISE:
        raise ValidationError("apply_response requires an EXERCISE activity")

    if T is None:
        T = cfg.t_exercise

    target = activity.target_concept
    if target not in state.concepts:
        raise UnknownConceptError(f"Concept {target} not in state")

    old_c = state.concepts[target]
    new_p = update_mastery(old_c.mastery, activity.difficulty, correct, T, cfg)
    new_h = entropy(new_p)

    new_c = LearnerConcept(
        mastery=new_p,
        uncertainty=new_h,
        assessed=True,
        last_practice_day=day,
        n_reviews=old_c.n_reviews + 1,
        half_life_days=old_c.half_life_days,
    )

    new_concepts = dict(state.concepts)
    new_concepts[target] = new_c
    record = UpdateRecord(target, old_c.mastery, new_p, old_c.uncertainty, new_h)

    return LearnerState(concepts=new_concepts), record


def apply_lesson(
    state: LearnerState, activity: Activity, cfg=DEFAULT_CONFIG, day=None
) -> tuple[LearnerState, UpdateRecord]:
    if activity.type != ActivityType.LESSON:
        raise ValidationError("apply_lesson requires a LESSON activity")

    target = activity.target_concept
    if target not in state.concepts:
        raise UnknownConceptError(f"Concept {target} not in state")

    old_c = state.concepts[target]
    new_p = learn(old_c.mastery, cfg.t_lesson)
    new_h = entropy(new_p)

    new_c = LearnerConcept(
        mastery=new_p,
        uncertainty=new_h,
        assessed=True,
        last_practice_day=day,
        n_reviews=old_c.n_reviews + 1,
        half_life_days=old_c.half_life_days,
    )

    new_concepts = dict(state.concepts)
    new_concepts[target] = new_c
    record = UpdateRecord(target, old_c.mastery, new_p, old_c.uncertainty, new_h)

    return LearnerState(concepts=new_concepts), record


def load_learner(path: str, concept_ids: tuple[str, ...]) -> LearnerState:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema_version") != 1:
        raise ValidationError(f"Invalid schema_version in {path}")

    concepts = {}
    for cid, cdata in data.get("concepts", {}).items():
        if cid not in concept_ids:
            raise UnknownConceptError(f"Concept {cid} in state file is unknown")
        concepts[cid] = LearnerConcept(
            mastery=cdata["mastery"],
            uncertainty=cdata["uncertainty"],
            assessed=cdata.get("assessed", False),
            last_practice_day=cdata.get("last_practice_day"),
            n_reviews=cdata.get("n_reviews", 0),
            half_life_days=cdata.get("half_life_days"),
        )
    for cid in concept_ids:
        if cid not in concepts:
            raise ValidationError(f"Missing concept {cid} in state file")
    return LearnerState(concepts=concepts)


def save_learner(state: LearnerState, path: str):
    data = {
        "schema_version": 1,
        "concepts": {
            cid: {
                "mastery": c.mastery,
                "uncertainty": c.uncertainty,
                "assessed": c.assessed,
                "last_practice_day": c.last_practice_day,
                "n_reviews": c.n_reviews,
                "half_life_days": c.half_life_days,
            }
            for cid, c in state.concepts.items()
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load_log(path: str) -> ExecutionLog:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return ExecutionLog()
    events = []
    for edata in data.get("events", []):
        events.append(
            Event(
                day=edata["day"],
                kind=EventType(edata["kind"]),
                activity_id=edata.get("activity_id"),
                minutes_elapsed=edata.get("minutes_elapsed", 0),
                correct=edata.get("correct"),
            )
        )
    return ExecutionLog(tuple(events))


def save_log(log: ExecutionLog, path: str):
    data = {
        "events": [
            {
                "day": e.day,
                "kind": e.kind.value,
                "activity_id": e.activity_id,
                "minutes_elapsed": e.minutes_elapsed,
                "correct": e.correct,
            }
            for e in log.events
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
