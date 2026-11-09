"""Thin FastAPI adapter over adaptengine.api.Engine for the demo UI (D45).

No planning, mastery or eligibility logic lives here: every decision comes from Engine
(plan/replan/next_activities/record/diagnose), adaptengine.session and the content loader.
The adapter only validates input, persists sessions, grades a chosen option against the
content file's answer key, and reshapes engine output for display.

Run from the repo root:  .venv/bin/python -m uvicorn frontend.api.app:app --port 8000
"""

import functools
import json
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from adaptengine.api import Engine
from adaptengine.core.config import DEFAULT_CONFIG
from adaptengine.core.errors import ValidationError
from adaptengine.core.validators import check_budget
from adaptengine.core.schema import ActivityType, Event, EventType, PlanContext
from adaptengine.curriculum.content import load_content
from adaptengine.curriculum.loader import load_activities, load_curriculum
from adaptengine.diagnostic import AdaptiveDiagnostic
from adaptengine.learner.state import ExecutionLog, is_evidence_mastered
from adaptengine.planner import serialize_plan
from adaptengine.replanner import compute_effective_context
from adaptengine.session import serialize_log

from . import store
from .schemas import (
    ConceptInfo,
    CreateSession,
    CurriculumDetail,
    CurriculumSummary,
    DiagnosticAnswer,
    EvaluationOut,
    EventRequest,
    EventResult,
    PlanRequest,
    SessionOut,
    SimulateOut,
    SimulateRequest,
    TraceOut,
)

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
MANIFEST = DATA / "review_manifest.json"
RESULTS_DIR = REPO / "experiments" / "results"
DIST = REPO / "frontend" / "web" / "dist"

app = FastAPI(title="AdaptEngine demo API", version="0.1.0")


