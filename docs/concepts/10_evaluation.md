# 10 — How the engine is evaluated

## Idea

The engine's probabilities come from its own model (BKT, [02](02_mastery_bkt.md)), so that model
cannot be used to judge the engine: a planner would look good by its own assumptions. The study
therefore runs the engine against simulated learners whose hidden ability $\theta^{\text{true}}_c$,
responses, learning and forgetting follow rules that differ from the engine's, and asks whether
those learners end up knowing the goal, and whether anything was taught out of order. Every
learner is built from a seed, so the same learner meets every arm and every result can be re-run.

## Notation

| Symbol | Meaning | Code name |
|---|---|---|
| $\theta^{\text{true}}_c$ | the simulated learner's hidden ability on concept $c$, in $[0, 1]$ (S4: 0 or 1) | `SimLearner.theta` |
| $a$ | 2PL discrimination, $a = 3.0$ for every profile | `Profile.a` |
| $\theta^{\star}$ | true-mastery bar: the learner "knows" $c$ when $\theta^{\text{true}}_c \ge 0.70$ | `TRUE_MASTERY` |
| $\gamma_L$, $\gamma_E$ | gain from a lesson / an exercise, as a share of the remaining gap | `lesson_gain`, `exercise_gain` |
| $\rho_c$ | readiness of $c$ (S1 only) | `SimLearner.readiness` |
| $R(\Delta t)$ | simulator retention after $\Delta t$ days | `SimLearner.retention` |
| $h$ | simulator half-life in days (profile or S3 draw); not the engine's `half_life_days` | `half_life` |
| $\tilde g$, $\tilde s$ | S4 guess and slip of the simulator (not the engine's $g(d)$, $s(d)$) | `S4_BKT`, `class_params` |
| $u$ | a keyed uniform draw in $[0, 1)$ | `keyed_uniform` |

Other symbols ($c$, $\mathrm{pre}(c)$, $p$, $d$, $B$, $D$, $\sigma$, $N$) are as in the
[notation table](README.md#notation).

## Maths

**Responses, worlds S0–S3 (2PL).** An exercise of difficulty $d$ on concept $c$ is answered
correctly with

$$P(\text{correct}) = \sigma\big(a\,(\theta^{\text{true}}_c - d)\big), \qquad a = 3.0,$$

with the logit clamped to $[-10, 10]$ (the clamp never binds at $a = 3$, since
$|\theta^{\text{true}}_c - d| \le 1$). The answer is correct when $u < P(\text{correct})$. The
`high_slip` profile then turns a correct answer wrong with probability 0.15 (a second keyed draw);
it never turns a wrong answer right.

**Responses, world S4 (binary know / don't know).** $\theta^{\text{true}}_c \in \{0, 1\}$ and

$$P(\text{correct}) = 1 - \tilde s \ \text{ if } \theta^{\text{true}}_c = 1, \qquad P(\text{correct}) = \tilde g \ \text{ if } \theta^{\text{true}}_c = 0.$$

In S4, $\tilde g = 0.30(1-d)$ and $\tilde s = 0.05 + 0.25\,d$: the engine's own heuristic, so S4 is
the world where the engine's model is right. In S4-assist09, $\tilde g$ and $\tilde s$ come per D6
difficulty class (easy $d < 0.35$, medium $< 0.65$, hard) from `config/fitted_assist09.json`:
guess 0.369 / 0.147 / 0.058, slip 0.132 / 0.342 / 0.646.

**Worlds.** Each changes one thing relative to S0.

| World | Initial $\theta^{\text{true}}_c$ | How it differs from the engine's model |
|---|---|---|
| S0 | $U(0.10, 0.90)$ per concept, independent, rounded to 4 decimals | continuous ability and 2PL responses (the engine assumes binary BKT) |
| S1 | as S0 | gains are multiplied by readiness $\rho_c$, so learning $c$ before its prerequisites is slow |
| S2 | $g \sim U(0.2, 0.8)$ per learner, $\theta^{\text{true}}_c = \min(0.95, \max(0.05, g + \mathcal{N}(0, 0.10)))$ | abilities correlated across concepts |
| S3 | as S0 | every learner forgets, with half-life $h \sim U(5, 30)$ days drawn per learner (unless the profile sets $h$) |
| S4 | 1 with probability $p_0 = 0.20$, else 0 | binary BKT learner with the engine's heuristic: well specified |
| S4-assist09 | 1 with probability 0.7415, else 0 | S4 with fitted ASSISTments guess/slip per class and exercise transition 0.0725 (lesson transition stays 0.20) |

**Learning.** After every lesson or exercise (right or wrong), in S0–S3:

$$\theta' = \theta^{\text{true}}_c \cdot R(\Delta t), \qquad \theta^{\text{true}}_c \leftarrow \min\big(0.98,\ \theta' + \gamma\,\rho_c\,(1 - \theta')\big)$$

with $\gamma = \gamma_L$ for a lesson and $\gamma_E$ for an exercise. Readiness is 1 except in S1:

$$\rho_c = \min_{q \in \mathrm{pre}(c)} \sigma\big(10\,(\theta^{\text{true}}_q - 0.70)\big) \quad (\rho_c = 1 \text{ if } c \text{ has no prerequisites}).$$

In S4 a lesson flips 0 to 1 with probability 0.20 and an exercise with probability 0.05 (0.0725 in
S4-assist09). The answer to an exercise is drawn before its learning step.

**Forgetting.** A power law,

$$R(\Delta t) = \frac{1}{1 + \Delta t / h},$$

applied when a concept is next practised and once at the deadline. It is a different family from
the engine's $r = 2^{-\Delta t/h}$ ([08](08_review_remediation.md)) on purpose, so review is not
judged by its own curve. There is no forgetting when $h$ is unset (nominal, high_slip and
rapid_learner profiles outside S3) and none in S4.

**Profiles.**

| Profile | $a$ | extra slip | $\gamma_L$ | $\gamma_E$ | $h$ (days) |
|---|---|---|---|---|---|
| nominal | 3.0 | 0 | 0.18 | 0.05 | none |
| high_slip | 3.0 | 0.15 | 0.18 | 0.05 | none |
| fast_forgetter | 3.0 | 0 | 0.18 | 0.05 | 7.0 |
| rapid_learner | 3.0 | 0 | 0.30 | 0.10 | none |

**Outcome.** The goal counts as mastered when $\theta^{\text{true}}_{\text{goal}} \ge 0.70$ at the
effective deadline, after the final forgetting step. "All required" means every concept in the goal
and its ancestors reaches 0.70.

**Arms.** An arm is a set of `EngineConfig` overrides on `DEFAULT_CONFIG` plus a harness mode
(D99). Modes: *closed* (call `Engine.next_activities` at the start of each day and after every wrong
answer; only today's slice is executed), *no_replan* (the first plan, or its best-effort days when
not FEASIBLE, never replanned), *static* (no engine: the goal and its ancestors in topological
order, lessons then exercises by id, next-fit packed into the budget). Under no_replan and static,
a missed day's scheduled activities are dropped; the closed loop plans them again.

| Experiment | Arms |
|---|---|
| E1 | `adapt`, `no_review` (review urgency 0), `no_replan`, `static`; in forgetting_21 also `adapt_h7`, `no_review_h7` (`half_life_days=7.0`) |
| E2 | engine `sweep` and `bisection`; harness-side `prior_only`, `fixed@n`, `irt_cat_global@n`, `irt_cat_per_concept@n` (n = bisection's question count, `experiments/core/diagnostics.py`) |
| E3 | `heuristic`, `fitted_assist09`, `fitted_ct` (`model_profile`) |
| E4 | `sweep`, `bisect_noconfirm`, `bisect_confirm`, each also `_fitted`; the diagnostic runs first on the goal and its ancestors (D54) |
| E5 | `greedy`, `hybrid`, `cpsat` (`planner_method`), and each `_bisect_confirm` |
| E6 | `baseline` and one-parameter scans, a $\theta \times k$ grid and the mastery criteria (`e6_configs()`) |

**Safety audits.** *Executed* (primary, D46): replay the real execution log through
`Engine.record` and count each completed or failed activity whose concept has a direct
prerequisite that was not evidence-mastered (D4, or confirmed under D57) in the recorded state at
that moment. *Plan-level* (secondary): every plan the engine makes (first plan and each replan) is
checked for prerequisite order (a prerequisite counts as unlocked if evidence-mastered now, reached
on the planner's optimistic replay of the schedule, or confirmed once all its scheduled checks
pass), days over the budget in force (less minutes already used today), and days after the
effective deadline. Static is checked only by the executed audit.

**Scenarios and horizon.** Budgets $B \in \{5, 10, 15, 30\}$. Deadline $D$ = new-content days of an
uncapped plan (deadline 60, maintenance reviews excluded) + 2, minimum 3. Events fall on day 2:

| Scenario | Event |
|---|---|
| calm | none |
| missed_day / missed_2days | day 2 missed / days 2 and 3 missed |
| budget_drop | budget falls to the next lower allowed budget (not run at $B = 5$) |
| budget_crash | budget falls to 5 (run only at $B = 30$) |
| deadline_cut / deadline_halved | deadline becomes $D - 1$ / $\max(2, \lfloor D/2 \rfloor)$ |
| forgetting_21 | deadline 21 days, `fast_forgetter` learners |

**Keyed seeding.** Every random draw is $u = $ `Random("|".join(key)).random()` for a key, not a
shared stream. Truth: key `seed|truth` (S2 `seed|S2`, S3 half-life `seed|S3h`, S4 per concept
`(seed, "S4init", c)`). The $n$-th answer to an activity: `(seed, tag, activity_id, n)` with tag
`run` (study) or `diag` (diagnostic); slip `(seed, "slip", activity_id, n)`; S4 learning
`(seed, "S4learn", c, n)`. So two arms that give the same learner the same item see the same draw,
and results do not depend on the number of worker processes.

## Worked example

One S0 learner, seed 1000, nominal profile, 4-node curriculum (goal C4, prerequisites C1, C2 → C3 →
C4), budget 15, calm. The horizon rule gives a deadline of 4 days.

Initial abilities: $\theta^{\text{true}}$ = C1 0.5577, C2 0.1103, C3 0.6860, C4 0.8151. The goal is
already above 0.70 at the start, which the engine does not know (it starts every concept at
$p_0 = 0.20$).

Exercise `E-C4-0.2` ($d = 0.2$): $P(\text{correct}) = \sigma(3 \cdot (0.8151 - 0.2)) = 0.8636$.
One lesson on C4 would move $\theta^{\text{true}}_{C4}$ from 0.8151 to
$0.8151 + 0.18\,(1 - 0.8151) = 0.8484$.

| Arm | Final $\theta^{\text{true}}_{C4}$ | Goal mastered | Minutes | Exercises | Executed violations | Plans checked (violations) |
|---|---|---|---|---|---|---|
| adapt | 0.8632 | yes | 33 | 9 | 0 | 5 (0) |
| static | 0.8765 | yes | 42 | 16 | 5 | — |

Both arms master the goal, so this learner adds 0 to the adapt − static goal-mastery difference
([11](11_study_statistics.md)). Static uses 9 more minutes and does 5 activities before a direct
prerequisite has evidence of mastery.

<details><summary>How these numbers were produced</summary>

`PYTHONPATH=. .venv/bin/python s10_episode.py` from the repository root:

```python
from experiments.core import curricula, scenarios
from experiments.core.arms import E1_ARMS
from experiments.core.episode import run_episode
from experiments.core.simulator import make_learner

eng = curricula.engine("4-node")
goal = curricula.goal_of(eng)                       # C4
sc = scenarios.make_scenario("calm", eng, goal, 15)
print("goal", goal, "horizon", sc.deadline, "events", sc.events)
sim = make_learner(eng, 1000, "S0", "nominal")
print("initial theta_true", sim.theta)
print("P(correct) C4, d=0.2: %.4f" % sim.p_correct("C4", 0.2))
th = sim.theta["C4"]; sim.learn("C4", True, 1)
print("one lesson on C4: %.4f -> %.4f" % (th, sim.theta["C4"]))
for name in ("adapt", "static"):
    r = run_episode(eng, 1000, sc, E1_ARMS[name], "S0", "nominal")
    print(name, {k: r[k] for k in ("goal_theta", "goal_mastered", "minutes", "exec_viol")},
          "exercises", len(r["attempts"]), "plan_checks", r.get("plan_checks"))
```

Output:

```
goal C4 horizon 4 events ()
initial theta_true {'C1': 0.5577, 'C2': 0.1103, 'C3': 0.686, 'C4': 0.8151}
P(correct) C4, d=0.2: 0.8636
one lesson on C4: 0.8151 -> 0.8484
adapt {'goal_theta': 0.8632, 'goal_mastered': True, 'minutes': 33, 'exec_viol': 0} exercises 9 plan_checks {'plans': 5, 'prereq': 0, 'budget': 0, 'deadline': 0}
static {'goal_theta': 0.8765, 'goal_mastered': True, 'minutes': 42, 'exec_viol': 5} exercises 16 plan_checks None
```

</details>

To run the experiments themselves, see [experiments/README.md](../../experiments/README.md).

## In the code

| Function or class | File | Config key | Default value |
|---|---|---|---|
| `SimLearner`, `Profile`, `PROFILES` | `experiments/core/simulator.py` | `Profile.a`, `lesson_gain`, `exercise_gain`, `slip`, `half_life` | 3.0, 0.18, 0.05, 0.0, None |
| `SimLearner.p_correct` | `experiments/core/simulator.py` | logit clamp | $[-10, 10]$ |
| `SimLearner.learn`, `readiness`, `retention`, `settle` | `experiments/core/simulator.py` | `READINESS_K`, `S3_HALF_LIFE` | 10.0, (5.0, 30.0) |
| `TRUE_MASTERY` | `experiments/core/simulator.py` | — | 0.70 |
| `S4_BKT`, `S4_P0`, `assist09_bkt`, `world_spec` | `experiments/core/simulator.py` | `ASSIST09` | `config/fitted_assist09.json` |
| `keyed_uniform`, `make_learner` | `experiments/core/simulator.py` | — | — |
| `Arm`, `E1_ARMS` … `E5_CONFIRM_ARMS`, `e6_configs` | `experiments/core/arms.py` | `MODES` | closed, no_replan, static |
| `SCENARIOS`, `BUDGETS`, `make_scenario`, `horizon`, `profile_for` | `experiments/core/scenarios.py` | `allowed_budgets` | (5, 10, 15, 30) |
| `run_episode`, `static_days` | `experiments/core/episode.py` | — | — |
| `executed_violations`, `plan_violations` | `experiments/core/audit.py` | `theta`, `k_responses` (via D4) | 0.85, 2 |
| `EPISODE_SEEDS`, `HEADLINE_SEEDS`, `DIAG_SEEDS` | `experiments/runners/common.py` | — | 1000–1199, 1000–1999, odd 101–599 |

## Tests

- `experiments/tests/unit/test_simulator.py` — binary S4, correlated S2, S1 readiness, power-law
  retention, truth draw and same-seed answers, high_slip, learning gain and cap.
- `experiments/tests/unit/test_scenarios.py` — events, horizon, budget rules.
- `experiments/tests/unit/test_audit.py` — executed-violation counts and plan-level checks,
  including confirmation checks.
- `experiments/tests/integration/test_episode.py` — closed loop replans after a wrong answer,
  no_replan never replans, static packing, minutes within budget, θ at confirmation.
- `experiments/tests/integration/test_determinism.py` — two runs identical, independent of `--procs`.
- `experiments/tests/integration/test_runners_smoke.py` — every runner end to end in smoke mode.

## Decisions

- [D36](../project/DECISIONS.md#d36) — keyed draws per interaction, four profiles, power-law
  retention, 0.70 true-mastery bar.
- [D37](../project/DECISIONS.md#d37) — the four planner arms adapt, no_review, no_replan, static.
- [D42](../project/DECISIONS.md#d42) — best-effort days, followed by no_replan when a plan is not FEASIBLE.
- [D46](../project/DECISIONS.md#d46) — executed-state audit is the primary safety metric.
- [D47](../project/DECISIONS.md#d47) — worlds S0–S4 and pre-registration.
- [D48](../project/DECISIONS.md#d48) — fitted profiles, used by S4-assist09 and the E3 arms.
- [D54](../project/DECISIONS.md#d54) — diagnostic scope: goal and its ancestors.
- [D98](../project/DECISIONS.md#d98), [D99](../project/DECISIONS.md#d99),
  [D102](../project/DECISIONS.md#d102) — one final study, `DEFAULT_CONFIG` baseline, one change per arm,
  harness now in `experiments/`.

## Limitations

- The simulator is hand-built. $a = 3.0$, the gains, the 0.70 bar and the forgetting law are
  assumptions, not fitted to Python learners; only S4-assist09 uses fitted numbers, and those come
  from school maths (ASSISTments).
- Answers are drawn from the stored $\theta^{\text{true}}_c$; forgetting is applied only when the
  concept is next practised and at the deadline, so an answer is drawn before the decay since the
  last practice.
- Under the 2PL world an easy item is often passed well below 0.70, so confirmation checks are weak
  evidence here (E4 H3 failed: false-pass rate 0.60–0.73; see
  [experiments/NOTES.md](../../experiments/NOTES.md#outcomes)).
- Static ignores evidence and breaks prerequisite order, yet it wins on goal mastery in 158 E1 cells,
  because adapt spends short budgets on prerequisites first
  ([NOTES](../../experiments/NOTES.md#outcomes), [T8](../../experiments/report/tables/T8.md)).
- No real learner is in the loop; real data enter only through E3 Part A and S4-assist09
  ([T5](../../experiments/report/tables/T5.md), [T14](../../experiments/report/tables/T14.md)).

## Values checked

Run with `PYTHONPATH=. .venv/bin/python` from the repository root; all were run and match.

- `experiments.core.simulator.TRUE_MASTERY` → 0.7
- `experiments.core.simulator.READINESS_K` → 10.0
- `experiments.core.simulator.S3_HALF_LIFE` → (5.0, 30.0)
- `experiments.core.simulator.S4_P0` → 0.2
- `experiments.core.simulator.S4_BKT` → {guess_coef 0.3, slip_base 0.05, slip_coef 0.25, t_lesson 0.2, t_ex 0.05}
- `experiments.core.simulator.assist09_bkt()` → p0 0.7415, t_ex 0.072513, class guess easy/medium/hard 0.369083 / 0.146758 / 0.057842, slip 0.132163 / 0.34157 / 0.645722
- `experiments.core.simulator.PROFILES` → as in the profile table (a 3.0; slip 0.15 for high_slip; gains 0.18 / 0.05, rapid_learner 0.30 / 0.10; half_life 7.0 for fast_forgetter)
- logit clamp: literal `max(-10.0, min(10.0, …))` in `SimLearner.p_correct` (read in source; at $a = 3.0$ the largest possible $|$logit$|$ is 3.0)
- `SimLearner(..., world="S4").p_correct(c, 0.4)` → 0.85 (known), 0.18 (unknown); S4-assist09 → 0.6584, 0.1468; S4-assist09 `bkt["t_lesson"]` → 0.2
- `SimLearner(1, ["C1"], profile=PROFILES["fast_forgetter"]).retention(14)` → 0.3333 (engine curve at the same $\Delta t$, $h$: 0.25)
- `experiments.core.scenarios.SCENARIOS` → the eight names above; `BUDGETS` → (5, 10, 15, 30)
- `DEFAULT_CONFIG.allowed_budgets` → (5, 10, 15, 30); `DEFAULT_CONFIG.half_life_days` → 30.0; `DEFAULT_CONFIG.p0` → 0.2 (via `from adaptengine.core.config import DEFAULT_CONFIG`)
- `experiments.core.arms.MODES` → ('closed', 'no_replan', 'static'); `list(E1_ARMS)`, `list(E4_ARMS)`, `list(E5_ARMS)`, `list(E5_CONFIRM_ARMS)` → as in the arms table
- `experiments.runners.common.EPISODE_SEEDS` → 1000–1199; `HEADLINE_SEEDS` → 1000–1999; `DIAG_SEEDS` → 101, 103, …, 599
