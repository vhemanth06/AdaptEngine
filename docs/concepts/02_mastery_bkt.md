# 02 · Mastery: Bayesian Knowledge Tracing

## Idea

The engine cannot see whether a learner knows a concept. It keeps a belief $p$, the probability
that the concept is mastered, and updates it after every answer with Bayesian Knowledge Tracing
(BKT): a right answer raises $p$, a wrong one lowers it, and practice adds a little learning. A
concept counts as mastered only when $p$ is high enough *and* the learner has answered enough
questions, so reading lessons alone can never unlock the next concept.

## Notation

| Symbol | Meaning | Code name |
|---|---|---|
| $p$ | belief before the update | `LearnerConcept.p` |
| $p'$ | belief after the observation (Bayes) step | `bayes_update(...)` |
| $p''$ | belief after the learning transition; this is the stored value | `update_mastery(...)` |
| $y$ | the answer: 1 correct, 0 wrong | `correct` |
| $d$, $g(d)$, $s(d)$ | item difficulty, guess, slip | `difficulty`, `guess(d)`, `slip(d)` |
| $P_c$ | predicted probability of a correct answer | `model.predict_correct(p, d)` |
| $t$ | learning transition: $t_{\text{exercise}}$, $t_{\text{lesson}}$, $t_{\text{diag}}$ | `t_exercise`, `t_lesson`, `t_diag` |
| $n$ | number of observed answers (exercise and diagnostic) | `LearnerConcept.responses` |
| $m$ | number of consecutive correct answers (reset by a wrong one) | `LearnerConcept.correct_streak` |
| $\theta$, $k$ | mastery threshold on $p$; minimum number of answers | `theta`, `k_responses` |
| $H(p)$, $H_{\max}$ | binary entropy; entropy cap of the two-threshold rule | `entropy(p)`, `certainty_max_entropy` |
| $p_0$ | start belief for every concept | `p0` |

## Maths

**Item model (heuristic default).** For an exercise of difficulty $d \in [d_{\min}, d_{\max}] = [0.05, 0.95]$:

$$g(d) = \text{guess\_coef} \cdot (1 - d) = 0.30\,(1-d), \qquad s(d) = \text{slip\_base} + \text{slip\_coef} \cdot d = 0.05 + 0.25\,d.$$

There is no clamping: a $d$ outside $[d_{\min}, d_{\max}]$ (or not a finite number) raises
`ValidationError`, and loading an exercise with such a difficulty fails. `EngineConfig` checks that
$g$ and $s$ lie strictly inside $(0, 1)$ at both $d_{\min}$ and $d_{\max}$. Fitted profiles replace
$g$ and $s$ by one pair per difficulty class ([03](03_item_models.md)); the equations below are unchanged.

**Predicted success.**

$$P_c(p, d) = p\,(1 - s(d)) + (1 - p)\,g(d)$$

**Observation (Bayes) step.**

$$y = 1:\quad p' = \frac{p\,(1 - s)}{p\,(1 - s) + (1 - p)\,g}, \qquad y = 0:\quad p' = \frac{p\,s}{p\,s + (1 - p)\,(1 - g)}$$

(the denominators are $P_c$ and $1 - P_c$; the code returns 0 if a denominator is 0, which cannot
happen with $g, s \in (0,1)$).

**Learning transition.** Applied after the observation step:

$$p'' = p' + (1 - p')\,t, \qquad t \in [0, 1].$$

Where each step is applied:

| Event | Observation step | Transition | Counts as evidence |
|---|---|---|---|
| Exercise answer (`COMPLETED` exercise, or `FAILED_ASSESSMENT` as a wrong answer) | yes | $t_{\text{exercise}} = 0.05$; $p''$ is stored (D5) | yes: $n{+}1$, status `ASSESSED` |
| Diagnostic answer | yes | $t_{\text{diag}} = 0.0$ (pure observation) | yes: $n{+}1$, status `ASSESSED` |
| Lesson (`COMPLETED` lesson) | no | $t_{\text{lesson}} = 0.20$: $p \leftarrow p + (1-p)\,t_{\text{lesson}}$ | no: `lessons_done`${}+1$ only |
| Planner projection | correct answer assumed for exercises | $t_{\text{exercise}}$ for exercises, $t_{\text{lesson}}$ for lessons | — (projection only) |
| Confirmation test (D57, opt-in) | yes | $0$ (observation only) | — |

**Binary entropy** (uncertainty about the hidden mastered/not-mastered state, in bits):

$$H(p) = -p \log_2 p - (1 - p) \log_2 (1 - p), \qquad H(0) = H(1) = 0.$$

