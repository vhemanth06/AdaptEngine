"""Choose the demo preset (Plan FE, FE-T3, D94) by the fixed procedure of §FE.6.

Not imported by the app. Every check goes through the API's TestClient, so it checks exactly what
the UI does. Run from the repo root:

    .venv/bin/python -m frontend.api.select_demo_preset

It prints a JSON record: the chosen candidate, its numbers, and every candidate rejected before it
with the first failing criterion. Its values are then written into frontend/api/demo.py by hand.
tests in frontend/api/tests/test_health_preset.py::test_demo_preset re-run `evaluate` on the stored values.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

KNOWN_SETS = (("C1", "C2", "C3", "C6"), ("C1", "C2", "C3", "C5", "C6"), ("C1", "C2", "C3"))
MODELS = ("fitted_assist09", "heuristic", "fitted_ct")
DEADLINES = (10, 14, 21)
BUDGETS = (10, 15, 30)
FIXED = {
    "curriculum": "8node_x10",
    "goal": "C8",
    "diagnostic_method": "bisection",
    "planner_method": "cpsat",
}


def _ok(r):
    assert r.status_code == 200, r.text
    return r.json()


def new_session(client, model, deadline, budget, **switches):
    body = {**FIXED, "model_profile": model, "deadline_day": deadline, "budget": budget, **switches}
    return _ok(client.post("/api/sessions", json=body))


def run_diagnostic(client, sid, known):
    """The scripted demo learner: right exactly on its known concepts (D94)."""
    view = _ok(client.get(f"/api/sessions/{sid}"))
    while not view["diagnostic"]["done"]:
        item = view["diagnostic"]["next_item"]
        body = {"activity_id": item["activity_id"], "correct": item["concept_id"] in known}
        view = _ok(client.post(f"/api/sessions/{sid}/diagnostic/answer", json=body))
    return view


def check_activities(plan) -> dict:
    """activity id -> concept for every confirmation check in the plan's trace."""
    return {
        a: r["concept_id"]
        for r in plan["trace"]
        if r.get("decision") == "CONFIRMATION"
        for a in r["activity_ids"]
    }


def tight_variant(client, sid, deadline, budget, allowed):
    """§FE.6 criterion 5 on the Setup session (before the diagnostic, as walkthrough step 1):
    the first variant whose plan is INFEASIBLE with CPSAT_INFEASIBLE and an option; then back to
    the preset must be FEASIBLE again ("then feasible again")."""
    tries = [(deadline, b) for b in sorted((b for b in allowed if b < budget), reverse=True)]
    tries += [(d, budget) for d in (deadline - 3, deadline - 5) if d >= 1]
    found = None
    for d, b in tries:
        plan = _ok(client.post(f"/api/sessions/{sid}/plan", json={"deadline_day": d, "budget": b}))[
            "plan"
        ]
        if (
            plan["status"] == "INFEASIBLE"
            and plan["reason"] == "CPSAT_INFEASIBLE"
            and plan["options"]
        ):
            found = {"deadline_day": d, "budget": b, "options": plan["options"]}
            break
    back = _ok(
        client.post(f"/api/sessions/{sid}/plan", json={"deadline_day": deadline, "budget": budget})
    )["plan"]
    return found, back["status"]


def study_wrong_on(client, sid, known, target, max_steps=40):
    """Walkthrough step 5: do today's work (lessons done, exercises answered as the scripted
    learner) until the current card is `target`, then answer it wrong."""
    view = _ok(client.get(f"/api/sessions/{sid}"))
    for _ in range(max_steps):
        if not view["today"] or not view["today"]["activities"]:
            return None
        aid = view["today"]["activities"][0]
        checks = check_activities(view["plan"])
        body = {"kind": "COMPLETED", "activity_id": aid}
        if aid == target:
            body["correct"] = False
            res = _ok(client.post(f"/api/sessions/{sid}/events", json=body))
            c = checks.get(aid, aid.split("-")[1])
            after = {x["concept_id"]: x for x in res["session"]["concepts"]}[c]
            return {
                "activity_id": aid,
                "concept_id": c,
                "changes": len(res["changes"]),
                "diag_confident_after": after["diag_confident"],
                "confirmed_after": after["confirmed"],
            }
        if aid.startswith("E-"):
            body["correct"] = aid.split("-")[1] in known
        view = _ok(client.post(f"/api/sessions/{sid}/events", json=body))["session"]
    return None


def prepared_session(client, model, deadline, budget, known):
    """A Setup session planned once, then diagnosed by the scripted learner (walkthrough 1-2)."""
    sid = new_session(client, model, deadline, budget)["session_id"]
    _ok(client.post(f"/api/sessions/{sid}/plan", json={}))
    run_diagnostic(client, sid, known)
    return sid


