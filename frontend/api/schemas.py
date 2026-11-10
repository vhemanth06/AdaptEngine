"""Pydantic request/response models for the demo API (validation at the HTTP boundary only).

Domain rules (allowed budgets, deadline order, event shapes) stay in the engine; its
ValidationError is mapped to HTTP 422 in app.py.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

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


class CreateSession(BaseModel):
    curriculum: str = _id()
    goal: str = _id()
    deadline_day: int = Field(ge=1, le=365)
    budget: int = Field(ge=1, le=600)
    profile: str = _id(default="w7_default")  # W8 B.1: named learner-model profile


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


class SimulateRequest(BaseModel):
    curriculum: str = _id()
    goal: str = _id()
    budget: int = Field(default=15, ge=1, le=600)
    arm: Literal[
        "adapt", "no_review", "no_replan", "static", "static_loop", "random_eligible",
        "adapt_final", "adapt_final_dx",
    ] = "adapt"  # fmt: skip
    scenario: Literal[
        "calm", "missed_day", "budget_drop", "deadline_cut", "missed_2days", "forgetting_21"
    ] = "missed_day"
    profile: Literal["nominal", "high_slip", "fast_forgetter", "rapid_learner"] = "nominal"
    world: Literal["S0", "S1", "S2", "S3", "S4"] = "S0"
    horizon: Optional[int] = Field(default=None, ge=3, le=60)  # None = W7 rule
    seed: int = Field(default=100, ge=0, le=10**6)
    n_seeds: int = Field(default=1, ge=1, le=100)


class PlanDayOut(BaseModel):
    day: int
    activities: list[str]
    duration: int


class PlanOut(BaseModel):
    config_hash: str
    status: Literal["FEASIBLE", "INFEASIBLE", "UNKNOWN"]
    reason: Optional[str] = None
    shortfall_days: int
    options: list[str]
    days: list[PlanDayOut]
    best_effort_days: list[PlanDayOut]
    feasibility_warning: Optional[str] = None
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
    context: ContextOut
    effective: Optional[ContextOut] = None  # engine's context after folding the log; None = over
    concepts: list[ConceptState]
    diagnostic: DiagnosticOut
    plan: Optional[PlanOut] = None
    today: Optional[PlanDayOut] = None
    replan_ms: Optional[float] = None
    events: list[EventOut]
    profile: str = "w7_default"
    feasibility_warning: Optional[str] = None  # W8 F.1 (expected projection; display only)


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


class SimEpisode(BaseModel):
    arm: str
    scenario: str
    seed: int
    goal_true_mastery: float
    goal_mastered: bool
    mean_true_mastery_goal_and_ancestors: float
    retention: float
    days_used: int
    executed_minutes_per_day: dict[str, int]
    plan_prereq_violations: int
    executed_prereq_violations: int
    budget_violations: int
    idle_days_unmastered: int
    idle_days_total: int
    minutes_used: int
    minutes_available: int
    minute_utilisation: float
    believed_mastered: int
    false_mastered: int
    total_activities_completed: int
    final_p: dict[str, float] = {}
    final_theta: dict[str, float] = {}
    goal_theta_by_minutes: list[list[float]] = []


class SimulateOut(BaseModel):
    scenario: Optional[dict[str, Any]] = None
    episodes: list[SimEpisode]
    note: Optional[str] = None


class EvaluationFile(BaseModel):
    name: str
    data: dict[str, Any]


class EvaluationOut(BaseModel):
    files: list[EvaluationFile]


# ------------------------------------------------------------------------- W8 additions


class Health(BaseModel):
    status: str
    engine_version: str
    code_hash: str
    profiles: list[str]
    default_profile: str
    flags: dict[str, Any]
    web_build: str  # "fresh" | "stale" | "missing"
    content_reviewer: Optional[str] = None


class DraftRequest(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_]{0,40}$")
    topic: str = Field(min_length=3, max_length=120)
    n_concepts: int = Field(default=3, ge=2, le=8)
    provider: Literal["stub", "anthropic", "ollama"] = "stub"


class DraftName(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_]{0,40}$")


class DraftEdit(BaseModel):
    content: dict[str, dict[str, Any]]


class ApproveRequest(DraftName):
    reviewer: str = Field(max_length=80)


class DraftOut(BaseModel):
    name: str
    meta: dict[str, Any]
    curriculum: dict[str, Any]
    activities: dict[str, Any]
    content: dict[str, Any]
    report: dict[str, Any]
    attempts: list[dict[str, Any]] = []


class PolicyPreviewRequest(BaseModel):
    policy: Literal[
        "deterministic", "bandit_frozen", "bandit_updating", "random", "agent", "agent_bad"
    ] = "deterministic"


class PolicyPreviewOut(BaseModel):
    policy: str
    today: Optional[PlanDayOut] = None
    days: list[PlanDayOut]
    decisions: list[dict[str, Any]]
    agent_label: Optional[str] = None


class ProposeRequest(BaseModel):
    mode: Literal["agent", "agent_bad"] = "agent"


class ProposeOut(BaseModel):
    accepted: bool
    violations: list[dict[str, Any]]
    rationale: str
    proposed_days: list[dict[str, Any]]
    reference_days: list[dict[str, Any]]
    agent_label: str


class StrategyOut(BaseModel):
    options: list[dict[str, Any]]
    default: str
    choice: str
    source: str
    rationale: Optional[str] = None
