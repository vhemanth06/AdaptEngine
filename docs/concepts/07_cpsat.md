# 07 · The CP-SAT planner and the hybrid planner

## Idea

The greedy planner ([06](06_planning.md)) packs one day at a time and can miss a deadline that a
better packing would meet. The CP-SAT planner takes the same workload and lets a constraint solver
(OR-Tools CP-SAT) choose the day of every item at once. It then gives an exact verdict and exact
advice: the minimum number of days needed, and the smallest budget that would work. The hybrid
planner keeps greedy's plan when it meets the deadline and calls CP-SAT only when it does not.

## Notation

Symbols from the [shared table](README.md#notation), plus:

| Symbol | Meaning | Code name |
|---|---|---|
| $i$ | an item: one occurrence of an activity in a concept's workload | `Item`, token `<activity>#<concept>#<index>` |
| $x_i$ | day index of item $i$, $0 \ldots n-1$ (index 0 = `current_day`) | `x[token]` |
| $b_{i,d}$ | 1 if item $i$ is on day index $d$ | `b[token][d]` |
| $n$ | horizon in days: $D - \text{current day} + 1$ | `n_days` |
| $\mathrm{cap}_d$ | minutes available on day $d$: $B - m_0$ on day 0, $B$ after | `_capacities` |
| $f_c$, $l_c$ | first and last item of concept $c$ | `first[c]`, `last[c]` |
| $F$ | finish day index: the latest last item | `makespan` |
| $\rho = (c, j)$ | the $j$-th optional review of $c$, $j = 0, 1, \ldots$ | `Review(concept, k)` |
| $z_\rho, y_\rho$ | review present (0/1) and its day index | `z[key]`, `y[key]` |
| $\mathrm{late}_\rho$ | days the review is later than its due day | `late[key]` |
| $\mathrm{gap}(h)$ | days until recall drops below `recall_threshold` | `_gap(h, cfg)` |
| $r_{\text{th}}$, $\gamma$ | recall threshold and half-life growth factor | `recall_threshold`, `half_life_growth` |
| $b^{\text{rev}}_{\rho,d}$ | 1 if review $\rho$ is on day index $d$ | `rb[key][d]` |
| $u_c$ | review urgency of $c$ | `Review.urgency` |
| $\lambda$ | lateness penalty | `cpsat_review_lateness_penalty` |
| $\mathrm{desc}(c)$ | number of transitive descendants of $c$ | `graph.descendant_count(c)` |

## Maths

**What is fixed.** The workload (which lessons and exercises, how many) comes from
`compute_workload` and is not changed: CP-SAT decides when, not what
([D70](../project/DECISIONS.md#d70)). Each workload occurrence becomes one item, so a repeated
exercise ([D41](../project/DECISIONS.md#d41)) gives two items. When a concept is flagged for
remediation and its first item is a lesson, that item is marked as remediation.

**Decision variables.** For each item, $n$ booleans $b_{i,d}$ and an integer $x_i = \sum_d d\,b_{i,d}$.
For each review $\rho$, a presence boolean $z_\rho$, a day $y_\rho$ and $\mathrm{late}_\rho \ge 0$.

**Hard constraints** (`cpsat_model.solve`):

$$\sum_d b_{i,d} = 1 \quad\text{(one placement per item)}$$

$$x_{c,j} \le x_{c,j+1} \quad\text{(order within a concept: lessons before exercises)}$$

$$x_{f_c} \ge x_{l_q} \quad \text{for each } q \in \mathrm{pre}(c) \text{ that has work (same day allowed)}$$

$$\sum_i \mathrm{dur}_i\, b_{i,d} + \sum_\rho \mathrm{dur}_\rho\, b^{\text{rev}}_{\rho,d} \le \mathrm{cap}_d \quad\text{(daily budget)}$$

$$F \ge x_{l_c}\ \ \forall c,\qquad F \le n - 1 \quad\text{(deadline)}$$

A prerequisite already evidence-mastered at plan start has no items and so no constraint.

**Reviews** ([D65](../project/DECISIONS.md#d65)). Every concept that has been practised or has work in
the plan ([D22](../project/DECISIONS.md#d22)) gets up to `cpsat_max_reviews_per_concept` = 3 optional
reviews, using the exercise `select_exercise` picks at its current $p$. A concept with an unmastered
prerequisite that has no work is never reviewed. With
$\mathrm{gap}(h) = \lfloor h \log_2(1/r_{\text{th}}) \rfloor + 1$ and
$h_j = h \cdot \gamma^j$:

$$z_{c,0} \Rightarrow y_{c,0} \ge x_{l_c} + \mathrm{gap}(h_0)\ \ \text{(or } y_{c,0} \ge \text{due offset if } c \text{ has no work)},\qquad
z_{c,j} \Rightarrow z_{c,j-1},\ \ y_{c,j} \ge y_{c,j-1} + \mathrm{gap}(h_j),$$

and $y_\rho \ge x_{l_q}$ for each prerequisite $q$ with work (gated as in greedy). $\mathrm{late}_\rho$
is at least $y_\rho$ minus the earliest allowed day. Reviews are optional, so they never make a goal
infeasible. The urgency is greedy's $u_c = (1 - r)(1 + \mathrm{desc}(c))$ at
$r = $ `recall_threshold`, or the replanner's `review_urgency` value when given.

**Objectives, lexicographic** ([D67](../project/DECISIONS.md#d67)). Each level is minimised, then fixed
(to its value if proven optimal, otherwise to "no worse") before the next:

| Level | Minimise |
|---|---|
| 1 | $F$: the goal finish day |
| 2 | $\sum_{i \text{ remediation}} x_i$: remediation as early as possible |
| 3 | $\sum_c (\mathrm{desc}(c) + 1)\, x_{l_c}$: concepts that unlock more finish earlier |
| 4 | $-\sum_\rho \big(\mathrm{round}(1000\,u_\rho)\, z_\rho - \mathrm{round}(1000\,\lambda\, u_\rho)\, \mathrm{late}_\rho\big)$: review reward |
| 5 | $\max_d \text{load}_d$: the peak daily load |

A level whose expression is the constant 0 (for example no remediation items) is skipped.

**Determinism** ([D68](../project/DECISIONS.md#d68)). One worker, `random_seed = cpsat_seed` (0), and
`max_deterministic_time = cpsat_max_work_units` (10.0) for every `Solve` call, so each level has its
own deterministic work-unit limit; this is a solver effort limit, not a grouping of items. With
`cpsat_use_greedy_hint = True` greedy's day for each item is the first hint; each later level is
hinted with the previous level's solution. Variables are created in a fixed order.

**Status.** If level 1 is proven, the plan is `FEASIBLE` with reason `CPSAT_OPTIMAL` (or
`CPSAT_FEASIBLE` if a later level stopped at its limit without proof). If the limit is hit before any
solution, the plan is `UNKNOWN`, `CPSAT_LIMIT_REACHED`, never a false `INFEASIBLE`. If the model is
infeasible, the plan is `INFEASIBLE`, `CPSAT_INFEASIBLE`, with exact advice:

- **Minimum days:** minimise $F$ alone, with no deadline and no reviews, over a horizon up to
  $\max(\text{greedy's last day}, D)$. Shortfall = that finish day $- D$, labelled "exactly" when proven
  optimal, else "at most".
- **Smallest working budget:** each allowed budget above $B$, in increasing order, is tried with the
  deadline; the first that fits is reported. The search stops at the first `UNKNOWN`.

**Planner selection** ([D62](../project/DECISIONS.md#d62), [D64](../project/DECISIONS.md#d64)).
`planner_method = "greedy"` (default) is unchanged ([D63](../project/DECISIONS.md#d63)). `"cpsat"`
always runs greedy first (for the hint and the upper bound) and then CP-SAT for every plan. `"hybrid"`
returns greedy's plan when its last day is $\le D$; otherwise CP-SAT takes over with the same model
([D66](../project/DECISIONS.md#d66)) in place of the oracle, and greedy's records are re-tagged as
superseded. In both non-greedy modes the early bounds return of [06](06_planning.md) is skipped.
Best effort ([D42](../project/DECISIONS.md#d42)) uses the fastest CP-SAT schedule of the deepest
reachable concept, without reviews, cut at $D$.

**Within a day**, items are listed by the topological order of their concept, then remediation,
reviews, new content, then position in the workload.

**Trace** (`cpsat_trace.py`, [D71](../project/DECISIONS.md#d71)). After the solve, each item gets one
`SELECTED` record (`CPSAT_ASSIGNED` or `REMEDIATION_INSERTED`) with `earliest_possible_day`,
`earliest_because` (`PLAN_START`, `PREVIOUS_ITEM_OF_CONCEPT`, `PREREQUISITE_<c>_FINISHES`) and
`placement`: `AT_EARLIEST`, `BUDGET_FULL` (every earlier allowed day was too full) or
`OBJECTIVE_TRADEOFF` (moved by levels 3–5). Scheduled reviews get `REVIEW_SCHEDULED`; an unscheduled
first review gets `REVIEW_DROPPED` (`DUE_AFTER_HORIZON` or `NOT_SCHEDULED_WITHIN_BUDGET`). One
`CPSAT_SOLVE` record holds the status, the value of each level, best bound, work units, seed and
whether the hint was used. For an infeasible plan it also holds `minimum_finish_day`,
`smallest_working_budget` and `shortfall_exact`. The records describe the final schedule, checked
against its constraints, not the solver's search.

## Worked example

4-node curriculum, new learner, goal C4, $B = 15$, `current_day` = 1. All three planners use the
workload of [06](06_planning.md) (12 items, 26 min).

**Deadline day 3** (the feasible case of 06):

| Planner | Status / reason | Day 1 | Day 2 | Finish day | Time (median) |
|---|---|---|---|---|---|
| greedy | `FEASIBLE` / `GREEDY_FEASIBLE` | C1 and C2 items, 12 min | C3 and C4 items, 14 min | 2 | 0.4 ms |
| cpsat | `FEASIBLE` / `CPSAT_OPTIMAL` | same | same | 2 | 12.7 ms |
| hybrid | `FEASIBLE` / `GREEDY_FEASIBLE` (no takeover) | same | same | 2 | 0.4 ms |

CP-SAT's levels: 1 → 1 (finish on day index 1 = day 2); 2 skipped (no remediation); 3 → 3
($3 \cdot 0 + 3 \cdot 0 + 2 \cdot 1 + 1 \cdot 1$ for C1, C2, C3, C4); 4 → 0; 5 → 14 (peak load).
Work units 0.000261, seed 0, hint used. The trace explains `L-C3` on day 2 as `BUDGET_FULL` (earliest
day 1, `PLAN_START`) and `L-C4` as `AT_EARLIEST` (`PREREQUISITE_C3_FINISHES`). All four first reviews
are `REVIEW_DROPPED`, `DUE_AFTER_HORIZON`: $\mathrm{gap}(30) = 10$ days, beyond the 3-day horizon.

**Deadline day 1** (the infeasible case of 06):

| Planner | Status / reason | Shortfall | Options | Time (median) |
|---|---|---|---|---|
| greedy | `INFEASIBLE` / `INSUFFICIENT_TIME_BUDGET` | 1 | "Increase daily budget to 30 min (fits in 1 days)"; "Extend deadline by at least 1 days to day 2" | 0.6 ms |
| cpsat | `INFEASIBLE` / `CPSAT_INFEASIBLE` | 1 | "Extend deadline by exactly 1 days to day 2 (proven minimum with CP-SAT)"; "Increase daily budget to 30 min (fits by the deadline, CP-SAT)" | 47.3 ms |
| hybrid | `INFEASIBLE` / `CPSAT_INFEASIBLE` (takeover) | 1 | same as cpsat | 46.4 ms |

`CPSAT_SOLVE` for cpsat and hybrid: `minimum_finish_day` 2, `smallest_working_budget` 30,
`shortfall_exact` True; mode `cpsat` and `hybrid_takeover`.

**Where hybrid helps: $B = 5$, deadline day 6.** Greedy's oracle proves `ORACLE_INFEASIBLE` with no
options ([06](06_planning.md)). Hybrid: `CPSAT_INFEASIBLE`, shortfall 1, "Extend deadline by exactly 1
days to day 7 (proven minimum with CP-SAT)" and "Increase daily budget to 10 min (fits by the
deadline, CP-SAT)".

Times are the median of 5 calls after one warm-up call on one laptop (Intel i7-1360P); they depend on
the machine. The first CP-SAT call in a process also pays the OR-Tools import (0.33 s here).

<details><summary>How these numbers were produced</summary>

Run from the repo root:

```
.venv/bin/python <scratchpad>/docs/scripts/cpsat07_example.py   # plans, objectives, trace
.venv/bin/python <scratchpad>/docs/scripts/cpsat07_timing.py    # median of 5 after warm-up
.venv/bin/python <scratchpad>/docs/scripts/cpsat07_b5.py        # B = 5, deadline 6
```

Core of `cpsat07_example.py`:

```python
for D in (3, 1):
    for method in ("greedy", "cpsat", "hybrid"):
        e = Engine.from_files("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json",
                              manifest_path="data/review_manifest.json",
                              config=replace(DEFAULT_CONFIG, planner_method=method))
        pl = e.plan(e.init_learner(), PlanContext(goal="C4", deadline_day=D, budget=15))
        print(pl.status.value, pl.reason, pl.shortfall_days, pl.days, pl.options)
        print([t for t in pl.trace if t.get("decision") in ("CPSAT_SOLVE", "REVIEW_DROPPED")])
```

`cpsat07_timing.py` times `e.plan(...)` with `time.perf_counter()` five times after one warm-up call
and prints the median; `cpsat07_b5.py` runs greedy and hybrid with
`PlanContext(goal="C4", deadline_day=6, budget=5)`.

</details>

## In the code

| Function or class | File | Config key | Default |
|---|---|---|---|
| dispatch in `_plan_goal` | `src/adaptengine/planner/plan.py` | `planner_method` | `"greedy"` |
| `build_problem`, `cpsat_plan`, `cpsat_best_effort`, `_gap` | `src/adaptengine/planner/cpsat_planner.py` | `cpsat_use_greedy_hint`, `cpsat_max_reviews_per_concept` | `True`, 3 |
| `solve`, `Item`, `Review`, `Problem`, `Solution`, `SCALE` | `src/adaptengine/planner/cpsat_model.py` | `cpsat_seed`, `cpsat_max_work_units`, `cpsat_review_lateness_penalty` | 0, 10.0, 0.1 |
| `explain`, `solve_record` | `src/adaptengine/planner/cpsat_trace.py` | — | — |
| review gap and growth | `src/adaptengine/planner/cpsat_planner.py` | `recall_threshold`, `half_life_days`, `half_life_growth` | 0.8, 30.0, 1.0 |
| config validation | `src/adaptengine/core/config.py` | all of the above | — |

OR-Tools is an optional extra (`pip install 'adaptengine[cpsat]'`, `ortools==9.14.6206`), imported only
by `cpsat_model.py`. Without it, `cpsat` and `hybrid` raise a `ValidationError` naming the extra and
never fall back to greedy ([D69](../project/DECISIONS.md#d69)).

## Tests

- `tests/unit/planner/test_cpsat_planner.py`: config validation, greedy unchanged, missing OR-Tools
  error, constraints respected, determinism, never infeasible where greedy succeeds, minimum days and
  budget against brute force, hybrid equals greedy on time and CP-SAT on takeover, best effort,
  remediation early.
- `tests/unit/planner/test_cpsat_reviews.py`: reviews never before due, unpractised concepts never
  reviewed, reviews gated by prerequisites, dropping reviews never breaks the goal, one trace record
  per activity with true reasons, exact advice in the infeasible trace.
- `tests/integration/test_closed_loop_planners.py`: scripted closed-loop episodes with no violations,
  events and mid-day replans, F1 confirmation, fitted profile, CLI via `--config`.
- `frontend/api/tests/test_parity.py`: API plans equal direct engine calls for `cpsat` and `hybrid`.

## Decisions

[D62](../project/DECISIONS.md#d62) three planners ·
[D63](../project/DECISIONS.md#d63) greedy untouched ·
[D64](../project/DECISIONS.md#d64) hybrid ·
[D65](../project/DECISIONS.md#d65) reviews in the model ·
[D66](../project/DECISIONS.md#d66) one shared model ·
[D67](../project/DECISIONS.md#d67) lexicographic objective ·
[D68](../project/DECISIONS.md#d68) determinism ·
[D69](../project/DECISIONS.md#d69) optional dependency ·
[D70](../project/DECISIONS.md#d70) same workload ·
[D71](../project/DECISIONS.md#d71) trace ·
[D72](../project/DECISIONS.md#d72) F3 evaluation ·
[D22](../project/DECISIONS.md#d22) never review an unpractised concept ·
[D42](../project/DECISIONS.md#d42) best effort.

## Limitations

- The plan is optimal for the projected workload, which assumes correct answers ([06](06_planning.md)).
  The closed loop replans after each answer, so later days are a forecast, not a better one.
- The number of exercises is fixed by the workload step; CP-SAT does not choose it (open item in
  [D70](../project/DECISIONS.md#d70)). A review's effect on projected $p$ is not modelled.
- Level 5 evens out the peak load only; idle days before $F$ are not modelled separately.
- Speed: CP-SAT is slow on large curricula. On synth-50 a cold-start plan takes about 35 s
  ([T13](../../experiments/report/tables/T13.md)) and a replan 31–42 s
  ([T13b](../../experiments/report/tables/T13b.md)), against about 5 ms for greedy and hybrid. Hybrid
  is as fast as greedy except when it takes over (synth-50 budget change: 36 s).
- Final study (E5, [`experiments/NOTES.md`](../../experiments/NOTES.md#outcomes)): same first verdict
  as greedy in every cell and 0 `UNKNOWN` ([T12](../../experiments/report/tables/T12.md)); 0
  executed prerequisite violations. Hybrid differs from greedy in only 2 of 434 cells (+0.020 goal
  mastery, both in favour of hybrid). Pure CP-SAT loses to greedy in 56 listed contrasts: 55 on
  minutes, by small amounts (its order leads to more exercise retries, with no gain in goal mastery),
  and 1 narrow goal-mastery loss (S0 8-node B15 calm with confirmation, −0.020).

## Values checked

All read with `from adaptengine.core.config import DEFAULT_CONFIG` and run on 2026-11-21:

- `DEFAULT_CONFIG.planner_method` → 'greedy'
- `DEFAULT_CONFIG.cpsat_seed` → 0
- `DEFAULT_CONFIG.cpsat_max_work_units` → 10.0
- `DEFAULT_CONFIG.cpsat_use_greedy_hint` → True
- `DEFAULT_CONFIG.cpsat_max_reviews_per_concept` → 3
- `DEFAULT_CONFIG.cpsat_review_lateness_penalty` → 0.1
- `DEFAULT_CONFIG.recall_threshold` → 0.8
- `DEFAULT_CONFIG.half_life_days` → 30.0; `DEFAULT_CONFIG.half_life_growth` → 1.0
- `DEFAULT_CONFIG.allowed_budgets` → (5, 10, 15, 30)
- `adaptengine.planner.cpsat_model.SCALE` → 1000
- `adaptengine.planner.cpsat_planner._gap(30.0, DEFAULT_CONFIG)` → 10
- `ortools.__version__` → 9.14.6206
