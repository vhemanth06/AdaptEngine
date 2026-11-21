# 08 — Forgetting, spaced review and remediation

## Idea

A concept the learner has mastered is not mastered for ever: without practice it is forgotten.
The engine predicts recall from the days since the concept was last practised and schedules a short
review exercise once predicted recall falls below a threshold. In the other direction, when a wrong
answer pushes the belief $p$ very low, the engine re-issues the concept's lesson before any more
exercises on it (remediation). Both kinds of work share the daily budget with new learning, in a
fixed order: remediation first, then reviews, then new content.

## Notation

| Symbol | Meaning | Config key / code name |
|---|---|---|
| $c$ | a concept | `concept_id` |
| $p$, $p_c$ | belief that $c$ is mastered | `LearnerConcept.p` |
| $h$, $h_c$ | memory half-life of $c$ in days | `LearnerConcept.half_life_days` (initial value `half_life_days`) |
| $\gamma$ | half-life growth factor after a correct review | `half_life_growth` |
| $\Delta t$ | whole days since $c$ was last practised | `day - last_practice_day` |
| $r$ | predicted recall of $c$ | `recall_at`, `recall` |
| $r^{*}$ | recall threshold: a review is due when $r < r^{*}$ | `recall_threshold` |
| $u$ | review urgency | `urgency_from_recall` |
| $n_{\text{desc}}(c)$ | number of concepts that depend on $c$, directly or indirectly | `graph.descendant_count(c)` |
| $p_{\text{rem}}$ | remediation threshold on $p$ | `remediation_threshold` |
| $t_{\text{lesson}}$ | learning transition of a lesson | `t_lesson` |

## Maths

**Recall.** For a concept with a practice day (any lesson or exercise recorded with a day; diagnostic
probes do not set it):

$$r = 2^{-\Delta t / h}, \qquad \Delta t = \max(0,\ \text{day} - \text{last\_practice\_day}).$$

