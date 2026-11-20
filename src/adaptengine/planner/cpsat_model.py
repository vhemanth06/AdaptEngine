"""CP-SAT scheduling model shared by the pure CP-SAT and hybrid planners (Plan 4, F3.4, D66).

The workload (what to study) is fixed (D70); the model decides on which day each item and each
optional review happens. Hard constraints: daily budget (day 0 reduced by minutes already used),
order within a concept, prerequisites (a concept's first item on or after each prerequisite's
last item; same day allowed, ordered first within the day), the deadline, and review rules
(due offsets, chains, prerequisite gating). Objective levels, solved lexicographically (D67):
1 goal finish day, 2 remediation days, 3 weighted concept finish days (descendants + 1),
4 review reward (urgency, minus a lateness penalty), 5 maximum daily load.

Determinism (D68): one worker, fixed seed, a deterministic work-unit limit per solve, the greedy
plan as hint, variables created in a fixed order. This is the only module that imports ortools,
lazily (D69).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..core.errors import ValidationError

SCALE = 1000  # review rewards are integers in the model


def cp_model():
    """The OR-Tools CP-SAT module, or a clear error naming the optional extra (D69)."""
    try:
        from ortools.sat.python import cp_model as cp
    except ImportError as e:  # never fall back to greedy silently
        raise ValidationError(
            "planner_method 'cpsat'/'hybrid' needs OR-Tools: pip install 'adaptengine[cpsat]' "
            f"(ortools==9.14.6206); import failed: {e}"
        )
    return cp


@dataclass(frozen=True)
class Item:
    token: str
    activity_id: str
    concept: str
    duration: int
    index: int  # position within the concept's workload
    remediation: bool = False


@dataclass(frozen=True)
class Review:
    concept: str
    k: int  # 0 = first review in the chain
    activity_id: str
    duration: int
    urgency: float
    gap: int  # days after the previous practice (finish day or previous review)
    start_offset: Optional[int]  # first review earliest day index if the concept has no work


@dataclass
class Problem:
    items: list[Item]
    by_concept: dict[str, list[int]]  # concept -> item positions in `items`, in order
    prereqs: dict[str, list[str]]  # concept with work -> prerequisites with work
    weights: dict[str, int]  # concept -> descendant count + 1
    reviews: list[Review] = field(default_factory=list)
    review_prereqs: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Solution:
    status: str  # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    item_day: dict[str, int] = field(default_factory=dict)  # token -> day index
    review_day: dict[tuple[str, int], int] = field(default_factory=dict)
    objectives: list = field(default_factory=list)
    best_bound: Optional[float] = None
    work_units: float = 0.0


def solve(
    problem: Problem,
    capacities: list[int],
    cfg,
    *,
    deadline_index: Optional[int],
    with_reviews: bool,
    hint: Optional[dict[str, int]] = None,
    levels: tuple[int, ...] = (1, 2, 3, 4, 5),
) -> Solution:
    """Lexicographic solve over the given objective levels (D67)."""
    cp = cp_model()
    m = cp.CpModel()
    n_days = len(capacities)
    days = range(n_days)
    x, b = {}, {}
    for it in problem.items:
        bits = [m.NewBoolVar(f"b|{it.token}|{d}") for d in days]
        m.AddExactlyOne(bits)
        x[it.token] = m.NewIntVar(0, n_days - 1, f"x|{it.token}")
        m.Add(x[it.token] == sum(d * v for d, v in zip(days, bits)))
        b[it.token] = bits
    first = {c: problem.items[ix[0]].token for c, ix in problem.by_concept.items()}
    last = {c: problem.items[ix[-1]].token for c, ix in problem.by_concept.items()}
    for c, ix in problem.by_concept.items():
        for i, j in zip(ix, ix[1:]):
            m.Add(x[problem.items[i].token] <= x[problem.items[j].token])
        for p in problem.prereqs.get(c, ()):
            m.Add(x[first[c]] >= x[last[p]])
    makespan = m.NewIntVar(0, n_days - 1, "F")
    for t in last.values():
        m.Add(makespan >= x[t])
    if deadline_index is not None:
        m.Add(makespan <= deadline_index)

    z, y, rb, late = {}, {}, {}, {}
    if with_reviews:
        for r in problem.reviews:
            key = (r.concept, r.k)
            z[key] = m.NewBoolVar(f"z|{key}")
            y[key] = m.NewIntVar(0, n_days - 1, f"y|{key}")
            bits = [m.NewBoolVar(f"rb|{key}|{d}") for d in days]
            m.Add(sum(bits) == z[key])
            m.Add(y[key] == sum(d * v for d, v in zip(days, bits))).OnlyEnforceIf(z[key])
            rb[key] = bits
            if r.k == 0:
                if r.concept in last:
                    m.Add(y[key] >= x[last[r.concept]] + r.gap).OnlyEnforceIf(z[key])
                else:
                    m.Add(y[key] >= r.start_offset).OnlyEnforceIf(z[key])
                due = None if r.concept in last else r.start_offset
            else:
                prev = (r.concept, r.k - 1)
                m.AddImplication(z[key], z[prev])
                m.Add(y[key] >= y[prev] + r.gap).OnlyEnforceIf(z[key])
                due = None
            for p in problem.review_prereqs.get(r.concept, ()):  # gated like greedy (W7 D7)
                m.Add(y[key] >= x[last[p]]).OnlyEnforceIf(z[key])
            late[key] = m.NewIntVar(0, n_days, f"late|{key}")
            if due is not None:
                m.Add(late[key] >= y[key] - due).OnlyEnforceIf(z[key])
            elif r.k == 0:
                m.Add(late[key] >= y[key] - x[last[r.concept]] - r.gap).OnlyEnforceIf(z[key])
            else:
                m.Add(late[key] >= y[key] - y[(r.concept, r.k - 1)] - r.gap).OnlyEnforceIf(z[key])
            m.Add(late[key] == 0).OnlyEnforceIf(z[key].Not())

    loads = []
    for d in days:
        load = sum(it.duration * b[it.token][d] for it in problem.items)
        if with_reviews:
            load += sum(r.duration * rb[(r.concept, r.k)][d] for r in problem.reviews)
        m.Add(load <= capacities[d])
        loads.append(load)

    objectives = {
        1: makespan,
        2: sum(x[it.token] for it in problem.items if it.remediation),
        3: sum(problem.weights[c] * x[t] for c, t in last.items()),
        5: None,
    }
    if 5 in levels:
        peak = m.NewIntVar(0, max(capacities, default=0), "peak")
        for load in loads:
            m.Add(peak >= load)
        objectives[5] = peak
    if with_reviews and problem.reviews:
        lam = cfg.cpsat_review_lateness_penalty
        objectives[4] = -sum(
            round(SCALE * r.urgency) * z[(r.concept, r.k)]
            - round(SCALE * lam * r.urgency) * late[(r.concept, r.k)]
            for r in problem.reviews
        )
    if hint:
        for tok, d in sorted(hint.items()):
            if tok in x and 0 <= d < n_days:
                m.AddHint(x[tok], d)

    solver = cp.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = cfg.cpsat_seed
    solver.parameters.max_deterministic_time = cfg.cpsat_max_work_units
    out = Solution(status="UNKNOWN")
    for level in levels:
        expr = objectives.get(level)
        if expr is None or (isinstance(expr, int) and expr == 0):
            continue
        m.Minimize(expr)
        status = solver.Solve(m)
        out.work_units += solver.ResponseProto().deterministic_time
        name = solver.StatusName(status)
        if name in ("INFEASIBLE", "MODEL_INVALID"):
            if not out.item_day:
                out.status = "INFEASIBLE"
            break
        if name not in ("OPTIMAL", "FEASIBLE"):
            if not out.item_day:
                out.status = "UNKNOWN"
                out.best_bound = solver.BestObjectiveBound()
            break
        value = round(solver.ObjectiveValue())
        if level == 1 or not out.item_day:
            out.status = name
            out.best_bound = solver.BestObjectiveBound()
        elif name != "OPTIMAL":
            out.status = "FEASIBLE"
        out.objectives.append({"level": level, "value": value, "status": name})
        out.item_day = {t: solver.Value(v) for t, v in x.items()}
        out.review_day = {k: solver.Value(y[k]) for k in z if solver.Value(z[k])}
        # fix this level (optimal: equal; otherwise: no worse) and hint the next level
        m.Add(expr == value) if name == "OPTIMAL" else m.Add(expr <= value)
        m.ClearHints()
        for t, v in x.items():
            m.AddHint(v, out.item_day[t])
    return out
