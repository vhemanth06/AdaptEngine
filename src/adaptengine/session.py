import json
import os
from dataclasses import dataclass, replace
from typing import Optional
from .core.errors import ValidationError, UnknownConceptError
from .core.schema import Activity, ActivityType, Event, EventType, PlanContext
from .learner.state import LearnerState, LearnerConcept, ExecutionLog, ConceptStatus
from .learner.mastery import update_mastery, learn, entropy
from .core.config import DEFAULT_CONFIG, EngineConfig
from .core.validators import check_bool, check_probability, check_non_negative_int


@dataclass(frozen=True)
class UpdateRecord:
    concept_id: str
    p_before: float
    p_after: float
    h_before: float
    h_after: float


def apply_response(
    state: LearnerState,
    activity: Activity,
    correct: bool,
    cfg: EngineConfig = DEFAULT_CONFIG,
    T: Optional[float] = None,
    day: Optional[int] = None,
    attempt_id: Optional[str] = None,
) -> tuple[LearnerState, UpdateRecord]:
    if activity.type != ActivityType.EXERCISE:
        raise ValidationError("apply_response requires an EXERCISE activity")

    check_bool(correct, "correct")
    if T is None:
        T = cfg.t_exercise

    target = activity.target_concept
    if target not in state.concepts:
        raise UnknownConceptError(f"Concept {target} not in state")

    old_c = state.concepts[target]

    # Idempotency: duplicate attempt_id is a no-op
    if attempt_id is not None and attempt_id in old_c.seen_attempt_ids:
        record = UpdateRecord(target, old_c.p, old_c.p, old_c.uncertainty, old_c.uncertainty)
        return state, record

    new_p = update_mastery(old_c.p, activity.difficulty, correct, T, cfg)
    new_h = entropy(new_p)

    new_responses = old_c.responses + 1
    new_correct = old_c.correct_responses + (1 if correct else 0)
    new_seen = old_c.seen_attempt_ids | ({attempt_id} if attempt_id else frozenset())

    if day is not None:
        check_non_negative_int(day, "day")
        new_day = max(old_c.last_practice_day or 0, day)
    else:
        new_day = old_c.last_practice_day

    new_c = replace(
        old_c,
        p=new_p,
        responses=new_responses,
        correct_responses=new_correct,
        status=ConceptStatus.ASSESSED,
        seen_attempt_ids=new_seen,
        last_practice_day=new_day,
        n_reviews=old_c.n_reviews + 1,
    )

    new_concepts = dict(state.concepts)
    new_concepts[target] = new_c
    record = UpdateRecord(target, old_c.p, new_p, old_c.uncertainty, new_h)

    return LearnerState(concepts=new_concepts), record


def apply_lesson(
    state: LearnerState,
    activity: Activity,
    cfg: EngineConfig = DEFAULT_CONFIG,
    day: Optional[int] = None,
    attempt_id: Optional[str] = None,
) -> tuple[LearnerState, UpdateRecord]:
    if activity.type != ActivityType.LESSON:
        raise ValidationError("apply_lesson requires a LESSON activity")

    target = activity.target_concept
    if target not in state.concepts:
        raise UnknownConceptError(f"Concept {target} not in state")

    old_c = state.concepts[target]

    # Idempotency
    if attempt_id is not None and attempt_id in old_c.seen_attempt_ids:
        record = UpdateRecord(target, old_c.p, old_c.p, old_c.uncertainty, old_c.uncertainty)
        return state, record

    new_p = learn(old_c.p, cfg.t_lesson)
    new_h = entropy(new_p)
    new_lessons = old_c.lessons_done + 1
    new_seen = old_c.seen_attempt_ids | ({attempt_id} if attempt_id else frozenset())

    if day is not None:
        check_non_negative_int(day, "day")
        new_day = max(old_c.last_practice_day or 0, day)
    else:
        new_day = old_c.last_practice_day

    # Lessons NEVER set status to ASSESSED; completing a lesson clears needs_remediation (D21)
    new_c = replace(
        old_c,
        p=new_p,
        lessons_done=new_lessons,
        seen_attempt_ids=new_seen,
        last_practice_day=new_day,
        n_reviews=old_c.n_reviews + 1,
        needs_remediation=False,
    )

    new_concepts = dict(state.concepts)
    new_concepts[target] = new_c
    record = UpdateRecord(target, old_c.p, new_p, old_c.uncertainty, new_h)

    return LearnerState(concepts=new_concepts), record