$H(p)$ is not confidence in a parameter estimate and does not shrink just because answers
accumulate: a surprising answer can raise it (example below: $p = 0.90$, wrong answer at $d = 0.5$
gives $p' = 0.6495$, and $H$ rises from 0.4690 to 0.9345).

**Mastery rule** (`mastered_by`, chosen by `mastery_criterion`):

| `mastery_criterion` | Concept is evidence-mastered when |
|---|---|
| `"bkt_threshold"` (default, D4) | $p \ge \theta$ and $n \ge k$, i.e. $p \ge 0.85$ and at least 2 answers |
| `"n_consecutive"` | $m \ge$ `n_consecutive` (3): the last 3 answers were correct; $p$ and $k$ are ignored |
| `"two_threshold"` | $p \ge \theta$, $n \ge k$ and $H(p) \le H_{\max} = 0.5$ (for $p > 0.5$ this means $p \ge 0.89$) |

`is_evidence_mastered(concept, cfg)` applies this rule. With `confirm_diag_confident = True`
(default off, D57) a concept that passed the confirmation test also counts while $p \ge \theta$.

**Prior.** Every concept starts at $p_0 = 0.20$ (`initial_state`). The sweep diagnostic's
`prior_mode = "flat"` (default, D59) starts from that state $p$; `prior_mode = "population"`
replaces $p$ of untouched concepts (no answers and $p = p_0$) by `population_p0` = 0.24 for the
sweep (`population_prior_config()`).

**Evidence-state semantics.** Each concept keeps three separate records:

1. *Exposure*: `lessons_done`. Lessons raise $p$ through $t_{\text{lesson}}$, but never change $n$
   or the status, so a concept studied by lessons only can never be evidence-mastered (D31). A
   completed lesson also clears `needs_remediation`.
2. *Evidence*: `responses` ($n$), `correct_responses`, `correct_streak` ($m$). Only exercise and
   diagnostic answers change them. `status` becomes `ASSESSED` after the first answer.
3. *Evidence-mastered*: the rule above.

Every update carries an `attempt_id`; an id already in `seen_attempt_ids` is a no-op.
`last_practice_day` becomes $\max(\text{old}, \text{day})$, so it never moves back; diagnostic
answers carry no day and leave it unchanged. A wrong answer that leaves $p <$
`remediation_threshold` (0.40) sets `needs_remediation` (see [08](08_review_remediation.md)).

## Worked example

4-node curriculum, concept C1, exercise `E-C1-0.4` ($d = 0.4$, so $g = 0.18$, $s = 0.15$), heuristic
model, default config. The learner starts at $p_0 = 0.20$, answers correctly, then wrongly.
Both answers are recorded with `Engine.record`.

| Step | $p$ before | $P_c$ | $p'$ (Bayes) | $p''$ (stored) | $H(p'')$ | $n$ | Evidence-mastered? |
|---|---|---|---|---|---|---|---|
| correct | 0.2000 | 0.3140 | 0.5414 | 0.5643 | 0.9880 | 1 | no ($p < 0.85$, $n < 2$) |
| wrong | 0.5643 | 0.5581 | 0.1916 | 0.2320 | 0.7814 | 2 | no ($p < 0.85$) |

Lessons alone, for comparison: eight lessons on C1 from $p_0$ give $p = 0.8658 \ge \theta$, yet
`lessons_done = 8`, `responses = 0`, status `UNASSESSED`, and the concept is **not**
evidence-mastered.

Reference values pinned by the tests ($d = 0.5$, so $g = 0.15$, $s = 0.175$):

| $p$ | Answer | $t$ | $p'$ | $p''$ |
|---|---|---|---|---|
| 0.50 | correct | 0.00 | 0.8462 | 0.8462 |
| 0.50 | wrong | 0.00 | 0.1707 | 0.1707 |
| 0.50 | correct | 0.05 | 0.8462 | 0.8538 |
| 0.50 | wrong | 0.05 | 0.1707 | 0.2122 |
| 0.90 | wrong | 0.00 | 0.6495 | 0.6495 ($H$: 0.4690 → 0.9345) |

<details><summary>How these numbers were produced</summary>

The script below, saved as `c02_bkt.py` outside the repository and run from the repository root:

```bash
.venv/bin/python <path-to>/c02_bkt.py
```

```python
from adaptengine.api import Engine
from adaptengine.core.schema import Event, EventType
from adaptengine.core.config import DEFAULT_CONFIG as cfg
from adaptengine.learner.state import ExecutionLog, is_evidence_mastered
from adaptengine.learner.mastery import guess, slip, bayes_update, entropy, learn

eng = Engine.from_files("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
s, log = eng.init_learner(), ExecutionLog()
d = eng.activities["E-C1-0.4"].difficulty
print(f"d={d} g={guess(d):.4f} s={slip(d):.4f} p0={s.concepts['C1'].p}")
for day, ok in ((1, True), (1, False)):
    p = s.concepts["C1"].p
    pc = eng.model.predict_correct(p, d)
    s, log = eng.record(s, log, Event(day=day, kind=EventType.COMPLETED, activity_id="E-C1-0.4", correct=ok))
    c = s.concepts["C1"]
    print(f"correct={ok}: p={p:.4f} P_c={pc:.4f} p'={bayes_update(p, d, ok):.4f} p''={c.p:.4f} "
          f"H={entropy(c.p):.4f} responses={c.responses} mastered={is_evidence_mastered(c, cfg)}")
p = cfg.p0
for _ in range(8):
    p = learn(p, cfg.t_lesson)
print(f"8 lessons from p0: p={p:.4f} >= theta {p >= cfg.theta}")
s2, log2 = eng.init_learner(), ExecutionLog()
for i in range(8):
    s2, log2 = eng.record(s2, log2, Event(day=1, kind=EventType.COMPLETED, activity_id="L-C1", attempt_id=f"l{i}"))
c = s2.concepts["C1"]
print(f"engine after 8 L-C1: p={c.p:.4f} lessons_done={c.lessons_done} responses={c.responses} "
      f"status={c.status.value} mastered={is_evidence_mastered(c, cfg)}")
for p, ok, T in ((0.5, True, 0.0), (0.5, False, 0.0), (0.5, True, 0.05), (0.5, False, 0.05), (0.9, False, 0.0)):
    pb = bayes_update(p, 0.5, ok)
    print(f"ref p={p} d=0.5 correct={ok} T={T}: p'={pb:.4f} p''={learn(pb, T):.4f} "
          f"H before={entropy(p):.4f} after={entropy(learn(pb, T)):.4f}")
```

Output:

```
d=0.4 g=0.1800 s=0.1500 p0=0.2
correct=True: p=0.2000 P_c=0.3140 p'=0.5414 p''=0.5643 H=0.9880 responses=1 mastered=False
correct=False: p=0.5643 P_c=0.5581 p'=0.1916 p''=0.2320 H=0.7814 responses=2 mastered=False
8 lessons from p0: p=0.8658 >= theta True
engine after 8 L-C1: p=0.8658 lessons_done=8 responses=0 status=UNASSESSED mastered=False
ref p=0.5 d=0.5 correct=True T=0.0: p'=0.8462 p''=0.8462 H before=1.0000 after=0.6194
ref p=0.5 d=0.5 correct=False T=0.0: p'=0.1707 p''=0.1707 H before=1.0000 after=0.6594
ref p=0.5 d=0.5 correct=True T=0.05: p'=0.8462 p''=0.8538 H before=1.0000 after=0.6001
ref p=0.5 d=0.5 correct=False T=0.05: p'=0.1707 p''=0.2122 H before=1.0000 after=0.7457
ref p=0.9 d=0.5 correct=False T=0.0: p'=0.6495 p''=0.6495 H before=0.4690 after=0.9345
```

</details>

## In the code

| Function or class | File | Config key | Default value |
|---|---|---|---|
| `guess`, `slip` | `src/adaptengine/learner/mastery.py` | `guess_coef`, `slip_base`, `slip_coef`, `d_min`, `d_max` | 0.30, 0.05, 0.25, 0.05, 0.95 |
| `bayes_update`, `learn`, `update_mastery`, `entropy` | `src/adaptengine/learner/mastery.py` | — | — |
| `CustomBKT` (heuristic `MasteryModel`) | `src/adaptengine/learner/adapter.py` | `model_profile` | `"heuristic"` |
| `update_concept_evidence` (single rebuild site for answers) | `src/adaptengine/learner/evidence.py` | `t_exercise`, `t_diag` (passed in) | 0.05, 0.0 |
| `apply_response`, `apply_lesson` | `src/adaptengine/session.py` | `t_exercise`, `t_lesson` | 0.05, 0.20 |
| `Engine.record` (remediation flag) | `src/adaptengine/api.py` | `remediation_threshold` | 0.40 |
| `mastered_by`, `is_evidence_mastered` | `src/adaptengine/learner/state.py` | `mastery_criterion`, `theta`, `k_responses`, `n_consecutive`, `certainty_max_entropy`, `confirm_diag_confident` | `"bkt_threshold"`, 0.85, 2, 3, 0.5, False |
| `initial_state`, `LearnerConcept` | `src/adaptengine/learner/state.py` | `p0` | 0.20 |
| sweep prior | `src/adaptengine/diagnostic/engine.py` | `prior_mode`, `population_p0` | `"flat"`, 0.24 |
| `EngineConfig` validation, `population_prior_config` | `src/adaptengine/core/config.py` | — | — |

## Tests

- `tests/unit/learner/test_mastery.py` — guess/slip table, the pinned update values, lesson
  transition, entropy values and the entropy rise, bounds, alternative mastery criteria (T5.4).
- `tests/unit/learner/test_adapter.py` — `CustomBKT` reference values.
- `tests/integration/test_state_session.py` — `test_apply_lesson_exposure_semantics` and the
  answer/lesson state updates.
- `tests/regression/test_feedback_fixes.py` — `test_lessons_vs_evidence_contract_decision_d31`.
- `tests/regression/test_defects_repro.py` — `test_repro_dd_lesson_assessed_and_replay`.
- `tests/regression/test_baseline_pins.py` — default (flat) and population prior pins.
- `tests/unit/planner/test_confirmation.py` — the confirmation clause of `is_evidence_mastered`.

## Decisions

- [D3](../project/DECISIONS.md#d3) — the entropy stop of the sweep uses $H(p)$.
- [D4](../project/DECISIONS.md#d4) — $p \ge \theta$ and $n \ge k$, $k = 2$, $\theta = 0.85$.
- [D5](../project/DECISIONS.md#d5) — the stored value is the post-transition $p''$.
- [D7](../project/DECISIONS.md#d7), [D31](../project/DECISIONS.md#d31) — lessons shift $p$ via
  $t_{\text{lesson}}$ but are not evidence.
- [D20](../project/DECISIONS.md#d20), [D22](../project/DECISIONS.md#d22) — remediation trigger;
  diagnostic answers set no practice day.
- [D33](../project/DECISIONS.md#d33) — one observation model for diagnostic, updates and planning.
- [D44](../project/DECISIONS.md#d44), [D59](../project/DECISIONS.md#d59) — `prior_mode`; the default
  sweep prior is $p_0 = 0.20$.
- [D57](../project/DECISIONS.md#d57) — opt-in confirmation clause.

The `n_consecutive` and `two_threshold` criteria (Week 7 task T5.4) have no D-number.

## Limitations

- The heuristic $g$, $s$, $t$, $p_0$ are synthetic defaults, not fitted to learners of this course.
  Fitted profiles exist ([03](03_item_models.md)) but are fitted on maths data.
- BKT has no forgetting inside the update; forgetting is a separate recall model
  ([08](08_review_remediation.md)). Each concept is tracked on its own: an answer on C3 says nothing
  about C1.
- $\theta$ and $k$ are decision rules, not estimates. Stricter rules lower goal mastery within the
  budget in the final study (E6: $\theta = 0.95$ down to −0.105; `n_consecutive` 3 down to −0.125);
  see the Outcomes section of [`experiments/NOTES.md`](../../experiments/NOTES.md).
- $t_{\text{exercise}}$ is applied after every answer, right or wrong, so a wrong answer still adds
  learning.

## Values checked

All read with `.venv/bin/python` from the repository root (`from adaptengine.core.config import
DEFAULT_CONFIG, population_prior_config`; `from adaptengine.learner.state import LearnerConcept`):

- `DEFAULT_CONFIG.p0` → 0.2; `LearnerConcept().p` → 0.2
- `DEFAULT_CONFIG.theta` → 0.85
- `DEFAULT_CONFIG.k_responses` → 2
- `DEFAULT_CONFIG.t_exercise` → 0.05; `DEFAULT_CONFIG.t_lesson` → 0.2; `DEFAULT_CONFIG.t_diag` → 0.0
- `DEFAULT_CONFIG.guess_coef` → 0.3; `DEFAULT_CONFIG.slip_base` → 0.05; `DEFAULT_CONFIG.slip_coef` → 0.25
- `DEFAULT_CONFIG.d_min` → 0.05; `DEFAULT_CONFIG.d_max` → 0.95
- `DEFAULT_CONFIG.mastery_criterion` → `"bkt_threshold"`
- `DEFAULT_CONFIG.n_consecutive` → 3; `DEFAULT_CONFIG.certainty_max_entropy` → 0.5
- `DEFAULT_CONFIG.confirm_diag_confident` → False
- `DEFAULT_CONFIG.prior_mode` → `"flat"`; `DEFAULT_CONFIG.population_p0` → 0.24;
  `population_prior_config().prior_mode` → `"population"`
- `DEFAULT_CONFIG.h_stop` → 0.5
- `DEFAULT_CONFIG.remediation_threshold` → 0.4
- $H(p) = 0.5$ at $p = 0.89$ (bisection on `entropy`, 4 decimals)

Confirmed by running them on 2026-11-21.
