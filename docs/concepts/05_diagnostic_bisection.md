# 05 — The bisection diagnostic and confirmation checks

## Idea

The sweep ([04](04_diagnostic_sweep.md)) learns about one concept per answer. The bisection
diagnostic instead treats what the learner knows as one knowledge state $K$: a set of concepts closed
under prerequisites. Every answer reweights all states at once, so a wrong answer on C3 also lowers
the belief in C4, and a right answer on C3 raises C1 and C2. Questions are chosen like a binary
search over the states, and the run stops when one state is probable enough. Concepts that were only
inferred, not asked, can then be confirmed with a few short checks in the plan instead of being
studied from scratch.

## Notation

| Symbol | Meaning | Config key / code name |
|---|---|---|
| $\mathcal{S}$ | concepts in scope | `select_scope`, `bisection_scope` |
| $K$, $\mathcal{K}$ | a knowledge state (down-set of the DAG restricted to $\mathcal{S}$) and the set of all of them | `enumerate_states` |
| $\pi(K)$ | prior or posterior probability of $K$ | `ExactPosterior.w` |
| $a_c$, $b_c$ | per-concept factors: weight if $c \in K$, if $c \notin K$ | `factors` |
| $h_a$, $\ell_a$ | $P(\text{correct} \mid c \in K)$ and $P(\text{correct} \mid c \notin K)$ for item $a$ on $c$ | `predict_correct(1, d)`, `predict_correct(0, d)` |
| $q_c$ | posterior marginal $P(c \in K)$; becomes $p_c$ | `post.marginal(c)` |
| $I_a$ | information of item $a$ about the state, $I(Y; K)$ | `item_information` |
| $\pi^{*}$ | posterior mass of the most probable state | `top_state()[1]` |
| $q_{\text{bit}}$ | questions per bit | `budget()`, `bisection_alpha` |
| $\varepsilon$ | assumed error rate of a confirmation; confirm at $1 - \varepsilon$ | `confirm_epsilon` |
| $P_{\text{pass}}$ | probability that all planned checks are answered correctly | `plan_checks` |
| $T_{\text{checks}}$, $T_{\text{full}}$ | minutes of the checks and of the normal workload | `route_concept` |

## Maths

**Scope (D54).** With goal concepts and `bisection_scope = "goal_ancestors"` (default):
$\mathcal{S}$ = goals ∪ their ancestors. With no goal: all concepts. With goals and
`bisection_scope = "all"`, the code uses the goal concepts only. Concepts outside $\mathcal{S}$ are
untouched.

**Prior (D51).** Each state gets the product of per-concept factors,
$\pi_0(K) \propto \prod_{c \in K} a_c \prod_{c \in \mathcal{S} \setminus K} b_c$:
- `uniform_states` (default): $a_c = b_c = 1$, so $\pi_0(K) = 1/|\mathcal{K}|$.
- `independent_p0` (experiment arm): $a_c = p_0$, $b_c = 1 - p_0$, restricted to down-sets.
- Earlier answers in the input state multiply in $a_c \leftarrow a_c\,p_c/p_0$,
  $b_c \leftarrow b_c\,(1-p_c)/(1-p_0)$ (posterior odds over prior odds; $p$ and $p_0$ clipped to
  $[10^{-6}, 1 - 10^{-6}]$). `prior_mode` and `population_p0` are not used here.

**Likelihood and update.** An item $a$ on concept $c$, answered $y$, uses the active item model with
no learning: $h_a = 1 - s(d)$, $\ell_a = g(d)$ for the heuristic. Then

$$\pi(K) \leftarrow \frac{\pi(K)\,P(y \mid K)}{Z}, \qquad P(y = 1 \mid K) = h_a \ \text{if } c \in K, \quad \ell_a \ \text{if } c \notin K$$

and the marginal is $q_c = \sum_{K \ni c} \pi(K)$. Because states are down-sets,
$q_{\text{child}} \le q_{\text{parent}}$.

**Question choice (D52).** Among unasked exercises of concepts with fewer than
`bisection_concept_cap` answers, maximise

$$I_a = H\big(q_c h_a + (1 - q_c)\ell_a\big) - q_c H(h_a) - (1 - q_c) H(\ell_a)$$

The answer depends on $K$ only through $1[c \in K]$, so this is the information about the whole state;
it equals the sweep's EIG evaluated at the joint marginal $q_c$. Ties use `candidate_sort_key` (D10).

**Stopping (D55, D56).** Checked before each question, in this order:
1. $\pi^{*} \ge$ `bisection_stop_confidence` (0.80) → `CONFIDENT`;
2. items asked $\ge n_{\max}$ (or `item_limit`) → `GLOBAL_CAP`;
3. best $I_a < 10^{-9}$ or no askable item → `NO_ITEMS`.

