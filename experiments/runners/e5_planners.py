"""E5 — Planners (report 5.5).

When does CP-SAT change outcomes, verdicts or advice compared with greedy, and at what planning
time? Arms (no diagnostic, closed loop): planner_method greedy, hybrid, cpsat (frozen: 10 work
units, seed 0, greedy hint, at most 3 reviews per concept, lateness penalty 0.1).
- greedy and hybrid: worlds S0-S4 x 4-node, 8-node, 8node_x10, synth-20 x budgets 5/10/15/30 x the
  8 scenarios, N = 200. E5 computes its own greedy cells: reuse of E1's adapt cells needed the
  code hash to show the code was the same, and was removed with it (D104; see NOTES.md).
- pure CP-SAT: 4-node, 8-node, 8node_x10; budgets 10 and 15; calm, missed_day, deadline_cut.
- with confirmation checks: each planner with bisection_config() (diagnostic first), worlds S0
  and S4, 8-node and 8node_x10, calm, budget 15.
- shortfall probe: cold-start plans at deadlines shorter than needed, per planner.
Latency (planning time, not deterministic) goes to E5_latency.json next to the results.

    python -m experiments.runners.e5_planners [--smoke] [--procs N] [--out PATH]
"""

from __future__ import annotations

import os
import statistics
import time
from dataclasses import replace

from adaptengine.core.config import DEFAULT_CONFIG
from adaptengine.core.schema import ActivityType, Event, EventType, PlanContext
from adaptengine.learner.state import ExecutionLog

from ..core import curricula as C
from ..core import metrics as M
from ..core.arms import E5_ARMS, E5_CONFIRM_ARMS, PLANNERS, Arm
from ..core.episode import first_plan, plan_summary, run_episode
from ..core.parallel import pmap
from ..core.results import Run, validate, write
from ..core.scenarios import BUDGETS, SCENARIOS, applies, horizon, make_scenario, profile_for
from ..core.simulator import WORLDS, make_learner
from . import common

EXP, NAME = "E5", "E5_planners"
CURRICULA = ("4-node", "8-node", "8node_x10", "synth-20")
PURE = {
    "curricula": ("4-node", "8-node", "8node_x10"),
    "budgets": (10, 15),
    "scenarios": ("calm", "missed_day", "deadline_cut"),
}
CONFIRM = {
    "worlds": ("S0", "S4"),
    "curricula": ("8-node", "8node_x10"),
    "budget": 15,
    "scenario": "calm",
}
# hybrid on synth-20 only here: measured 10-360 s per episode elsewhere (about 36 h on 15 workers)
HYBRID_SYNTH = {"curricula": ("synth-20",), "budgets": (15, 30), "scenarios": ("calm",)}
LATENCY_CURRICULA = ("4-node", "8-node", "8node_x10", "synth-20", "synth-50")
EVENTS = ("missed_day", "wrong_answer", "deadline_change", "budget_change")
REPS = 30


def in_pure(cur, budget, scen) -> bool:
    return cur in PURE["curricula"] and budget in PURE["budgets"] and scen in PURE["scenarios"]


def in_hybrid(cur, budget, scen) -> bool:
    h = HYBRID_SYNTH
    if cur not in h["curricula"]:
        return True
    return budget in h["budgets"] and scen in h["scenarios"]


def grid(smoke: bool) -> list:
    if smoke:
        return [("S0", "4-node", 15, "calm", p, False) for p in PLANNERS] + [
            ("S0", "8-node", 15, "calm", p, True) for p in PLANNERS
        ]
    units = []
    for w in WORLDS:
        for c in CURRICULA:
            for b in BUDGETS:
                for s in SCENARIOS:
                    if applies(s, b) and in_hybrid(c, b, s):
                        for p in PLANNERS:
                            if p != "cpsat" or in_pure(c, b, s):
                                units.append((w, c, b, s, p, False))
    for w in CONFIRM["worlds"]:
        for c in CONFIRM["curricula"]:
            for p in PLANNERS:
                units.append((w, c, CONFIRM["budget"], CONFIRM["scenario"], p, True))
    return units


def arm_of(planner: str, confirm: bool) -> Arm:
    return E5_CONFIRM_ARMS[f"{planner}_bisect_confirm"] if confirm else E5_ARMS[planner]