A concept never practised has no recall (`None`) and is never reviewed ([D22](../project/DECISIONS.md#d22)).
$r = 0.5$ when $\Delta t = h$. Every new practice moves `last_practice_day` to the later day, which
resets $\Delta t$ to 0. The code computes $r$ for every practised concept, not only mastered ones.

**Half-life.** $h$ starts at `half_life_days` (30 days) for every concept. It changes only after a
*review response* (an answer on a concept that was already evidence-mastered before the answer):

$$h \leftarrow \begin{cases} \gamma \cdot h & \text{review answered correctly} \\ h & \text{otherwise.} \end{cases}$$

With the default $\gamma = 1.0$ the half-life never changes; $\gamma$ is an ablation knob
([D23](../project/DECISIONS.md#d23)). The greedy planner's projection keeps $h$ fixed for the
reviews it plans; the CP-SAT planner uses $h\gamma^{k}$ for the $k$-th planned review of a concept.

**Review due.** A review of $c$ is due on a day when $r < r^{*}$, with $r^{*} = 0.80$
([D24](../project/DECISIONS.md#d24)). With $h = 30$ this first happens when
$\Delta t > 30 \log_2(1/0.8) \approx 9.66$, that is 10 days after the last practice.

**Urgency** ([D25](../project/DECISIONS.md#d25)), for a due concept:

$$u = (1 - r)\,(1 + n_{\text{desc}}(c)).$$

It grows as recall falls and is larger for concepts many others depend on; the $+1$ keeps leaf
concepts above 0. `review_urgency` returns 0 for a concept that is not due.

**Priority order** ([D26](../project/DECISIONS.md#d26)). Each day the greedy scheduler fills the
budget from three tiers, always taking the best candidate of the lowest tier first:

1. Tier 0, remediation: the queued remediation lesson of a flagged concept.
2. Tier 1, reviews: one exercise per due concept per day, ordered by $u$ (highest first).
3. Tier 2, new lessons and exercises, ordered by the planner score (see [06](06_planning.md)).

Ties break on `activity_id`. The prerequisite gate applies to every tier: no activity for a concept
while a direct prerequisite still has queued work or is not evidence-mastered. An item that does not
fit the remaining minutes is skipped and packing continues. A review exercise is chosen by the
difficulty policy (predicted success nearest `target_success` = 0.75); a concept's exercises may be
reused ([D27](../project/DECISIONS.md#d27)).

**Maintenance reviews** ([D43](../project/DECISIONS.md#d43)). With `maintenance_reviews = True` the
scheduler does not stop when new content runs out: it keeps visiting days up to `deadline_day` and
schedules due reviews only. With `False` it stops after the last new item.

**Remediation trigger** ([D20](../project/DECISIONS.md#d20), [D28](../project/DECISIONS.md#d28)).
`Engine.record` sets `needs_remediation = True` on the target concept when an exercise answer is
wrong and the updated belief (after the BKT step, learning transition included) satisfies

$$p < p_{\text{rem}} = 0.40.$$

This applies both to a `COMPLETED` exercise with `correct = False` and to a `FAILED_ASSESSMENT`
event, which is applied as a failed exercise response. A correct answer never sets the flag, and a
later answer does not clear it.

**Remediation content** ([D21](../project/DECISIONS.md#d21)). For a flagged concept that still needs
work, the workload starts with the concept's first lesson (lowest `activity_id`), even if that lesson
was completed before; the projection raises $p$ by $p \leftarrow p + (1-p)\,t_{\text{lesson}}$.
The scheduler places it in tier 0 with reason `REMEDIATION_INSERTED`; the concept's other work waits
until it is done. Completing any lesson on the concept clears the flag.

## Worked example

4-node curriculum (C1, C2 → C3 → C4), default configuration ($h = 30$, $\gamma = 1.0$,
$r^{*} = 0.80$, $p_{\text{rem}} = 0.40$).

**Forgetting a mastered concept.** On day 1 the learner completes `L-C1`, then answers `E-C1-0.2`
and `E-C1-0.4` correctly: $p_{C1}$ goes 0.360 → 0.694 → 0.919, with 2 responses, so C1 is
evidence-mastered. `last_practice_day = 1`, $h = 30$. C1 has 2 descendants (C3, C4).

| Day | $\Delta t$ | $r$ | Due ($r < 0.80$) | $u$ |
|---|---|---|---|---|
| 5 | 4 | 0.912 | no | 0 |
| 10 | 9 | 0.812 | no | 0 |
| **11** | **10** | **0.794** | **yes (first day due)** | **0.619** |
| 15 | 14 | 0.724 | yes | 0.829 |
| 30 | 29 | 0.512 | yes | 1.465 |
| 40 | 39 | 0.406 | yes | 1.782 |

Replanning on day 11 toward goal C4 (budget 10, deadline 20) puts the review first:
day 11 = `E-C1-0.6` (review, `REVIEW_DUE`), `L-C2`, `E-C2-0.2`, `E-C2-0.4` (8 min); day 12 = C3;
day 13 = C4. With the deadline at day 30, the maintenance tier adds review-only days:
day 21 `E-C1-0.8`, `E-C2-0.6`; day 22 `E-C3-0.6`; day 23 `E-C4-0.6`. With
`maintenance_reviews = False` there are no days after day 13.

If the learner answers the day-11 review (`E-C1-0.6`) correctly, `last_practice_day` becomes 11 and `n_reviews`
becomes 1. With $\gamma = 1.0$, $h$ stays 30 and the next review is due on day 21; with
$\gamma = 1.5$, $h$ becomes 45 and the next review is due on day 26.

**Remediation after a failed assessment.** A new learner completes `L-C2` on day 1
($p_{C2}$ = 0.360) and then records `FAILED_ASSESSMENT` on `E-C2-0.4`: $p_{C2}$ = 0.139 < 0.40, so
`needs_remediation = True`. Replanning toward C3 (budget 10, deadline 10, 5 min already used on
day 1) gives:

| Day | Activities | Minutes |
|---|---|---|
| 1 | `L-C2` (`REMEDIATION_INSERTED`), `E-C2-0.2` | 5 |
| 2 | `E-C2-0.4`, `L-C1`, `E-C1-0.2`, `E-C1-0.4` | 7 |
| 3 | `L-C3`, `E-C3-0.2`, `E-C3-0.4` | 7 |

When the learner completes `L-C2` again (day 2), $p_{C2}$ = 0.311 and the flag is cleared.

<details><summary>How these numbers were produced</summary>

Run from the repo root as `.venv/bin/python - <<'EOF'` … `EOF` with this script:

```python
from dataclasses import replace
from adaptengine.api import Engine
from adaptengine.core.config import DEFAULT_CONFIG as CFG
from adaptengine.core.schema import Event, EventType as ET, PlanContext
from adaptengine.learner.state import ExecutionLog
from adaptengine.review.forgetting import recall, is_review_due, review_urgency

F = ("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
eng = Engine.from_files(*F)
def done(s, log, day, aid, ok=None, kind=ET.COMPLETED, att=None):
    return eng.record(s, log, Event(day=day, kind=kind, activity_id=aid, correct=ok, attempt_id=att,
                                    minutes_elapsed=eng.activities[aid].duration))
s, log = eng.init_learner(), ExecutionLog()
for aid, ok in [("L-C1", None), ("E-C1-0.2", True), ("E-C1-0.4", True)]:
    s, log = done(s, log, 1, aid, ok); print(aid, round(s.concepts["C1"].p, 3))
c1, n = s.concepts["C1"], eng.graph.descendant_count("C1")
for d in (5, 10, 11, 15, 30, 40):
    print(d, round(recall(c1, d), 3), is_review_due(c1, d, CFG), round(review_urgency(c1, d, n, CFG), 3))
for dl, m in ((20, True), (30, True), (30, False)):
    e = Engine.from_files(*F, config=replace(CFG, maintenance_reviews=m))
    p = e.replan(s, log, PlanContext(goal="C4", deadline_day=dl, budget=10, current_day=11))
    print(dl, m, [(x.day, x.activities) for x in p.days])
p1 = eng.replan(s, log, PlanContext(goal="C1", deadline_day=30, budget=10, current_day=11))
print("goal C1:", p1.reason, p1.days)
for g in (1.0, 1.5):
    e = Engine.from_files(*F, config=replace(CFG, half_life_growth=g))
    c = e.record(s, log, Event(day=11, kind=ET.COMPLETED, activity_id="E-C1-0.6", correct=True,
                               minutes_elapsed=2))[0].concepts["C1"]
    print(g, c.half_life_days, c.n_reviews, next(d for d in range(11, 99) if is_review_due(c, d, CFG)))
s, log = done(eng.init_learner(), ExecutionLog(), 1, "L-C2"); print(round(s.concepts["C2"].p, 3))
s, log = done(s, log, 1, "E-C2-0.4", kind=ET.FAILED_ASSESSMENT)
print(round(s.concepts["C2"].p, 3), s.concepts["C2"].needs_remediation)
p = eng.replan(s, log, PlanContext(goal="C3", deadline_day=10, budget=10, current_day=1))
print([(x.day, x.activities, x.duration) for x in p.days])
print([t["activity_id"] for t in p.trace if t.get("reason") == "REMEDIATION_INSERTED"])
s, log = done(s, log, 2, "L-C2", att="L-C2-again")
print(round(s.concepts["C2"].p, 3), s.concepts["C2"].needs_remediation)
```

Output:

```
L-C1 0.36
E-C1-0.2 0.694
E-C1-0.4 0.919
5 0.912 False 0.0
10 0.812 False 0.0
11 0.794 True 0.619
15 0.724 True 0.829
30 0.512 True 1.465
40 0.406 True 1.782
20 True [(11, ('E-C1-0.6', 'L-C2', 'E-C2-0.2', 'E-C2-0.4')), (12, ('L-C3', 'E-C3-0.2', 'E-C3-0.4')), (13, ('L-C4', 'E-C4-0.2', 'E-C4-0.4'))]
30 True [(11, ('E-C1-0.6', 'L-C2', 'E-C2-0.2', 'E-C2-0.4')), (12, ('L-C3', 'E-C3-0.2', 'E-C3-0.4')), (13, ('L-C4', 'E-C4-0.2', 'E-C4-0.4')), (21, ('E-C1-0.8', 'E-C2-0.6')), (22, ('E-C3-0.6',)), (23, ('E-C4-0.6',))]
30 False [(11, ('E-C1-0.6', 'L-C2', 'E-C2-0.2', 'E-C2-0.4')), (12, ('L-C3', 'E-C3-0.2', 'E-C3-0.4')), (13, ('L-C4', 'E-C4-0.2', 'E-C4-0.4'))]
goal C1: GOAL_ALREADY_MASTERED ()
1.0 30.0 1 21
1.5 45.0 1 26
0.36
0.139 True
[(1, ('L-C2', 'E-C2-0.2'), 5), (2, ('E-C2-0.4', 'L-C1', 'E-C1-0.2', 'E-C1-0.4'), 7), (3, ('L-C3', 'E-C3-0.2', 'E-C3-0.4'), 7)]
['L-C2', 'L-C2']
0.311 False
```

</details>

## In the code

| Function or class | File | Config key | Default |
|---|---|---|---|
| `recall_at`, `recall` | `src/adaptengine/review/forgetting.py` | `half_life_days` | 30.0 |
| `is_review_due`, `review_urgency`, `urgency_from_recall`, `compute_review_urgencies` | `src/adaptengine/review/forgetting.py` | `recall_threshold` | 0.80 |
| `update_concept_evidence` (half-life growth, `n_reviews`, `last_practice_day`) | `src/adaptengine/learner/evidence.py` | `half_life_growth` | 1.0 |
| `apply_lesson` (clears `needs_remediation`) | `src/adaptengine/session.py` | `t_lesson` | 0.20 |
| `Engine.record` (remediation flag on wrong answer / `FAILED_ASSESSMENT`) | `src/adaptengine/api.py` | `remediation_threshold` | 0.40 |
| `compute_workload` (remediation lesson first) | `src/adaptengine/planner/workload.py` | — | — |
| `run_greedy_schedule` (tiers, maintenance) | `src/adaptengine/planner/schedule.py` | `maintenance_reviews` | True |
| review exercise choice (`select_exercise`) | `src/adaptengine/planner/difficulty.py` | `target_success` | 0.75 |
| `build_problem` (CP-SAT reviews, $h\gamma^k$) | `src/adaptengine/planner/cpsat_planner.py` | `cpsat_max_reviews_per_concept` | 3 |

The `review_urgency` argument of `Engine.plan` / `Engine.replan` overrides the computed urgency per
concept; a value of 0 disables that concept's reviews (the evaluation's `no_review` arm passes 0 for
every concept).

## Tests

- `tests/unit/review/test_review.py` — recall values, due test, urgency formula, reviews firing with a
  short half-life, `n_reviews` counting review answers only.
- `tests/integration/test_plan_replan_scenarios.py` — TC5.2 (failed exercise sets the flag and inserts
  the lesson), TC5.3 (urgent review before new content), TC6.2 (failed assessment with remediation).
- `tests/unit/planner/test_planner_projection.py` — reviews wait for prerequisite relearning.
- `tests/unit/planner/test_cpsat_reviews.py` — CP-SAT reviews never before due, never for unpractised
  concepts, gated by prerequisites.
- `tests/integration/test_state_session.py`, `tests/regression/test_feedback_fixes.py` —
  `needs_remediation` and `half_life_days` survive response, lesson and diagnostic updates; a lesson
  clears the flag; snapshot validation of both fields.
- `frontend/api/tests/test_sessions.py` — the demo API reports `needs_remediation` after a wrong answer.

## Decisions

[D20](../project/DECISIONS.md#d20) remediation trigger,
[D21](../project/DECISIONS.md#d21) remediation content,
[D22](../project/DECISIONS.md#d22) no review before first practice,
[D23](../project/DECISIONS.md#d23) recall model and `half_life_growth`,
[D24](../project/DECISIONS.md#d24) recall threshold,
[D25](../project/DECISIONS.md#d25) urgency,
[D26](../project/DECISIONS.md#d26) tier order,
[D27](../project/DECISIONS.md#d27) review content,
[D28](../project/DECISIONS.md#d28) `FAILED_ASSESSMENT`,
[D41](../project/DECISIONS.md#d41) exercise repeats,
[D43](../project/DECISIONS.md#d43) configurable half-life, maintenance tier, single recall function.

## Limitations

- The half-life is the same for every concept and learner and, with $\gamma = 1$, never changes.
  Recall is a prediction from time alone: no answer ever lowers $p$ because of forgetting, and a
  review's outcome only updates $p$ through the normal BKT step.
- Recall is computed for every practised concept, including ones still being learned; the threshold
  test does not check mastery.
- If every concept on the goal path is already mastered, `plan` returns `GOAL_ALREADY_MASTERED` with
  no days, so no maintenance reviews are scheduled (the script in the worked example shows this for goal C1 on day 11).
- Remediation is one fixed step (re-issue the first lesson); there is no alternative explanation or
  easier content, and the flag is not set by several wrong answers that keep $p \ge 0.40$.
- The trigger values (0.80, 0.40, 30 days) are design defaults, not fitted to learner data.
- In the final study reviews do change outcomes under forgetting: `adapt_h7` differs from
  `no_review_h7` in 49 of 80 `forgetting_21` cells (E1 H4, held; see
  [experiments/NOTES.md, Outcomes](../../experiments/NOTES.md#outcomes)). That result uses an engine
  half-life of 7 days, not the 30-day default.

## Values checked

All read with `from adaptengine.core.config import DEFAULT_CONFIG` and run on 2026-11-21:

- `DEFAULT_CONFIG.half_life_days` → 30.0
- `DEFAULT_CONFIG.half_life_growth` → 1.0
- `DEFAULT_CONFIG.recall_threshold` → 0.8
- `DEFAULT_CONFIG.remediation_threshold` → 0.4
- `DEFAULT_CONFIG.maintenance_reviews` → True
- `DEFAULT_CONFIG.target_success` → 0.75
- `DEFAULT_CONFIG.t_lesson` → 0.2
- `DEFAULT_CONFIG.cpsat_max_reviews_per_concept` → 3
- `Engine.from_files(...4node...).graph.descendant_count("C1")` → 2
