from typing import Mapping
from dataclasses import replace
from .core.config import EngineConfig, DEFAULT_CONFIG
from .core.schema import Event, EventType, ActivityType, Activity, Plan, PlanContext
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
    def from_files(
        cls,
        curriculum_path: str,
        activities_path: str,
        manifest_path: str = None,
        config: EngineConfig = DEFAULT_CONFIG,
        allow_unreviewed: bool = False,
    ) -> "Engine":
        concepts = load_curriculum(
            curriculum_path, manifest_path, allow_unreviewed=allow_unreviewed
        )
        activities = load_activities(
            activities_path, concepts, manifest_path, allow_unreviewed=allow_unreviewed, cfg=config
        )
        return cls(concepts, activities, config)

    def init_learner(self) -> LearnerState:
        return initial_state(self.graph.concepts(), self.config)

    def diagnose(
        self,
        state: LearnerState,
        response_provider,
        goal_concepts=None,
        model=None,
    ):
        from .diagnostic import AdaptiveDiagnostic

        diagnostic = AdaptiveDiagnostic(self.graph, self.activities, self.config)
        return diagnostic.run(state, response_provider, goal_concepts, model)

    def plan(
        self,
        state: LearnerState,
        ctx: PlanContext,
        *,
        done_ids=None,
        review_urgency=None,
        model=None,
    ) -> Plan:
        from .planner import plan as run_plan

        if done_ids is None:
            done_ids = ()

        return run_plan(
            self.graph,
            self.activities,
            state,
            ctx,
            done_ids=done_ids,
            review_urgency=review_urgency,
            model=model,
            cfg=self.config,
        )

    def replan(
        self,
        state: LearnerState,
        log: ExecutionLog,
        ctx: PlanContext,
        *,
        review_urgency=None,
        model=None,
    ) -> Plan:
        from .replanner import replan as run_replan

        return run_replan(
            self.graph,
            self.activities,
            state,
            log,
            ctx,
            review_urgency=review_urgency,
            model=model,
            cfg=self.config,
        )

    def record(
        self, state: LearnerState, log: ExecutionLog, event: Event
    ) -> tuple[LearnerState, ExecutionLog]:
        if not isinstance(event, Event):
            raise ValidationError(f"event must be an Event instance, got {type(event).__name__}")

        # Deterministic attempt_id if not provided
        attempt_id = event.attempt_id
        if attempt_id is None:
            attempt_id = (
                f"{event.activity_id or event.kind.value}-d{event.day}-{len(log.events) + 1}"
            )
            event = Event(
                day=event.day,
                kind=event.kind,
                activity_id=event.activity_id,
                minutes_elapsed=event.minutes_elapsed,
                correct=event.correct,
                attempt_id=attempt_id,
                value=event.value,
            )

        # Log-level duplicate attempt_id check (Finding 7)
        if any(e.attempt_id == attempt_id for e in log.events):
            return state, log

        if event.kind == EventType.MISSED:
            return state, log.append(event)

        if event.kind == EventType.DEADLINE_CHANGED:
            return state, log.append(event)

        if event.kind == EventType.BUDGET_CHANGED:
            if event.value not in self.config.allowed_budgets:
                raise ValidationError(
                    f"BUDGET_CHANGED value {event.value} not in allowed_budgets {self.config.allowed_budgets}"
                )
            return state, log.append(event)

        if event.kind == EventType.FAILED_ASSESSMENT:
            if event.activity_id not in self.activities:
                raise UnknownConceptError(f"Unknown activity {event.activity_id}")
            activity = self.activities[event.activity_id]
            if activity.type != ActivityType.EXERCISE:
                raise ValidationError("FAILED_ASSESSMENT requires an EXERCISE activity")
            target = activity.target_concept

            if target in state.concepts and attempt_id in state.concepts[target].seen_attempt_ids:
                return state, log

            # Applied as a failed response (D28)
            new_state, _ = apply_response(
                state,
                activity,
                False,
                self.config,
                day=event.day,
                attempt_id=attempt_id,
            )
            # Forced remediation check (D20, D28)
            target_c = new_state.concepts[target]
            if target_c.p < self.config.remediation_threshold:
                new_c = replace(target_c, needs_remediation=True)
                new_state = LearnerState(concepts={**new_state.concepts, target: new_c})

            # Ensure event in log has correct=False
            if event.correct is None:
                event = Event(
                    day=event.day,
                    kind=event.kind,
                    activity_id=event.activity_id,
                    minutes_elapsed=event.minutes_elapsed,
                    correct=False,
                    attempt_id=attempt_id,
                    value=event.value,
                )
            return new_state, log.append(event)

        if event.kind == EventType.COMPLETED:
            if event.activity_id not in self.activities:
                raise UnknownConceptError(f"Unknown activity {event.activity_id}")
            activity = self.activities[event.activity_id]
            target = activity.target_concept

            # Idempotency check: if this attempt was already recorded on the concept, no-op
            if target in state.concepts and attempt_id in state.concepts[target].seen_attempt_ids:
                return state, log

            if activity.type == ActivityType.EXERCISE:
                if event.correct is None:
                    raise ValidationError("COMPLETED EXERCISE requires correct field")
                new_state, _ = apply_response(
                    state,
                    activity,
                    event.correct,
                    self.config,
                    day=event.day,
                    attempt_id=attempt_id,
                )
                # Remediation check if incorrect response leaves p < remediation_threshold (D20)
                if event.correct is False:
                    target_c = new_state.concepts[target]
                    if target_c.p < self.config.remediation_threshold:
                        new_c = replace(target_c, needs_remediation=True)
                        new_state = LearnerState(concepts={**new_state.concepts, target: new_c})

                return new_state, log.append(event)
            elif activity.type == ActivityType.LESSON:
                if event.correct is not None:
                    raise ValidationError("COMPLETED LESSON must not have correct field")
                new_state, _ = apply_lesson(
                    state,
                    activity,
                    self.config,
                    day=event.day,
                    attempt_id=attempt_id,
                )
                return new_state, log.append(event)

        return state, log.append(event)
