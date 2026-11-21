# 09 — Events and replanning

## Idea

A plan is a forecast: the learner may skip a day, answer wrongly, or change the deadline or the daily
time. The engine records each such change as an event in an execution log and then builds a new plan
from the current learner state, the log and the original context. Nothing is patched in place: every
replan is a fresh call of the same planner, so it obeys the same rules and passes the same checks as
the first plan.

## Notation

| Symbol | Meaning | Config key / code name |
|---|---|---|
| $B$ | daily budget in minutes (initial, then as changed by events) | `PlanContext.budget` |
| $D$ | deadline day (initial, then as changed by events) | `PlanContext.deadline_day` |
| $d_0$ | current day of the initial context | `PlanContext.current_day` |
| $d^{\star}$ | start day of the replan (effective current day) | `compute_effective_context(...)[1]` |
| $m_d$ | minutes recorded on day $d$ by `COMPLETED` and `FAILED_ASSESSMENT` events | `minutes_elapsed` |
| $L$ | the execution log, an ordered tuple of events | `ExecutionLog.events` |
| $p_c$ | belief that concept $c$ is mastered | `LearnerConcept.p` |

## Maths

**Events and what they change** (`EventType` in `src/adaptengine/core/schema.py`; applied by
`Engine.record`). Every event is appended to $L$; an event whose `attempt_id` is already in $L$ is
ignored, so recording twice is safe.