@app.exception_handler(ValidationError)
def _engine_validation(_: Request, exc: ValidationError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(store.SessionNotFound)
def _no_session(_: Request, exc: store.SessionNotFound):
    return JSONResponse(status_code=404, content={"detail": f"unknown session {exc.args[0]}"})


# ---------------------------------------------------------------------------- curricula


@dataclass(frozen=True)
class Bundle:
    engine: Engine
    concepts: tuple
    content: Optional[dict]


def _curriculum_ids() -> list[str]:
    cur = DATA / "curriculum"
    return sorted(
        p.stem.removeprefix("curriculum_")
        for p in cur.glob("curriculum_*.json")
        if (cur / p.name.replace("curriculum_", "activities_", 1)).exists()
    )


@functools.cache
def _bundle(cid: str) -> Bundle:
    if cid not in _curriculum_ids():
        raise HTTPException(404, f"unknown curriculum {cid}")
    concepts = load_curriculum(str(DATA / "curriculum" / f"curriculum_{cid}.json"), str(MANIFEST))
    acts = load_activities(
        str(DATA / "curriculum" / f"activities_{cid}.json"),
        concepts,
        str(MANIFEST),
        cfg=DEFAULT_CONFIG,
    )
    content_path = DATA / "content" / f"content_{cid}.json"
    content = dict(load_content(str(content_path), acts)) if content_path.exists() else None
    return Bundle(Engine(concepts, acts, DEFAULT_CONFIG), concepts, content)


@app.get("/api/curricula", response_model=list[CurriculumSummary])
def list_curricula():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    out = []
    for cid in _curriculum_ids():
        content_key = f"data/content/content_{cid}.json"
        row = {
            "id": cid,
            "concepts": 0,
            "activities": 0,
            "reviewed": True,
            "has_content": (REPO / content_key).exists(),
            "content_reviewer": manifest.get(content_key, {}).get("reviewer"),
        }
        try:
            b = _bundle(cid)
            row.update(concepts=len(b.concepts), activities=len(b.engine.activities))
        except ValidationError as e:
            row.update(reviewed=False, review_error=str(e))
        out.append(row)
    return out


@app.get("/api/curricula/{cid}", response_model=CurriculumDetail)
def get_curriculum(cid: str):
    b = _bundle(cid)
    g, cfg = b.engine.graph, b.engine.config
    return {
        "id": cid,
        "concepts": [
            ConceptInfo(
                concept_id=c.concept_id,
                description=c.description,
                prerequisites=list(g.prerequisites(c.concept_id)),
                depth=g.depth(c.concept_id),
            )
            for c in b.concepts
        ],
        "activities": [
            {
                "activity_id": a.activity_id,
                "type": a.type.value,
                "target_concept": a.target_concept,
                "duration": a.duration,
                "difficulty": a.difficulty,
            }
            for a in b.engine.activities.values()
        ],
        "content": b.content,
        "allowed_budgets": list(cfg.allowed_budgets),
        "theta": cfg.theta,
        "k_responses": cfg.k_responses,
    }


# --------------------------------------------------------------------------- diagnostic


class NeedAnswer(Exception):
    """Raised by the replay provider when the recorded answers run out (quick-path stepwise)."""

    def __init__(self, activity):
        self.activity = activity


def _replay(engine: Engine, answers: list, sid: str, n_max: Optional[int] = None):
    """Re-run the deterministic diagnostic from the initial state with the recorded answers.

    Returns (DiagnosticResult | None, pending activity | None). With n_max, the engine's
    diagnostic stops after that many items, giving the exact state after a prefix of answers.
    """
    queue = list(answers)

    def provider(activity):
        if not queue:
            raise NeedAnswer(activity)
        aid, correct = queue.pop(0)
        if aid != activity.activity_id:
            raise RuntimeError(f"diagnostic replay diverged at {aid} vs {activity.activity_id}")
        return correct

    try:
        if n_max is None:
            return engine.diagnose(engine.init_learner(), provider, session_id=sid), None
        cfg = replace(engine.config, n_max=n_max)
        diag = AdaptiveDiagnostic(engine.graph, engine.activities, cfg, model=engine.model)
        return diag.run(engine.init_learner(), provider, session_id=sid), None
    except NeedAnswer as e:
        return None, e.activity


def _item_rows(result) -> list[dict]:
    return [
        {
            "activity_id": it.activity_id,
            "concept_id": it.concept_id,
            "correct": it.response,
            "p_before": it.p_before,
            "p_after": it.p_after,
        }
        for it in result.item_log
    ]


def _diagnostic_view(engine: Engine, answers: list, sid: str) -> dict:
    result, pending = _replay(engine, answers, sid)
    if result is not None:
        return {
            "done": True,
            "items": _item_rows(result),
            "live_p": {c: x.p for c, x in result.state.concepts.items()},
            "concept_results": [
                {
                    "concept_id": c,
                    "p": r.p,
                    "n_items": r.n_items,
                    "stop_reason": r.stop_reason.value,
                }
                for c, r in result.concept_results.items()
            ],
        }
    view = {
        "done": False,
        "next_item": {"activity_id": pending.activity_id, "concept_id": pending.target_concept},
        "items": [
            {
                "activity_id": a,
                "concept_id": engine.activities[a].target_concept,
                "correct": c,
            }
            for a, c in answers
        ],
        "live_p": {c: x.p for c, x in engine.init_learner().concepts.items()},
    }
    if answers:
        try:
            prefix, _ = _replay(engine, answers, sid, n_max=len(answers))
        except (RuntimeError, ValidationError):
            prefix = None  # the engine's stop rules differ for a truncated run: no live bars
        rows = _item_rows(prefix) if prefix is not None else []
        if [r["activity_id"] for r in rows] == [a for a, _ in answers]:
            view["items"] = rows
            view["live_p"] = {c: x.p for c, x in prefix.state.concepts.items()}
        else:
            view["live_p"] = None
    return view


# ------------------------------------------------------------------------------ sessions


def _open(sid: str):
    meta = store.load_meta(sid)
    b = _bundle(meta["curriculum"])
    state, log, ctx = store.load_state(sid, b.engine.graph.concepts())
    return b, state, log, ctx, meta


def _ctx_dict(ctx: Optional[PlanContext]) -> Optional[dict]:
    if ctx is None:
        return None
    return {
        "goal": ctx.goal,
        "deadline_day": ctx.deadline_day,
        "budget": ctx.budget,
        "current_day": ctx.current_day,
        "minutes_used_today": ctx.minutes_used_today,
    }


def _day_dict(d) -> Optional[dict]:
    return (
        None
        if d is None
        else {"day": d.day, "activities": list(d.activities), "duration": d.duration}
    )


def _run_plan(engine: Engine, state, log, ctx, meta: dict) -> None:
    """The engine's online loop (T2.2): replan from the real state and log, commit today's slice."""
    t0 = time.perf_counter()
    today, plan = engine.next_activities(state, log, ctx)
    meta["replan_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    meta["plan"] = serialize_plan(plan, engine.config)
    meta["today"] = _day_dict(today)


def _view(b: Bundle, sid: str, state, log, ctx, meta: dict) -> dict:
    cfg = b.engine.config
    eff, _, _ = compute_effective_context(ctx, log)
    return {
        "session_id": sid,
        "curriculum": meta["curriculum"],
        "context": _ctx_dict(ctx),
        "effective": _ctx_dict(eff),
        "concepts": [
            {
                "concept_id": cid,
                "p": c.p,
                "responses": c.responses,
                "lessons_done": c.lessons_done,
                "status": c.status.value,
                "evidence_mastered": is_evidence_mastered(c, cfg),
                "needs_remediation": c.needs_remediation,
            }
            for cid, c in state.concepts.items()
        ],
        "diagnostic": _diagnostic_view(b.engine, meta["diag_answers"], sid),
        "plan": meta.get("plan"),
        "today": meta.get("today"),
        "replan_ms": meta.get("replan_ms"),
        "events": serialize_log(log)["events"],
    }


def _grade(b: Bundle, activity_id: str, choice: Optional[int], correct: Optional[bool]):
    if choice is None:
        return correct
    if correct is not None:
        raise HTTPException(422, "send either choice or correct, not both")
    entry = (b.content or {}).get(activity_id)
    if not entry or "correct" not in entry:
        raise HTTPException(422, f"no answer key for {activity_id}; send correct instead")
    return choice == entry["correct"]


@app.post("/api/sessions", response_model=SessionOut)
def create_session(req: CreateSession):
    b = _bundle(req.curriculum)
    ctx = PlanContext(goal=req.goal, deadline_day=req.deadline_day, budget=req.budget)
    check_budget(ctx.budget, b.engine.config.allowed_budgets)  # config-driven since W7 T5.1
    if req.goal not in b.engine.graph.concepts():
        raise HTTPException(422, f"unknown goal concept {req.goal}")
    sid = store.new_id()
    state, log = b.engine.init_learner(), ExecutionLog()
    meta = {"curriculum": req.curriculum, "diag_answers": []}
    store.save(sid, state, log, ctx, meta)
    return _view(b, sid, state, log, ctx, meta)


@app.get("/api/sessions/{sid}", response_model=SessionOut)
def get_session(sid: str):
    b, state, log, ctx, meta = _open(sid)
    return _view(b, sid, state, log, ctx, meta)


@app.post("/api/sessions/{sid}/diagnostic/answer", response_model=SessionOut)
def diagnostic_answer(sid: str, req: DiagnosticAnswer):
    b, state, log, ctx, meta = _open(sid)
    if log.events:
        raise HTTPException(409, "diagnostic must run before any study events")
    answers = [tuple(a) for a in meta["diag_answers"]]
    result, pending = _replay(b.engine, answers, sid)
    if result is not None:
        raise HTTPException(409, "diagnostic already finished")
    if req.activity_id != pending.activity_id:
        raise HTTPException(409, f"expected an answer to {pending.activity_id}")
    correct = _grade(b, req.activity_id, req.choice, req.correct)
    if correct is None:
        raise HTTPException(422, "choice or correct is required")
    answers.append((req.activity_id, correct))
    meta["diag_answers"] = answers
    result, _ = _replay(b.engine, answers, sid)
    if result is not None:
        state = result.state
        _run_plan(b.engine, state, log, ctx, meta)
    store.save(sid, state, log, ctx, meta)
    return _view(b, sid, state, log, ctx, meta)


@app.post("/api/sessions/{sid}/plan", response_model=SessionOut)
def make_plan(sid: str, req: PlanRequest):
    b, state, log, ctx, meta = _open(sid)
    ctx = PlanContext(
        goal=req.goal or ctx.goal,
        deadline_day=req.deadline_day or ctx.deadline_day,
        budget=req.budget or ctx.budget,
    )
    check_budget(ctx.budget, b.engine.config.allowed_budgets)
    if ctx.goal not in b.engine.graph.concepts():
        raise HTTPException(422, f"unknown goal concept {ctx.goal}")
    _run_plan(b.engine, state, log, ctx, meta)
    store.save(sid, state, log, ctx, meta)
    return _view(b, sid, state, log, ctx, meta)


def _first_days(plan: Optional[dict]) -> dict[str, int]:
    if not plan:
        return {}
    days = plan["days"] or plan["best_effort_days"]
    out: dict[str, int] = {}
    for d in days:
        for aid in d["activities"]:
            out.setdefault(aid, d["day"])
    return out


@app.post("/api/sessions/{sid}/events", response_model=EventResult)
def post_event(sid: str, req: EventRequest):
    b, state, log, ctx, meta = _open(sid)
    eng = b.engine
    kind = EventType(req.kind)
    eff, _, _ = compute_effective_context(ctx, log)
    act = None
    if req.activity_id is not None:
        act = eng.activities.get(req.activity_id)
        if act is None:
            raise HTTPException(422, f"unknown activity {req.activity_id}")
    day = req.day
    if day is None:
        today = meta.get("today")
        if kind in (EventType.COMPLETED, EventType.FAILED_ASSESSMENT) and today:
            day = today["day"]
        elif eff is not None:
            day = eff.current_day
        else:
            raise HTTPException(409, "the session is past its deadline; send day explicitly")
    correct = None
    if act is not None and act.type == ActivityType.EXERCISE:
        correct = _grade(b, act.activity_id, req.choice, req.correct)
    event = Event(
        day=day,
        kind=kind,
        activity_id=req.activity_id,
        minutes_elapsed=act.duration if act is not None else 0,
        correct=correct,
        value=req.value,
    )
    before = state.concepts[act.target_concept] if act is not None else None
    state, log = eng.record(state, log, event)
    old_plan = meta.get("plan")
    _run_plan(eng, state, log, ctx, meta)
    store.save(sid, state, log, ctx, meta)

    update = None
    if act is not None:
        after = state.concepts[act.target_concept]
        update = {
            "concept_id": act.target_concept,
            "p_before": before.p,
            "p_after": after.p,
            "correct": correct,
            "needs_remediation": after.needs_remediation,
            "evidence_mastered": is_evidence_mastered(after, eng.config),
            "explanation": (b.content or {}).get(act.activity_id, {}).get("explanation"),
        }
    old, new = _first_days(old_plan), _first_days(meta["plan"])
    changes = [
        {"activity_id": a, "old_day": old.get(a), "new_day": new.get(a)}
        for a in sorted(old.keys() | new.keys())
        if old.get(a) != new.get(a)
    ]
    return {
        "session": _view(b, sid, state, log, ctx, meta),
        "update": update,
        "old_status": old_plan["status"] if old_plan else None,
        "changes": changes,
    }


@app.get("/api/sessions/{sid}/trace", response_model=TraceOut)
def get_trace(sid: str, activity_id: Optional[str] = None):
    meta = store.load_meta(sid)
    if not meta.get("plan"):
        raise HTTPException(409, "no plan yet")
    trace = meta["plan"]["trace"]
    if activity_id is None:
        return {"records": trace, "deferred_same_day": []}
    records = [r for r in trace if r.get("activity_id") == activity_id]
    days = {r.get("day") for r in records if r.get("decision") == "SELECTED"}
    deferred = [
        r
        for r in trace
        if r.get("decision") == "DEFERRED"
        and r.get("day") in days
        and r.get("activity_id") != activity_id
    ]
    return {"activity_id": activity_id, "records": records, "deferred_same_day": deferred}


# ---------------------------------------------------------------------- autopilot / eval


@app.post("/api/simulate", response_model=SimulateOut)
def simulate(req: SimulateRequest):
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))  # experiments/ is a repo-root package, not installed
    from experiments.arms import get_scenario, run_episode
    from experiments.sim import PROFILES

    eng = _bundle(req.curriculum).engine
    if req.goal not in eng.graph.concepts():
        raise HTTPException(422, f"unknown goal concept {req.goal}")
    sc = get_scenario(req.scenario, eng, eng.init_learner(), goal=req.goal, budget=req.budget)
    if sc is None:
        return {"episodes": [], "note": f"{req.scenario} does not apply at budget {req.budget}"}
    episodes = []
    for seed in range(req.seed, req.seed + req.n_seeds):
        ep = run_episode(eng, seed=seed, scenario=sc, arm=req.arm, profile=PROFILES[req.profile])
        ep["executed_minutes_per_day"] = {
            str(d): m for d, m in ep["executed_minutes_per_day"].items()
        }
        episodes.append(ep)
    scenario = {
        "name": sc.name,
        "budget": sc.budget,
        "deadline": sc.deadline,
        "goal": sc.goal,
        "events": [[d, k.value, v] for d, k, v in sc.events],
    }
    return {"scenario": scenario, "episodes": episodes}


def _compact(x: Any) -> Any:
    if isinstance(x, dict):
        return {
            k: _compact(v)
            for k, v in x.items()
            if not str(k).startswith("per_seed") and k != "attempts"
        }
    if isinstance(x, list):
        return [_compact(v) for v in x[:200]]
    return x


@app.get("/api/evaluation", response_model=EvaluationOut)
def evaluation():
    names = ["evaluation_results.json", "replan_latency.json"]
    names += sorted(p.name for p in RESULTS_DIR.glob("w7_*.json"))
    files = []
    for name in names:
        try:
            data = json.loads((RESULTS_DIR / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # missing or half-written results are simply not shown
        if isinstance(data, dict):
            files.append({"name": name, "data": _compact(data)})
    return {"files": files}


if DIST.is_dir():  # serve the built web app (one-command demo); API routes take precedence
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
