"""Pure CP-SAT and hybrid planners (Plan 4, F3, D62-D71).

Both take the workload the shared pipeline computed (D70) and the greedy schedule (hint, upper
bound, and hybrid's first answer), and return the same Plan shape as the greedy path.
"""

from __future__ import annotations

import math
from ..core.schema import ActivityType, Plan, PlanDay, PlanStatus
from ..review.forgetting import urgency_from_recall
from ..learner.state import is_evidence_mastered
from . import cpsat_model as cm
from .cpsat_trace import explain, solve_record
from .difficulty import select_exercise


def _gap(h: float, cfg) -> int:
    """Smallest whole number of days after which recall 2^(-dt/h) < recall_threshold (as greedy)."""
    return math.floor(h * math.log2(1.0 / cfg.recall_threshold)) + 1


def build_problem(graph, activities, state, ctx, workload, model, cfg, review_urgency):
    items, by_concept = [], {}
    for c in graph.topological_order():
        acts = workload.get(c, ())
        for i, a in enumerate(acts):
            rem = (
                i == 0
                and state is not None
                and state.concepts[c].needs_remediation
                and a.type == ActivityType.LESSON
            )
            by_concept.setdefault(c, []).append(len(items))
            items.append(cm.Item(f"{a.activity_id}#{c}#{i}", a.activity_id, c, a.duration, i, rem))
    prereqs = {c: [p for p in graph.prerequisites(c) if p in by_concept] for c in by_concept}
    weights = {c: graph.descendant_count(c) + 1 for c in by_concept}
    problem = cm.Problem(items, by_concept, prereqs, weights)
    if state is None:
        return problem
    for c in sorted(state.concepts):
        uc = state.concepts[c]
        practised = uc.last_practice_day is not None or c in by_concept
        if not practised:
            continue  # D22: never reviewed
        if review_urgency is not None and c in review_urgency:
            if review_urgency[c] <= 0.0:
                continue
            urgency = review_urgency[c]
        else:
            urgency = urgency_from_recall(cfg.recall_threshold, graph.descendant_count(c))
        pre = graph.prerequisites(c)
        if any(
            p not in by_concept and not is_evidence_mastered(state.concepts[p], cfg) for p in pre
        ):
            continue  # gated forever, as greedy's gated() for an unmastered prerequisite
        exs = [
            a
            for a in activities.values()
            if a.target_concept == c and a.type == ActivityType.EXERCISE
        ]
        if not exs:
            continue
        ex = select_exercise(
            sorted(exs, key=lambda a: a.activity_id), uc.p, cfg.target_success, model, cfg
        )
        start = None
        if c not in by_concept:
            start = max(0, uc.last_practice_day + _gap(uc.half_life_days, cfg) - ctx.current_day)
        for k in range(cfg.cpsat_max_reviews_per_concept):
            h = uc.half_life_days * (cfg.half_life_growth**k)
            problem.reviews.append(
                cm.Review(c, k, ex.activity_id, ex.duration, urgency, _gap(h, cfg), start)
            )
        problem.review_prereqs[c] = [p for p in pre if p in by_concept]
    return problem


def _capacities(ctx, n_days, budget=None):
    b = ctx.budget if budget is None else budget
    return [b - ctx.minutes_used_today] + [b] * (n_days - 1)


def _hint(problem, greedy_days, current_day, activities):
    """Greedy's day for each workload token (k-th occurrence of a concept's queue, in order)."""
    pos = {c: 0 for c in problem.by_concept}
    out = {}
    for day in greedy_days:
        for aid in day.activities:
            c = activities[aid].target_concept
            ix = problem.by_concept.get(c, [])
            if pos.get(c, 0) < len(ix) and problem.items[ix[pos[c]]].activity_id == aid:
                out[problem.items[ix[pos[c]]].token] = day.day - current_day
                pos[c] += 1
    return out


def _days(problem, sol, ctx, graph, activities):
    topo = {c: i for i, c in enumerate(graph.topological_order())}
    per_day: dict[int, list] = {}
    for it in problem.items:
        kind = 0 if it.remediation else 2
        per_day.setdefault(sol.item_day[it.token], []).append(
            (topo[it.concept], kind, it.index, it.activity_id)
        )
    for (c, k), d in sol.review_day.items():
        aid = next(r.activity_id for r in problem.reviews if r.concept == c and r.k == k)
        per_day.setdefault(d, []).append((topo[c], 1, -1, aid))
    days = []
    for d in sorted(per_day):
        aids = tuple(x[3] for x in sorted(per_day[d]))
        days.append(PlanDay(ctx.current_day + d, aids, sum(activities[a].duration for a in aids)))
    return tuple(days)


def _review_due(r, sol):
    return r.start_offset if r.k == 0 and r.start_offset is not None else None


def _min_days(problem, ctx, cfg, horizon, hint, budget=None):
    return cm.solve(
        problem,
        _capacities(ctx, horizon, budget),
        cfg,
        deadline_index=None,
        with_reviews=False,
        hint=hint,
        levels=(1,),
    )


