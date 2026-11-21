"""Plan 4 (F3): greedy / pure CP-SAT / hybrid planners (F3-TC1 to TC5, TC7, TC10)."""

import collections
import dataclasses
import itertools
import os
import sys

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

pytest.importorskip("ortools")

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG, EngineConfig  # noqa: E402
from adaptengine.core.errors import ValidationError  # noqa: E402
from adaptengine.core.schema import Activity, ActivityType, Concept, PlanContext, PlanStatus  # noqa: E402
from adaptengine.learner.state import LearnerState  # noqa: E402
from experiments.core.audit import budget_violations, plan_violations  # noqa: E402

CUR = os.path.join(repo_root, "data", "curriculum")


def _eng(method, name="8node", **kw):
    cfg = dataclasses.replace(DEFAULT_CONFIG, planner_method=method, **kw)
    return Engine.from_files(
        f"{CUR}/curriculum_{name}.json",
        f"{CUR}/activities_{name}.json",
        config=cfg,
        allow_unreviewed=name.endswith("x10"),
    )


CONTEXTS = [
    PlanContext(goal="C8", deadline_day=14, budget=15),
    PlanContext(goal="C8", deadline_day=6, budget=15),
    PlanContext(goal="C8", deadline_day=5, budget=10, current_day=2, minutes_used_today=4),
    PlanContext(goal="C5", deadline_day=4, budget=10),
    PlanContext(goal="C8", deadline_day=3, budget=15),
    PlanContext(goal="C8", deadline_day=5, budget=10),  # greedy misses, a packing exists (takeover)
]


# ---------------- F3-T1: config, dispatch, optional import ----------------


@pytest.mark.parametrize(
    "kw",
    [
        {"planner_method": "ilp"},
        {"cpsat_seed": 1.5},
        {"cpsat_max_work_units": 0},
        {"cpsat_use_greedy_hint": 1},
        {"cpsat_max_reviews_per_concept": 0},
        {"cpsat_review_lateness_penalty": 2.0},
    ],
)
def test_invalid_f3_config(kw):
    with pytest.raises(ValidationError):
        EngineConfig(**kw)


def test_greedy_default_unchanged_f3_tc1():
    assert DEFAULT_CONFIG.planner_method == "greedy"
    e, plain = (
        _eng("greedy"),
        Engine.from_files(f"{CUR}/curriculum_8node.json", f"{CUR}/activities_8node.json"),
    )
    for ctx in CONTEXTS:
        assert e.plan(e.init_learner(), ctx) == plain.plan(plain.init_learner(), ctx)


def test_missing_ortools_clear_error_f3_tc10(monkeypatch):
    monkeypatch.setitem(sys.modules, "ortools.sat.python", None)  # import now fails
    monkeypatch.setitem(sys.modules, "ortools.sat.python.cp_model", None)
    for method in ("cpsat", "hybrid"):
        e = _eng(method)
        with pytest.raises(ValidationError, match=r"\[cpsat\]"):
            e.plan(e.init_learner(), PlanContext(goal="C8", deadline_day=3, budget=15))
    e = _eng("greedy")
    assert e.plan(e.init_learner(), CONTEXTS[0]).status == PlanStatus.FEASIBLE


def _plan_prereq(e, state, plan, days):
    """Plan-level prerequisite violations of `days` (replaces experiments/checks.py::
    count_plan_prereq_violations); budget and deadline do not affect the prerequisite count."""
    return plan_violations(e, state, plan, budget=10**6, deadline=10**6, days=days)["prereq"]


# ---------------- F3-T2: constraints, determinism, never worse than greedy ----------------


@pytest.mark.parametrize("ctx", CONTEXTS)
def test_cpsat_plans_respect_constraints_f3_tc2(ctx):
    e = _eng("cpsat")
    st = e.init_learner()
    p = e.plan(st, ctx)
    days = p.days or p.best_effort_days
    assert _plan_prereq(e, st, p, days) == 0
    cap = lambda d: ctx.budget - (ctx.minutes_used_today if d == ctx.current_day else 0)  # noqa: E731
    assert budget_violations(e, days, cap) == 0
    assert all(ctx.current_day <= d.day <= ctx.deadline_day for d in days)
    # within-concept order: lessons before exercises (D16)
    order = [a for d in days for a in d.activities]
    for c in {e.activities[a].target_concept for a in order}:
        kinds = [e.activities[a].type for a in order if e.activities[a].target_concept == c]
        first_ex = next((i for i, k in enumerate(kinds) if k == ActivityType.EXERCISE), len(kinds))
        assert ActivityType.LESSON not in kinds[first_ex:] or c in {"C1"}  # remediation only


def test_cpsat_deterministic_f3_tc3():
    e = _eng("cpsat")
    for ctx in CONTEXTS[:3]:
        assert e.plan(e.init_learner(), ctx) == e.plan(e.init_learner(), ctx)


@pytest.mark.parametrize("name", ["4node", "8node", "8node_x10"])
def test_never_infeasible_where_greedy_succeeds_f3_tc4(name):
    g, c = _eng("greedy", name), _eng("cpsat", name)
    goal = sorted(g.graph.concepts())[-1]
    for dl, b in ((4, 10), (6, 15), (10, 5), (3, 30)):
        ctx = PlanContext(goal=goal, deadline_day=dl, budget=b)
        pg, pc = g.plan(g.init_learner(), ctx), c.plan(c.init_learner(), ctx)
        if pg.status == PlanStatus.FEASIBLE:
            assert pc.status == PlanStatus.FEASIBLE
            assert pc.days[-1].day <= pg.days[-1].day or pc.reason.startswith("CPSAT")
        if pc.status == PlanStatus.UNKNOWN:
            assert pc.reason == "CPSAT_LIMIT_REACHED"