def wrong_check_outcomes(client, model, deadline, budget, known, today_checks):
    """Step 5 per check in today's order, each on a fresh prepared session. The walkthrough uses
    the first check whose wrong answer replans and does not confirm the concept anyway (a wrong
    answer on a near-certain concept can still pass the epsilon test)."""
    outcomes = [
        study_wrong_on(client, prepared_session(client, model, deadline, budget, known), known, a)
        for a in today_checks
    ]
    usable = [o for o in outcomes if o and o["changes"] > 0 and not o["confirmed_after"]]
    return outcomes, (usable[0] if usable else None)


def evaluate(client, known, model, deadline, budget):
    """Every §FE.6 criterion for one candidate; returns (passed criteria, details)."""
    known = set(known)
    rows = {r["id"]: r for r in _ok(client.get("/api/curricula"))}
    passed = {"1": rows["8node_x10"]["reviewed"]}
    allowed = _ok(client.get("/api/curricula/8node_x10"))["allowed_budgets"]

    setup = new_session(client, model, deadline, budget)
    sid = setup["session_id"]
    first = _ok(client.post(f"/api/sessions/{sid}/plan", json={}))["plan"]
    tight, back = tight_variant(client, sid, deadline, budget, allowed)
    passed["5"] = first["status"] == "FEASIBLE" and tight is not None and back == "FEASIBLE"

    view = run_diagnostic(client, sid, known)
    sweep = new_session(client, model, deadline, budget, diagnostic_method="sweep")
    sweep_view = run_diagnostic(client, sweep["session_id"], known)
    results = view["diagnostic"]["concept_results"]
    inferred = [r["concept_id"] for r in results if r["stop_reason"] == "INFERRED"]
    n_bis, n_sweep = len(view["diagnostic"]["items"]), len(sweep_view["diagnostic"]["items"])
    # criterion 2, split so a fallback can drop one half: 2a fewer questions, 2b something INFERRED
    passed["2a"] = n_bis < n_sweep
    passed["2b"] = bool(inferred)

    plan = view["plan"]
    checks = check_activities(plan)
    passed["3"] = plan["status"] == "FEASIBLE" and bool(checks)
    today = view["today"]["activities"] if view["today"] else []
    today_checks = [a for a in today if a in checks]
    passed["4"] = bool(today_checks)
    outcomes, step5 = (
        wrong_check_outcomes(client, model, deadline, budget, known, today_checks)
        if passed["4"]
        else ([], None)
    )
    details = {
        "known": sorted(known),
        "model_profile": model,
        "deadline_day": deadline,
        "budget": budget,
        "setup_first_plan": first["status"],
        "tight": tight,
        "questions_bisection": n_bis,
        "questions_sweep": n_sweep,
        "inferred": inferred,
        "info": view["diagnostic"]["info"],
        "plan_after_diagnostic": plan["status"],
        "check_activities": checks,
        "today": today,
        "today_checks": today_checks,
        "wrong_on_each_check": outcomes,
        "study_wrong_on_check": step5,
    }
    return passed, details


def main():
    from fastapi.testclient import TestClient

    os.environ.setdefault("ADAPTENGINE_SESSIONS_DIR", tempfile.mkdtemp(prefix="ae-preset-"))
    from frontend.api.app import app

    client = TestClient(app)
    keys = ("known", "model_profile", "deadline_day", "budget")
    runs = [
        evaluate(client, known, model, deadline, budget)
        for known in KNOWN_SETS
        for model in MODELS
        for deadline in DEADLINES
        for budget in BUDGETS
    ]
    # §FE.6 fallbacks: a criterion that no candidate meets is dropped (its step leaves the
    # walkthrough); if none then meets 3-4 as well, take the first that meets the rest.
    criteria = set(runs[0][0])
    never = {c for c in criteria if not any(p[c] for p, _ in runs)}
    for required in (criteria - never, criteria - never - {"3", "4"}):
        chosen = next((i for i, (p, _) in enumerate(runs) if all(p[c] for c in required)), None)
        if chosen is not None:
            break
    rejected = []
    for p, d in runs[: chosen if chosen is not None else len(runs)]:
        failing = min(c for c in required if not p[c])
        rejected.append({**{k: d[k] for k in keys}, "failing_criterion": failing})
    out = {
        "chosen": None if chosen is None else runs[chosen][1],
        "passed": None if chosen is None else runs[chosen][0],
        "has_check": "3" in required,
        "dropped": sorted(criteria - required),
        "never_met": sorted(never),
        "rejected": rejected,
    }
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
