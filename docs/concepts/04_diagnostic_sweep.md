# 04 — The diagnostic sweep (expected information gain)

## Idea

Before planning, the engine asks a few exercises to estimate what the learner already knows. The
default diagnostic (the "sweep") walks the concepts in prerequisite order and, for each one, asks the
unasked exercise whose answer is expected to reduce the uncertainty about that concept the most. It
stops a concept once its belief $p$ is confident enough, keeps to a small total budget of questions,
and skips concepts whose prerequisites look clearly unmastered. The result is a starting $p$ per
concept for the planner.

## Notation

| Symbol | Meaning | Config key / code name |
|---|---|---|
| $p$, $p_c$ | belief that concept $c$ is mastered (see [02](02_mastery_bkt.md)) | `LearnerConcept.p` |
| $p_0$ | cold-start prior | `p0` |
| $p_{\text{pop}}$ | population base-rate prior (optional) | `population_p0` |
| $d$ | difficulty of the candidate exercise $a$ | `Activity.difficulty` |
| $g(d)$, $s(d)$ | guess and slip of an item of difficulty $d$ (see [03](03_item_models.md)) | `guess_coef`, `slip_base`, `slip_coef` |
| $P_c$ | predicted probability of a correct answer | `model.predict_correct(p, d)` |
| $p'_{+}$, $p'_{-}$ | belief after a correct / wrong answer, no learning | `model.update(p, d, y, 0.0)` |
| $H(p)$ | binary entropy in bits | `learner.mastery.entropy` |
| $\mathrm{EIG}(a)$ | expected information gain of asking item $a$ | `compute_eig` |
| $N_{\max}$ | global item cap for the whole diagnostic | `n_max` |
| $n_c^{\max}$ | per-concept item cap | `concept_cap` |
| $H_{\text{stop}}$ | entropy stop threshold | `h_stop` |
| $n_c^{\min}$ | answers required before an entropy stop | `min_items_per_concept` |
| $p_{\text{skip}}$ | descendants are skipped when an ancestor ends below this | `skip_threshold` |

## Maths

**Information gain of one item.** For the concept being diagnosed, with current belief $p$ and a
candidate exercise of difficulty $d$ (`diagnostic/scoring.py::compute_eig`):

$$P_c = p\,(1 - s(d)) + (1 - p)\,g(d)$$

$$p'_{+} = \frac{p\,(1 - s(d))}{P_c}, \qquad p'_{-} = \frac{p\,s(d)}{1 - P_c}$$

$$\mathrm{EIG}(a) = H(p) - \left[ P_c\,H(p'_{+}) + (1 - P_c)\,H(p'_{-}) \right], \qquad H(p) = -p \log_2 p - (1-p)\log_2(1-p)$$

- It is **per concept**: only $p_c$ of the item's own concept enters. Descendants, other concepts
  and the space of knowledge states play no part (that is what the bisection diagnostic adds, see
  [05](05_diagnostic_bisection.md)).
- The expectation is weighted by the model's own predicted answer probabilities $P_c$ and $1-P_c$.
- $p'_{\pm}$ are computed with transition 0 (no learning inside the diagnostic). The explicit
  formulas above are the heuristic `CustomBKT`; with a fitted profile the same expression is
  evaluated through the active `MasteryModel`. The result is clipped at 0.

**Selection and tie-breaking (D10).** Among the unasked exercises of the concept, the engine takes
the smallest key `candidate_sort_key(EIG, d, activity_id)`
$= \left(-\mathrm{round}(\mathrm{EIG}, 9),\ \mathrm{round}(|d - 0.5|, 9),\ \text{id}\right)$:
largest EIG (rounded to 9 decimals), then difficulty nearest 0.5, then the lexicographically
smallest `activity_id`.

**Answer update.** The answer is applied with `update_concept_evidence` at transition
$t_{\text{diag}} = 0$, so $p \leftarrow p'_{+}$ or $p'_{-}$; responses and status (`ASSESSED`) change.

**Order and stopping.** Goal concepts (default: all) are visited in a stable topological order
(ties by `concept_id`). For one concept, after each answer:

