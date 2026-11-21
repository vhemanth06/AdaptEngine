# 03 · Item models: from difficulty to guess and slip

## Idea

A BKT update ([02](02_mastery_bkt.md)) needs two numbers per exercise: how often a learner who
has *not* mastered the concept still answers right (guess), and how often one who *has* mastered
it answers wrong (slip). AdaptEngine gets them from the exercise's authored difficulty $d$, either
by a fixed formula (the heuristic, the default) or from a profile fitted on real student data. The
choice changes how much one answer moves the belief, and so how many questions the engine asks.

## Notation

| Symbol | Meaning | Code name |
|---|---|---|
| $d$ | authored item difficulty in $[d_{\min}, d_{\max}] = [0.05, 0.95]$ | `Activity.difficulty` |
| $\kappa(d)$ | difficulty class of $d$: easy, medium or hard | `get_difficulty_class(d)` |
| $g(d)$, $s(d)$ | heuristic guess and slip (continuous in $d$) | `guess(d)`, `slip(d)` |
| $g_\kappa$, $s_\kappa$ | guess and slip of class $\kappa$ | `class_params[κ]["guess"]`, `["slip"]` |
| $d_\kappa$ | representative difficulty of class $\kappa$ | `DEFAULT_CLASS_PARAMS[κ]["rep_d"]` |
| $P_c$ | predicted probability of a correct answer | `model.predict_correct(p, d)` |
| $\pi_0$, $\lambda$ | fitted prior and learn rate stored in a profile | profile `p0`, `t_exercise` |

## Maths

**Heuristic (default, `model_profile = "heuristic"`, class `CustomBKT`).**
$g(d) = 0.30\,(1-d)$ and $s(d) = 0.05 + 0.25\,d$, used at the exact $d$ of the item (no classes,
no clamping; see [02](02_mastery_bkt.md)).

**Difficulty classes (D6).**

$$\kappa(d) = \begin{cases} \text{easy} & d < 0.35 \\ \text{medium} & 0.35 \le d < 0.65 \\ \text{hard} & d \ge 0.65 \end{cases}$$

A $d$ outside $[d_{\min}, d_{\max}]$ raises `ValidationError`.

**Class adapter.** The class version of the heuristic takes the heuristic at one representative
difficulty per class, $g_\kappa = g(d_\kappa)$, $s_\kappa = s(d_\kappa)$:

| Class | $d_\kappa$ | $g_\kappa$ | $s_\kappa$ |
|---|---|---|---|
| easy | 0.20 | 0.240 | 0.100 |
| medium | 0.50 | 0.150 | 0.175 |
| hard | 0.80 | 0.060 | 0.250 |

`PyBKTAdapter` uses these class values, so it equals `CustomBKT` only at $d = d_\kappa$; at other
difficulties they differ (example below, $d = 0.4$).

**Fitted profile (`model_profile = "config/fitted_*.json"`, class `ClassBKT`).** Same maths, with the
fitted $g_\kappa$, $s_\kappa$ of the item's class:

$$P_c = p\,(1 - s_{\kappa(d)}) + (1 - p)\,g_{\kappa(d)},$$

and the Bayes and transition steps of [02](02_mastery_bkt.md) with $g_{\kappa(d)}$, $s_{\kappa(d)}$.
How strongly a wrong answer lowers the odds $p/(1-p)$ is the factor $s_\kappa / (1 - g_\kappa)$; a
correct answer multiplies them by $(1 - s_\kappa) / g_\kappa$.

**What the profile is used for.**

- Its class guess and slip: always, when the profile is selected (`build_model`).
- Its prior $\pi_0$: **never**. Learners start at `p0` = 0.20 (and the sweep at `population_p0`
  only when `prior_mode = "population"`).
- Its learn rate $\lambda$: only with `use_profile_learn = True` (default False). `profile_config`
  then copies $\lambda$ into `t_exercise`; `t_lesson` is unchanged. `use_profile_learn` with the
  heuristic is rejected.
