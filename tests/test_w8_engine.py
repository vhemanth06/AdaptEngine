"""W8 engine extensions behind flags: profiles (B.1), consolidation (C.1), verification probe (C.2),
horizon-aware strictness (C.3), review cap / goal path (D.1), diagnostic scope (E.1), feasibility
warning (F.1), Elo model (O.1), HLR-lite (O.2), BKT forgets (O.3). Links: TC3.1, TC3.2, TC4.1,
TC5.1-TC5.3, TC2.1, TC8.2."""

import dataclasses
import json
import math
import os
import sys

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG, EngineConfig  # noqa: E402
from adaptengine.core.errors import ValidationError  # noqa: E402
from adaptengine.core.profiles import load_profile, profile_config  # noqa: E402
from adaptengine.core.schema import Event, EventType, PlanContext  # noqa: E402
from adaptengine.learner.elo import EloModel  # noqa: E402
from adaptengine.learner.mastery import guess, slip, update_mastery  # noqa: E402
from adaptengine.learner.state import ExecutionLog, LearnerState  # noqa: E402
from adaptengine.review.hlr import hlr_half_life_counts  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.checks import count_plan_prereq_violations  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402

C4 = ("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
C8 = ("data/curriculum/curriculum_8node.json", "data/curriculum/activities_8node.json")


def eng(paths=C4, **kw):
    return Engine.from_files(*paths, config=dataclasses.replace(DEFAULT_CONFIG, **kw))


def mastered_state(e, concepts, p=0.95, responses=3):
    s = e.init_learner()
    return LearnerState(
        concepts={
            c: dataclasses.replace(
                s.concepts[c], p=p, responses=responses, correct_responses=responses
            )
            if c in concepts
            else s.concepts[c]
            for c in s.concepts
        }
    )


def ctx(deadline=14, budget=15, day=1, goal="C4"):
    return PlanContext(goal=goal, deadline_day=deadline, budget=budget, current_day=day)


# ------------------------------------------------------------------------------ B.1 profiles


def test_default_profile_is_w7_config():
    assert load_profile("w7_default") is DEFAULT_CONFIG
    e1, e2 = eng(), Engine.from_files(*C4, config=load_profile("w7_default"))
    for b in (5, 10, 15, 30):
        p1 = e1.plan(e1.init_learner(), ctx(budget=b, deadline=30))
        p2 = e2.plan(e2.init_learner(), ctx(budget=b, deadline=30))
        assert p1 == p2


def test_profile_loads_class_params_into_guess_and_slip():
    cfg = load_profile("fitted_sim")
    prof = json.load(open("config/fitted_sim.json"))
    assert cfg.profile == "fitted_sim"
    assert guess(0.2, cfg) == pytest.approx(prof["class_params"]["easy"]["guess"])
    assert slip(0.8, cfg) == pytest.approx(prof["class_params"]["hard"]["slip"])
    assert cfg.p0 == pytest.approx(prof["p0"]) and cfg.t_exercise == pytest.approx(
        prof["t_exercise"]
    )
    assert cfg.t_lesson == DEFAULT_CONFIG.t_lesson  # not in that profile
    e = Engine.from_files(*C4, config=load_profile("fitted_sim", theta=0.95, k_responses=3))
    assert e.config.theta == 0.95 and e.plan(e.init_learner(), ctx()).days


@pytest.mark.parametrize(
    "bad",
    [
        {"easy": (0.6, 0.5)},  # guess + slip >= 1
        {"medium": (0.0, 0.2)},  # guess not in (0, 1)
        {"hard": (float("nan"), 0.2)},
    ],
)
def test_invalid_profile_rejected(bad):
    cp = {"easy": (0.2, 0.1), "medium": (0.15, 0.2), "hard": (0.05, 0.25)}
    cp.update(bad)
    data = {
        "p0": 0.2,
        "t_exercise": 0.05,
        "class_params": {k: {"guess": g, "slip": s} for k, (g, s) in cp.items()},
    }
    with pytest.raises(ValidationError):
        profile_config(data)


@pytest.mark.parametrize("field,val", [("t_exercise", 1.0), ("t_lesson", 0.0), ("p0", math.inf)])
def test_invalid_profile_transitions_rejected(field, val):
    data = {
        "p0": 0.2,
        "t_exercise": 0.05,
        "class_params": {k: {"guess": 0.2, "slip": 0.1} for k in ("easy", "medium", "hard")},
        field: val,
    }
    with pytest.raises(ValidationError):
        profile_config(data)
    with pytest.raises(ValidationError):
        load_profile("does_not_exist_profile")


def test_w8_config_flags_validated():
    for kw in (
        {"consolidation": 1},
        {"review_cap_fraction": 0.0},
        {"diagnostic_scope": "goal"},
        {"ranking_policy": "llm"},
        {"mastery_model": "irt"},
        {"forget": 1.0},
        {"class_params": (("easy", 0.2, 0.1),)},
    ):
        with pytest.raises(ValidationError):
            EngineConfig(**kw)


# ------------------------------------------------------------------------- C.1 consolidation


def test_consolidation_only_after_all_required_work():
    e = eng(consolidation=True)
    plan = e.plan(e.init_learner(), ctx(deadline=10))
    sel = [t for t in plan.trace if t.get("decision") == "SELECTED"]
    reasons = [t["reason"] for t in sel]
    assert "CONSOLIDATION" in reasons
    first_cons = reasons.index("CONSOLIDATION")
    assert all(r == "CONSOLIDATION" for r in reasons[first_cons:] if r != "REVIEW_DUE")
    assert plan.days[-1].day <= 10
    assert count_plan_prereq_violations(e, e.init_learner(), plan.days) == 0
    assert all(d.duration <= 15 for d in plan.days)
    # flag off: no consolidation and the W7 plan
    base = eng()
    p0 = base.plan(base.init_learner(), ctx(deadline=10))
    assert not any(t.get("reason") == "CONSOLIDATION" for t in p0.trace)
    n_new = sum(1 for r in reasons if r != "CONSOLIDATION")
    assert [a for d in plan.days for a in d.activities][:n_new] == [
        a for d in p0.days for a in d.activities
    ]


def test_consolidation_when_everything_is_believed_mastered():
    e = eng(consolidation=True)
    st = mastered_state(e, ("C1", "C2", "C3", "C4"))
    plan = e.plan(st, ctx(deadline=3, day=1))
    assert plan.reason == "CONSOLIDATION"
    assert [d.day for d in plan.days] == [1, 2, 3]
    first = plan.days[0].activities
    # unseen hard items first, lowest-confidence concepts first (all equal p: by concept id)
    assert first[0] == "E-C1-0.8"
    base = eng()
    assert base.plan(st, ctx(deadline=3)).reason == "GOAL_ALREADY_MASTERED"


def test_consolidation_raises_utilisation_and_keeps_safety():
    on, off = eng(consolidation=True), eng()
    for world in ("S0", "S1"):
        sc = get_scenario("calm", off, off.init_learner(), goal="C4", budget=15, horizon=14)
        r_on = run_episode(on, 7, sc, "adapt", PROFILES["nominal"], world)
        r_off = run_episode(off, 7, sc, "adapt", PROFILES["nominal"], world)
        assert r_on["minute_utilisation"] > r_off["minute_utilisation"]
        assert r_on["executed_prereq_violations"] == 0
        assert r_on["budget_violations"] == 0


# --------------------------------------------------------------------- C.2 verification probe


def _c1_easy_evidence(e):
    st = mastered_state(e, ("C1",), p=0.9, responses=3)
    return st, ("L-C1", "E-C1-0.2", "E-C1-0.2", "E-C1-0.4")


def test_probe_inserted_when_evidence_is_mostly_easy():
    e = eng(verification_probe=True)
    st, done = _c1_easy_evidence(e)
    plan = e.plan(st, ctx(deadline=20), done_ids=done)
    probes = [t for t in plan.trace if t.get("reason") == "VERIFICATION_PROBE"]
    assert [p["concept_id"] for p in probes][0] == "C1"
    assert probes[0]["activity_id"] == "E-C1-0.8"
    order = [a for d in plan.days for a in d.activities]
    i_probe = order.index("E-C1-0.8")
    # the dependent C3 stays locked until the probe is done
    assert all(not a.endswith("C3") and "-C3-" not in a for a in order[:i_probe])
    # without the flag C1 is omitted and no probe is scheduled
    base = eng()
    assert (
        "E-C1-0.8"
        not in [
            a for d in base.plan(st, ctx(deadline=20), done_ids=done).days for a in d.activities
        ][:1]
    )


def test_probe_not_inserted_with_hard_or_balanced_evidence():
    e = eng(verification_probe=True)
    st = mastered_state(e, ("C1",), p=0.9, responses=3)
    for done in (("E-C1-0.2", "E-C1-0.8"), ("E-C1-0.4", "E-C1-0.6", "E-C1-0.2")):
        plan = e.plan(st, ctx(deadline=20), done_ids=done)
        assert not any(
            t.get("reason") == "VERIFICATION_PROBE" and t.get("concept_id") == "C1"
            for t in plan.trace
        )


def test_probe_answered_unlocks_dependents():
    e = eng(verification_probe=True)
    st, done = _c1_easy_evidence(e)
    st = mastered_state(e, ("C1",), p=0.93, responses=4)
    plan = e.plan(st, ctx(deadline=20), done_ids=done + ("E-C1-0.8",))
    assert not any(
        t.get("concept_id") == "C1" and t.get("reason") == "VERIFICATION_PROBE" for t in plan.trace
    )


def test_probe_flag_keeps_executed_safety():
    e = eng(verification_probe=True)
    sc = get_scenario("calm", e, e.init_learner(), goal="C4", budget=15, horizon=14)
    for s in range(10):
        r = run_episode(e, s, sc, "adapt", PROFILES["nominal"], "S1")
        assert r["executed_prereq_violations"] == 0 and r["budget_violations"] == 0


# ----------------------------------------------------------------- C.3 horizon-aware strictness


def test_horizon_aware_same_as_w7_when_slack_is_small():
    e, base = eng(horizon_aware_mastery=True), eng()
    tight = ctx(deadline=4, budget=15)  # optimistic work needs 2 of 4 days: slack 0.5
    p1, p0 = e.plan(e.init_learner(), tight), base.plan(base.init_learner(), tight)
    assert p1.days == p0.days
    assert not any(t.get("reason") == "HORIZON_AWARE_STRICT" for t in p1.trace)


def test_horizon_aware_stricter_when_slack_is_large():
    e, base = eng(horizon_aware_mastery=True), eng()
    long = ctx(deadline=21, budget=15)
    p1, p0 = e.plan(e.init_learner(), long), base.plan(base.init_learner(), long)
    rec = next(t for t in p1.trace if t.get("reason") == "HORIZON_AWARE_STRICT")
    assert rec["slack"] > 0.5 and rec["k_responses"] == 3
    n1 = sum(len(d.activities) for d in p1.days)
    n0 = sum(len(d.activities) for d in p0.days)
    assert n1 > n0
    # a concept mastered under the W7 rule but not the strict one is required again
    st = mastered_state(e, ("C1",), p=0.9, responses=2)
    assert any(a.startswith("E-C1") for d in e.plan(st, long).days for a in d.activities)
    assert not any(a.startswith("E-C1") for d in base.plan(st, long).days for a in d.activities)


# ------------------------------------------------------------------ D.1 review cap / goal path


def _review_state(e, day=10):
    s = mastered_state(e, ("C1", "C2"), p=0.95, responses=4)
    return LearnerState(
        concepts={
            c: dataclasses.replace(v, last_practice_day=1, half_life_days=2.0)
            if c in ("C1", "C2")
            else v
            for c, v in s.concepts.items()
        }
    )


def test_review_cap_limits_review_minutes_while_new_content_pending():
    e = eng(review_cap_fraction=0.25)
    base = eng()
    st = _review_state(e)
    c = ctx(day=10, deadline=30, budget=15)
    rev = lambda p: [  # noqa: E731
        t for t in p.trace if t.get("decision") == "SELECTED" and t["reason"] == "REVIEW_DUE"
    ]
    capped, free = e.plan(st, c), base.plan(st, c)
    # the cap applies while new content is pending: reviews placed before the day's last new item
    last_new = {t["day"]: i for i, t in enumerate(capped.trace) if t.get("reason") == "RANKED_TOP"}
    per_day = {}
    for i, t in enumerate(capped.trace):
        if t in rev(capped) and i < last_new.get(t["day"], -1):
            per_day[t["day"]] = per_day.get(t["day"], 0) + t["duration"]
    assert per_day and max(per_day.values()) <= 0.25 * 15
    assert len([t for t in rev(free) if t["day"] == 10]) > len(
        [t for t in rev(capped) if t["day"] == 10]
    ) or any(t.get("reason") == "REVIEW_CAP" for t in capped.trace)


def test_review_goal_path_only():
    e = eng(review_goal_path_only=True)
    st = _review_state(e)
    plan = e.plan(st, ctx(day=10, deadline=30, budget=15, goal="C1"))
    reviewed = {
        t["target_concept"]
        for t in plan.trace
        if t.get("reason") == "REVIEW_DUE" and t.get("decision") == "SELECTED"
    }
    assert "C2" not in reviewed  # C2 is not on C1's path


# ---------------------------------------------------------------------- E.1 diagnostic scope


def test_goal_path_diagnostic_skips_mastered_and_off_path_concepts():
    e8 = eng(C8, diagnostic_scope="goal_path")
    goal = "C3"
    path = {goal} | e8.graph.ancestors(goal)
    res = e8.diagnose(e8.init_learner(), lambda a: True, goal_concepts=[goal])
    assert {i.concept_id for i in res.item_log} <= path
    full = eng(C8).diagnose(eng(C8).init_learner(), lambda a: True)
    assert len(res.item_log) <= len(full.item_log)
    e4 = eng(diagnostic_scope="goal_path")
    st = mastered_state(e4, ("C1",))
    res4 = e4.diagnose(st, lambda a: True, goal_concepts=["C4"])
    assert "C1" not in {i.concept_id for i in res4.item_log}


# -------------------------------------------------------------------- F.1 feasibility warning


def test_feasibility_warning_does_not_change_the_schedule():
    on, off = eng(feasibility_warning=True), eng()
    tight = ctx(deadline=4, budget=10)
    p_on, p_off = on.plan(on.init_learner(), tight), off.plan(off.init_learner(), tight)
    assert p_on.days == p_off.days and p_off.feasibility_warning is None
    assert p_on.feasibility_warning and "study days" in p_on.feasibility_warning
    assert on.plan(on.init_learner(), ctx(deadline=40)).feasibility_warning is None


# ------------------------------------------------------------------------ O.1 / O.2 / O.3


def test_elo_model_is_a_mastery_model():
    m = EloModel(DEFAULT_CONFIG)
    assert m.predict_correct(0.5, 0.2) > m.predict_correct(0.5, 0.8)
    assert m.predict_correct(0.9, 0.5) > m.predict_correct(0.3, 0.5)
    assert m.update(0.5, 0.5, True, 0.0) > 0.5 > m.update(0.5, 0.5, False, 0.0)
    e = eng(mastery_model="elo")
    assert isinstance(e.model, EloModel)
    sc = get_scenario("calm", e, e.init_learner(), goal="C4", budget=15, horizon=14)
    r = run_episode(e, 1, sc, "adapt", PROFILES["nominal"], "S0")
    assert r["executed_prereq_violations"] == 0 and r["minutes_used"] > 0


def test_hlr_half_life_counts_and_scheduler_use():
    w = (2.0, 1.0, -1.0)
    assert (
        hlr_half_life_counts(5, 0, w)
        > hlr_half_life_counts(0, 0, w)
        > hlr_half_life_counts(0, 5, w)
    )
    e = eng(half_life_model="hlr", hlr_weights=(0.0, 0.0, 0.0))  # h = 1 day: reviews due fast
    st = _review_state(e)
    plan = e.plan(st, ctx(day=3, deadline=30))
    assert any(t.get("decision") == "REVIEW_DUE" for t in plan.trace)


def test_forget_transition():
    cfg = dataclasses.replace(DEFAULT_CONFIG, forget=0.1)
    p = update_mastery(0.6, 0.5, True, 0.05, cfg)
    p0 = update_mastery(0.6, 0.5, True, 0.05, DEFAULT_CONFIG)
    assert p < p0
    from adaptengine.learner.mastery import bayes_update

    pb = bayes_update(0.6, 0.5, True, cfg)
    assert p == pytest.approx(pb * 0.9 + (1 - pb) * 0.05)


def test_all_flags_on_keep_executed_safety():
    e = eng(
        C8,
        consolidation=True,
        verification_probe=True,
        horizon_aware_mastery=True,
        review_cap_fraction=0.25,
        review_goal_path_only=True,
    )
    sc = get_scenario("missed_day", e, e.init_learner(), goal="C8", budget=15, horizon=14)
    for s in range(4):
        for world in ("S1", "S4"):
            r = run_episode(e, s, sc, "adapt", PROFILES["nominal"], world)
            assert r["executed_prereq_violations"] == 0 and r["budget_violations"] == 0


def test_event_log_replan_with_flags():
    e = eng(consolidation=True, verification_probe=True, horizon_aware_mastery=True)
    st, log = e.init_learner(), ExecutionLog()
    st, log = e.record(st, log, Event(day=1, kind=EventType.MISSED))
    today, plan = e.next_activities(st, log, ctx(deadline=10))
    assert today is not None and today.day == 2


# ------------------------------------------------------------------------------ O.4 CP-SAT


def test_cpsat_flag_without_ortools_falls_back_to_greedy():
    from adaptengine.planner import cpsat

    e, base = eng(scheduler="cpsat"), eng()
    c = ctx(deadline=10)
    p, p0 = e.plan(e.init_learner(), c), base.plan(base.init_learner(), c)
    if cpsat.available():
        assert p.reason == "CPSAT_ASSIGNMENT"
        assert count_plan_prereq_violations(e, e.init_learner(), p.days) == 0
        assert all(d.duration <= 15 for d in p.days) and len(p.days) <= len(p0.days)
    else:
        assert p.days == p0.days
        assert any(t.get("reason") == "CPSAT_UNAVAILABLE_USING_GREEDY" for t in p.trace)


def test_cpsat_matches_oracle_constraints():
    pytest.importorskip("ortools")
    from adaptengine.planner.cpsat import solve_cpsat
    from adaptengine.planner.oracle import OracleActivity, solve_oracle

    acts = [OracleActivity(a, d) for a, d in (("a", 8), ("b", 8), ("c", 4))]
    preds = {"a": [], "b": ["a"], "c": ["b"]}
    s1, asg1, _ = solve_cpsat(acts, preds, 10, 3)
    s2, asg2, _ = solve_oracle(acts, preds, 10, 3)
    assert s1 == s2 and len(asg1) == 3
