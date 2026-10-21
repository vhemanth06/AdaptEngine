import json
import math
import os
from dataclasses import dataclass, replace
from typing import Optional
from .core.errors import ValidationError, UnknownConceptError
from .core.schema import Activity, ActivityType, Event, EventType, PlanContext
from .learner.state import LearnerState, LearnerConcept, ExecutionLog, ConceptStatus
from .learner.mastery import learn, entropy
from .learner.adapter import CustomBKT, MasteryModel
from .learner.evidence import update_concept_evidence
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
    model: Optional[MasteryModel] = None,
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
    if model is None:
        model = CustomBKT(cfg)

    new_c, changed = update_concept_evidence(
        old_c,
        activity.difficulty,
        correct,
        transition=T,
        model=model,
        cfg=cfg,
        day=day,
        attempt_id=attempt_id,
    )

    if not changed:
        record = UpdateRecord(target, old_c.p, old_c.p, old_c.uncertainty, old_c.uncertainty)
        return state, record

    new_concepts = dict(state.concepts)
    new_concepts[target] = new_c
    record = UpdateRecord(target, old_c.p, new_c.p, old_c.uncertainty, new_c.uncertainty)

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
    tmp_path = f"{abs_path}.{os.getpid()}.tmp"
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
                "p": c.p,
                "uncertainty": c.uncertainty,
                "status": c.status.value,
                "responses": c.responses,
                "correct_responses": c.correct_responses,
                "lessons_done": c.lessons_done,
                "seen_attempt_ids": sorted(list(c.seen_attempt_ids)),
                "half_life_days": c.half_life_days,
                "last_practice_day": c.last_practice_day,
                "n_reviews": c.n_reviews,
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

        # 1. p and mastery validation (must agree if both present)
        has_p = "p" in cdata and cdata["p"] is not None
        has_mastery = "mastery" in cdata and cdata["mastery"] is not None
        if has_p and has_mastery:
            p_check = check_probability(cdata["p"], f"concept {cid} p")
            m_check = check_probability(cdata["mastery"], f"concept {cid} mastery")
            if abs(p_check - m_check) > 1e-6:
                raise ValidationError(
                    f"Concept {cid} has conflicting 'p' ({cdata['p']}) and 'mastery' ({cdata['mastery']})"
                )
            raw_p = p_check
        elif has_p:
            raw_p = check_probability(cdata["p"], f"concept {cid} p")
        elif has_mastery:
            raw_p = check_probability(cdata["mastery"], f"concept {cid} mastery")
        else:
            raw_p = DEFAULT_CONFIG.p0

        p_val = check_probability(raw_p, f"concept {cid} p")

        # 2. assessed validation (must be boolean)
        has_assessed = "assessed" in cdata and cdata["assessed"] is not None
        assessed_val = None
        if has_assessed:
            assessed_val = check_bool(cdata["assessed"], f"concept {cid} assessed")

        # 3. status validation & consistency with assessed
        raw_status = cdata.get("status")
        if raw_status is not None:
            try:
                status = ConceptStatus(raw_status)
            except ValueError:
                raise ValidationError(f"Invalid status {raw_status} in concept {cid}")
            if assessed_val is not None:
                if status == ConceptStatus.ASSESSED and not assessed_val:
                    raise ValidationError(
                        f"Concept {cid} status ASSESSED contradicts assessed=False"
                    )
                if status == ConceptStatus.UNASSESSED and assessed_val:
                    raise ValidationError(
                        f"Concept {cid} status UNASSESSED contradicts assessed=True"
                    )
        else:
            if assessed_val is not None:
                status = ConceptStatus.ASSESSED if assessed_val else ConceptStatus.UNASSESSED
            else:
                status = ConceptStatus.UNASSESSED

        # 4. responses validation: legacy assessed: true without responses is rejected
        if (status == ConceptStatus.ASSESSED or assessed_val is True) and "responses" not in cdata:
            raise ValidationError(
                f"Legacy assessed: true without responses field is rejected for concept {cid}"
            )
        responses = cdata.get("responses", 0)
        check_non_negative_int(responses, f"concept {cid} responses")

        # 5. uncertainty validation: finite, non-negative, and agrees with entropy(p) within 1e-3
        if "uncertainty" in cdata and cdata["uncertainty"] is not None:
            raw_u = cdata["uncertainty"]
            if (
                isinstance(raw_u, bool)
                or not isinstance(raw_u, (int, float))
                or not math.isfinite(raw_u)
                or raw_u < 0.0
            ):
                raise ValidationError(
                    f"Concept {cid} uncertainty must be a finite non-negative number, got {raw_u!r}"
                )
            expected_h = entropy(p_val)
            if abs(float(raw_u) - expected_h) > 1e-3:
                raise ValidationError(
                    f"Concept {cid} uncertainty {raw_u} does not agree with entropy(p) {expected_h:.4f}"
                )

        # 6. half_life_days validation: missing/None means default 30.0; present must be positive finite number
        raw_hl = cdata.get("half_life_days")
        if raw_hl is None:
            half_life_days = 30.0
        else:
            if (
                isinstance(raw_hl, bool)
                or not isinstance(raw_hl, (int, float))
                or not math.isfinite(raw_hl)
                or raw_hl <= 0
            ):
                raise ValidationError(
                    f"Concept {cid} half_life_days must be a positive finite number, got {raw_hl!r}"
                )
            half_life_days = float(raw_hl)

        # 7. needs_remediation validation: must be boolean, missing means False
        raw_rem = cdata.get("needs_remediation")
        if raw_rem is None:
            needs_remediation = False
        else:
            needs_remediation = check_bool(raw_rem, f"concept {cid} needs_remediation")

        seen_raw = cdata.get("seen_attempt_ids", [])
        if not isinstance(seen_raw, list):
            raise ValidationError(f"seen_attempt_ids must be a list for concept {cid}")

        concepts[cid] = LearnerConcept(
            concept_id=cid,
            p=p_val,
            lessons_done=cdata.get("lessons_done", 0),
            responses=responses,
            correct_responses=cdata.get("correct_responses", 0),
            status=status,
            seen_attempt_ids=frozenset(str(x) for x in seen_raw),
            half_life_days=half_life_days,
            last_practice_day=cdata.get("last_practice_day"),
            n_reviews=cdata.get("n_reviews", 0),
            needs_remediation=needs_remediation,
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
    if isinstance(data, dict) and ("state" in data or "learner" in data):
        state_data = data.get("state") or data.get("learner")
        if (
            isinstance(state_data, dict)
            and "schema_version" not in state_data
            and "schema_version" in data
        ):
            state_data = dict(state_data)
            state_data["schema_version"] = data["schema_version"]
        data = state_data
    return deserialize_learner(data, concept_ids)


def save_log(log: ExecutionLog, path: str):
    _atomic_write_json(serialize_log(log), path)


def load_log(path: str) -> ExecutionLog:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return ExecutionLog()
    if isinstance(data, dict) and "log" in data:
        log_data = data["log"]
        if (
            isinstance(log_data, dict)
            and "schema_version" not in log_data
            and "schema_version" in data
        ):
            log_data = dict(log_data)
            log_data["schema_version"] = data["schema_version"]
        data = log_data
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
    if "context" in data and data["context"] is not None:
        cdata = data["context"]
        if not isinstance(cdata, dict):
            raise ValidationError(f"Invalid snapshot context in {path}: must be an object")
        for req in ("goal", "deadline_day", "budget"):
            if req not in cdata:
                raise ValidationError(f"Invalid snapshot context in {path}: missing '{req}'")
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
    for req in ("goal", "deadline_day", "budget"):
        if req not in cdata:
            return None
    return PlanContext(
        goal=cdata["goal"],
        deadline_day=cdata["deadline_day"],
        budget=cdata["budget"],
        current_day=cdata.get("current_day", 1),
    )
