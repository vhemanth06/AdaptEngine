"""Pydantic request/response models for the demo API (validation at the HTTP boundary only).

Domain rules (allowed budgets, deadline order, event shapes) stay in the engine; its
ValidationError is mapped to HTTP 422 in app.py.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

_ID = r"^[A-Za-z0-9_.\-]{1,64}$"


def _id(**kw):
    return Field(pattern=_ID, **kw)


class CurriculumSummary(BaseModel):
    id: str
    concepts: int
    activities: int
    reviewed: bool
    review_error: Optional[str] = None
    has_content: bool
    content_reviewer: Optional[str] = None


class ConceptInfo(BaseModel):
    concept_id: str
    description: str
    prerequisites: list[str]
    depth: int


class ActivityInfo(BaseModel):
    activity_id: str
    type: Literal["LESSON", "EXERCISE"]
    target_concept: str
    duration: int
    difficulty: Optional[float] = None


class CurriculumDetail(BaseModel):
    id: str
    concepts: list[ConceptInfo]
    activities: list[ActivityInfo]
    # activity_id -> content entry (data/content schema); None when no content file exists
    content: Optional[dict[str, dict[str, Any]]] = None
    allowed_budgets: list[int]
    theta: float
    k_responses: int


# F2 (D60): named item-model profiles only; a client never sends a file path, and fitted_sim
# (fitted on our own simulator) is not offered
ModelProfile = Literal["heuristic", "fitted_assist09", "fitted_ct"]
DiagnosticMethod = Literal["sweep", "bisection"]
PlannerMethod = Literal[
    "greedy", "cpsat", "hybrid"
]  # F3 (D62); cpsat/hybrid need the [cpsat] extra  # F1 (D49); "bisection" = bisection_config()


class CreateSession(BaseModel):
    curriculum: str = _id()
    goal: str = _id()
    deadline_day: int = Field(ge=1, le=365)
    budget: int = Field(ge=1, le=600)
    model_profile: Optional[ModelProfile] = None  # None = "heuristic"
    diagnostic_method: Optional[DiagnosticMethod] = None  # None = "sweep"
    planner_method: Optional[PlannerMethod] = None  # None = "greedy"


class PlanRequest(BaseModel):
    """Optional overrides of the session's base context (Setup screen)."""

    goal: Optional[str] = _id(default=None)
    deadline_day: Optional[int] = Field(default=None, ge=1, le=365)
    budget: Optional[int] = Field(default=None, ge=1, le=600)


class DiagnosticAnswer(BaseModel):
    activity_id: str = _id()
    # Either the chosen option index (graded against the content file) or a self-reported result
    choice: Optional[int] = Field(default=None, ge=0, le=3)
    correct: Optional[bool] = None


class EventRequest(BaseModel):
    kind: Literal["COMPLETED", "FAILED_ASSESSMENT", "MISSED", "BUDGET_CHANGED", "DEADLINE_CHANGED"]
    day: Optional[int] = Field(default=None, ge=0, le=365)  # default: the engine's current day
    activity_id: Optional[str] = _id(default=None)
    choice: Optional[int] = Field(default=None, ge=0, le=3)
    correct: Optional[bool] = None
    value: Optional[int] = Field(default=None, ge=0, le=600)


class PlanDayOut(BaseModel):
    day: int
    activities: list[str]
    duration: int


class PlanOut(BaseModel):
    # extra keys pass through, so a fitted-profile plan keeps its "model_profile" provenance and
    # the API plan stays equal to serialize_plan (D45) for both profiles
    model_config = ConfigDict(extra="allow")

    config_hash: str
    status: Literal["FEASIBLE", "INFEASIBLE", "UNKNOWN"]
    reason: Optional[str] = None
    shortfall_days: int
    options: list[str]
    days: list[PlanDayOut]
    best_effort_days: list[PlanDayOut]
    trace: list[dict[str, Any]]


