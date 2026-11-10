"""W8 WP-L A2' LLM ranker: adversarial outputs fall back (AGENT_FALLBACK), 0 violations, offline
(stub provider). Links TC3.1, TC7.1."""

import json
import os
import sys

import pytest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from adaptengine.api import Engine  # noqa: E402
from adaptengine.authoring.providers import ProviderError, StubProvider  # noqa: E402
from adaptengine.core.schema import PlanContext  # noqa: E402
from adaptengine.policy.agent import AgentOutputError, AgentRankingPolicy, parse_ranking  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.sim import PROFILES  # noqa: E402

C4 = ("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
CTX = PlanContext(goal="C4", deadline_day=20, budget=15, current_day=1)


def reverse(payload):
    return json.dumps(
        {"ranking": list(reversed(payload["candidates"])), "rationale": "harder first"}
    )


def timeout(payload):
    raise ProviderError("timeout after 30s")


BAD = {
    "unknown_id": lambda p: json.dumps({"ranking": ["E-NOPE"], "rationale": ""}),
    "duplicates": lambda p: json.dumps({"ranking": [p["candidates"][0]] * 2}),
    "out_of_set": lambda p: json.dumps({"ranking": ["L-C4"]}),  # real id, not offered
    "malformed": lambda p: "Sure! Here is my ranking: E-C1-0.2",
    "empty": lambda p: json.dumps({"ranking": []}),
    "timeout": timeout,
}


def test_parse_ranking_strict():
    assert parse_ranking('{"ranking": ["a"], "rationale": "x"}', ["a", "b"]) == (["a"], "x")
    for text in ('{"ranking": ["c"]}', '{"ranking": ["a", "a"]}', "[]", "{", '{"ranking": "a"}'):
        with pytest.raises(AgentOutputError):
            parse_ranking(text, ["a", "b"])


def test_valid_agent_answer_is_used_and_logged():
    e = Engine.from_files(*C4, policy=AgentRankingPolicy(StubProvider({"rank": reverse})))
    plan = e.plan(e.init_learner(), CTX)
    sel = [t for t in plan.trace if t.get("decision") == "POLICY_SELECTED"]
    assert sel and all(t["propensity"] == 1.0 and t["policy"] == "agent" for t in sel)
    assert all(t["chosen"] == t["candidates"][-1] and t["rationale"] == "harder first" for t in sel)
    assert any(not t["agrees_with_deterministic"] for t in sel)


def test_stub_default_agrees_with_deterministic_plan():
    base, agent = (
        Engine.from_files(*C4),
        Engine.from_files(*C4, policy=AgentRankingPolicy(StubProvider())),
    )
    assert base.plan(base.init_learner(), CTX).days == agent.plan(agent.init_learner(), CTX).days


@pytest.mark.parametrize("kind", sorted(BAD))
def test_adversarial_output_falls_back_with_zero_violations(kind):
    base = Engine.from_files(*C4)
    e = Engine.from_files(*C4, policy=AgentRankingPolicy(StubProvider({"rank": BAD[kind]})))
    plan = e.plan(e.init_learner(), CTX)
    assert plan.days == base.plan(base.init_learner(), CTX).days
    fb = [t for t in plan.trace if t.get("decision") == "AGENT_FALLBACK"]
    assert fb and not any(t.get("decision") == "POLICY_SELECTED" for t in plan.trace)
    sc = get_scenario("calm", e, e.init_learner(), goal="C4", budget=15, horizon=14)
    for seed in range(3):
        r = run_episode(e, seed, sc, "adapt", PROFILES["nominal"], "S1")
        assert r["executed_prereq_violations"] == 0 and r["budget_violations"] == 0


def test_agent_policy_is_non_learning():
    pol = AgentRankingPolicy(StubProvider())
    assert pol.learning is False and not hasattr(pol, "update")