def run_unit(unit) -> dict:
    (world, cur, budget, scen, planner, confirm), seeds = unit
    base = C.engine(cur)
    sc = make_scenario(scen, base, C.goal_of(base), budget)
    arm = arm_of(planner, confirm)
    e = C.engine(cur, arm.config())
    fp = None if confirm else first_plan(e, e.init_learner(), sc)
    rows = [run_episode(e, s, sc, arm, world, profile_for(scen), first=fp) for s in seeds]
    entry = common.arm_entry(rows)
    entry["metrics"].pop("attempt_histogram")
    return entry


def agreement(arms: dict) -> dict:
    st = {p: arms[p]["per_learner"]["first_status"] for p in arms}
    out = {}
    for p in arms:
        if p != "greedy":
            same = [a == b for a, b in zip(st[p], st["greedy"])]
            out[f"{p}_vs_greedy"] = round(sum(same) / len(same), 4)
    out["unknown_rate"] = {
        p: round(sum(s == "UNKNOWN" for s in v) / len(v), 4) for p, v in st.items()
    }
    return out


def assemble(units, entries, reused_keys) -> list:
    cells: dict = {}
    for (w, c, b, s, p, conf), entry in zip(units, entries):
        k = (w, c, b, s, conf)
        cell = cells.setdefault(
            k,
            {
                "key": {
                    "world": w,
                    "curriculum": c,
                    "budget": b,
                    "scenario": s,
                    "confirmation": conf,
                },
                "arms": {},
            },
        )
        cell["arms"][p] = entry
    out = []
    for k, cell in cells.items():
        arms = cell["arms"]
        base = C.engine(k[1])
        cell["key"]["deadline"] = make_scenario(k[3], base, C.goal_of(base), k[2]).deadline
        cell["key"]["greedy_reused_from_E1"] = k in reused_keys
        cell["contrasts"] = {
            f"{p}_minus_greedy": common.contrast(arms[p], arms["greedy"])
            for p in arms
            if p != "greedy"
        }
        cell["contrasts"]["first_plan_agreement"] = agreement(arms)
        out.append(cell)
    return out


