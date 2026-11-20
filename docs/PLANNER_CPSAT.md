# CP-SAT planners (Plan 4, F3; D62–D72)

`EngineConfig.planner_method` selects how the workload is packed into days:

| | `greedy` (default) | `cpsat` | `hybrid` |
|---|---|---|---|
| Schedule | day-by-day priority packing (`planner/schedule.py`) | CP-SAT for every plan | greedy first |
| Deadline missed | backtracking oracle (may say `UNKNOWN`) | exact verdict | CP-SAT takes over (exact verdict + packing) |
| Infeasibility advice | bounds + greedy estimate | exact minimum days, smallest working budget | exact |
| Reviews | priority tier | optional model tasks in due windows | greedy's tier; the model on takeover |
| Trace | greedy records | CP-SAT records | greedy; on takeover greedy records are superseded |

All three share the workload step (what to study, D70), the bounds check (greedy only returns
early on it) and the `Plan` output. `schedule.py` and `oracle.py` are unchanged. CP-SAT needs the
optional extra `pip install 'adaptengine[cpsat]'` (`ortools==9.14.6206`); without it, `cpsat` and
`hybrid` raise a `ValidationError` naming the extra and never fall back to greedy (D69). From the
terminal: `--config` with `{"planner_method": "cpsat"}` (D89).

## Model (`planner/cpsat_model.py`)

- **Items:** one token per workload occurrence (`<activity>#<concept>#<i>`, as the oracle, so D41
  repeats work); variable $x_i$ = day index in `current_day … deadline_day`.
- **Budget:** per day, item and review minutes ≤ budget; day 0 reduced by `minutes_used_today`.
- **Order:** $x_i \le x_{i+1}$ within a concept (lessons before exercises, remediation first).
- **Prerequisites (hard):** a concept's first item ≥ each prerequisite's last item (same day
  allowed; the prerequisite is ordered first within the day). Prerequisites mastered at plan start
  have no items and no constraint. With F1 confirmation on, an unconfirmed prerequisite's checks are
  its workload, so gating stays strict.
- **Deadline:** goal finish $F \le D-1$.
- **Reviews (D65):** for every practised concept (D22), up to `cpsat_max_reviews_per_concept`
  optional reviews: presence $z$, day $y$. The first review is due `gap` days after the last
  practice (plan start state) or after the concept's last item in the plan; each next review `gap`
  days after the previous one, with the half-life grown by `half_life_growth`. `gap` = the smallest
  whole number of days with $2^{-dt/h} <$ `recall_threshold`, as greedy's strict test. Reviews are
  gated like greedy's (after every prerequisite's queued work; never while a prerequisite without
  work is unmastered), at most one per concept per day, and never make a goal infeasible.
  The review's effect on projected p is not modelled (greedy updates it, but nothing in the plan
  depends on it).
- **Objective (D67), lexicographic** (each level optimised, then fixed): (1) goal finish day,
  (2) sum of remediation item days, (3) $\sum_c (\text{descendants}+1) \cdot f_c$, (4) review reward
  $\sum z_r u_r - \lambda u_r \cdot \text{lateness}_r$ with greedy's urgency $(1-r)(1+\text{descendants})$
  at $r$ = `recall_threshold`, (5) the maximum daily load (an even load; idle days before $F$ are not
  modelled separately).
- **Determinism (D68):** 1 worker, `cpsat_seed`, `cpsat_max_work_units` deterministic time per
  level, greedy's plan as hint (`cpsat_use_greedy_hint`), variables created in a fixed order.
- **Within a day:** items ordered by topological order of their concept, then remediation, reviews,
  new content, then position in the concept's workload.

**Infeasible case (exact advice):** minimum days = minimise $F$ without the deadline (horizon up to
the greedy upper bound); shortfall = that minus the deadline, marked exact when proven optimal.
Smallest working budget = the first larger allowed budget whose feasibility solve succeeds. A solve
that hits the work limit without a proof answers `UNKNOWN`, never a false `INFEASIBLE`.

**Best effort (D42):** with `cpsat` / `hybrid`, the deepest reachable concept's fastest CP-SAT
schedule, truncated at the deadline.

## Trace (`planner/cpsat_trace.py`, D71)

- One `SELECTED` record per scheduled item (`CPSAT_ASSIGNED`, or `REMEDIATION_INSERTED`) and review
  (`REVIEW_SCHEDULED`), with greedy's keys, so the one-record-per-activity audit (TC7.1) holds.
- Item records carry `earliest_possible_day` and `earliest_because` (`PLAN_START`,
  `PREVIOUS_ITEM_OF_CONCEPT`, `PREREQUISITE_<c>_FINISHES`) and `placement`: `AT_EARLIEST`,
  `BUDGET_FULL` (every day from the earliest day to the day before was too full; `full_days`), or
  `OBJECTIVE_TRADEOFF` (moved by objective levels 3–5).
- `REVIEW_DROPPED` for a first review not scheduled (`DUE_AFTER_HORIZON` or
  `NOT_SCHEDULED_WITHIN_BUDGET`).
- One `CPSAT_SOLVE` record: status, objective value per level, best bound, work units, seed, hint
  used; for infeasible plans also `minimum_finish_day`, `shortfall_exact`,
  `smallest_working_budget`.
- The explanations are computed after the solve from the final schedule and tested for truth; they
  describe the result, not the solver's search.

## Scope

The closed loop replans every day and after every wrong answer, so days after today are a
forecast. CP-SAT's plan is optimal for the projected workload (which assumes correct answers), not a
better forecast; the gains are expected in tight, disrupted or infeasible cases.