| Condition (checked in this order) | Stop reason |
|---|---|
| $n_c \ge n_c^{\min}$ and $H(p_c) \le H_{\text{stop}}$ | `ENTROPY` |
| $n_c \ge n_c^{\max}$ | `CONCEPT_CAP` |
| total items $\ge N_{\max}$ | `GLOBAL_CAP` (later concepts get 0 items and the same reason) |
| no unasked exercise left for $c$ | `NO_ITEMS` |

Every concept that is reached gets at least one item: the entropy test runs only after an answer.

**Descendant pruning (D8, `pruning_mode`).** When a concept finishes with final $p_c$:
- `hard` (default): if $p_c < p_{\text{skip}}$, every not-yet-diagnosed in-goal descendant is marked
  `SKIPPED_ANCESTOR_UNMASTERED`; it keeps its $p$, status and 0 items.
- `soft`: descendants are still diagnosed, but a descendant with no responses and $p > p_c$ starts at
  $p_c$.
- `none`: no effect.

**Selection scope (`selection_scope`).** `concept_sweep` (default) finishes one concept before the
next. `frontier` picks, at every step, the max-EIG unasked item over all open concepts whose in-goal
prerequisites are finished; the same per-concept stops apply, and concepts never opened end as
`NOT_REACHED` (or `GLOBAL_CAP` when the budget ran out).

**Starting prior (`prior_mode`, D59).** `flat` (default): each concept starts at its state value,
$p_0 = 0.20$ for an untouched learner. `population`: a concept with no responses and $p = p_0$ starts
at $p_{\text{pop}} = 0.24$; a $p$ set by the caller is kept. `population_prior_config()` restores this.

**Output.** `DiagnosticResult` holds `state` (a new `LearnerState`), `concept_results`
(per concept: `p`, `h` $= H(p)$, `status`, `n_items`, `stop_reason`), `item_log` (per item:
`concept_id`, `activity_id`, `difficulty`, `response`, `p_before`, `p_after`, `eig`), `total_items`
($\le N_{\max}$) and `info` (empty for the sweep). No item is asked twice; the input state is not
changed. `item_limit` lowers $N_{\max}$ for a prefix replay.

## Worked example

4-node curriculum (C1, C2 → C3 → C4), default config, cold-start learner ($p = 0.20$ everywhere).
Scripted learner: correct on every C1 and C2 item, wrong on every other item.

At the start, the EIG of the four C1 items is 0.2224 ($d$ = 0.2), 0.2317 (0.4), 0.2528 (0.6) and
0.2937 (0.8): the hard item wins because its guess rate is lowest ($g(0.8) = 0.06$).

| # | Concept | Item asked | EIG | Answer | $p$ before → after | $H(p)$ after |
|---|---|---|---|---|---|---|
| 1 | C1 | E-C1-0.8 | 0.2937 | correct | 0.2000 → 0.7576 | 0.7990 |
| 2 | C1 | E-C1-0.2 | 0.2787 | correct | 0.7576 → 0.9214 | 0.3973 |
| 3 | C2 | E-C2-0.8 | 0.2937 | correct | 0.2000 → 0.7576 | 0.7990 |
| 4 | C2 | E-C2-0.2 | 0.2787 | correct | 0.7576 → 0.9214 | 0.3973 |
| 5 | C3 | E-C3-0.8 | 0.2937 | wrong | 0.2000 → 0.0623 | 0.3367 |

At step 2 the remaining C1 items scored 0.2787 ($d$ = 0.2), 0.2714 (0.6) and 0.2691 (0.4).

| Concept | Final $p$ | $H$ | Status | Items | Stop reason |
|---|---|---|---|---|---|
| C1 | 0.9214 | 0.3973 | ASSESSED | 2 | ENTROPY |
| C2 | 0.9214 | 0.3973 | ASSESSED | 2 | ENTROPY |
| C3 | 0.0623 | 0.3367 | ASSESSED | 1 | ENTROPY |
| C4 | 0.2000 | 0.7219 | UNASSESSED | 0 | SKIPPED_ANCESTOR_UNMASTERED |

Why it stopped: C1 and C2 needed a second answer because $H = 0.7990 > 0.50$ after one; after two,
$H = 0.3973 \le 0.50$. One wrong answer on C3 gave $H = 0.3367 \le 0.50$, and $p = 0.0623 < 0.40$
hard-pruned C4. 5 items were used of $N_{\max} = 6$.