def cpsat_plan(
    graph,
    activities,
    state,
    ctx,
    workload,
    init_trace,
    greedy_days,
    greedy_trace,
    model,
    cfg,
    review_urgency,
    *,
    takeover: bool,
) -> Plan:
    """Schedule the workload with CP-SAT (pure mode, or hybrid's takeover when greedy missed)."""
    problem = build_problem(graph, activities, state, ctx, workload, model, cfg, review_urgency)
    hint = (
        _hint(problem, greedy_days, ctx.current_day, activities)
        if cfg.cpsat_use_greedy_hint
        else None
    )
    n_days = ctx.deadline_day - ctx.current_day + 1
    caps = _capacities(ctx, n_days)
    sol = cm.solve(problem, caps, cfg, deadline_index=n_days - 1, with_reviews=True, hint=hint)
    head = list(init_trace) + (_supersede(greedy_trace) if takeover else [])
    mode = {"mode": "hybrid_takeover" if takeover else "cpsat"}
    if sol.status in ("OPTIMAL", "FEASIBLE"):
        trace = head + explain(problem, sol, caps, ctx.current_day, activities, _review_due)
        trace.append(solve_record(sol, cfg, hint is not None, mode))
        return Plan(
            PlanStatus.FEASIBLE,
            _days(problem, sol, ctx, graph, activities),
            f"CPSAT_{sol.status}",
            0,
            (),
            tuple(trace),
        )

    greedy_last = greedy_days[-1].day if greedy_days else ctx.current_day
    if sol.status == "UNKNOWN":  # limit hit without a proof: never a false INFEASIBLE (F3-TC4)
        rec = solve_record(sol, cfg, hint is not None, mode)
        return Plan(
            PlanStatus.UNKNOWN,
            (),
            "CPSAT_LIMIT_REACHED",
            max(0, greedy_last - ctx.deadline_day),
            (),
            tuple(head + [rec]),
        )

    # INFEASIBLE: exact advice (F3-T3)
    horizon = max(greedy_last, ctx.deadline_day) - ctx.current_day + 1
    md = _min_days(problem, ctx, cfg, horizon, hint)
    exact = md.status == "OPTIMAL"
    options, extra = [], {}
    if md.status in ("OPTIMAL", "FEASIBLE"):
        finish = ctx.current_day + md.objectives[0]["value"]
        shortfall = finish - ctx.deadline_day
        options.append(
            f"Extend deadline by {'exactly' if exact else 'at most'} {shortfall} days to day {finish}"
            f" ({'proven minimum' if exact else 'best found'} with CP-SAT)"
        )
        extra["minimum_finish_day"] = finish if exact else None
    else:
        shortfall = max(0, greedy_last - ctx.deadline_day)
    for b in sorted(x for x in cfg.allowed_budgets if x > ctx.budget):
        fit = cm.solve(
            problem,
            _capacities(ctx, n_days, b),
            cfg,
            deadline_index=n_days - 1,
            with_reviews=False,
            hint=hint,
            levels=(1,),
        )
        if fit.status in ("OPTIMAL", "FEASIBLE"):
            options.append(f"Increase daily budget to {b} min (fits by the deadline, CP-SAT)")
            extra["smallest_working_budget"] = b
            break
        if fit.status == "UNKNOWN":
            break  # no proof for this budget: stop rather than skip to a larger one
    extra["shortfall_exact"] = exact
    rec = solve_record(sol, cfg, hint is not None, {**mode, **extra})
    return Plan(
        PlanStatus.INFEASIBLE,
        (),
        "CPSAT_INFEASIBLE",
        shortfall,
        tuple(options),
        tuple(head + [rec]),
    )


def cpsat_best_effort(graph, activities, state, ctx, workload, model, cfg):
    """D42 with CP-SAT: the target's fastest schedule (no deadline), truncated at the deadline."""
    problem = build_problem(graph, activities, None, ctx, workload, model, cfg, None)
    horizon = max(ctx.deadline_day, ctx.current_day) - ctx.current_day + 1
    total = sum(it.duration for it in problem.items)
    horizon = max(horizon, math.ceil(total / max(1, ctx.budget)) + len(problem.items) + 1)
    sol = _min_days(problem, ctx, cfg, horizon, None)
    if sol.status not in ("OPTIMAL", "FEASIBLE"):
        return (), []
    days = tuple(
        d for d in _days(problem, sol, ctx, graph, activities) if d.day <= ctx.deadline_day
    )
    caps = _capacities(ctx, horizon)
    recs = [
        r
        for r in explain(problem, sol, caps, ctx.current_day, activities, _review_due)
        if r.get("day") is None or r["day"] <= ctx.deadline_day
    ]
    return days, recs


def _supersede(greedy_trace) -> list:
    from .plan import _supersede as sup

    return sup(greedy_trace)
