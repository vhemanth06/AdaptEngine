"""W8 WP-N A3 orchestrator: closed option set, fallback, 0 violations (stub). TC3.1, TC7.1."""

import dataclasses
import json
import os
import sys

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from adaptengine.agents.orchestrator import choose_option, orchestrated_next  # noqa: E402
from adaptengine.api import Engine  # noqa: E402
from adaptengine.authoring.providers import StubProvider  # noqa: E402
from adaptengine.learner.state import LearnerState  # noqa: E402
from adaptengine.planner.options import build_options, default_option  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402

C4 = ("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")


@pytest.fixture
def e():
    return Engine.from_files(*C4)


def test_option_set_is_closed_and_conditional(e):
    st = e.init_learner()
    assert [o["id"] for o in build_options(e.graph, st, "C4", 1)] == ["continue"]
    c1 = dataclasses.replace(
        st.concepts["C1"], p=0.1, responses=2, needs_remediation=True, last_practice_day=1
    )
    c2 = dataclasses.replace(
        st.concepts["C2"],
        p=0.95,
        responses=3,
        correct_responses=2,
        correct_streak=0,
        last_practice_day=1,
        half_life_days=2.0,
    )
    st2 = LearnerState(concepts={**st.concepts, "C1": c1, "C2": c2})
    ids = [o["id"] for o in build_options(e.graph, st2, "C4", 10)]
    assert ids == ["continue", "remediate:C1", "rediagnose:C1", "review:C2", "rediagnose:C2"]
    assert default_option(build_options(e.graph, st2, "C4", 10)) == "remediate:C1"


@pytest.mark.parametrize(
    "answer,source",
    [
        ('{"option": "teleport"}', "fallback"),
        ("garbage", "fallback"),
        ('{"option": "continue", "rationale": "ok"}', "agent"),
    ],
)
def test_choice_outside_set_falls_back(answer, source):
    opts = [
        {"id": "continue", "kind": "continue", "why": ""},
        {"id": "review:C1", "kind": "review", "why": ""},
    ]
    choice, info = choose_option(
        StubProvider({"orchestrate": lambda p: answer}), opts, {"day": 1, "goal": "C4", "left": 15}
    )
    assert info["source"] == source and choice in {"continue", "review:C1"}
    assert choice == ("review:C1" if source == "fallback" else "continue")


@pytest.mark.parametrize("pick", ["first", "last", "bogus"])
def test_orchestrated_episodes_have_zero_violations(e, pick):
    def responder(payload):
        opts = [o["id"] for o in payload["options"]]
        return json.dumps({"option": {"first": opts[0], "last": opts[-1], "bogus": "x"}[pick]})

    prov = StubProvider({"orchestrate": responder})
    log = []

    def nxt(s, lg, ctx, review_urgency=None):
        return orchestrated_next(e, s, lg, ctx, prov, review_urgency, log)

    sc = get_scenario("calm", e, e.init_learner(), goal="C4", budget=15, horizon=14)
    for seed in range(4):
        r = run_episode(e, seed, sc, "adapt", PROFILES["nominal"], "S1", next_fn=nxt)
        assert r["executed_prereq_violations"] == 0 and r["budget_violations"] == 0
    assert log and all(rec["choice"] in rec["options"] or rec.get("rejected") for rec in log)