def shortfall_probe(smoke: bool) -> list:
    """Cold-start plans at deadlines shorter than the calm horizon needs: greedy's bound-based or
    greedy-overshoot shortfall vs CP-SAT's exact shortfall (and hybrid's)."""
    rows = []
    curricula = ("4-node",) if smoke else CURRICULA
    for cur in curricula:
        base = C.engine(cur)
        goal = C.goal_of(base)
        for b in (15,) if smoke else (10, 15):
            need = horizon(base, goal, b) - 2
            for dl in sorted({max(1, need - 1), max(1, need - 2), max(1, (need + 1) // 2)}):
                row = {"curriculum": cur, "budget": b, "needed_days": need, "deadline": dl}
                for p in PLANNERS:
                    e = C.engine(cur, replace(DEFAULT_CONFIG, planner_method=p))
                    plan = e.plan(
                        e.init_learner(), PlanContext(goal=goal, deadline_day=dl, budget=b)
                    )
                    row[p] = {**plan_summary(plan), "options": list(plan.options)}
                rows.append(row)
    return rows


def _ci(c):
    return f"{c['diff']:+.4f} [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]"


def _lab(c):
    k = c["key"]
    return f"{k['world']}|{k['curriculum']}|B{k['budget']}|{k['scenario']}" + (
        "|confirm" if k["confirmation"] else ""
    )


def hypotheses(cells: list) -> dict:
    ex = sum(a["metrics"]["executed_prereq_violations"] for c in cells for a in c["arms"].values())
    pl = sum(a["metrics"]["plan_level_violations"] for c in cells for a in c["arms"].values())
    plans = sum(a["metrics"]["plan_checks"]["plans"] for c in cells for a in c["arms"].values())
    n_feas = n_unk = 0
    bad2 = []
    for c in cells:
        g = c["arms"]["greedy"]["per_learner"]["first_status"]
        h = c["arms"]["hybrid"]["per_learner"]["first_status"]
        for a, b in zip(g, h):
            if a == "FEASIBLE":
                n_feas += 1
                if b != "FEASIBLE":
                    bad2.append(_lab(c))
            elif a == "UNKNOWN":
                n_unk += 1
                if b not in ("FEASIBLE", "INFEASIBLE"):
                    bad2.append(_lab(c))
    h3 = [
        c
        for c in cells
        if all(s == "FEASIBLE" for s in c["arms"]["greedy"]["per_learner"]["first_status"])
    ]
    bad3 = [
        c
        for c in h3
        if M.direction(c["contrasts"]["hybrid_minus_greedy"]["goal_mastered"]) != "no_difference"
    ]
    return {
        "H1": {
            "held": ex == 0,
            "evidence": f"executed violations, all planners, {len(cells)} cells: {ex}",
        },
        "H2": {
            "held": not bad2,
            "evidence": f"learner first plans with greedy FEASIBLE: {n_feas}, greedy UNKNOWN: {n_unk}; mismatches in: "
            + (", ".join(sorted(set(bad2))) or "none"),
        },
        "H3": {
            "held": not bad3,
            "evidence": f"{len(h3)} cells with every greedy first plan FEASIBLE; hybrid-greedy goal-mastery CI excludes 0 in: "
            + (
                ", ".join(
                    f"{_lab(c)} {_ci(c['contrasts']['hybrid_minus_greedy']['goal_mastered'])}"
                    for c in bad3
                )
                or "none"
            ),
        },
        "H4": {
            "held": pl == 0,
            "evidence": f"plan-level violations, all planners: {pl} over {plans} plans checked",
        },
        "cpsat": {
            "held": None,
            "evidence": "descriptive (no direction predicted); losing cells listed in cpsat_losses",
        },
    }


def cpsat_losses(cells: list) -> list:
    out = []
    for c in cells:
        d = c["contrasts"].get("cpsat_minus_greedy")
        if not d:
            continue
        lost = [k for k in ("goal_mastered", "all_required") if d[k]["ci95"][1] < 0]
        if d["minutes"]["ci95"][0] > 0:
            lost.append("minutes")
        if lost:
            out.append({"cell": _lab(c), "lost_on": lost, **d})
    return out


# ---------------------------------------------------------------- latency (timing, separate file)


def _time(fn, reps: int) -> dict:
    fn()  # untimed warm-up
    ts = []
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t)
    return {
        "mean_s": round(statistics.mean(ts), 5),
        "sd_s": round(statistics.pstdev(ts), 5),
        "median_s": round(statistics.median(ts), 5),
        "max_s": round(max(ts), 5),
    }


def mid_plan_state(cur: str):
    """Day 2 state after day 1's work by seed 1000 in S0 under the greedy closed loop."""
    g = C.engine(cur)
    goal = C.goal_of(g)
    dl = horizon(g, goal, 15)
    sim = make_learner(g, 1000, "S0")
    state, log, used = g.init_learner(), ExecutionLog(), 0
    while True:
        today, _ = g.next_activities(state, log, PlanContext(goal=goal, deadline_day=dl, budget=15))
        if today is None:
            break
        wrong = False
        for aid in today.activities:
            a = g.activities[aid]
            if used + a.duration > 15:
                break
            y = (
                sim.respond(a.target_concept, aid, a.difficulty)
                if a.type == ActivityType.EXERCISE
                else None
            )
            state, log = g.record(
                state,
                log,
                Event(
                    day=1,
                    kind=EventType.COMPLETED,
                    activity_id=aid,
                    minutes_elapsed=a.duration,
                    correct=y,
                ),
            )
            sim.learn(a.target_concept, a.type == ActivityType.LESSON, 1)
            used += a.duration
            if y is False:
                wrong = True
                break
        if not wrong:
            break
    return goal, dl, state, log


def latency(smoke: bool) -> list:
    reps = 2 if smoke else REPS
    curricula = ("4-node",) if smoke else LATENCY_CURRICULA
    rows = []
    for cur in curricula:
        base = C.engine(cur)
        goal = C.goal_of(base)
        dl = horizon(base, goal, 15)
        _, _, st, log = mid_plan_state(cur)
        # the wrong answer: the first exercise of greedy's day-2 slice
        today, _ = base.next_activities(
            st, log, PlanContext(goal=goal, deadline_day=dl, budget=15, current_day=2)
        )
        ex = next(
            (
                x
                for x in (today.activities if today else ())
                if base.activities[x].type == ActivityType.EXERCISE
            ),
            None,
        )
        ex = ex or next(
            a.activity_id for a in base.activities.values() if a.type == ActivityType.EXERCISE
        )
        events = {
            "missed_day": Event(day=2, kind=EventType.MISSED),
            "wrong_answer": Event(
                day=2,
                kind=EventType.COMPLETED,
                activity_id=ex,
                minutes_elapsed=base.activities[ex].duration,
                correct=False,
            ),
            "deadline_change": Event(day=2, kind=EventType.DEADLINE_CHANGED, value=dl - 1),
            "budget_change": Event(day=2, kind=EventType.BUDGET_CHANGED, value=10),
        }
        for p in PLANNERS:
            e = C.engine(cur, replace(DEFAULT_CONFIG, planner_method=p))
            ctx = PlanContext(goal=goal, deadline_day=dl, budget=15)
            rows.append(
                {
                    "key": {
                        "kind": "cold_start",
                        "curriculum": cur,
                        "planner": p,
                        "budget": 15,
                        "deadline": dl,
                    },
                    "arms": {
                        p: {
                            "n": reps,
                            "metrics": _time(lambda: e.plan(e.init_learner(), ctx), reps),
                        }
                    },
                }
            )
            for ev_name, ev in events.items():
                s2, l2 = e.record(st, log, ev)
                ctx2 = PlanContext(goal=goal, deadline_day=dl, budget=15, current_day=2)
                rows.append(
                    {
                        "key": {
                            "kind": "replan",
                            "curriculum": cur,
                            "planner": p,
                            "event": ev_name,
                            "budget": 15,
                            "deadline": dl,
                        },
                        "arms": {
                            p: {"n": reps, "metrics": _time(lambda: e.replan(s2, l2, ctx2), reps)}
                        },
                    }
                )
    return rows


def main(argv=None) -> dict:
    args = common.parse(EXP, argv)
    run, out = common.start(EXP, NAME, args)
    for c in CURRICULA + LATENCY_CURRICULA:
        C.paths(c)
    seeds = common.SMOKE_EPISODE_SEEDS if args.smoke else common.EPISODE_SEEDS
    units = grid(args.smoke)
    done = dict(zip(units, pmap(run_unit, [(u, seeds) for u in units], args.procs)))
    reused: dict = {}
    cells = assemble(units, [done[u] for u in units], set())
    design = {
        "question": "When does CP-SAT change outcomes, verdicts or advice compared with greedy, and at what planning time?",
        "arms": {n: a.describe() for n, a in {**E5_ARMS, **E5_CONFIRM_ARMS}.items()},
        "cpsat_frozen": {
            k: getattr(DEFAULT_CONFIG, k)
            for k in (
                "cpsat_max_work_units",
                "cpsat_seed",
                "cpsat_use_greedy_hint",
                "cpsat_max_reviews_per_concept",
                "cpsat_review_lateness_penalty",
            )
        },
        "worlds": list(WORLDS),
        "curricula": list(CURRICULA),
        "budgets": list(BUDGETS),
        "scenarios": list(SCENARIOS),
        "pure_cpsat_subset": {k: list(v) for k, v in PURE.items()},
        "hybrid_synth20_subset": {k: list(v) for k, v in HYBRID_SYNTH.items()},
        "confirmation_cells": {
            k: (list(v) if isinstance(v, tuple) else v) for k, v in CONFIRM.items()
        },
        "greedy_reuse": "none: E5 computes its own greedy cells (E1 reuse removed with the code hash, D104)",
        "seeds": {"episodes": [1000, 1199]} if not args.smoke else {"episodes": list(seeds)},
    }
    doc = common.finish(
        run,
        out,
        design=design,
        content_review={c: C.content_review(c) for c in CURRICULA},
        cells=cells,
        hypotheses=hypotheses(cells),
        reused=reused,
        shortfall_probe=shortfall_probe(args.smoke),
        cpsat_losses=cpsat_losses(cells),
    )
    lat_run = Run("E5_latency", run.prereg, 1)
    load_before = os.getloadavg()
    lat = latency(args.smoke)
    load_after = os.getloadavg()
    lat_doc = lat_run.finish(
        design={
            "label": "timing (not deterministic)",
            "reps": 2 if args.smoke else REPS,
            "budget": 15,
            "curricula": list(LATENCY_CURRICULA),
            "events": list(EVENTS),
            "replan_state": "day 2 after day 1's work by seed 1000 in S0 (greedy closed loop)",
            "seeds": {"replan_state": 1000},
            "workers": 1,
            "load_average_1_5_15": {
                "before": [round(x, 2) for x in load_before],
                "after": [round(x, 2) for x in load_after],
            },
        },
        content_review={c: C.content_review(c) for c in LATENCY_CURRICULA},
        cells=lat,
        hypotheses={},
    )
    validate(lat_doc)
    write(lat_doc, os.path.join(os.path.dirname(out), "E5_latency.json"))
    return doc


if __name__ == "__main__":
    main()