<details><summary>How these numbers were produced</summary>

Run from the repo root: `.venv/bin/python <scratchpad>/docs/scripts/c04_sweep.py`

```python
from adaptengine.api import Engine
from adaptengine.learner.mastery import entropy
from adaptengine.diagnostic.scoring import compute_eig

eng = Engine.from_files("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
answer = lambda a: a.target_concept in {"C1", "C2"}
st = eng.init_learner()
for aid in ["E-C1-0.2", "E-C1-0.4", "E-C1-0.6", "E-C1-0.8"]:
    print(aid, round(compute_eig(0.2, eng.activities[aid], eng.config, eng.model), 4))
print({x: round(compute_eig(0.7576, eng.activities[x], eng.config, eng.model), 4)
       for x in ["E-C1-0.2", "E-C1-0.4", "E-C1-0.6"]})
r = eng.diagnose(st, answer, session_id="ex")
for x in r.item_log:
    print(x.concept_id, x.activity_id, x.response, f"{x.eig:.4f}",
          f"{x.p_before:.4f}->{x.p_after:.4f}", f"H={entropy(x.p_after):.4f}")
for c, cr in r.concept_results.items():
    print(c, f"{cr.p:.4f} {cr.h:.4f}", cr.status.name, cr.n_items, cr.stop_reason.name)
print(r.total_items)
# one-answer entropies over the whole difficulty range (used under Limitations)
from adaptengine.learner.adapter import CustomBKT
m, cfg = CustomBKT(eng.config), eng.config
ds = [cfg.d_min + i * (cfg.d_max - cfg.d_min) / 900 for i in range(901)]
print("max H after 1 wrong", round(max(entropy(m.update(0.2, d, False, 0.0)) for d in ds), 4))
print("min H after 1 right", round(min(entropy(m.update(0.2, d, True, 0.0)) for d in ds), 4))
print({d: round(entropy(m.update(0.2, d, True, 0.0)), 4) for d in (0.8, 0.92, 0.95)})
```
</details>

## In the code

| Function or class | File | Config key | Default |
|---|---|---|---|
| `compute_eig` | `src/adaptengine/diagnostic/scoring.py` | `guess_coef`, `slip_base`, `slip_coef` | 0.30, 0.05, 0.25 |
| `candidate_sort_key` | `src/adaptengine/diagnostic/scoring.py` | — | 9-decimal rounding |
| `AdaptiveDiagnostic.run` (global cap) | `src/adaptengine/diagnostic/engine.py` | `n_max` | 6 |
| `AdaptiveDiagnostic.run` (per-concept cap) | `src/adaptengine/diagnostic/engine.py` | `concept_cap` | 2 |
| `AdaptiveDiagnostic.run` (entropy stop) | `src/adaptengine/diagnostic/engine.py` | `h_stop`, `min_items_per_concept` | 0.50, 1 |
| `AdaptiveDiagnostic._prune` | `src/adaptengine/diagnostic/engine.py` | `pruning_mode`, `skip_threshold` | `"hard"`, 0.40 |
| `AdaptiveDiagnostic._run_frontier` | `src/adaptengine/diagnostic/engine.py` | `selection_scope` | `"concept_sweep"` |
| `AdaptiveDiagnostic.run` (prior) | `src/adaptengine/diagnostic/engine.py` | `prior_mode`, `population_p0`, `p0` | `"flat"`, 0.24, 0.20 |
| `update_concept_evidence` | `src/adaptengine/learner/evidence.py` | `t_diag` | 0.0 |
| `DiagnosticResult`, `StopReason` | `src/adaptengine/diagnostic/engine.py` | — | — |
| `DIAGNOSTICS`, `Engine.diagnose` | `src/adaptengine/diagnostic/__init__.py`, `src/adaptengine/api.py` | `diagnostic_method` | `"sweep"` |
| `population_prior_config` | `src/adaptengine/core/config.py` | — | `prior_mode="population"`, 0.24 |
| `StateSpaceDiagnostic` (W7 T3.6 variant) | `src/adaptengine/diagnostic/state_space.py` | `MAX_CONCEPTS` (module constant) | 12 |

