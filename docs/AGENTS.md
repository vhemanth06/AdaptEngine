# Agentic layer (A0–A3): what each agent may do

All agents are **disabled by default** (D56) and sit above the deterministic core: core packages
(`core`, `curriculum`, `learner`, `diagnostic`, `planner`, `review`, `replanner`, `policy`) never
import `adaptengine.authoring`, `adaptengine.agents` or a network client
(`tests/test_architecture.py`). **Agents propose; the engine validates and decides.** Every failure
falls back to the deterministic path. Only the bandit (A2, `POLICY_SPEC.md`) learns from feedback.

| Agent | Module | May | Engine check | Fallback | Learns? |
|---|---|---|---|---|---|
| A0 Authoring Aid (D54) | `authoring/draft.py`, `authoring/checks.py` | write drafts to `data/drafts/<name>/` | loaders (schema, DAG, difficulty, content) + authoring checks; retry ≤ 2 | draft stays a draft; never written to `data/curriculum/` | no |
| A1 Plan Proposer (D57) | `agents/plan_proposer.py` | propose a whole day-by-day plan | `planner/validate_proposal.py`: ids exist, no duplicate lessons, each day ≤ budget, within [start, deadline], prerequisite order under the plan's projection, goal reached | deterministic plan + `PROPOSAL_REJECTED` with the violated rules | no |
| A2 Bandit (D53) | `policy/bandit.py` | re-order the top-K eligible new-content candidates | chosen id must be offered and fit | `POLICY_FALLBACK` → deterministic | **yes** (ridge) |
| A2′ LLM Ranker (D55) | `policy/agent.py` | re-order the same candidates and explain | strict JSON: non-empty list of distinct offered ids | `AGENT_FALLBACK` → deterministic | no |
| A3 Orchestrator (D58) | `agents/orchestrator.py`, `planner/options.py` | pick one engine-generated option (continue / remediate X / review Y / re-diagnose Z / consolidate) | option ∈ generated set; resulting slice prerequisite-safe in the real state and within today's budget | engine default (tier order: remediate, review, continue) | no |

## Providers (`authoring/providers.py`)

- `StubProvider` — deterministic, offline templates (tests, CI, demo).
- `AnthropicProvider` — Claude through the official SDK (`pip install -e ".[agents]"`; credentials
  from `ANTHROPIC_API_KEY` or an `ant auth login` profile). Default model `claude-opus-5-5`,
  server-side refusal fallback enabled (`fallbacks: "default"`); refusals raise `ProviderError`
  and fall back. Current Claude models reject sampling parameters, so there is no temperature 0.
- `OllamaProvider` — a local model (`ollama pull llama3.1:8b`), temperature 0, JSON format.
- `CachedProvider` — prompt-hash disk cache (`experiments/results/agent_cache/`), records model,
  latency and timestamp; `replay_only=True` never calls the network (evaluation and demo replay).

No learner data beyond the per-concept summary in the prompt is sent; authoring prompts contain
only the topic.

## Running the live agents (human step)

```bash
pip install -e ".[agents]"
export ANTHROPIC_API_KEY=...            # or: ant auth login
python experiments/run_agent_eval.py --provider anthropic --populate   # fills the cache once
python experiments/run_agent_eval.py --provider anthropic              # replays from the cache
```