- The selected model is the engine's one model (D33): diagnostic, answer updates, exercise
  choice and planner projections. An explicit `model=` argument to `Engine` still wins. With a
  fitted profile, `serialize_plan` adds the profile's name, file SHA-256, fit code hash and
  timestamp under `"model_profile"`.

**Fitting (EM).** `experiments/core/realdata.py` fits standard BKT (prior, learn, guess, slip; no
forgetting) by a vectorised Baum–Welch (`fast_em`): 5 random restarts from pyBKT 1.4.3's ranges
(prior $U(0,1)$, learn $U(0,0.4)$, guess $U(0,0.4)$, slip $U(0,0.3)$), best by log-likelihood, stop at
$|\Delta \log L| \le 0.005$ or 100 iterations. Two levels:

| Fit | Function | Shared across skills | Per class or skill |
|---|---|---|---|
| class profile | `fit_classes` | one prior, one learn | guess and slip per class: easy, medium, hard, and `unrated` (items with fewer than 20 answers) |
| per skill | `fit_per_skill` | — | prior, learn, guess, slip for each skill separately, no classes |

Item difficulty in the data is $d = 1 - (\text{share of correct answers on the item})$, clipped to
$[0.05, 0.95]$ and mapped by $\kappa$. Each sequence is one (student, skill) pair. The profile files
keep the easy, medium and hard pairs plus the shared prior and learn rate. "Per skill" exists
only in the evaluation (E3 Part A): it is a comparison model with its own parameters for every
skill, and the engine cannot use it because this course's concepts are not those skills.

### Profile files

| File | Data | Prior (unused) | Learn | Guess / slip: easy · medium · hard | Use |
|---|---|---|---|---|---|
| `config/fitted_assist09.json` | ASSISTments 2009–10 skill-builder, 81 maths skills | 0.7415 | 0.072513 | 0.369/0.132 · 0.147/0.342 · 0.058/0.646 | recommended fitted profile |
| `config/fitted_ct.json` | Cognitive Tutor, 9 maths skills, 15,935 answers | 0.634033 | 0.11673 | 0.477/0.111 · 0.277/0.366 · 0.002/0.634 | robustness cross-check only |
| `config/fitted_sim.json` | this project's own simulator | 0.484101 | 0.245312 | 0.518/0.008 · 0.548/0.327 · 0.026/0.241 | do not use (circular) |

`load_profile` rejects a file with a missing class, a guess or slip outside $(0, 1)$,
$g_\kappa + s_\kappa \ge 1$, or a learn rate outside $[0, 1)$. It keeps the file's
`constraint_warnings`: both maths fits flag hard `slip>0.5`. The demo API accepts only the names
`heuristic`, `fitted_assist09` and `fitted_ct`, never a path. The CLI takes `--model-profile <path>`
and `--config <file.json>` (D89).

## Worked example

Three 4-node exercises, one per class, for a learner at $p = 0.2$ and at $p = 0.9$. "Heuristic"
is the engine default (`CustomBKT`, exact $d$); "class heuristic" is `PyBKTAdapter` (D6 class
values); "fitted" is `config/fitted_assist09.json` (`ClassBKT`).

| Item | $d$ | Class | $p$ | $P_c$ heuristic | $P_c$ class heuristic | $P_c$ fitted_assist09 |
|---|---|---|---|---|---|---|
| `E-C1-0.2` | 0.2 | easy | 0.2 | 0.3720 | 0.3720 | 0.4688 |
| `E-C1-0.2` | 0.2 | easy | 0.9 | 0.8340 | 0.8340 | 0.8180 |
| `E-C1-0.4` | 0.4 | medium | 0.2 | 0.3140 | 0.2850 | 0.2491 |
| `E-C1-0.4` | 0.4 | medium | 0.9 | 0.7830 | 0.7575 | 0.6073 |
| `E-C1-0.8` | 0.8 | hard | 0.2 | 0.1980 | 0.1980 | 0.1171 |
| `E-C1-0.8` | 0.8 | hard | 0.9 | 0.6810 | 0.6810 | 0.3246 |