class ContextOut(BaseModel):
    goal: str
    deadline_day: int
    budget: int
    current_day: int = 1
    minutes_used_today: int = 0


class ConceptState(BaseModel):
    concept_id: str
    p: float
    responses: int
    lessons_done: int
    status: str
    evidence_mastered: bool
    needs_remediation: bool
    diag_confident: bool = False  # F1 flags (D57), read from the learner state
    confirmed: bool = False


class DiagnosticItem(BaseModel):
    activity_id: str
    concept_id: str
    correct: Optional[bool] = None
    p_before: Optional[float] = None
    p_after: Optional[float] = None


class ConceptResult(BaseModel):
    concept_id: str
    p: float
    n_items: int
    stop_reason: str


class DiagnosticOut(BaseModel):
    done: bool
    next_item: Optional[DiagnosticItem] = None
    items: list[DiagnosticItem]
    # p per concept after the answers so far (None if the engine could not replay a prefix)
    live_p: Optional[dict[str, float]] = None
    concept_results: list[ConceptResult] = []
    # the engine's DiagnosticResult.info (bisection: mode, n_states, bits, n_max, q_bit, top_state,
    # top_state_p, scope; the sweep: {}); while running, the prefix replay's info when one exists
    info: Optional[dict[str, Any]] = None


class EventOut(BaseModel):
    day: int
    kind: str
    activity_id: Optional[str] = None
    minutes_elapsed: int = 0
    correct: Optional[bool] = None
    attempt_id: Optional[str] = None
    value: Optional[int] = None


class SessionOut(BaseModel):
    session_id: str
    curriculum: str
    model_profile: str = "heuristic"
    diagnostic_method: str = "sweep"
    planner_method: str = "greedy"
    context: ContextOut
    effective: Optional[ContextOut] = None  # engine's context after folding the log; None = over
    concepts: list[ConceptState]
    diagnostic: DiagnosticOut
    plan: Optional[PlanOut] = None
    today: Optional[PlanDayOut] = None
    replan_ms: Optional[float] = None
    events: list[EventOut]


class PlanChange(BaseModel):
    activity_id: str
    old_day: Optional[int] = None
    new_day: Optional[int] = None


class ConceptUpdate(BaseModel):
    concept_id: str
    p_before: float
    p_after: float
    correct: Optional[bool] = None
    needs_remediation: bool
    evidence_mastered: bool
    explanation: Optional[str] = None


class EventResult(BaseModel):
    session: SessionOut
    update: Optional[ConceptUpdate] = None
    old_status: Optional[str] = None
    changes: list[PlanChange]


class TraceOut(BaseModel):
    activity_id: Optional[str] = None
    records: list[dict[str, Any]]
    deferred_same_day: list[dict[str, Any]]
    # the plan's CONFIRMATION record whose activity_ids contain activity_id (F1, D57), if any
    confirmation: Optional[dict[str, Any]] = None


class Health(BaseModel):
    status: str
    engine_version: str
    api_version: str
    code_hash: str
    config_hash_default: str
    ortools_available: bool
    web_build: Literal["fresh", "stale", "missing"]
    # curriculum id -> reviewer of data/content/content_<id>.json (None: no content file)
    content_review: dict[str, Optional[str]]
    # curriculum id -> passes the review gate (same check as /api/curricula)
    curriculum_review: dict[str, bool]


class DemoTight(BaseModel):
    deadline_day: int
    budget: int


class DemoPreset(BaseModel):
    """The fixed demo setup (D94), chosen by frontend/api/select_demo_preset.py."""

    curriculum: str
    goal: str
    deadline_day: int
    budget: int
    model_profile: ModelProfile
    diagnostic_method: DiagnosticMethod
    planner_method: PlannerMethod
    known: list[str]
    tight: DemoTight
    has_check: bool
    wrong_check: Optional[str] = None  # the check Study step 5 answers wrong (None: no check)
