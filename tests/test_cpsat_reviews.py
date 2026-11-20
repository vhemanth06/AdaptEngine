"""Plan 4 (F3-T4, F3-T5): reviews in the CP-SAT model and the CP-SAT trace (F3-TC6, F3-TC8)."""

import collections
import dataclasses
import math
import os
import sys

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

pytest.importorskip("ortools")

from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import DEFAULT_CONFIG  # noqa: E402
from adaptengine.core.schema import PlanContext, PlanStatus  # noqa: E402
from adaptengine.learner.state import LearnerState  # noqa: E402

CUR = os.path.join(repo_root, "data", "curriculum")
CTX = PlanContext(goal="C8", deadline_day=14, budget=15, current_day=3)


def _eng(method="cpsat", **kw):
    cfg = dataclasses.replace(DEFAULT_CONFIG, planner_method=method, **kw)
    return Engine.from_files(
        f"{CUR}/curriculum_8node.json", f"{CUR}/activities_8node.json", config=cfg
    )


def _practised(e, h=2.0):
    """C1, C2 mastered and practised on day 1 with a short half-life; C3 practised but unmastered."""
    st = e.init_learner()
    c = dict(st.concepts)
    for cid in ("C1", "C2"):
        c[cid] = dataclasses.replace(
            c[cid], p=0.95, responses=2, correct_responses=2, last_practice_day=1, half_life_days=h
        )
    c["C3"] = dataclasses.replace(
        c["C3"], p=0.4, responses=1, correct_responses=1, last_practice_day=1, half_life_days=h
    )
    c["C1"] = dataclasses.replace(
        c["C1"], p=0.5, responses=1, correct_responses=1
    )  # C1 has work again
    return LearnerState(concepts=c)


def _gap(h, cfg):
    return math.floor(h * math.log2(1 / cfg.recall_threshold)) + 1


def _reviews(p):
    return [t for t in p.trace if t.get("reason") == "REVIEW_SCHEDULED"]


def test_reviews_appear_and_never_before_due_f3_tc6():
    e = _eng()
    st = _practised(e)
    p = e.plan(st, CTX)
    assert p.status == PlanStatus.FEASIBLE
    revs = _reviews(p)
    assert revs  # short half-life: reviews appear (as the W7 T2.6 test for greedy)
    item_days = collections.defaultdict(list)
    for t in p.trace:
        if t.get("reason") in ("CPSAT_ASSIGNED", "REMEDIATION_INSERTED"):
            item_days[t["target_concept"]].append(t["day"])
    by_concept = collections.defaultdict(list)
    for t in revs:
        by_concept[t["target_concept"]].append(t)
    for c, rs in by_concept.items():
        uc = st.concepts[c]
        prev = max(item_days[c]) if item_days[c] else uc.last_practice_day
        for k, t in enumerate(sorted(rs, key=lambda r: r["day"])):
            h = uc.half_life_days * e.config.half_life_growth**k
            assert t["day"] >= prev + _gap(h, e.config)  # never before its due day
            prev = t["day"]


def test_unpracticed_never_reviewed_f3_tc6():
    e = _eng()
    p = e.plan(_practised(e), CTX)
    reviewed = {t["target_concept"] for t in _reviews(p)}
    planned = {t["target_concept"] for t in p.trace if t.get("reason") == "CPSAT_ASSIGNED"}
    assert "C4" not in reviewed  # never practised and not on the goal path (D22)
    assert reviewed <= planned | {"C1", "C2", "C3"}


def test_reviews_gated_by_unfinished_prerequisites_w7_defect7():
    e = _eng()
    p = e.plan(_practised(e), CTX)
    c1_last = max(
        t["day"]
        for t in p.trace
        if t.get("reason") in ("CPSAT_ASSIGNED", "REMEDIATION_INSERTED")
        and t["target_concept"] == "C1"
    )
    for t in _reviews(p):
        if t["target_concept"] == "C3":
            assert t["day"] >= c1_last  # C3's prerequisite C1 still had queued work


def test_dropping_reviews_never_breaks_the_goal_f3_tc6():
    e = _eng()
    st = _practised(e)
    with_r = e.plan(st, CTX)
    without = e.plan(st, CTX, review_urgency={c: 0.0 for c in e.graph.concepts()})
    assert not _reviews(without)

    def finish(p):
        return max(
            t["day"]
            for t in p.trace
            if t.get("reason") in ("CPSAT_ASSIGNED", "REMEDIATION_INSERTED")
        )

    assert finish(with_r) == finish(without)  # level 1 (goal finish) comes before reviews


# ---------------- F3-T5: trace ----------------


@pytest.mark.parametrize(
    "method,ctx", [("cpsat", CTX), ("hybrid", PlanContext(goal="C8", deadline_day=5, budget=10))]
)
def test_one_record_per_activity_and_reasons_true_f3_tc8(method, ctx):
    e = _eng(method)
    st = _practised(e) if method == "cpsat" else e.init_learner()
    p = e.plan(st, ctx)
    assert p.status == PlanStatus.FEASIBLE
    sel = collections.Counter(
        (t["day"], t["activity_id"]) for t in p.trace if t.get("decision") == "SELECTED"
    )
    planned = collections.Counter((d.day, a) for d in p.days for a in d.activities)
    assert sel == planned  # TC7.1: exactly one record per planned activity
    assert sum(t.get("decision") == "CPSAT_SOLVE" for t in p.trace) == 1
    load = {d.day: d.duration for d in p.days}
    cap = {
        d: ctx.budget - (ctx.minutes_used_today if d == ctx.current_day else 0)
        for d in range(ctx.current_day, ctx.deadline_day + 1)
    }
    last_day = {}
    for t in p.trace:
        if t.get("reason") in ("CPSAT_ASSIGNED", "REMEDIATION_INSERTED"):
            last_day[t["target_concept"]] = max(last_day.get(t["target_concept"], 0), t["day"])
    for t in p.trace:
        if t.get("reason") not in ("CPSAT_ASSIGNED", "REMEDIATION_INSERTED"):
            continue
        assert t["earliest_possible_day"] <= t["day"]
        assert (t["placement"] == "AT_EARLIEST") == (t["day"] == t["earliest_possible_day"])
        if t["placement"] == "BUDGET_FULL":
            a, b = t["full_days"]
            assert all(cap[d] - load.get(d, 0) < t["duration"] for d in range(a, b + 1))
        if t["earliest_because"].startswith("PREREQUISITE_"):
            q = t["earliest_because"].split("_")[1]
            assert last_day[q] == t["earliest_possible_day"]


def test_infeasible_trace_has_exact_advice_f3_tc8():
    e = _eng()
    p = e.plan(e.init_learner(), PlanContext(goal="C8", deadline_day=3, budget=15))
    rec = next(t for t in p.trace if t.get("decision") == "CPSAT_SOLVE")
    assert rec["status"] == "INFEASIBLE" and rec["shortfall_exact"] is True
    assert rec["minimum_finish_day"] == 3 + p.shortfall_days
    assert rec["smallest_working_budget"] == 30
