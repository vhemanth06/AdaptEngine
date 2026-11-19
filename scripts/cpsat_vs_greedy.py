#!/usr/bin/env python3
"""Exploratory (not pre-registered): greedy (+ B&B oracle) vs CP-SAT scheduling on tight deadlines.

  .venv/bin/python scripts/cpsat_vs_greedy.py [--smoke]

Lives in scripts/ and writes experiments/results/cpsat_vs_greedy.json, so the PRODUCT_RERUN
experiment_hash (experiments/**/*.py) is unchanged.

Engine: the product engine (fitted_S1, PRODUCT_OVERRIDES) with maintenance_reviews off, as the web app.
Arms:   greedy  = scheduler "greedy" (greedy packing; B&B oracle with node limit 1000 when greedy
                  misses the deadline)
        cpsat   = scheduler "cpsat" (exact CP-SAT packing, 5 s limit; falls back to greedy if undecided)
        hybrid  = the web app: greedy, re-run with cpsat only when greedy returns UNKNOWN (derived)
Cases:  curriculum x goal x budget {5,10,15,30} x learner state (fresh + seeded partial states).
        L = greedy's last day under a 1000-day deadline. Instances are the deadlines d = L, L-1, ...
        down to the first d both arms reject by the time-budget bound (the contested window).
Per instance: status, reason, last plan day, wall ms (one timed run after a per-engine warm-up),
validate_proposal violations of every FEASIBLE plan, and the CP-SAT solver's own verdict. The engine
discards a CP-SAT INFEASIBLE proof (falls back to greedy + oracle, src/adaptengine/planner/plan.py), so
the verdict is recorded by wrapping cpsat.solve_cpsat in this script; engine code is not changed.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
from dataclasses import replace

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from adaptengine.core.schema import PlanContext  # noqa: E402
from adaptengine.planner import cpsat  # noqa: E402
from adaptengine.planner.validate_proposal import validate_proposal  # noqa: E402
from experiments.common import goal_of, product_engine, write_result  # noqa: E402

BUDGETS = (5, 10, 15, 30)
FAR = 1000
SEED = 20261115
_VERDICT: dict = {}
_solve = cpsat.solve_cpsat


def _spy(*a, **k):
    status, assignment, info = _solve(*a, **k)
    _VERDICT.update(status=status.value, solver_s=info.get("wall_s"))
    return status, assignment, info


cpsat.solve_cpsat = _spy  # _cpsat_plan looks it up on the module at call time


def states(e, n_partial, rng):
    """Fresh learner + n_partial seeded partial-knowledge states (30% mastered, 30% partly known)."""
    out = [("fresh", e.init_learner())]
    for k in range(n_partial):
        cs = dict(e.init_learner().concepts)
        for c in e.graph.concepts():
            r = rng.random()
            if r < 0.3:
                cs[c] = replace(cs[c], p=0.97, responses=3, correct_responses=3, correct_streak=3)
            elif r < 0.6:
                cs[c] = replace(cs[c], p=round(rng.uniform(0.2, 0.9), 3))
        out.append((f"partial{k}", replace(e.init_learner(), concepts=cs)))
    return out


def run_arm(e, state, ctx):
    _VERDICT.clear()
    t = time.perf_counter()
    p = e.plan(state, ctx)
    ms = (time.perf_counter() - t) * 1000.0
    feasible = p.status.value == "FEASIBLE"
    bad = (
        validate_proposal(e.graph, e.activities, state, ctx, p.days, model=e.model, cfg=e.config)
        if feasible and p.days
        else []
    )
    return {
        "status": p.status.value,
        "reason": p.reason,
        "last_day": p.days[-1].day if feasible and p.days else None,
        "ms": round(ms, 3),
        "violations": [b["rule"] for b in bad],
        "cpsat_verdict": _VERDICT.get("status"),  # None = solver not called (bound check / greedy arm)
        "cpsat_solver_s": _VERDICT.get("solver_s"),
    }


def bound_rejected(r):
    return r["status"] == "INFEASIBLE" and r["reason"] == "INSUFFICIENT_TIME_BUDGET"


def run(curricula, goals_per_synth, n_partial):
    rng = random.Random(SEED)
    rows = []
    for cur in curricula:
        g = product_engine(cur, maintenance_reviews=False)
        c = product_engine(cur, maintenance_reviews=False, scheduler="cpsat")
        concepts = list(g.graph.concepts())
        if cur.startswith("synth-"):
            goals = [goal_of(g)] + rng.sample([x for x in concepts if x != goal_of(g)], goals_per_synth - 1)
        else:
            goals = concepts
        warm = PlanContext(goal=goals[0], deadline_day=FAR, budget=BUDGETS[-1])
        g.plan(g.init_learner(), warm), c.plan(c.init_learner(), warm)  # warm-up (imports, caches)
        for sname, s in states(g, n_partial, rng):
            for goal in goals:
                for b in BUDGETS:
                    far = g.plan(s, PlanContext(goal=goal, deadline_day=FAR, budget=b))
                    if far.status.value != "FEASIBLE" or not far.days or far.reason == "GOAL_ALREADY_MASTERED":
                        continue
                    L = far.days[-1].day
                    for d in range(L, 0, -1):
                        ctx = PlanContext(goal=goal, deadline_day=d, budget=b)
                        rg, rc = run_arm(g, s, ctx), run_arm(c, s, ctx)
                        if bound_rejected(rg) and bound_rejected(rc):
                            break
                        rows.append(
                            {"curriculum": cur, "state": sname, "goal": goal, "budget": b,
                             "deadline": d, "L": L, "greedy": rg, "cpsat": rc}  # fmt: skip
                        )
        print(f"{cur}: {sum(r['curriculum'] == cur for r in rows)} instances", flush=True)
    return rows


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 2) if xs else None


def summarize(rows):
    out = {}
    for cur in sorted({r["curriculum"] for r in rows}):
        rs = [r for r in rows if r["curriculum"] == cur]
        hyb = [r["cpsat"] if r["greedy"]["status"] == "UNKNOWN" else r["greedy"] for r in rs]
        hyb_ms = [
            r["greedy"]["ms"] + (r["cpsat"]["ms"] if r["greedy"]["status"] == "UNKNOWN" else 0) for r in rs
        ]

        def outcomes(arm):
            res = [r[arm] for r in rs] if arm != "hybrid" else hyb
            return {k: sum(x["status"] == k for x in res) for k in ("FEASIBLE", "INFEASIBLE", "UNKNOWN")}

        def lat(ms):
            return {"median": pct(ms, 0.5), "p95": pct(ms, 0.95), "max": round(max(ms), 2)}

        # shortest feasible deadline per case (state, goal, budget)
        cases = {}
        for r in rs:
            k = (r["state"], r["goal"], r["budget"])
            for arm in ("greedy", "cpsat"):
                if r[arm]["status"] == "FEASIBLE":
                    cases.setdefault(k, {}).setdefault(arm, r["deadline"])
                    cases[k][arm] = min(cases[k][arm], r["deadline"])
        both = [v for v in cases.values() if "greedy" in v and "cpsat" in v]
        saved = [v["greedy"] - v["cpsat"] for v in both]
        same_d = [r for r in rs if r["greedy"]["status"] == r["cpsat"]["status"] == "FEASIBLE"]
        out[cur] = {
            "instances": len(rs),
            "cases": len(cases),
            "outcomes": {a: outcomes(a) for a in ("greedy", "cpsat", "hybrid")},
            "cpsat_rescues": sum(r["greedy"]["status"] != "FEASIBLE" and r["cpsat"]["status"] == "FEASIBLE" for r in rs),
            "cpsat_losses": sum(r["greedy"]["status"] == "FEASIBLE" and r["cpsat"]["status"] != "FEASIBLE" for r in rs),
            "cpsat_solver_verdicts": {
                k: sum(r["cpsat"]["cpsat_verdict"] == k for r in rs) for k in ("FEASIBLE", "INFEASIBLE", "UNKNOWN")
            },
            "greedy_unknown_cpsat_verdict": {
                k: sum(r["greedy"]["status"] == "UNKNOWN" and r["cpsat"]["cpsat_verdict"] == k for r in rs)
                for k in ("FEASIBLE", "INFEASIBLE", "UNKNOWN")
            },
            "shortest_deadline_days_saved": {
                "cases": len(both),
                "cases_cpsat_shorter": sum(x > 0 for x in saved),
                "mean": round(statistics.mean(saved), 3) if saved else None,
                "max": max(saved) if saved else None,
            },
            "same_deadline_both_feasible": {
                "instances": len(same_d),
                "mean_last_day_greedy": round(statistics.mean(r["greedy"]["last_day"] for r in same_d), 3) if same_d else None,
                "mean_last_day_cpsat": round(statistics.mean(r["cpsat"]["last_day"] for r in same_d), 3) if same_d else None,
            },
            "latency_ms": {
                "greedy": lat([r["greedy"]["ms"] for r in rs]),
                "cpsat": lat([r["cpsat"]["ms"] for r in rs]),
                "hybrid": lat(hyb_ms),
            },
            "violations": {a: sum(len(r[a]["violations"]) for r in rs) for a in ("greedy", "cpsat")},
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    if not cpsat.available():
        raise SystemExit("ortools is not importable (pip install -e '.[solver]')")
    import ortools

    curricula = ("4node_x10",) if a.smoke else ("4node_x10", "8node_x10", "synth-20-x10")
    t0 = time.perf_counter()
    rows = run(curricula, goals_per_synth=2 if a.smoke else 4, n_partial=1 if a.smoke else 3)
    payload = {
        "design": __doc__.strip(),
        "pre_registered": False,
        "ortools": ortools.__version__,
        "seed": SEED,
        "wall_s": round(time.perf_counter() - t0, 1),
        "summary": summarize(rows),
        "rows": rows,
    }
    path = write_result("cpsat_vs_greedy_smoke" if a.smoke else "cpsat_vs_greedy", payload)
    print(json.dumps(payload["summary"], indent=1))
    print("wrote", path)
    return payload


if __name__ == "__main__":
    main()
