# A2 Bandit Ranking Policy — formal specification (D53)

The bandit is AdaptEngine's **single feedback-driven policy** (Assignment §2.2.11). It is off by
default (`EngineConfig.ranking_policy = "deterministic"`, `Engine(policy=None)`).

| Element | Definition (implementation) |
|---|---|
| Decision point | Each slot the scheduler fills from the **new-content tier** (Tier 2). Remediation (Tier 0), due reviews (Tier 1) and consolidation (Tier 3) keep their deterministic order. Hook: `planner/schedule._policy_pick`. |
| Action set | The deterministic scheduler's Tier 2 candidates that are prerequisite-safe and fit the remaining day budget, capped at the top K = 5 by deterministic score (`policy_top_k`). |
| Observations | `policy/features.extract` (17 values, scaled to about [0, 1]): bias; p; responses (/10, capped); days since practice (/14, capped; the planner's clock is in days, so this replaces "minutes since practice"); projected P(correct); \|P(correct) − 0.75\|; unlock value u/(1+u); review urgency (/5); goal-path flag; lesson flag; difficulty class (easy/medium/hard one-hot); deterministic rank (/4); day index; remaining days; remaining budget fraction. Non-finite features raise and trigger the fallback. |
| Policy | LinUCB scores s = wᵀx + α √(xᵀA⁻¹x) (w = A⁻¹b) and a softmax with temperature τ: P(i) = exp(s_i/τ)/Σ exp(s_j/τ). α = 0.3, τ = 0.1. Propensities are exact. The draw uses a keyed SHA-256 uniform of (policy seed, config seed, day, slot, minutes left), so runs are reproducible. Pure Python (`policy/bandit.py`). |
| Logged per decision | Trace record `POLICY_SELECTED`: candidates, propensities (unrounded), features, chosen id and its propensity, deterministic choice, policy name and version (`linucb-softmax/<mode>/n<updates>`). Experiments write executed decisions to `experiments/results/policy_logs/*.jsonl` with the observed reward. |
| Reward | Learning progress on the chosen activity's concept: change in the rolling success rate over the last w = 4 attempts (after vs before the new answer), clipped to [−1, 1]; 0 for a concept's first attempt. A lesson's reward is the learning progress at the next exercise on that concept (0 if there is none). Correctness itself is not the reward. Computed by the caller (`experiments/policy_runner.py`), because it needs the observed answer. |
| Update rule | Online ridge regression (λ = 1): Sherman–Morrison update of A⁻¹ and b += r x, only in mode `updating`. |
| Variants | `deterministic` (reference, no hook), `bandit_frozen` (weights from `config/policy_frozen.json`, fixed), `bandit_updating` (starts from the frozen weights, keeps learning within one learner), `random` (uniform, propensity 1/K). |
| Fallback | Deterministic choice with a `POLICY_FALLBACK` record when: the policy is disabled; ≤ 1 candidate (`SINGLE_CANDIDATE`); features are missing or non-finite; the policy raises; it returns an id that was not offered (`StopIteration`) or one that does not fit the remaining budget. |
| Safety | The policy receives only engine-filtered candidates; the engine re-checks the returned id (offered, fits). Tests assert 0 executed prerequisite violations and 0 budget violations for every variant (`tests/test_policy.py`). |
| Training | `experiments/train_policy.py`: one `updating` policy, zero initial weights, shared across learners, run sequentially on even seeds 6000–6398 in S1 and S4 × 4-node and 8-node. |
| Evaluation | `experiments/run_policy_eval.py`: paired odd seeds, S1/S4 × 4-node/8-node, adapt_final, B = 15, calm, 14 days; goal and all-required mastery vs deterministic; executed violations; OPE (IPS, SNIPS, DR; `experiments/ope.py`) of the frozen policy from the random and updating logs vs its simulated value. Results: `experiments/results/w8_policy_eval.json`, notes §9. |

The LLM ranker (A2′, D55) implements the same `RankingPolicy` interface but is **non-learning**: no reward, no update, no memory, propensity 1.0 (`policy/agent.py`).