Odds factor of a wrong answer, $s/(1-g)$: easy 0.132 (heuristic) vs 0.209 (fitted); medium 0.183 vs
0.400; hard 0.266 vs 0.685. Under the fitted profile a wrong answer on a hard item is weak evidence,
because fitted hard items have slip 0.646: a learner at $p = 0.9$ gets them right only 32 % of the time.

With the fitted profile selected, learners still start at $p = 0.2$ (the profile's prior 0.7415 is
unused) and `t_exercise` stays 0.05; with `use_profile_learn = True` it becomes 0.072513.

<details><summary>How these numbers were produced</summary>

The script below, saved as `c03_items.py` outside the repository and run from the repository root:

```bash
.venv/bin/python <path-to>/c03_items.py
```

```python
from dataclasses import replace
from adaptengine.api import Engine
from adaptengine.core.config import DEFAULT_CONFIG as cfg
from adaptengine.learner.adapter import DEFAULT_CLASS_PARAMS, get_difficulty_class, PyBKTAdapter
from adaptengine.learner.profiles import build_model, load_profile, profile_config

print("D6 class params:", {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in DEFAULT_CLASS_PARAMS.items()})
fit_cfg = replace(cfg, model_profile="config/fitted_assist09.json")
heur, fit, pyb = build_model(cfg), build_model(fit_cfg), PyBKTAdapter(cfg)
print(type(heur).__name__, type(fit).__name__, "pyBKT available:", pyb.is_library_available)
eng = Engine.from_files("data/curriculum/curriculum_4node.json", "data/curriculum/activities_4node.json")
for aid in ("E-C1-0.2", "E-C1-0.4", "E-C1-0.8"):
    d = eng.activities[aid].difficulty
    k = get_difficulty_class(d)
    gp = fit.class_params[k]
    for p in (0.2, 0.9):
        print(f"{aid} d={d} class={k} p={p}: heuristic P_c={heur.predict_correct(p, d):.4f} "
              f"class-heuristic={pyb.predict_correct(p, d):.4f} fitted_assist09 P_c={fit.predict_correct(p, d):.4f}")
    lr_h = heur.cfg.slip_base + heur.cfg.slip_coef * d, 1 - heur.cfg.guess_coef * (1 - d)
    print(f"   wrong-answer odds factor s/(1-g): heuristic={lr_h[0]/lr_h[1]:.3f} fitted={gp['slip']/(1-gp['guess']):.3f}")
pr = load_profile("config/fitted_assist09.json")
print("profile p0 (unused):", pr.p0, "t_exercise:", pr.t_exercise, "warnings:", dict(pr.warnings))
print("learner start p with profile:", Engine.from_files("data/curriculum/curriculum_4node.json",
      "data/curriculum/activities_4node.json", config=fit_cfg).init_learner().concepts["C1"].p)
print("t_exercise default / with use_profile_learn:", profile_config(fit_cfg).t_exercise,
      profile_config(replace(fit_cfg, use_profile_learn=True)).t_exercise)
print("boundaries:", [(d, get_difficulty_class(d)) for d in (0.05, 0.3499, 0.35, 0.6499, 0.65, 0.95)])
```

Output:

```
D6 class params: {'easy': {'rep_d': 0.2, 'guess': 0.24, 'slip': 0.1}, 'medium': {'rep_d': 0.5, 'guess': 0.15, 'slip': 0.175}, 'hard': {'rep_d': 0.8, 'guess': 0.06, 'slip': 0.25}}
CustomBKT ClassBKT pyBKT available: True
E-C1-0.2 d=0.2 class=easy p=0.2: heuristic P_c=0.3720 class-heuristic=0.3720 fitted_assist09 P_c=0.4688
E-C1-0.2 d=0.2 class=easy p=0.9: heuristic P_c=0.8340 class-heuristic=0.8340 fitted_assist09 P_c=0.8180
   wrong-answer odds factor s/(1-g): heuristic=0.132 fitted=0.209
E-C1-0.4 d=0.4 class=medium p=0.2: heuristic P_c=0.3140 class-heuristic=0.2850 fitted_assist09 P_c=0.2491
E-C1-0.4 d=0.4 class=medium p=0.9: heuristic P_c=0.7830 class-heuristic=0.7575 fitted_assist09 P_c=0.6073
   wrong-answer odds factor s/(1-g): heuristic=0.183 fitted=0.400
E-C1-0.8 d=0.8 class=hard p=0.2: heuristic P_c=0.1980 class-heuristic=0.1980 fitted_assist09 P_c=0.1171
E-C1-0.8 d=0.8 class=hard p=0.9: heuristic P_c=0.6810 class-heuristic=0.6810 fitted_assist09 P_c=0.3246
   wrong-answer odds factor s/(1-g): heuristic=0.266 fitted=0.685
profile p0 (unused): 0.7415 t_exercise: 0.072513 warnings: {'hard': ('slip>0.5',)}
learner start p with profile: 0.2
t_exercise default / with use_profile_learn: 0.05 0.072513
boundaries: [(0.05, 'easy'), (0.3499, 'easy'), (0.35, 'medium'), (0.6499, 'medium'), (0.65, 'hard'), (0.95, 'hard')]
```

</details>

## In the code

| Function or class | File | Config key | Default value |
|---|---|---|---|
| `get_difficulty_class` | `src/adaptengine/learner/adapter.py` | `d_min`, `d_max` | 0.05, 0.95 |
| `derive_class_params`, `DEFAULT_CLASS_PARAMS` | `src/adaptengine/learner/adapter.py` | `guess_coef`, `slip_base`, `slip_coef` | 0.30, 0.05, 0.25 |
| `CustomBKT`, `PyBKTAdapter` | `src/adaptengine/learner/adapter.py` | — | — |
| `load_profile`, `ClassBKT`, `build_model` | `src/adaptengine/learner/profiles.py` | `model_profile` | `"heuristic"` |
| `profile_config` | `src/adaptengine/learner/profiles.py` | `use_profile_learn` | False |
| `resolve_profile_path` (working directory first, then repository root) | `src/adaptengine/core/config.py` | `model_profile` | — |
| `fast_em`, `fit_classes`, `fit_per_skill`, `classify`, `crossvalidate` | `experiments/core/realdata.py` | — | 5 restarts, tol 0.005, 100 iterations |
| E3 runner | `experiments/runners/e3_calibration.py` | — | — |

## Tests

- `tests/unit/learner/test_adapter.py` — D6 class boundaries, adapter vs oracle parity, answer sequence.
- `tests/unit/learner/test_profiles.py` — heuristic default, profile loading and rejection, `ClassBKT`
  hand values, profile prior ignored, learn rate only with the switch, one shared model, provenance.
- `tests/regression/test_feedback_fixes.py` — `test_pybkt_adapter_genuine_parity`.
- `tests/integration/test_cli_config.py` — `--model-profile` and `--config` on the CLI.
- `tests/integration/test_closed_loop_planners.py` — closed loop with a fitted profile.
- `frontend/api/tests/test_sessions.py`, `frontend/api/tests/test_parity.py` — named profiles in the demo API.
- `experiments/tests/unit/test_realdata.py` — EM recovers known parameters; folds never share a student.

### pyBKT parity

`PyBKTAdapter` also builds a real `pyBKT` model with the same prior (`p0`), learn rate
(`t_exercise`), class guess and slip, and no forgetting. Three tests tie the maths together:

- `tests/regression/test_feedback_fixes.py::test_pybkt_adapter_genuine_parity` runs the answer
  sequence 1, 0, 0, 1, 1, 0, 1, 1 through pyBKT's `predict` and through the adapter, one class at a
  time at $d_\kappa$, and requires the largest difference in predicted mastery and predicted
  correctness to be below $10^{-6}$. A copy with every slip raised by 0.01 must differ by more than
  $10^{-4}$. The test is skipped if pyBKT is missing, unless `REQUIRE_PYBKT=1` is set, which makes it fail.
