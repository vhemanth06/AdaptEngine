"""Post-solve explanations for CP-SAT plans (Plan 4, F3.5, D71).

Records use greedy's keys (decision, activity_id, target_concept, day, duration, reason), so the
"Why?" panel, the API and the one-record-per-activity audit (TC7.1) work unchanged. They describe
the final schedule, checked against its constraints; they are not the solver's search.
"""

from __future__ import annotations


def explain(problem, sol, capacities, current_day, activities, review_due) -> list[dict]:
    """One SELECTED record per scheduled item and review, plus REVIEW_DROPPED records."""
    load = [0] * len(capacities)
    for it in problem.items:
        load[sol.item_day[it.token]] += it.duration
    for (c, k), d in sol.review_day.items():
        load[d] += next(r.duration for r in problem.reviews if r.concept == c and r.k == k)
    last = {c: problem.items[ix[-1]].token for c, ix in problem.by_concept.items()}
    out: list[dict] = []
    for c, ix in problem.by_concept.items():
        for pos, i in enumerate(ix):
            it = problem.items[i]
            day = sol.item_day[it.token]
            earliest, because = 0, "PLAN_START"
            if pos:
                prev = sol.item_day[problem.items[ix[pos - 1]].token]
                if prev > earliest:
                    earliest, because = prev, "PREVIOUS_ITEM_OF_CONCEPT"
            for p in problem.prereqs.get(c, ()):
                pd = sol.item_day[last[p]]
                if pd > earliest:
                    earliest, because = pd, f"PREREQUISITE_{p}_FINISHES"
            rec = {
                "decision": "SELECTED",
                "activity_id": it.activity_id,
                "target_concept": c,
                "day": current_day + day,
                "duration": it.duration,
                "reason": "REMEDIATION_INSERTED" if it.remediation else "CPSAT_ASSIGNED",
                "earliest_possible_day": current_day + earliest,
                "earliest_because": because,
            }
            if day == earliest:
                rec["placement"] = "AT_EARLIEST"
            elif all(capacities[d] - load[d] < it.duration for d in range(earliest, day)):
                rec["placement"] = "BUDGET_FULL"
                rec["full_days"] = [current_day + earliest, current_day + day - 1]
            else:
                rec["placement"] = "OBJECTIVE_TRADEOFF"  # moved by objective levels 3-5
            out.append(rec)
    for r in problem.reviews:
        key = (r.concept, r.k)
        if key in sol.review_day:
            d = sol.review_day[key]
            out.append(
                {
                    "decision": "SELECTED",
                    "activity_id": r.activity_id,
                    "target_concept": r.concept,
                    "day": current_day + d,
                    "duration": r.duration,
                    "reason": "REVIEW_SCHEDULED",
                    "review_number": r.k + 1,
                }
            )
        elif r.k == 0:
            due = review_due(r, sol)
            out.append(
                {
                    "decision": "REVIEW_DROPPED",
                    "concept_id": r.concept,
                    "due_day": None if due is None else current_day + due,
                    "reason": "DUE_AFTER_HORIZON"
                    if due is None or due >= len(capacities)
                    else "NOT_SCHEDULED_WITHIN_BUDGET",
                }
            )
    return out


def solve_record(sol, cfg, hint_used: bool, extra: dict) -> dict:
    return {
        "decision": "CPSAT_SOLVE",
        "reason": f"CPSAT_{sol.status}",
        "status": sol.status,
        "objectives": sol.objectives,
        "best_bound": sol.best_bound,
        "work_units": round(sol.work_units, 6),
        "seed": cfg.cpsat_seed,
        "hint_used": hint_used,
        **extra,
    }
