#!/usr/bin/env python3
"""W8 L.4 / M.3 / N.3: exploratory agent evaluations (FINAL_A5 §7). S1, 4-node, B = 15, calm,
14 days, N = 50 paired odd seeds, adapt_final engine.

  --provider stub                      plumbing run (labelled: not an agent evaluation)
  --provider anthropic[:model] --populate   call the model once and fill the cache
  --provider anthropic[:model]         replay from experiments/results/agent_cache/ only (offline)

Writes experiments/results/w8_agent_eval_<provider>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [p for p in (repo_root, os.path.join(repo_root, "src")) if p not in sys.path]

from adaptengine.agents.orchestrator import orchestrated_next  # noqa: E402
from adaptengine.agents.plan_proposer import propose_plan  # noqa: E402
from adaptengine.authoring.providers import ProviderError, make_provider  # noqa: E402
from adaptengine.core.schema import PlanContext  # noqa: E402
from adaptengine.learner.state import ExecutionLog  # noqa: E402
from adaptengine.policy import BanditPolicy  # noqa: E402
from adaptengine.policy.agent import AgentRankingPolicy  # noqa: E402
from experiments.arms import get_scenario, run_episode  # noqa: E402
from experiments.policy_runner import final_engine, run_policy_episode  # noqa: E402
from experiments.provenance import stamp  # noqa: E402
from experiments.sim import PROFILES, make_sim  # noqa: E402
from experiments.stats import paired_summary  # noqa: E402
from experiments.w8_common import REPORT_SEEDS, engine, goal_of  # noqa: E402

SEEDS = REPORT_SEEDS[:50]
WORLD, CUR = "S1", "4-node"
CACHE = os.path.join(repo_root, "experiments", "results", "agent_cache")


def ranker_eval(provider):
    rows = {"deterministic": [], "bandit_frozen": [], "agent": []}
    lat, fallbacks, decisions, agree = [], 0, 0, 0
    for s in SEEDS:
        rows["deterministic"].append(run_policy_episode(CUR, WORLD, s, None)[0])
        frozen = BanditPolicy.load(
            os.path.join(repo_root, "config/policy_frozen.json"), mode="frozen", seed=s
        )
        rows["bandit_frozen"].append(run_policy_episode(CUR, WORLD, s, frozen)[0])
        pol = AgentRankingPolicy(provider)
        e = final_engine(CUR, WORLD, policy=pol)
        sc = get_scenario(
            "calm",
            engine(CUR),
            engine(CUR).init_learner(),
            goal=goal_of(engine(CUR)),
            budget=15,
            horizon=14,
        )
        plans = []

        def nxt(st, log, ctx, review_urgency=None):
            t0 = time.perf_counter()
            today, plan = e.next_activities(st, log, ctx, review_urgency=review_urgency)
            lat.append(time.perf_counter() - t0)
            plans.append(plan)
            return today, plan

        rows["agent"].append(
            run_episode(e, s, sc, "adapt", PROFILES["nominal"], WORLD, next_fn=nxt)
        )
        for p in plans:
            for t in p.trace:
                if t.get("decision") == "POLICY_SELECTED":
                    decisions += 1
                    agree += t["agrees_with_deterministic"]
                elif t.get("decision") == "AGENT_FALLBACK":
                    decisions += 1
                    fallbacks += 1
    g = {k: [float(r["goal_mastered"]) for r in v] for k, v in rows.items()}
    a = {k: [float(r["all_required_mastered"]) for r in v] for k, v in rows.items()}
    return {
        "goal_mastery": {k: round(statistics.mean(v), 4) for k, v in g.items()},
        "agent_vs_deterministic": paired_summary(g["agent"], g["deterministic"]),
        "agent_vs_bandit_frozen": paired_summary(g["agent"], g["bandit_frozen"]),
        "all_required": {k: round(statistics.mean(v), 4) for k, v in a.items()},
        "executed_violations_agent": sum(r["executed_prereq_violations"] for r in rows["agent"]),
        "ranking_decisions": decisions,
        "fallback_rate": round(fallbacks / decisions, 4) if decisions else None,
        "agreement_with_deterministic": round(agree / max(1, decisions - fallbacks), 4),
        "mean_replan_latency_s": round(statistics.mean(lat), 4) if lat else None,
    }


def proposer_eval(provider):
    e = final_engine(CUR, WORLD)
    acc, lengths, ref_lengths, reasons = 0, [], [], {}
    for s in SEEDS:
        ctx = PlanContext(goal=goal_of(e), deadline_day=14, budget=15, current_day=1)
        # each seed starts from its own diagnosed state, so prompts differ across learners
        sim = make_sim(e, s, PROFILES["nominal"], world=WORLD)
        st = e.diagnose(e.init_learner(), lambda a: sim.respond(a.target_concept, a.activity_id, a.difficulty, tag="diag"),
                        goal_concepts=[ctx.goal], session_id=f"m3-{s}").state  # fmt: skip
        plan, r = propose_plan(e, st, ExecutionLog(), ctx, provider)
        acc += r["accepted"]
        lengths.append(len(plan.days))
        ref_lengths.append(len(r["reference_days"]))
        for v in r["violations"]:
            reasons[v["rule"]] = reasons.get(v["rule"], 0) + 1
    return {"n": len(SEEDS), "acceptance_rate": round(acc / len(SEEDS), 4), "violations_by_rule": reasons,
            "mean_plan_days": round(statistics.mean(lengths), 3), "mean_reference_days": round(statistics.mean(ref_lengths), 3)}  # fmt: skip


def orchestrator_eval(provider):
    e = final_engine(CUR, WORLD)
    sc = get_scenario("calm", e, e.init_learner(), goal=goal_of(e), budget=15, horizon=14)
    base, orch, recs = [], [], []
    for s in SEEDS:
        base.append(run_episode(e, s, sc, "adapt", PROFILES["nominal"], WORLD))

        def nxt(st, log, ctx, review_urgency=None):
            return orchestrated_next(e, st, log, ctx, provider, review_urgency, recs)

        orch.append(run_episode(e, s, sc, "adapt", PROFILES["nominal"], WORLD, next_fn=nxt))

    def fm(rs):
        return round(
            sum(r["false_mastered"] for r in rs) / max(1, sum(r["believed_mastered"] for r in rs)),
            4,
        )

    return {
        "decisions": len(recs),
        "agreement_with_tier_order": round(sum(r["choice"] == r["default"] for r in recs) / max(1, len(recs)), 4),
        "fallback_rate": round(sum(r.get("source") == "fallback" for r in recs) / max(1, len(recs)), 4),
        "choices": {k: sum(r["choice"].split(":")[0] == k for r in recs) for k in ("continue", "remediate", "review", "rediagnose", "consolidate")},
        "false_mastery": {"adapt_final": fm(base), "orchestrated": fm(orch)},
        "utilisation": {"adapt_final": round(statistics.mean(r["minute_utilisation"] for r in base), 4),
                        "orchestrated": round(statistics.mean(r["minute_utilisation"] for r in orch), 4)},
        "goal_mastery_vs_adapt_final": paired_summary([float(r["goal_mastered"]) for r in orch], [float(r["goal_mastered"]) for r in base]),
        "executed_violations": sum(r["executed_prereq_violations"] for r in orch),
    }  # fmt: skip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="stub")
    ap.add_argument("--populate", action="store_true", help="allow network calls to fill the cache")
    a = ap.parse_args()
    live = a.provider != "stub"
    try:
        provider = make_provider(
            a.provider, cache_dir=CACHE if live else None, replay_only=live and not a.populate
        )
    except ProviderError as e:
        print(f"provider unavailable: {e}")
        return 2
    t0 = time.time()
    out = {
        "metadata": {**stamp(), "provider": a.provider, "model": getattr(provider, "model", None), "seeds": "odd 2001-2099 (50)",
                     "label": "exploratory" if live else "stub plumbing run: not an agent evaluation"},
        "ranker_L4": ranker_eval(provider),
        "proposer_M3": proposer_eval(provider),
        "orchestrator_N3": orchestrator_eval(provider),
    }  # fmt: skip
    out["metadata"]["runtime_s"] = round(time.time() - t0, 1)
    name = a.provider.replace(":", "_")
    with open(os.path.join(repo_root, f"experiments/results/w8_agent_eval_{name}.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in out.items() if k != "metadata"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