$$n_{\max} = \min\Big(\#\text{items},\ \max\big(n_{\min},\ \min(n_{\text{ceil}},\ \lceil \text{bits} \cdot q_{\text{bit}} \rceil)\big)\Big), \qquad q_{\text{bit}} = \frac{1}{\max_a I_a\big|_{q = 0.5}}$$

with bits $= \log_2 |\mathcal{K}|$ in exact mode, or the chain-cover bound
$\sum_j \log_2(L_j + 1)$ over a minimum chain cover in sampling mode. `bisection_alpha` replaces
$q_{\text{bit}}$ when set.

**Inference (D53).** Exact enumeration while $|\mathcal{K}| \le$ `bisection_exact_state_limit`
(5000). Above it, `SamplingPosterior`: `bisection_samples` (4000) weighted particles seeded by
`bisection_seed`, moved by a Metropolis chain on down-sets (add a concept whose prerequisites are in
$K$, remove one with no dependants in $K$), resampled when the effective sample size drops below
half; marginals are Rao-Blackwellised.

**Output.** Every in-scope concept gets $p_c = q_c$. Responses, streak, status and attempt ids
change only for asked concepts. Per-concept stop reason: `INFERRED` (never asked), `CONCEPT_CAP`
(cap reached), otherwise the run's reason. `info` holds `mode`, `n_states`, `bits`, `n_max`,
`q_bit`, `top_state`, `top_state_p`, `scope`.

### Confirmation checks (D57, on with `confirm_diag_confident`, set by `bisection_config()`)

**Flags at the end of the diagnostic** (`BisectionDiagnostic._flag`), per in-scope concept not yet
evidence-mastered:
- asked directly at least `confirm_min_direct` (1) times and $p_c \ge 1 - \varepsilon = 0.98$ →
  `confirmed`;
- otherwise, if some exercise of $c$ could lift $p_c$ to $0.98$ with at most `confirm_max_checks`
  (3) correct answers (`checks_to_confirm`, transition 0) → `diag_confident`.

**Epsilon test after each direct answer** on a `diag_confident` concept
(`confirmation_flags` in `src/adaptengine/learner/evidence.py`): with $p_{\text{obs}}$ = the observation-only update of
$p$, set `confirmed` if $p_{\text{obs}} \ge 1 - \varepsilon$ and responses $\ge$ `confirm_min_direct`;
a wrong answer that leaves $0.98$ out of reach within `confirm_max_checks` clears `diag_confident`.
Mastered = D4 **or** (`confirmed` and $p \ge \theta$), in `is_evidence_mastered`.

**Planner** (`src/adaptengine/planner/workload.py` calls `route_concept` in `src/adaptengine/planner/confirmation.py` for a
`diag_confident` concept not in remediation):
1. `plan_checks` repeatedly adds the unseen exercise with the largest EIG at the running
   $p_{\text{obs}}$ and assumes it is answered correctly, until $p_{\text{obs}} \ge 0.98$, at least
   one check is chosen, and responses + checks $\ge$ `confirm_min_direct`. More than
   `confirm_max_checks` needed, or no item left → normal study. When unseen items run out,
   `allow_exercise_repeats` (D41) allows the least recently attempted one.
2. $P_{\text{pass}} = p \prod_i h_i + (1 - p) \prod_i \ell_i$ over the chosen checks.
3. Checks replace the workload iff

$$T_{\text{checks}} < P_{\text{pass}} \cdot T_{\text{full}}$$

This rule is in code: the module docstring and `route_concept` (`if not t_checks < p_pass * t_full`)
in `src/adaptengine/planner/confirmation.py`; D57 calls it "the minutes rule". The trace record has
reason `CONFIRMATION_CHECK`. Gating stays strict: dependants wait until the checks are done.

## Worked example

4-node curriculum (C1, C2 → C3 → C4), `bisection_config()`, cold-start learner, goal C4. Scripted
learner: correct on C1 and C2 items, wrong otherwise.

Scope = {C1, C2, C3, C4}; exact mode with $|\mathcal{K}| = 6$ states: ∅, {C1}, {C2}, {C1, C2},
{C1, C2, C3}, {C1, C2, C3, C4}. Uniform prior $1/6 = 0.1667$; starting marginals C1 0.6667,
C2 0.6667, C3 0.3333, C4 0.1667. Best item at $q = 0.5$: E-C1-0.8 ($h = 0.75$, $\ell = 0.06$,
$I = 0.4044$), so $q_{\text{bit}} = 2.4726$; bits $= \log_2 6 = 2.585$; $n_{\max} = \lceil 6.39 \rceil = 7$.

| # | Item | $I_a$ | Answer | Top state | $\pi^{*}$ | $p$: C1, C2, C3, C4 |
|---|---|---|---|---|---|---|
| 0 | — | — | — | (∅, tied) | 0.1667 | 0.6667, 0.6667, 0.3333, 0.1667 |
| 1 | E-C3-0.8 | 0.3800 | wrong | ∅ | 0.2207 | 0.5587, 0.5587, 0.1174, 0.0587 |
| 2 | E-C1-0.8 | 0.3937 | correct | {C1} | 0.3715 | 0.9406, 0.5988, 0.1976, 0.0988 |
| 3 | E-C2-0.8 | 0.3808 | correct | {C1, C2} | 0.5888 | 0.9491, 0.9491, 0.3132, 0.1566 |
| 4 | E-C3-0.6 | 0.3283 | wrong | {C1, C2} | 0.7768 | 0.9329, 0.9329, 0.0939, 0.0470 |
| 5 | E-C3-0.4 | 0.1264 | wrong | {C1, C2} | 0.8414 | 0.9273, 0.9273, 0.0186, 0.0093 |

The first question lands mid-DAG (C3). The wrong answer on C3 also lowers C4, and the right answer
on C1 raises C3 (0.1174 → 0.1976). After 5 of 7 items $\pi^{*} = 0.8414 \ge 0.80$: stop `CONFIDENT`.

| Concept | $p$ | Items | Stop reason | `diag_confident` | `confirmed` |
|---|---|---|---|---|---|
| C1 | 0.9273 | 1 | CONFIDENT | True | False |
| C2 | 0.9273 | 1 | CONFIDENT | True | False |
| C3 | 0.0186 | 3 | CONCEPT_CAP | False | False |
| C4 | 0.0093 | 0 | INFERRED | False | False |

C1 is not confirmed ($0.9273 < 0.98$), but one correct answer could confirm it
(`checks_to_confirm`: E-C1-0.2 → 2, E-C1-0.4/0.6/0.8 → 1), so it is flagged. C4 (never asked) is
inferred unmastered.

**Checks in the plan** (`eng.plan`, budget 15, deadline day 10, no `done_ids`): for C1 the planner
picks E-C1-0.2 first (EIG 0.1121 at $p = 0.9273$, the largest), which lifts $p_{\text{obs}}$ only to
0.9795 $< 0.98$, so it adds E-C1-0.4 (EIG 0.0348 vs 0.0319 at 0.9795); after both, 0.9956.
$P_{\text{pass}} = 0.7125$, $T_{\text{checks}} = 2$ min $< 0.7125 \times 6 = 4.28$ min, so the
trace records `CONFIRMATION_CHECK` with items E-C1-0.2, E-C1-0.4 (C2 the same). Plan FEASIBLE:
day 1 E-C1-0.2, E-C1-0.4, E-C2-0.2, E-C2-0.4, L-C3, E-C3-0.2, E-C3-0.4 (11 min); day 2 L-C4,
E-C4-0.2, E-C4-0.4, E-C4-0.6 (9 min).

<details><summary>How these numbers were produced</summary>

Run from the repo root: `.venv/bin/python <scratchpad>/docs/scripts/c05_bisect.py`

```python
from adaptengine.api import Engine
from adaptengine.core.config import bisection_config
from adaptengine.core.schema import PlanContext
from adaptengine.diagnostic.bisection import item_information
from adaptengine.diagnostic.scoring import compute_eig
from adaptengine.learner.evidence import checks_to_confirm

cfg = bisection_config()
eng = Engine.from_files("data/curriculum/curriculum_4node.json",
                        "data/curriculum/activities_4node.json", config=cfg)
answer = lambda a: a.target_concept in {"C1", "C2"}
st, goal = eng.init_learner(), ["C4"]
for aid in ["E-C1-0.2", "E-C1-0.4", "E-C1-0.6", "E-C1-0.8"]:
    d = eng.activities[aid].difficulty
    hi, lo = eng.model.predict_correct(1.0, d), eng.model.predict_correct(0.0, d)
    print(aid, f"hi={hi:.4f} lo={lo:.4f} I(0.5)={item_information(0.5, hi, lo):.4f}")
r = eng.diagnose(st, answer, goal_concepts=goal, session_id="ex")
print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.info.items()})
for n in range(r.total_items + 1):  # prefix replays give the posterior after each answer
    rr = eng.diagnose(st, answer, goal_concepts=goal, session_id="ex", item_limit=n)
    print(n, rr.info["top_state"], f"{rr.info['top_state_p']:.4f}",
          {c: round(cr.p, 4) for c, cr in rr.concept_results.items()})
for x in r.item_log:
    print(x.activity_id, x.response, f"I={x.eig:.4f}", f"p_c {x.p_before:.4f}->{x.p_after:.4f}")
for c, cr in r.concept_results.items():
    s = r.state.concepts[c]
    print(c, f"{cr.p:.4f}", cr.n_items, cr.stop_reason.name, s.diag_confident, s.confirmed)
p = r.state.concepts["C1"].p
print({a: checks_to_confirm(p, eng.activities[a].difficulty, eng.model, cfg)
       for a in ["E-C1-0.2", "E-C1-0.4", "E-C1-0.6", "E-C1-0.8"]})
po = p
for aid in ["E-C1-0.2", "E-C1-0.4"]:  # the checks the planner picks, by EIG at the running p
    print(f"{po:.4f}", {a: round(compute_eig(po, eng.activities[a], cfg, eng.model), 4)
                        for a in ["E-C1-0.2", "E-C1-0.4", "E-C1-0.6", "E-C1-0.8"]})
    po = eng.model.update(po, eng.activities[aid].difficulty, True, 0.0)
print("after two correct checks", f"{po:.4f}")
plan = eng.plan(r.state, PlanContext(goal="C4", deadline_day=10, budget=15))
print(plan.status.name)
for t in plan.trace:
    if t.get("decision") == "CONFIRMATION":
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in t.items()})
for day in plan.days:
    print(day.day, day.activities, day.duration)
```
</details>

## In the code

| Function or class | File | Config key | Default |
|---|---|---|---|
| `DIAGNOSTICS`, `Engine.diagnose` | `src/adaptengine/diagnostic/__init__.py`, `src/adaptengine/api.py` | `diagnostic_method` | `"sweep"` (`"bisection"` in `bisection_config()`) |
| `bisection_config` | `src/adaptengine/core/config.py` | `diagnostic_method`, `confirm_diag_confident` | `"bisection"`, True |
| `select_scope` | `src/adaptengine/diagnostic/knowledge_space.py` | `bisection_scope` | `"goal_ancestors"` |
| `BisectionDiagnostic._factors` | `src/adaptengine/diagnostic/bisection.py` | `bisection_prior`, `p0` | `"uniform_states"`, 0.20 |
| `enumerate_states`, `ExactPosterior` | `src/adaptengine/diagnostic/knowledge_space.py` | `bisection_exact_state_limit` | 5000 |
| `SamplingPosterior`, `chain_cover_bits` | `src/adaptengine/diagnostic/knowledge_space.py` | `bisection_samples`, `bisection_seed` | 4000, 0 |
| `item_information`, `INFO_FLOOR` | `src/adaptengine/diagnostic/bisection.py` | — | $10^{-9}$ |
| `BisectionDiagnostic.run` | `src/adaptengine/diagnostic/bisection.py` | `bisection_stop_confidence`, `bisection_concept_cap` | 0.80, 3 |
| `BisectionDiagnostic.budget` | `src/adaptengine/diagnostic/bisection.py` | `bisection_n_min`, `bisection_n_ceiling`, `bisection_alpha` | 6, 40, None |
| `BisectionDiagnostic._flag` | `src/adaptengine/diagnostic/bisection.py` | `confirm_epsilon`, `confirm_min_direct`, `confirm_max_checks` | 0.02, 1, 3 |
| `checks_to_confirm`, `confirmation_flags` | `src/adaptengine/learner/evidence.py` | same | same |
| `is_evidence_mastered` | `src/adaptengine/learner/state.py` | `confirm_diag_confident`, `theta` | False, 0.85 |
| `plan_checks`, `route_concept` | `src/adaptengine/planner/confirmation.py` | `confirm_*`, `allow_exercise_repeats` | as above, True |
| routing hook | `src/adaptengine/planner/workload.py` | `confirm_diag_confident` | False |

## Tests

- `tests/unit/diagnostic/test_bisection.py` — config validation, registry, noiseless chain as binary
  search (`test_noiseless_chain_is_binary_search_f1_tc4`), budget formula
  (`test_budget_formula_f1_tc6`), out-of-scope untouched, mid-DAG first question, `item_limit`
  prefix, earlier evidence, `independent_p0` arm, sampling on a wide DAG.
- `tests/unit/diagnostic/test_knowledge_space.py` — state counts, limit, 8-node starting marginals,
  hand-computed posterior, marginals respect prerequisites, sampling vs exact, seed determinism,
  bits bound, goal scope.
- `tests/unit/planner/test_confirmation.py` — flags, epsilon test, mastered-with-confirmation,
  routing, dependants wait for checks, closed loop, repeats when items run out, CLI parity,
  `test_unconfirmed_concept_always_gets_a_check_regression`.
- `tests/integration/test_closed_loop_planners.py`, `experiments/tests/unit/test_diagnostics.py`,
  `frontend/api/tests/test_parity.py`, `frontend/api/tests/test_sessions.py` — bisection end to end.

## Decisions

[D49](../project/DECISIONS.md#d49) bisection as a registered option,
[D50](../project/DECISIONS.md#d50) down-set knowledge states,
[D51](../project/DECISIONS.md#d51) uniform prior, [D52](../project/DECISIONS.md#d52) question choice,
[D53](../project/DECISIONS.md#d53) exact or sampling inference, [D54](../project/DECISIONS.md#d54)
scope, [D55](../project/DECISIONS.md#d55) stopping, [D56](../project/DECISIONS.md#d56) budget,
[D57](../project/DECISIONS.md#d57) confirmation and the minutes rule,
[D10](../project/DECISIONS.md#d10) ties, [D41](../project/DECISIONS.md#d41) repeats,
[D58](../project/DECISIONS.md#d58) the evaluation plan.

## Limitations

- The model assumes every answer depends only on whether the item's concept is in $K$, with the
  item model's guess and slip; there is no learning, partial mastery or forgetting during the run.
- The uniform prior over states is set by the DAG shape, not fitted to any population: on 8-node
  (18 states) every learner starts with C1 at 16/18 = 0.89 and C8 at 2/18 = 0.11
  (`test_8node_starting_marginals_f1_tc12`).
- The planner picks checks by EIG, not by the fewest checks: in the example two checks were planned
  for C1 although one correct answer on E-C1-0.4 alone would have reached 0.98.
- E2: on scripted learners bisection's Brier is far below the sweep's in all 6 tested cells (−0.229
  to −0.475, E2 H1); in the simulated worlds it is never below the prior-only baseline (0 of 15
  cells, E2 H3), and it asks many more questions
  ([T3](../../experiments/report/tables/T3.md), [T4](../../experiments/report/tables/T4.md)).
- E4: confirmation checks are weak evidence in the simulator. 60–73 % of confirmations happen
  while the simulated learner's $\theta^{\text{true}}_c$ is below the true-mastery bar 0.70 (E4 H3
  failed; limit 0.10), because an easy check item is often answered correctly below that bar under
  the 2PL simulator. Bisection with confirmation raises goal mastery but its total-minutes saving
  is not significant (E4 H2, [T9](../../experiments/report/tables/T9.md),
  [T10](../../experiments/report/tables/T10.md)). See
  [NOTES Outcomes](../../experiments/NOTES.md#outcomes).

## Values checked

Read with `from adaptengine.core.config import DEFAULT_CONFIG, bisection_config` and
`from adaptengine.diagnostic.bisection import INFO_FLOOR`; all run on 2026-11-21.

- `DEFAULT_CONFIG.diagnostic_method` → `'sweep'`; `bisection_config().diagnostic_method` → `'bisection'`
- `DEFAULT_CONFIG.confirm_diag_confident` → False; `bisection_config().confirm_diag_confident` → True
- `DEFAULT_CONFIG.bisection_prior` → `'uniform_states'`
- `DEFAULT_CONFIG.bisection_scope` → `'goal_ancestors'`
- `DEFAULT_CONFIG.bisection_exact_state_limit` → 5000
- `DEFAULT_CONFIG.bisection_samples` → 4000
- `DEFAULT_CONFIG.bisection_seed` → 0
- `DEFAULT_CONFIG.bisection_stop_confidence` → 0.8
- `DEFAULT_CONFIG.bisection_n_min` → 6
- `DEFAULT_CONFIG.bisection_n_ceiling` → 40
- `DEFAULT_CONFIG.bisection_alpha` → None
- `DEFAULT_CONFIG.bisection_concept_cap` → 3
- `DEFAULT_CONFIG.confirm_epsilon` → 0.02
- `DEFAULT_CONFIG.confirm_max_checks` → 3
- `DEFAULT_CONFIG.confirm_min_direct` → 1
- `DEFAULT_CONFIG.allow_exercise_repeats` → True
- `DEFAULT_CONFIG.p0` → 0.2; `DEFAULT_CONFIG.theta` → 0.85
- `INFO_FLOOR` → 1e-09