- `tests/unit/learner/test_adapter.py::test_adapter_oracle_parity_at_representative_difficulties`
  checks `PyBKTAdapter` against `CustomBKT` within $10^{-9}$ at $d_\kappa$ for predictions and
  updates ($t$ = 0, 0.05, 0.20).
- `tests/unit/learner/test_profiles.py::test_classbkt_equals_pybkt_adapter_f2_tc3` checks that
  `ClassBKT` and `PyBKTAdapter` give identical results for the same class values.

## Decisions

- [D6](../project/DECISIONS.md#d6) — three difficulty classes and their boundaries.
- [D33](../project/DECISIONS.md#d33) — one observation model everywhere.
- [D48](../project/DECISIONS.md#d48) — fitted parameters as named profiles; the heuristic stays the
  default until a fitted profile beats it on held-out data from this course's learners.
- [D60](../project/DECISIONS.md#d60) — `model_profile`, prior never used, `use_profile_learn`,
  `fitted_sim` not to be used, `fitted_ct` cross-check only.
- [D61](../project/DECISIONS.md#d61) — evaluation of heuristic vs fitted.
- [D89](../project/DECISIONS.md#d89) — CLI access to `--model-profile` and `--config`.

## Limitations

- Both real-data fits come from school maths, not Python programming.
- Difficulties in this repository's curricula are authored, not measured, so the class of an item
  may be wrong. In the fits, difficulty is measured from the data.
- Three classes are coarse: within a class every item gets the same guess and slip.
- One prior and learn rate are shared across all skills in the class profile.
- On held-out real students the fitted class profile predicts answers better than the D6 class
  heuristic (assist09 Brier 0.195 vs 0.225, ECE 0.009 vs 0.132; ct Brier 0.207 vs 0.245), and the
  per-skill fit is only slightly better again (assist09 Brier 0.193):
  [`experiments/report/tables/T5.md`](../../experiments/report/tables/T5.md). The E3 Part A
  "heuristic" is the class version (`PyBKTAdapter` values with prior $p_0$ and learn
  $t_{\text{exercise}}$), not the continuous default.
- Weaker evidence per answer costs questions: in simulation the sweep asks on average 0.48 more
  diagnostic items with `fitted_assist09` and 1.30 more with `fitted_ct` (E3 H3), while next-answer
  Brier improves on every curriculum (E3 H2). See the Outcomes section of
  [`experiments/NOTES.md`](../../experiments/NOTES.md).

## Values checked

All read with `.venv/bin/python` from the repository root on 2026-11-21:

- `DEFAULT_CONFIG.model_profile` → `"heuristic"`; `DEFAULT_CONFIG.use_profile_learn` → False
  (`from adaptengine.core.config import DEFAULT_CONFIG`)
- `DEFAULT_CONFIG.guess_coef` → 0.3; `slip_base` → 0.05; `slip_coef` → 0.25; `d_min` → 0.05; `d_max` → 0.95
- `DEFAULT_CONFIG.p0` → 0.2; `DEFAULT_CONFIG.t_exercise` → 0.05; `DEFAULT_CONFIG.population_p0` → 0.24
- `DEFAULT_CLASS_PARAMS` → easy 0.24/0.10, medium 0.15/0.175, hard 0.06/0.25 at $d_\kappa$ 0.20/0.50/0.80
  (`from adaptengine.learner.adapter import DEFAULT_CLASS_PARAMS`)
- Class boundaries: `get_difficulty_class(0.3499)` → easy, `(0.35)` → medium, `(0.6499)` → medium, `(0.65)` → hard
- `load_profile("config/fitted_assist09.json")`: `p0` → 0.7415, `t_exercise` → 0.072513,
  `warnings` → `{'hard': ('slip>0.5',)}`, class values as in the profile table
- `config/fitted_ct.json` and `config/fitted_sim.json` values read with `json.load`
- `realdata.MIN_ITEM_ANSWERS` → 20, `fast_em` defaults `num_fits=5`, `tol=0.005`, `maxiter=100`
  (read from `experiments/core/realdata.py`)
