"""A2' LLM Ranker (W8 L.1/L.2, D55): a NON-LEARNING proposer over the engine's top-K candidates.

The agent sees a learner summary, the eligible candidates with their features and the
deterministic choice, and answers strict JSON {"ranking": [...], "rationale": "..."}. It has no
reward, no update rule and no memory across calls, so the bandit stays the project's single
feedback-driven policy. The engine validates the answer: it must be a non-empty list of distinct
candidate ids; anything else (unknown, duplicate or out-of-set id, malformed JSON, a provider
error or timeout) raises, and the scheduler falls back to the deterministic choice
(AGENT_FALLBACK). The propensity of the chosen id is logged as 1.0 (deterministic answer).

The provider is injected (anything with complete(prompt, *, task, payload) -> str); network
providers and the response cache live in adaptengine.authoring.providers, outside the core.
"""

from __future__ import annotations

import hashlib
import json
import os

_TEMPLATE = os.path.join(os.path.dirname(__file__), "agent_prompt.md")


class AgentOutputError(ValueError):
    """The agent's answer failed engine validation."""


def parse_ranking(text: str, candidate_ids: list[str]) -> tuple[list[str], str]:
    """Strict validator: JSON object with a non-empty ranking of distinct candidate ids."""
    try:
        obj = json.loads(text)
    except (TypeError, ValueError) as e:
        raise AgentOutputError(f"malformed JSON: {e}")
    if not isinstance(obj, dict) or not isinstance(obj.get("ranking"), list):
        raise AgentOutputError("answer must be an object with a 'ranking' list")
    ranking = obj["ranking"]
    if not ranking or not all(isinstance(x, str) for x in ranking):
        raise AgentOutputError("ranking must be a non-empty list of activity ids")
    if len(set(ranking)) != len(ranking):
        raise AgentOutputError("ranking contains duplicate ids")
    unknown = [x for x in ranking if x not in candidate_ids]
    if unknown:
        raise AgentOutputError(f"ranking contains ids outside the candidate set: {unknown}")
    rationale = obj.get("rationale", "")
    return ranking, rationale if isinstance(rationale, str) else ""


class AgentRankingPolicy:
    name = "agent"
    is_agent = True
    learning = False  # D55: no reward, no update, no memory

    def __init__(self, provider):
        self.provider = provider
        with open(_TEMPLATE, encoding="utf-8") as f:
            self.template = f.read()

    @property
    def version(self) -> str:
        model = getattr(self.provider, "model", "?")
        return f"{getattr(self.provider, 'name', 'provider')}:{model}"

    def prompt(self, candidates: list[dict], context: dict) -> str:
        learner = sorted({(c["concept"], round(c["p"], 3), c["responses"]) for c in candidates})
        lines = [
            f"- {c['activity_id']} ({c['type'].lower()}, concept {c['concept']}, "
            f"{c['duration']} min, difficulty {c['difficulty']}, "
            f"P(correct) {'-' if c['p_correct'] is None else round(c['p_correct'], 3)}, "
            f"unlocks {int(c['unlock'])})"
            for c in candidates
        ]
        return self.template.format(
            goal=context["goal"],
            day=context["day"],
            deadline_day=context["deadline_day"],
            remaining_budget=context["remaining_budget"],
            budget=context["budget"],
            learner="\n".join(f"- {c}: p={p}, responses={n}" for c, p, n in learner),
            candidates="\n".join(lines),
            deterministic_choice=candidates[0]["activity_id"],
        )

    def choose(self, candidates: list[dict], context: dict) -> tuple[str, float, dict]:
        ids = [c["activity_id"] for c in candidates]
        prompt = self.prompt(candidates, context)
        text = self.provider.complete(
            prompt, task="rank", payload={"candidates": ids, "context": context}
        )
        ranking, rationale = parse_ranking(text, ids)
        return (
            ranking[0],
            1.0,
            {
                "ranking": ranking,
                "rationale": rationale[:400],
                "agrees_with_deterministic": ranking[0] == ids[0],
                "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
                "model": getattr(self.provider, "model", None),
            },
        )