# ---------------- F3-T2/T3: brute force on a tiny instance ----------------


def _tiny(method, budget):
    concepts = (Concept("A"), Concept("B", ("A",)), Concept("C"))
    acts = (
        Activity("L-A", ActivityType.LESSON, "A", 3),
        Activity("E-A", ActivityType.EXERCISE, "A", 2, difficulty=0.2),
        Activity("L-B", ActivityType.LESSON, "B", 4),
        Activity("E-B", ActivityType.EXERCISE, "B", 2, difficulty=0.2),
        Activity("L-C", ActivityType.LESSON, "C", 3),
        Activity("E-C", ActivityType.EXERCISE, "C", 3, difficulty=0.2),
    )
    cfg = dataclasses.replace(
        DEFAULT_CONFIG,
        planner_method=method,
        allowed_budgets=(5, 6, 7, 10, 12),
        maintenance_reviews=False,
        theta=0.2,
        k_responses=1,
    )
    return Engine(concepts, acts, cfg)


def _brute_min_days(e, workload, budget, max_days=8):
    toks = [(c, a) for c in sorted(workload) for a in workload[c]]
    best = None
    for days in itertools.product(range(max_days), repeat=len(toks)):
        load = collections.Counter()
        for (c, a), d in zip(toks, days):
            load[d] += a.duration
        if any(v > budget for v in load.values()):
            continue
        pos = {}
        ok = True
        for (c, a), d in zip(toks, days):
            if c in pos and d < pos[c][-1]:
                ok = False
            pos.setdefault(c, []).append(d)
        for c, ds in pos.items():
            for p in e.graph.prerequisites(c):
                if p in pos and ds[0] < pos[p][-1]:
                    ok = False
        if ok:
            f = max(days)
            best = f if best is None else min(best, f)
    return best


def test_brute_force_minimum_days_and_budget_f3_tc5():
    from adaptengine.planner import compute_workload

    e = _tiny("cpsat", 6)
    st = e.init_learner()
    wl, _, _ = compute_workload(e.graph, e.activities, st, "B", model=e.model, cfg=e.config)
    wl = {c: a for c, a in wl.items() if a}
    for budget in (6, 7):
        brute = _brute_min_days(e, wl, budget) + 1  # days used
        ok = e.plan(st, PlanContext(goal="B", deadline_day=brute, budget=budget))
        assert ok.status == PlanStatus.FEASIBLE and ok.days[-1].day == brute
        bad = e.plan(st, PlanContext(goal="B", deadline_day=brute - 1, budget=budget))
        assert bad.status == PlanStatus.INFEASIBLE and bad.shortfall_days == 1
        solve = next(t for t in bad.trace if t.get("decision") == "CPSAT_SOLVE")
        assert solve["minimum_finish_day"] == brute and solve["shortfall_exact"] is True
        smallest = next(
            (b for b in (7, 10, 12) if _brute_min_days(e, wl, b) + 1 <= brute - 1), None
        )
        assert solve.get("smallest_working_budget") == smallest
        assert smallest == 12  # 11 minutes of work fit in one day only from 12 minutes
        # the bounds check never contradicts CP-SAT: bounds-feasible problems may still be infeasible,
        # never the other way round
        g = _tiny("greedy", budget)
        assert (
            g.plan(st, PlanContext(goal="B", deadline_day=brute, budget=budget)).status
            != PlanStatus.INFEASIBLE
        )


# ---------------- F3-T6: hybrid ----------------


@pytest.mark.parametrize("ctx", CONTEXTS)
def test_hybrid_equals_greedy_on_time_and_cpsat_on_takeover_f3_tc7(ctx):
    g, h, c = _eng("greedy"), _eng("hybrid"), _eng("cpsat")
    st = g.init_learner()
    pg, ph, pc = g.plan(st, ctx), h.plan(st, ctx), c.plan(st, ctx)
    if pg.status == PlanStatus.FEASIBLE and pg.reason == "GREEDY_FEASIBLE":
        assert ph == pg
    else:
        assert ph.status == pc.status and ph.days == pc.days
        assert ph.shortfall_days == pc.shortfall_days and ph.options == pc.options
        assert ph.status != PlanStatus.UNKNOWN or pc.status == PlanStatus.UNKNOWN
        assert any(t.get("decision") == "GREEDY_ATTEMPT" for t in ph.trace)


def test_best_effort_uses_selected_planner():
    e = _eng("cpsat")
    p = e.plan(e.init_learner(), PlanContext(goal="C8", deadline_day=3, budget=15))
    assert p.status == PlanStatus.INFEASIBLE and p.best_effort_days
    assert all(d.day <= 3 for d in p.best_effort_days)
    assert any(t.get("reason") == "CPSAT_ASSIGNED" and t.get("best_effort") for t in p.trace)
    assert _plan_prereq(e, e.init_learner(), p, p.best_effort_days) == 0


def test_state_with_remediation_puts_it_early():
    e = _eng("cpsat")
    st = e.init_learner()
    c1 = dataclasses.replace(st.concepts["C1"], needs_remediation=True, p=0.3, responses=2)
    st = LearnerState(concepts={**st.concepts, "C1": c1})
    p = e.plan(st, PlanContext(goal="C3", deadline_day=10, budget=15))
    assert p.days[0].activities[0] == "L-C1"
    assert any(t.get("reason") == "REMEDIATION_INSERTED" for t in p.trace)
