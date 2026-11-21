# 06 · Building the plan: workload, priorities, greedy packing, feasibility

## Idea

The learner names a goal concept, a daily budget $B$ in minutes and a deadline day $D$. The planner
works out what is still needed to master the goal (the workload), packs that work into days under the
budget so that no concept is studied before its prerequisites, and says whether the goal can be
reached by the deadline. If it cannot, the planner says by how many days it misses, what would fix
it, and still gives a best-effort plan so the learner is never left idle.

## Notation

Symbols from the [shared table](README.md#notation), plus:

| Symbol | Meaning | Config key / code name |
|---|---|---|
| $g$ | goal concept | `PlanContext.goal` |
| $\mathrm{anc}(g)$ | all ancestors of $g$ (transitive prerequisites) | `graph.ancestors(g)` |
| $R$ | required concepts: $g$ and its ancestors that are not evidence-mastered | — |
| $W_c$ | the workload of concept $c$: an ordered queue of lessons and exercises | `workload[c]` |
| $n_c$ | projected responses on $c$ | `responses` |
| $P^{*}$ | target success probability for exercise choice | `target_success` |
| $\mathrm{desc}(c)$ | number of transitive descendants of $c$ | `graph.descendant_count(c)` |
| $u_c$ | review urgency of $c$ | `urgency_from_recall` |
| $w_{\text{review}}, w_{\text{unlock}}, w_{\text{fit}}$ | weights of the new-content score | `w_review`, `w_unlock`, `w_fit` |
| $\mathrm{dur}(a)$ | duration of activity $a$ in minutes | `Activity.duration` |
| $m_0$ | minutes already used on the start day | `PlanContext.minutes_used_today` |
| $n_{\text{days}}$ | days available: $D - \text{current day} + 1$ | `days_left` |
| $\mathrm{cp}(c)$ | critical-path minutes ending at $c$ | `cp[c]` |

## Maths

**Required concepts** ([D4](../project/DECISIONS.md#d4) evidence-mastered rule, see
[02](02_mastery_bkt.md)):

$$R = \big(\{g\} \cup \mathrm{anc}(g)\big) \setminus \{c : p_c \ge \theta \text{ and } \text{responses}_c \ge k\}.$$

**Workload of each $c \in R$** (`compute_workload`, topological order). The queue is: a repeat of the
concept's lesson if it is flagged for remediation ([D21](../project/DECISIONS.md#d21), see
[08](08_review_remediation.md)); then every lesson not yet done; then exercises
([D16](../project/DECISIONS.md#d16): lessons before exercises). Each lesson moves the projected belief
by $p \leftarrow p + (1-p)\,t_{\text{lesson}}$. Exercises are added one at a time until the mastery
rule holds on the projection ([D11](../project/DECISIONS.md#d11): every answer assumed correct,
`projection_mode = "optimistic"`):

$$\text{repeat while not}\;\big(p \ge \theta \;\text{and}\; n_c \ge k\big):\quad
e^{*} = \arg\min_{e}\, \big|P_c(p, d_e) - P^{*}\big|,\quad p \leftarrow \mathrm{update}(p, d_{e^{*}}, \text{correct}, t_{\text{exercise}}),\quad n_c \leftarrow n_c + 1,$$

with $P_c(p,d) = p\,(1 - s(d)) + (1-p)\,g(d)$ (see [02](02_mastery_bkt.md), [03](03_item_models.md)).
So the number of exercises is the smallest count that lifts the projected $p$ to $\theta$ with at least
$k$ responses.

- **Exercise choice** (`select_exercise`, [D10](../project/DECISIONS.md#d10)): smallest
  $|P_c - P^{*}|$, then smallest $|d - 0.50|$, then lexicographic `activity_id` (both distances
  rounded to 9 decimals).
- **Candidates** ([D41](../project/DECISIONS.md#d41), `allow_exercise_repeats = True`): exercises
  not yet seen (neither done nor already in this projection) come first; when none are left, the
  least-recently-attempted one is reused. With repeats off, done exercises are excluded. If no
  candidate is left, or 200 exercises are projected for one concept, the plan is `INFEASIBLE` with
  reason `CONTENT_INSUFFICIENT`.
- `projection_mode = "expected"` (not the default) pads the queue to
  $\lceil \sum 1/P_c \rceil$ exercises, the expected count when answers can be wrong.

**Priority tiers** (`run_greedy_schedule`, [D26](../project/DECISIONS.md#d26)). Each day, candidates
are ranked by the key (tier, $-$score, `activity_id`), and the top one is taken:

| Tier | Candidates | Score |
|---|---|---|
| 0 | first item of a remediation-flagged concept (the repeat lesson) | constant 100 |
| 1 | a review exercise for a concept with predicted recall $r < $ `recall_threshold` (see [08](08_review_remediation.md)) | $u_c = (1 - r)(1 + \mathrm{desc}(c))$ ([D25](../project/DECISIONS.md#d25)) |
| 2 | the next item of each concept's queue | $w_{\text{review}} \cdot 0 + w_{\text{unlock}} \cdot \mathrm{desc}(c) + w_{\text{fit}} \cdot \mathrm{fit}$ |

with $\mathrm{fit} = 1 - |P_c(p, d) - P^{*}|$ for an exercise and $0$ for a lesson
([D14](../project/DECISIONS.md#d14)); the unlock term counts transitive descendants
([D13](../project/DECISIONS.md#d13)). In tier 2 the review term is always 0, so $w_{\text{review}}$
has no effect in the current code. After all queues are empty, a maintenance tier keeps scheduling due
reviews only, until day $D$ ([D43](../project/DECISIONS.md#d43)).

**Packing rules.**

- **Budget:** a candidate longer than the minutes left today is skipped (trace `DEFERRED`,
  `DOES_NOT_FIT_REMAINING_TIME`) and packing goes on with the next one
  ([D15](../project/DECISIONS.md#d15)). The start day has $B - m_0$ minutes.
- **Prerequisite gate:** no item of $c$ while a direct prerequisite still has queued work. A concept
  unlocks its dependants as soon as its projected queue is scheduled
  ([D11](../project/DECISIONS.md#d11)), on the same day if time is left, in prerequisite order
  ([D12](../project/DECISIONS.md#d12)).
- **Projection:** after each scheduled item the planner updates its projected $p$ as if the answer
  were correct (lesson: $p + (1-p)t_{\text{lesson}}$; exercise: BKT update with correct $=$ true).
  This projected $p$ feeds the fit term and the choice of review exercise.
- **Day numbers** are absolute, from `current_day` ([D18](../project/DECISIONS.md#d18)).
- **Stop:** the loop stops after day $\max(3D, 100)$ or after 15 consecutive days without progress on
  the queues ([D40](../project/DECISIONS.md#d40)).

**Budget check.** $B$ must be one of `allowed_budgets` = (5, 10, 15, 30), otherwise a
`ValidationError` is raised. $D$ and $B$ come from the effective context, which folds deadline and
budget change events over the starting context ([D29](../project/DECISIONS.md#d29)).

**Feasibility bounds** (`check_feasibility_bounds`, run before greedy):

$$T_{\text{total}} = \left\lceil \frac{\sum_{c}\sum_{a \in W_c} \mathrm{dur}(a) + m_0}{B} \right\rceil,\qquad
\mathrm{cp}(c) = \sum_{a \in W_c}\mathrm{dur}(a) + \max_{q \in \mathrm{pre}(c)} \mathrm{cp}(q),\qquad
T_{\text{cp}} = \left\lceil \frac{\mathrm{cp}(g) + m_0}{B} \right\rceil.$$

The goal is `INFEASIBLE` when an item is longer than $B$ (`ACTIVITY_EXCEEDS_BUDGET`) or when
$\max(T_{\text{total}}, T_{\text{cp}}) > n_{\text{days}}$. The reason is
`CRITICAL_PATH_EXCEEDS_DEADLINE` if $T_{\text{cp}} > T_{\text{total}}$, otherwise
`INSUFFICIENT_TIME_BUDGET`. The shortfall is $\max(T_{\text{total}}, T_{\text{cp}}) - n_{\text{days}}$.

**Shortfall advice** (options): for every allowed budget $b > B$, "Increase daily budget to $b$ min
(fits in / requires $\max(\lceil \text{total}/b \rceil, \lceil \mathrm{cp}(g)/b \rceil)$ days)"; then
"Extend deadline by at least (shortfall) days to day $\text{current day} + \max(T_{\text{total}}, T_{\text{cp}}) - 1$".

**Backtracking oracle** (`solve_oracle`). It runs only when the bounds pass but greedy's last day is
after $D$. Items are ordered topologically (Kahn's algorithm, ties by id). Each item goes to a day no
earlier than its predecessors' days, with the day total $\le B$ (day 0 starts at $m_0$). A branch is
pruned when the remaining minutes exceed the remaining capacity, and only the first empty day is
tried (the others are symmetric). It answers `FEASIBLE` with a packing, `INFEASIBLE` when every branch
fails, or `UNKNOWN` when it reaches `oracle_node_limit` = 1000 nodes
([D17](../project/DECISIONS.md#d17)). It never gives a false `INFEASIBLE`. After an oracle failure
the shortfall is greedy's last day $- D$.

**Verdicts** (`Plan.status`, `Plan.reason`):

| Status | Reasons |
|---|---|
| `FEASIBLE` | `GOAL_ALREADY_MASTERED`, `GREEDY_FEASIBLE`, `ORACLE_ASSIGNMENT` |
| `INFEASIBLE` | `CONTENT_INSUFFICIENT`, `ACTIVITY_EXCEEDS_BUDGET`, `INSUFFICIENT_TIME_BUDGET`, `CRITICAL_PATH_EXCEEDS_DEADLINE`, `ORACLE_INFEASIBLE` |
| `UNKNOWN` | `ORACLE_LIMIT_EXCEEDED` |

**Best effort** ([D42](../project/DECISIONS.md#d42)). For any status other than `FEASIBLE`, the plan
keeps its verdict, shortfall and options and adds `best_effort_days`. Concepts in
$\{g\} \cup \mathrm{anc}(g)$ are tried deepest first (ties by id). The first one whose workload can be
built and is not empty is scheduled by greedy, and days after $D$ are dropped. The trace starts with a
`BEST_EFFORT` / `DEEPEST_REACHABLE` record.

## Worked example

4-node curriculum (C1, C2 → C3 → C4), new learner ($p_0 = 0.20$ everywhere), goal C4, $B = 15$,
`current_day` = 1, default config.

**Workload, step by step for C1.** After `L-C1`, $p = 0.360$. $P_c$ at $p = 0.360$: `E-C1-0.2` 0.478,
`E-C1-0.4` 0.421, `E-C1-0.6` 0.365, `E-C1-0.8` 0.308, so `E-C1-0.2` is closest to 0.75. After a
correct answer, $p = 0.694$ ($n = 1$). `E-C1-0.2` is now seen, so the unseen exercises come first:
`E-C1-0.4` 0.645, `E-C1-0.6` 0.592, `E-C1-0.8` 0.539, and `E-C1-0.4` is picked. After it,
$p = 0.919 \ge 0.85$ and $n = 2 \ge k$: done.

| Concept | Workload | Minutes |
|---|---|---|
| C1 | `L-C1`, `E-C1-0.2`, `E-C1-0.4` | 6 |
| C2 | `L-C2`, `E-C2-0.2`, `E-C2-0.4` | 6 |
| C3 | `L-C3`, `E-C3-0.2`, `E-C3-0.4` | 7 |
| C4 | `L-C4`, `E-C4-0.2`, `E-C4-0.4` | 7 |
| total | | 26 |

**Feasible case, deadline day 3.** Bounds: $T_{\text{total}} = \lceil 26/15 \rceil = 2$,
$\mathrm{cp}(C4) = 7 + 7 + 6 = 20$, so $T_{\text{cp}} = 2 \le 3$ days. Verdict `FEASIBLE`,
`GREEDY_FEASIBLE`.

| Day | Activities | Minutes |
|---|---|---|
| 1 | `L-C1`, `E-C1-0.2`, `E-C1-0.4`, `L-C2`, `E-C2-0.2`, `E-C2-0.4` | 12 |
| 2 | `L-C3`, `E-C3-0.2`, `E-C3-0.4`, `L-C4`, `E-C4-0.2`, `E-C4-0.4` | 14 |

Scores on day 1: `L-C1` 2.000 (unlock 2: C3 and C4; fit 0, a lesson); `E-C1-0.2` 2.728 (fit
$1 - |0.478 - 0.75| = 0.728$); `E-C1-0.4` 2.895 (fit 0.895). `L-C1` beats `L-C2` (both 2.000) on
`activity_id`. With 3 minutes left on day 1, `L-C3` (5 min) is `DEFERRED`; nothing else fits, because
C3's exercises wait behind its lesson and C4 is gated. On day 2, C4 starts right after C3 finishes
(same-day unlock).

**Infeasible case, deadline day 1.** $n_{\text{days}} = 1$ but 2 days are needed. Verdict
`INFEASIBLE`, reason `INSUFFICIENT_TIME_BUDGET` ($T_{\text{cp}} = T_{\text{total}}$), shortfall 1 day.
Options:

- "Increase daily budget to 30 min (fits in 1 days)"
- "Extend deadline by at least 1 days to day 2"

Best effort: target C4 (`DEEPEST_REACHABLE`), day 1 = `L-C1`, `E-C1-0.2`, `E-C1-0.4`, `L-C2`,
`E-C2-0.2`, `E-C2-0.4` (12 min).

**Oracle case, $B = 5$, deadline day 6.** The bounds pass ($\lceil 26/5 \rceil = 6$ days), but greedy
finishes on day 7. The oracle explores 80 nodes and proves `ORACLE_INFEASIBLE`, shortfall 1, with no
options (see Limitations). With `oracle_node_limit = 10` the same plan is `UNKNOWN`,
`ORACLE_LIMIT_EXCEEDED`. Both keep a 6-day best-effort plan.

<details><summary>How these numbers were produced</summary>

Run from the repo root:

```
.venv/bin/python <scratchpad>/docs/scripts/plan06_example.py
.venv/bin/python <scratchpad>/docs/scripts/plan06_oracle.py
```

`plan06_example.py` (core lines):

```python
e = Engine.from_files("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json",
                      manifest_path="data/review_manifest.json")
s, m, cfg = e.init_learner(), e.model, e.config
p = learn(s.concepts["C1"].p, cfg.t_lesson)                       # 0.360
w, _, _ = compute_workload(e.graph, e.activities, s, "C4", model=m, cfg=cfg)
exs = sorted(C1 exercises, key=activity_id)                        # E-C1-0.2 ... E-C1-0.8
for a in w["C1"][1:]:                                              # P_c of each exercise, then update
    print({x.activity_id: round(m.predict_correct(p, x.difficulty), 3) for x in exs}, a.activity_id)
    p = m.update(p, a.difficulty, True, cfg.t_exercise)
for D in (3, 1):
    ctx = PlanContext(goal="C4", deadline_day=D, budget=15)
    print(check_feasibility_bounds(e.graph, w, ctx, cfg=cfg).__dict__)
    pl = e.plan(s, ctx)        # status, reason, shortfall, days, options, best_effort_days, trace scores
```

`plan06_oracle.py`: the same engine with `replace(DEFAULT_CONFIG, oracle_node_limit=lim)` for
`lim` in (1000, 10), `e.plan(e.init_learner(), PlanContext(goal="C4", deadline_day=6, budget=5))`,
printing status, reason, shortfall, options and `nodes_explored` from the trace.

</details>

## In the code

| Function or class | File | Config key | Default |
|---|---|---|---|
| `plan`, `_plan_goal`, `_best_effort` | `src/adaptengine/planner/plan.py` | `allowed_budgets` | (5, 10, 15, 30) |
| `compute_workload`, `WorkloadCache` | `src/adaptengine/planner/workload.py` | `allow_exercise_repeats`, `projection_mode` | `True`, `"optimistic"` |
| `select_exercise` | `src/adaptengine/planner/difficulty.py` | `target_success` | 0.75 |
| `run_greedy_schedule` | `src/adaptengine/planner/schedule.py` | `w_review`, `w_unlock`, `w_fit`, `maintenance_reviews` | 1.0, 1.0, 1.0, `True` |
| `check_feasibility_bounds` | `src/adaptengine/planner/feasibility.py` | `allowed_budgets` (for options) | (5, 10, 15, 30) |
| `solve_oracle` | `src/adaptengine/planner/oracle.py` | `oracle_node_limit` | 1000 |
| mastery rule in the projection (`mastered_by`) | `src/adaptengine/learner/state.py` | `theta`, `k_responses` | 0.85, 2 |
| projected belief update | `src/adaptengine/learner/mastery.py` | `t_lesson`, `t_exercise` | 0.20, 0.05 |

The projection guard of 200 exercises per concept is `_MAX_PROJECTED_EXERCISES` in `workload.py`.
`planner_method` (default `"greedy"`) selects the scheduler; the CP-SAT and hybrid planners are in
[07](07_cpsat.md).

## Tests

- `tests/unit/planner/test_planner.py`: exercise choice and tie rule (`test_difficulty_policy_tc42`),
  cold-start workload, prerequisite safety, budget adherence, infeasible short deadline, exact oracle
  and its node limit (`test_exact_oracle_tc35`, `test_exact_oracle_node_limit_tc36`), oracle trace.
- `tests/unit/planner/test_planner_projection.py`: exercise repeats (D41), expected projection,
  best effort (D42), allowed budgets from config.
- `tests/unit/review/test_review.py`: maintenance reviews fire (`test_review_due_fires_with_short_half_life_t2_6`).
- `tests/integration/test_plan_replan_scenarios.py`: mastered concept omitted, remediation lesson,
  review before new content (tier order), trace coverage.
- `tests/regression/test_baseline_pins.py`, `tests/regression/test_feedback_fixes.py`: pinned plans
  and config-driven $\theta$, $k$ in the planner; INFEASIBLE/UNKNOWN exit codes.

## Decisions

[D10](../project/DECISIONS.md#d10) tie rule ·
[D11](../project/DECISIONS.md#d11) projection assumes correct answers; unlock once projected work is scheduled ·
[D12](../project/DECISIONS.md#d12) same-day unlock ·
[D13](../project/DECISIONS.md#d13) unlock = descendant count ·
[D14](../project/DECISIONS.md#d14) lesson fit 0 ·
[D15](../project/DECISIONS.md#d15) skip items that do not fit ·
[D16](../project/DECISIONS.md#d16) lessons before exercises ·
[D17](../project/DECISIONS.md#d17) oracle node limit ·
[D18](../project/DECISIONS.md#d18) absolute day numbers ·
[D19](../project/DECISIONS.md#d19) reserved, no decision ·
[D26](../project/DECISIONS.md#d26) tier order ·
[D29](../project/DECISIONS.md#d29) effective deadline and budget ·
[D35](../project/DECISIONS.md#d35) `WorkloadCache` ·
[D38](../project/DECISIONS.md#d38) oracle trace records ·
[D40](../project/DECISIONS.md#d40) starvation stop ·
[D41](../project/DECISIONS.md#d41) exercise repeats ·
[D42](../project/DECISIONS.md#d42) best effort ·
[D43](../project/DECISIONS.md#d43) maintenance reviews.

## Limitations

- The workload assumes every answer is correct, so it is a lower bound on real practice. The
  closed loop replans after each answer ([09](09_replanning.md)); `projection_mode = "expected"` is
  available but not the default.
- Greedy is not optimal. It can miss a deadline that a better packing would meet; the oracle catches
  this only up to 1000 nodes and otherwise answers `UNKNOWN`.
- When the bounds pass but greedy and the oracle fail, the options list is empty (worked example,
  $B = 5$, deadline 6): the bounds give no advice and the oracle gives none either. The hybrid planner
  gives exact advice in this case ([07](07_cpsat.md)).
- $w_{\text{review}}$ multiplies a term that is always 0 in tier 2; reviews are ranked by tier 1.
- Final study: 0 executed prerequisite violations for all planners and 0 `UNKNOWN` first plans
  (E5 H1, H2 in [`experiments/NOTES.md`](../../experiments/NOTES.md#outcomes);
  [T12](../../experiments/report/tables/T12.md), [T12b](../../experiments/report/tables/T12b.md)).
  The static baseline beats adapt on goal mastery in 158 E1 cells: the planner holds the goal back
  until its prerequisites have evidence of mastery, while static breaks prerequisite order for
  178–200 of its 200 learners in each of those cells (E1 mechanism check in
  [`experiments/NOTES.md`](../../experiments/NOTES.md#outcomes)).

## Values checked

All read with `from adaptengine.core.config import DEFAULT_CONFIG` and run on 2026-11-21:

- `DEFAULT_CONFIG.target_success` → 0.75
- `DEFAULT_CONFIG.w_review`, `.w_unlock`, `.w_fit` → 1.0, 1.0, 1.0
- `DEFAULT_CONFIG.allowed_budgets` → (5, 10, 15, 30)
- `DEFAULT_CONFIG.oracle_node_limit` → 1000
- `DEFAULT_CONFIG.allow_exercise_repeats` → True
- `DEFAULT_CONFIG.projection_mode` → 'optimistic'
- `DEFAULT_CONFIG.maintenance_reviews` → True
- `DEFAULT_CONFIG.theta` → 0.85; `DEFAULT_CONFIG.k_responses` → 2
- `DEFAULT_CONFIG.t_lesson` → 0.2; `DEFAULT_CONFIG.t_exercise` → 0.05; `DEFAULT_CONFIG.p0` → 0.2
- `DEFAULT_CONFIG.recall_threshold` → 0.8
- `DEFAULT_CONFIG.planner_method` → 'greedy'
- `adaptengine.planner.workload._MAX_PROJECTED_EXERCISES` → 200
- 15 starvation days and the $\max(3D, 100)$ horizon: checked as literals in the source of
  `run_greedy_schedule` (`inspect.getsource`).