| Event | Learner state | Plan context (through $L$) |
|---|---|---|
| `COMPLETED` (lesson) | $p \leftarrow p + (1-p)\,t_{\text{lesson}}$; `last_practice_day` set; `needs_remediation` cleared | adds `minutes_elapsed` to $m_d$; activity counted as done |
| `COMPLETED` (exercise, `correct` required) | BKT update of $p$, responses +1; if wrong and $p <$ `remediation_threshold`, `needs_remediation = True` ([08](08_review_remediation.md)) | adds $m_d$; activity counted as done |
| `FAILED_ASSESSMENT` (exercise only) | applied as a wrong exercise answer, then the same remediation check ([D28](../project/DECISIONS.md#d28)) | adds $m_d$ (not counted as a completed activity) |
| `MISSED` | unchanged | $d^{\star} \ge$ missed day $+ 1$; the missed day adds 0 minutes ([D30](../project/DECISIONS.md#d30)) |
| `DEADLINE_CHANGED` (`value` = new $D \ge$ event day) | unchanged | $D \leftarrow$ `value` |
| `BUDGET_CHANGED` (`value` must be in `allowed_budgets`) | unchanged | $B \leftarrow$ `value` |

**Effective context** ([D29](../project/DECISIONS.md#d29)). `compute_effective_context` folds $L$
over the initial context in log order:

- $D$ and $B$ take the value of the last `DEADLINE_CHANGED` / `BUDGET_CHANGED` event;
- $d^{\star} = \max(d_0,\ \text{last missed day} + 1,\ \text{last day with recorded work})$;
- while $m_{d^{\star}} \ge B$ (the budget in force at the end of the log), $d^{\star} \leftarrow d^{\star} + 1$;
- `minutes_used_today` $= m_{d^{\star}}$, so the start day only offers $B - m_{d^{\star}}$ minutes.

If $d^{\star} > D$ there is no effective context and `replan` returns `INFEASIBLE` with reason
`DEADLINE_EXCEEDED`, the shortfall $d^{\star} - D$ and two options (extend the deadline, raise the
budget).

**The frontier: what is replanned.** `replan` passes the effective context, the current state and
the completed activity ids to `plan`. Everything not yet achieved is replanned from $d^{\star}$:
concepts on the goal path that are already evidence-mastered are omitted, completed lessons are not
queued again (except a remediation lesson), and exercises are chosen afresh with unseen ones first;
a completed exercise can come back only when a concept's unseen exercises run out
([D41](../project/DECISIONS.md#d41)). Each completed activity gets an `OMITTED` trace record with
reason `REPLAN_PRESERVED_COMPLETED`. Past days are never rescheduled. If the goal is not reachable,
the plan keeps the verdict and adds `best_effort_days` ([D42](../project/DECISIONS.md#d42)).

**Memoisation** ([D35](../project/DECISIONS.md#d35)). A caller may pass a `WorkloadCache` to
`plan`, `replan` and `next_activities`. It stores each concept's projected workload under a key made
of the concept, its full learner record, the completed ids on that concept, the configuration, the
model and a catalogue fingerprint. A concept whose record did not change since the last replan is
read from the cache; only changed concepts are recomputed. The `Engine` itself holds no cache, and
the result equals a call without a cache (`Plan ==` on days, status, shortfall and trace).

**Same planner, same audit.** `replan` is `compute_effective_context` followed by the ordinary
`plan` call; there is no separate repair algorithm. A replan therefore uses the same workload
projection, prerequisite gate, budget packing, feasibility check and fallback as a first plan. In
the evaluation every plan, first or replanned, is checked by the same plan-level audit
(`experiments/core/audit.py::plan_violations`: prerequisite order, daily budget in force, effective
deadline), and the executed log is replayed through `Engine.record` for the executed-state audit
([D46](../project/DECISIONS.md#d46)).

**Online loop.** `Engine.next_activities` replans from the real state and log and returns only the
slice for $d^{\star}$ (from `best_effort_days` when the plan is not `FEASIBLE`), or `None` if that
day has no activity. It is meant to be called at the start of each day and after each wrong answer.

**Working ahead.** A learner may do more than the day's slice. The extra activities are recorded on
the day they were done and count as done in the next replan. Once $m_{d^{\star}} \ge B$ the engine's
start day moves to the next day, so the next slice belongs to tomorrow
(`tests/integration/test_plan_replan_scenarios.py::test_working_ahead_replan`).

**Finished day in the demo** ([D96](../project/DECISIONS.md#d96)). The demo keeps the learner's day
in the session context. When the engine's slice is for a later day (budget used, or minutes left but
no remaining item fits), the demo shows no "today" slice and the day as complete; only
`POST /api/sessions/{sid}/next-day` (or a `MISSED` event before the deadline) moves `current_day`
on, and next-day returns 409 on the deadline day. Next day logs nothing; unused minutes are not
carried over. Events without a day are recorded on the learner's day. No engine change was needed:
the engine already starts from $\max(d_0, \text{day implied by the log})$.

## Worked example

4-node curriculum, goal C4, budget 15, deadline day 6, novice learner. One `WorkloadCache` is
shared by all replans. Each replan is compared with an uncached replan and checked by
`plan_violations`; every comparison was equal and every audit returned
`{'prereq': 0, 'budget': 0, 'deadline': 0}`.

| Step | Effective context ($d^{\star}$, $B$, $D$, used) | New plan | Cache hits / misses |
|---|---|---|---|
| Initial plan | 1, 15, 6, 0 | day 1: `L-C1, E-C1-0.2, E-C1-0.4, L-C2, E-C2-0.2, E-C2-0.4` (12 min); day 2: `L-C3, E-C3-0.2, E-C3-0.4, L-C4, E-C4-0.2, E-C4-0.4` (14 min) | 0 / 4 |
| Day 1 slice done, all correct | 1, 15, 6, 12 | day 2: C3 and C4 as above (14 min); 3 min left on day 1 but `L-C3` takes 5 | 2 / 4 |
| `MISSED` day 2 | 3, 15, 6, 0 | day 3: the same six activities (14 min) | 4 / 4 |
| Day 3: `L-C3` done, then `E-C3-0.2` wrong | 3, 15, 6, 6 | day 3: `L-C3` (remediation), `E-C3-0.4`, `E-C3-0.6` (8 min); day 4: `L-C4, E-C4-0.2, E-C4-0.4` (7 min) | 5 / 5 |
| `BUDGET_CHANGED` to 10 on day 3 | 3, 10, 6, 6 | day 4: `L-C3, E-C3-0.4, E-C3-0.6` (8 min); day 5: `L-C4, E-C4-0.2, E-C4-0.4` (7 min) | 7 / 5 |

What happened at each step:

- `MISSED` left the learner state unchanged; the start day moved to 3 and the whole plan slid by one
  day.
- The wrong answer moved $p_{C3}$ from 0.360 to 0.115 < 0.40, so `needs_remediation` was set and the
  plan re-issues `L-C3` first. `E-C3-0.2` is not reused because C3 still has unseen exercises. Only
  C3's workload was recomputed (one new miss); C4's came from the cache.
- `BUDGET_CHANGED` left the state unchanged. With 6 of 10 minutes used, the 4 minutes left on day 3
  do not fit `L-C3` (5 min), so the plan starts on day 4 and `next_activities` returns `None` for
  day 3. In the demo this is the "Day 3 complete" case of D96.
- The final plan's trace has 8 `REPLAN_PRESERVED_COMPLETED` records (one per completed activity),
  2 `ALREADY_EVIDENCE_MASTERED` (C1, C2) and 1 `REMEDIATION_INSERTED` workload record.
- A `BUDGET_CHANGED` to 12 is rejected (`ValidationError`: not in `allowed_budgets` (5, 10, 15, 30)).

<details><summary>How these numbers were produced</summary>

Run from the repo root as `PYTHONPATH=. .venv/bin/python - <<'EOF'` … `EOF` with this script
(`PYTHONPATH=.` makes `experiments` importable for the audit):

```python
from adaptengine.api import Engine
from adaptengine.core.schema import Event, EventType as ET, PlanContext
from adaptengine.learner.state import ExecutionLog
from adaptengine.planner import WorkloadCache
from adaptengine.replanner import compute_effective_context
from experiments.core.audit import plan_violations, executed_days

eng = Engine.from_files("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
ctx0 = PlanContext(goal="C4", deadline_day=6, budget=15, current_day=1)
s, log, cache = eng.init_learner(), ExecutionLog(), WorkloadCache()

def show(label):
    eff, _, _ = compute_effective_context(ctx0, log)
    p = eng.replan(s, log, ctx0, workload_cache=cache)
    print(f"== {label}: day={eff.current_day} budget={eff.budget} deadline={eff.deadline_day} "
          f"used={eff.minutes_used_today} | {p.status.value} | same as uncached: {p == eng.replan(s, log, ctx0)}")
    for d in executed_days(p):
        print(f"   day {d.day}: {', '.join(d.activities)} ({d.duration} min)")
    print("  ", plan_violations(eng, s, p, eff.budget, eff.deadline_day, eff.current_day,
                                eff.minutes_used_today), f"cache hits={cache.hits} misses={cache.misses}")
    return p

def rec(day, kind, aid=None, ok=None, value=None):
    global s, log
    before = s
    m = eng.activities[aid].duration if aid else 0
    s, log = eng.record(s, log, Event(day=day, kind=kind, activity_id=aid, minutes_elapsed=m,
                                      correct=ok, value=value))
    return before

p = show("initial plan")
for aid in p.days[0].activities:  # day 1: the learner does the whole slice, all correct
    rec(1, ET.COMPLETED, aid, True if aid.startswith("E-") else None)
show("after day 1")
print("MISSED leaves state unchanged:", rec(2, ET.MISSED) == s)
show("after MISSED day 2")
rec(3, ET.COMPLETED, "L-C3")
b = rec(3, ET.COMPLETED, "E-C3-0.2", False)
print(f"wrong E-C3-0.2: p(C3) {b.concepts['C3'].p:.3f} -> {s.concepts['C3'].p:.3f}, "
      f"needs_remediation={s.concepts['C3'].needs_remediation}")
show("after wrong answer, day 3")
print("BUDGET_CHANGED leaves state unchanged:", rec(3, ET.BUDGET_CHANGED, value=10) == s)
p = show("after BUDGET_CHANGED to 10, day 3")
print("next_activities today:", eng.next_activities(s, log, ctx0)[0])
from collections import Counter
print(Counter(t.get("reason") for t in p.trace if t.get("decision") in ("OMITTED", "INSERTED")))
try:
    rec(3, ET.BUDGET_CHANGED, value=12)
except Exception as e:
    print(type(e).__name__, e)
```

Output:

```
== initial plan: day=1 budget=15 deadline=6 used=0 | FEASIBLE | same as uncached: True
   day 1: L-C1, E-C1-0.2, E-C1-0.4, L-C2, E-C2-0.2, E-C2-0.4 (12 min)
   day 2: L-C3, E-C3-0.2, E-C3-0.4, L-C4, E-C4-0.2, E-C4-0.4 (14 min)
   {'prereq': 0, 'budget': 0, 'deadline': 0} cache hits=0 misses=4
== after day 1: day=1 budget=15 deadline=6 used=12 | FEASIBLE | same as uncached: True
   day 2: L-C3, E-C3-0.2, E-C3-0.4, L-C4, E-C4-0.2, E-C4-0.4 (14 min)
   {'prereq': 0, 'budget': 0, 'deadline': 0} cache hits=2 misses=4
MISSED leaves state unchanged: True
== after MISSED day 2: day=3 budget=15 deadline=6 used=0 | FEASIBLE | same as uncached: True
   day 3: L-C3, E-C3-0.2, E-C3-0.4, L-C4, E-C4-0.2, E-C4-0.4 (14 min)
   {'prereq': 0, 'budget': 0, 'deadline': 0} cache hits=4 misses=4
wrong E-C3-0.2: p(C3) 0.360 -> 0.115, needs_remediation=True
== after wrong answer, day 3: day=3 budget=15 deadline=6 used=6 | FEASIBLE | same as uncached: True
   day 3: L-C3, E-C3-0.4, E-C3-0.6 (8 min)
   day 4: L-C4, E-C4-0.2, E-C4-0.4 (7 min)
   {'prereq': 0, 'budget': 0, 'deadline': 0} cache hits=5 misses=5
BUDGET_CHANGED leaves state unchanged: True
== after BUDGET_CHANGED to 10, day 3: day=3 budget=10 deadline=6 used=6 | FEASIBLE | same as uncached: True
   day 4: L-C3, E-C3-0.4, E-C3-0.6 (8 min)
   day 5: L-C4, E-C4-0.2, E-C4-0.4 (7 min)
   {'prereq': 0, 'budget': 0, 'deadline': 0} cache hits=7 misses=5
next_activities today: None
Counter({'REPLAN_PRESERVED_COMPLETED': 8, 'ALREADY_EVIDENCE_MASTERED': 2, 'REMEDIATION_INSERTED': 1})
ValidationError BUDGET_CHANGED value 12 not in allowed_budgets (5, 10, 15, 30)
```

</details>

## In the code

| Function or class | File | Config key | Default |
|---|---|---|---|
| `EventType`, `Event` (field rules per event) | `src/adaptengine/core/schema.py` | — | — |
| `Engine.record` | `src/adaptengine/api.py` | `allowed_budgets`, `remediation_threshold` | (5, 10, 15, 30), 0.40 |
| `Engine.replan`, `Engine.next_activities` | `src/adaptengine/api.py` | — | — |
| `apply_response`, `apply_lesson` | `src/adaptengine/session.py` | `t_exercise`, `t_lesson` | 0.05, 0.20 |
| `compute_effective_context`, `replan` | `src/adaptengine/replanner/replan.py` | — | — |
| `plan` (same planner for first plan and replan) | `src/adaptengine/planner/plan.py` | `planner_method` | `"greedy"` |
| `WorkloadCache` | `src/adaptengine/planner/workload.py` | — (constructor `maxsize`) | 4096 entries |
| exercise reuse in the workload | `src/adaptengine/planner/workload.py` | `allow_exercise_repeats` | True |
| `ExecutionLog` | `src/adaptengine/learner/state.py` | — | — |
| `next_day`, `post_event`, `_run_plan` (demo, D96) | `frontend/api/app.py` | — | — |
| `plan_violations`, `executed_violations` (evaluation audit) | `experiments/core/audit.py` | — | — |

## Tests

- `tests/integration/test_plan_replan_scenarios.py` — TC6.1 missed day (no lost or duplicated work),
  TC6.2 failed assessment with remediation, TC6.3 deadline change, TC6.4 budget change, working ahead,
  CLI replan.
- `tests/integration/test_engine_api.py` — `MISSED`, `DEADLINE_CHANGED`, `BUDGET_CHANGED` through
  `Engine`, duplicate events ignored.
- `tests/unit/replanner/test_replan_frontier.py` — cached replans equal full recomputation on a grid
  and on random event sequences; the cache is used and is not shared across engines.
- `tests/unit/planner/test_planner_projection.py` — `next_activities` returns the first day of
  `replan`; budgets come from config; best-effort plans.
- `tests/regression/test_defects_repro.py` — a mid-day replan never exceeds the remaining budget.
- `tests/unit/core/test_schema.py` — event field validation.
- `tests/integration/test_closed_loop_planners.py`, `experiments/tests/integration/test_episode.py` —
  closed-loop runs with events.
- `frontend/api/tests/test_sessions.py` — `test_finished_day_waits_for_next_day`,
  `test_next_day_not_past_the_deadline` (D96); `frontend/api/tests/test_parity.py` — demo plans equal
  direct `Engine` calls.

## Decisions

[D28](../project/DECISIONS.md#d28) `FAILED_ASSESSMENT`,
[D29](../project/DECISIONS.md#d29) effective context as a fold over the log,
[D30](../project/DECISIONS.md#d30) replan from the day after a missed day,
[D35](../project/DECISIONS.md#d35) caller-owned `WorkloadCache`,
[D41](../project/DECISIONS.md#d41) exercise repeats,
[D42](../project/DECISIONS.md#d42) best-effort days when infeasible,
[D45](../project/DECISIONS.md#d45) the demo is an adapter; the engine decides,
[D46](../project/DECISIONS.md#d46) executed-state audit,
[D96](../project/DECISIONS.md#d96) finished day and "Next day" in the demo.

## Limitations

- Replanning reacts only to recorded events. It does not predict missed days or keep slack for them;
  each plan assumes every future answer is correct (optimistic projection, see [06](06_planning.md)).
- A missed day changes no learner state: forgetting during the gap only shows up through recall and
  reviews ([08](08_review_remediation.md)).
- `DEADLINE_CHANGED` and `BUDGET_CHANGED` replace the value for all remaining days; there is no
  per-day budget.
- The engine skips to the next day only when the day's minutes reach $B$; when a few minutes remain
  but nothing fits, the engine's start day stays put and `next_activities` returns `None` (the demo
  handles this with D96).
- In the final study replanning after missed days did not beat `no_replan` in most cells:
  adapt − no_replan was above 0 in only 6 of 40 missed-day cells and below 0 in many (E1 H3, failed;
  see [experiments/NOTES.md, Outcomes](../../experiments/NOTES.md#outcomes)).

## Values checked

All read with `from adaptengine.core.config import DEFAULT_CONFIG` and run on 2026-11-21:

- `DEFAULT_CONFIG.allowed_budgets` → (5, 10, 15, 30)
- `DEFAULT_CONFIG.remediation_threshold` → 0.4
- `DEFAULT_CONFIG.t_exercise` → 0.05
- `DEFAULT_CONFIG.t_lesson` → 0.2
- `DEFAULT_CONFIG.planner_method` → 'greedy'
- `DEFAULT_CONFIG.allow_exercise_repeats` → True
- `WorkloadCache().maxsize` → 4096 (via `from adaptengine.planner import WorkloadCache`)