`StateSpaceDiagnostic` evaluates the same EIG over prerequisite-consistent mastery patterns and falls
back to the sweep above 12 goal concepts. It is not in the `DIAGNOSTICS` registry, so
`diagnostic_method` cannot select it; only tests call it.

## Tests

- `tests/unit/diagnostic/test_diagnostic.py` — caps (`test_adversarial_learner_bounded_by_n_max`),
  entropy stop, cold start, surprise answers, hard pruning, no repeats, immutability, determinism,
  D10 ties, `min_items_per_concept`, pruning modes, frontier scope, population prior, flag
  validation, and the state-space variant.
- `tests/regression/test_feedback_fixes.py` — `test_compute_eig_matches_hand_calc_at_d_06`, the
  diagnostic using the injected model, session ids and replay.
- `tests/regression/test_baseline_pins.py` — D59 pins (flat vs population prior).
- `tests/integration/test_state_session.py` — diagnostic results through the session layer.
- `experiments/tests/unit/test_diagnostics.py` — the sweep as an evaluation arm.

## Decisions

[D1](../project/DECISIONS.md#d1) global cap, [D2](../project/DECISIONS.md#d2) per-concept cap
(both lowered by D44), [D3](../project/DECISIONS.md#d3) entropy stop,
[D8](../project/DECISIONS.md#d8) descendant pruning, [D10](../project/DECISIONS.md#d10) tie-breaking,
[D44](../project/DECISIONS.md#d44) the four flags and the selected defaults ($N_{\max} = 6$,
cap 2), [D59](../project/DECISIONS.md#d59) flat prior by default,
[D59a](../project/DECISIONS.md#d59a) name of `population_prior_config()`,
[D49](../project/DECISIONS.md#d49) the `DIAGNOSTICS` registry (sweep stays the default).

## Limitations

- The EIG looks at one concept at a time. An answer on C3 says nothing to the sweep about C1 or C2,
  and the DAG is used only for ordering and pruning.
- At the cold-start prior $p_0 = 0.20$ one wrong answer always ends a concept (largest $H$ after one
  wrong answer over $d \in [0.05, 0.95]$ is 0.3584 $< 0.50$) and, below $p_{\text{skip}}$, prunes its
  whole subtree. One right answer ends it only on very hard items ($H$ = 0.799 at $d$ = 0.8, 0.5226
  at 0.92, 0.3939 at 0.95). A single slip on a root concept can therefore hide everything above it.
- With $N_{\max} = 6$ the sweep cannot reach most concepts of an 8-concept curriculum.
- In the final study the sweep's Brier score on scripted learners is far worse than bisection's for
  advanced learners (4-node 0.420 vs 0.036; 8-node 0.511 vs 0.036) and slightly better for novices
  ([T4](../../experiments/report/tables/T4.md)). In the simulated worlds it beats the prior-only
  baseline in 5 of 15 cells (E2 H3, [NOTES Outcomes](../../experiments/NOTES.md#outcomes),
  [T3](../../experiments/report/tables/T3.md)).

## Values checked

Read with `from adaptengine.core.config import DEFAULT_CONFIG, population_prior_config` and
`from adaptengine.diagnostic.state_space import MAX_CONCEPTS`; all run on 2026-11-21.

- `DEFAULT_CONFIG.p0` → 0.2
- `DEFAULT_CONFIG.t_diag` → 0.0
- `DEFAULT_CONFIG.guess_coef`, `.slip_base`, `.slip_coef` → 0.3, 0.05, 0.25
- `DEFAULT_CONFIG.n_max` → 6
- `DEFAULT_CONFIG.concept_cap` → 2
- `DEFAULT_CONFIG.h_stop` → 0.5
- `DEFAULT_CONFIG.min_items_per_concept` → 1
- `DEFAULT_CONFIG.skip_threshold` → 0.4
- `DEFAULT_CONFIG.pruning_mode` → `'hard'`
- `DEFAULT_CONFIG.selection_scope` → `'concept_sweep'`
- `DEFAULT_CONFIG.prior_mode` → `'flat'`
- `DEFAULT_CONFIG.population_p0` → 0.24
- `DEFAULT_CONFIG.diagnostic_method` → `'sweep'`
- `population_prior_config().prior_mode`, `.population_p0` → `'population'`, 0.24
- `MAX_CONCEPTS` → 12