def _atomic_write_json(data: dict, path: str):
    abs_path = os.path.abspath(path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    tmp_path = f"{abs_path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, abs_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def serialize_learner(state: LearnerState) -> dict:
    return {
        "schema_version": 1,
        "concepts": {
            cid: {
                "concept_id": c.concept_id,
                "p": c.p,
                "mastery": c.p,
                "uncertainty": c.uncertainty,
                "lessons_done": c.lessons_done,
                "responses": c.responses,
                "correct_responses": c.correct_responses,
                "status": c.status.value,
                "assessed": c.assessed,
                "seen_attempt_ids": sorted(c.seen_attempt_ids),
                "last_practice_day": c.last_practice_day,
                "n_reviews": c.n_reviews,
                "half_life_days": c.half_life_days,
                "needs_remediation": c.needs_remediation,
            }
            for cid, c in state.concepts.items()
        },
    }


def deserialize_learner(data: dict, concept_ids: tuple[str, ...]) -> LearnerState:
    if not isinstance(data, dict):
        raise ValidationError("Learner state root must be a JSON object")
    if data.get("schema_version") != 1:
        raise ValidationError("Invalid schema_version in learner state")

    raw_concepts = data.get("concepts")
    if not isinstance(raw_concepts, dict):
        raise ValidationError("Learner concepts must be a JSON object mapping concept IDs to state")

    for cid in raw_concepts:
        if cid not in concept_ids:
            raise UnknownConceptError(f"Concept {cid} in state file is unknown")

    concepts = {}
    for cid in concept_ids:
        if cid not in raw_concepts:
            raise ValidationError(f"Missing concept {cid} in state file")
        cdata = raw_concepts[cid]
        if not isinstance(cdata, dict):
            raise ValidationError(f"Concept {cid} data must be an object")

        raw_p = cdata.get("p", cdata.get("mastery"))
        if raw_p is None:
            raw_p = DEFAULT_CONFIG.p0
        p_val = check_probability(raw_p, f"concept {cid} p")

        raw_status = cdata.get("status")
        if raw_status is not None:
            try:
                status = ConceptStatus(raw_status)
            except ValueError:
                raise ValidationError(f"Invalid status {raw_status} in concept {cid}")
        else:
            status = ConceptStatus.ASSESSED if cdata.get("assessed") else ConceptStatus.UNASSESSED

        seen_raw = cdata.get("seen_attempt_ids", [])
        if not isinstance(seen_raw, list):
            raise ValidationError(f"seen_attempt_ids must be a list for concept {cid}")

        concepts[cid] = LearnerConcept(
            concept_id=cid,
            p=p_val,
            lessons_done=cdata.get("lessons_done", 0),
            responses=cdata.get("responses", 1 if status == ConceptStatus.ASSESSED else 0),
            correct_responses=cdata.get("correct_responses", 0),
            status=status,
            seen_attempt_ids=frozenset(str(x) for x in seen_raw),
            half_life_days=cdata.get("half_life_days") or 30.0,
            last_practice_day=cdata.get("last_practice_day"),
            n_reviews=cdata.get("n_reviews", 0),
            needs_remediation=cdata.get("needs_remediation", False),
        )

    return LearnerState(concepts=concepts)


def serialize_log(log: ExecutionLog) -> dict:
    return {
        "schema_version": 1,
        "events": [
            {
                "day": e.day,
                "kind": e.kind.value,
                "activity_id": e.activity_id,
                "minutes_elapsed": e.minutes_elapsed,
                "correct": e.correct,
                "attempt_id": e.attempt_id,
                "value": e.value,
            }
            for e in log.events
        ],
    }


def deserialize_log(data: dict) -> ExecutionLog:
    if not isinstance(data, dict):
        raise ValidationError("Execution log root must be a JSON object")

    raw_events = data.get("events", [])
    if not isinstance(raw_events, list):
        raise ValidationError("Execution log 'events' must be a list")

    events = []
    for edata in raw_events:
        if not isinstance(edata, dict):
            raise ValidationError("Each event must be a JSON object")
        try:
            kind = EventType(edata["kind"])
        except (ValueError, KeyError, TypeError):
            raise ValidationError(f"Invalid event kind: {edata.get('kind')!r}")

        events.append(
            Event(
                day=edata["day"],
                kind=kind,
                activity_id=edata.get("activity_id"),
                minutes_elapsed=edata.get("minutes_elapsed", 0),
                correct=edata.get("correct"),
                attempt_id=edata.get("attempt_id"),
                value=edata.get("value"),
            )
        )
    return ExecutionLog(tuple(events))


def save_learner(state: LearnerState, path: str):
    _atomic_write_json(serialize_learner(state), path)


def load_learner(path: str, concept_ids: tuple[str, ...]) -> LearnerState:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return deserialize_learner(data, concept_ids)


def save_log(log: ExecutionLog, path: str):
    _atomic_write_json(serialize_log(log), path)


def load_log(path: str) -> ExecutionLog:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return ExecutionLog()
    return deserialize_log(data)


def save_snapshot(
    state: LearnerState,
    log: ExecutionLog,
    path: str,
    context: Optional[PlanContext] = None,
):
    """Write an atomic snapshot containing learner state, execution log, and optional context."""
    data = {
        "schema_version": 1,
        "state": serialize_learner(state),
        "log": serialize_log(log),
    }
    if context is not None:
        data["context"] = {
            "goal": context.goal,
            "deadline_day": context.deadline_day,
            "budget": context.budget,
            "current_day": context.current_day,
        }
    _atomic_write_json(data, path)


def load_snapshot(
    path: str, concept_ids: tuple[str, ...], include_context: bool = False
) -> tuple[LearnerState, ExecutionLog] | tuple[LearnerState, ExecutionLog, Optional[PlanContext]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValidationError(f"Invalid snapshot format in {path}")
    state_data = data.get("state") or data.get("learner")
    if state_data is None or not isinstance(state_data, dict):
        raise ValidationError(f"Invalid snapshot format in {path}: missing 'state' or 'learner'")
    if "schema_version" not in state_data:
        state_data = dict(state_data)
        state_data["schema_version"] = data["schema_version"]
    state = deserialize_learner(state_data, concept_ids)

    log_data = data.get("log")
    if log_data is None or not isinstance(log_data, dict):
        raise ValidationError(f"Invalid snapshot format in {path}: missing 'log'")
    if "schema_version" not in log_data:
        log_data = dict(log_data)
        log_data["schema_version"] = data["schema_version"]
    log = deserialize_log(log_data)
    ctx = None
    if "context" in data and isinstance(data["context"], dict):
        cdata = data["context"]
        ctx = PlanContext(
            goal=cdata["goal"],
            deadline_day=cdata["deadline_day"],
            budget=cdata["budget"],
            current_day=cdata.get("current_day", 1),
        )
    if include_context:
        return state, log, ctx
    return state, log


def load_snapshot_context(path: str) -> Optional[PlanContext]:
    """Load optional plan context from an atomic snapshot file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "context" not in data or not isinstance(data["context"], dict):
        return None
    cdata = data["context"]
    return PlanContext(
        goal=cdata["goal"],
        deadline_day=cdata["deadline_day"],
        budget=cdata["budget"],
        current_day=cdata.get("current_day", 1),
    )
