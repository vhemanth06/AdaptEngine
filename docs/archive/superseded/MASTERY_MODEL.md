> Archived (21 Nov 2026). Historical record of the project at the time it was written; paths, commands and numbers may no longer match the repository. Current documentation: [docs/README.md](../../README.md).

# Mastery Model Specification

This document defines the mathematical foundation, evidence state semantics, parameter heuristics, and adapter mappings for AdaptEngine's Bayesian Knowledge Tracing (BKT) implementation.

---

## 1. Mathematical Equations

For a given concept with prior mastery probability $p \in [0, 1]$ and an exercise with synthetic difficulty $d \in [d_{\min}, d_{\max}]$:

### Item Response Parameters
- **Guess probability:**
  $$g(d) = \text{guess\_coef} \cdot (1 - d) = 0.30 \cdot (1 - d)$$
- **Slip probability:**
  $$s(d) = \text{slip\_base} + \text{slip\_coef} \cdot d = 0.05 + 0.25 \cdot d$$
- **Predicted success probability:**
  $$P_c(p, d) = p \cdot (1 - s(d)) + (1 - p) \cdot g(d)$$

### Bayesian Observation Update
- **If response is correct ($y = 1$):**
  $$p' = \frac{p \cdot (1 - s(d))}{P_c(p, d)}$$
- **If response is incorrect ($y = 0$):**
  $$p' = \frac{p \cdot s(d)}{1 - P_c(p, d)}$$

### Learning Transition
- **Post-transition mastery:**
  $$p'' = p' + (1 - p') \cdot T$$
  where $T \in [0, 1]$ is the transition parameter ($T_{\text{exercise}} = 0.05$, $T_{\text{diag}} = 0.0$, $T_{\text{lesson}} = 0.20$).

> **Decision D5 Note:** In AdaptEngine, the value stored after an exercise update is the **post-transition** probability $p''$. Tests assert both pre-transition $p'$ and post-transition $p''$.

---

## 2. Reference Values Table

The following reference constants are pinned in the test suite and verification scripts:

| Prior $p$ | Difficulty $d$ | Correct? | Transition $T$ | Posterior $p'$ | Stored Value $p''$ | Note |
|---|---|---|---|---|---|---|
| 0.50 | 0.50 | Correct | 0.00 | 0.8462 | 0.8462 | Pre-transition baseline |
| 0.50 | 0.50 | Incorrect | 0.00 | 0.1707 | 0.1707 | Downward update |
| 0.50 | 0.50 | Correct | 0.05 | 0.8462 | 0.8538 | Standard exercise update |
| 0.50 | 0.50 | Incorrect | 0.05 | 0.1707 | 0.2122 | Standard exercise update |
| 0.90 | 0.50 | Incorrect | 0.00 | 0.6495 | 0.6495 | Surprise incorrect response |

---

## 3. Synthetic Parameters (Non-Empirical Heuristics)

> **Important Notice:** The parameters below are **synthetic heuristics** designed for prototype verification and algorithm testing. They are **not** fitted against empirical learner telemetry.

| Parameter | Symbol | Value | Interpretation | Status |
|---|---|---|---|---|
| Prior mastery | $p_0$ | 0.20 | Default mastery assigned on cold start | Synthetic heuristic |
| Mastery threshold | $\theta$ | 0.85 | Target probability for concept mastery | Synthetic heuristic |
| Exercise transition | $T_{\text{exercise}}$ | 0.05 | Latent learning probability per exercise | Synthetic heuristic |
| Diagnostic transition | $T_{\text{diag}}$ | 0.00 | Pure observation update (no learning during diagnostic) | Exact mathematical design |
| Lesson transition | $T_{\text{lesson}}$ | 0.20 | Prior shift from direct instructional exposure | Synthetic heuristic |
| Guess coefficient | $\text{guess\_coef}$ | 0.30 | Scales guess probability with $(1 - d)$ | Synthetic heuristic |
| Slip base | $\text{slip\_base}$ | 0.05 | Minimum slip probability at $d = 0$ | Synthetic heuristic |
| Slip coefficient | $\text{slip\_coef}$ | 0.25 | Scales slip probability with $d$ | Synthetic heuristic |
| Difficulty bounds | $[d_{\min}, d_{\max}]$ | $[0.05, 0.95]$ | Valid range for exercise difficulties | Strict engine constraint |

---

## 4. Shannon Entropy and Uncertainty Interpretation

Binary Shannon entropy is defined as:
$$H(p) = -p \log_2(p) - (1 - p) \log_2(1 - p)$$
with boundary conventions $H(0) = H(1) = 0$.

### Critical Invariant on Entropy Interpretation:
$H(p)$ represents the uncertainty regarding a **binary latent mastery state** (whether the learner is in the mastered state $L=1$ or unmastered state $L=0$).
- $H(p)$ is **not** confidence in a parameter estimate.
- $H(p)$ does **not** monotonically decrease merely because evidence accumulates.
- A surprising response can cause entropy to **increase**. For example, when a learner with high mastery ($p = 0.90, H \approx 0.469$) answers a medium exercise incorrectly, posterior mastery drops to $p' = 0.6495$, causing entropy to surge to $H \approx 0.935$.

---

## 5. Evidence-State Semantics

Each concept in the learner state tracks three distinct layers of interaction:
1. **Instructional Exposure (`lessons_done`):** Incremented by completed lesson activities. Raises prior mastery via $T_{\text{lesson}} = 0.20$. **Lessons never mark a concept as `ASSESSED` and do not count toward evidence-mastered.**
2. **Observed Assessment Evidence (`responses`, `correct_responses`):** Incremented only by observed exercise and diagnostic attempts. A concept attains `status = ASSESSED` only after at least 1 assessment response.
3. **Evidence-Mastered (`evidence_mastered`):**
   $$\text{evidence\_mastered} := p \ge \theta \text{ and } \text{responses} \ge k$$
   Under Decision D4, $k = 2$ observed responses and $p \ge 0.85$. Replaying a lesson multiple times (even 8x to achieve $p = 0.865 > \theta$) will **never** mark the concept as evidence-mastered.

### Idempotency and Time Rules
- **Attempt Idempotency:** Every interaction event is tagged with an `attempt_id`. An event whose `attempt_id` has already been recorded in `seen_attempt_ids` is treated as a deterministic no-op (state unchanged).
- **Monotonic Practice Time:** `last_practice_day = max(old_practice_day, event.day)`. Practice days never move backwards even if historical events are recorded out of order.

---

## 6. Adapter Difficulty Mapping (D6)

The `PyBKTAdapter` maps continuous difficulties $d \in [d_{\min}, d_{\max}]$ into 3 discrete item classes:

| Class Name | Difficulty Range | Representative $d$ | Mapped Guess $g$ | Mapped Slip $s$ |
|---|---|---|---|---|
| **easy** | $d < 0.35$ | 0.20 | 0.240 | 0.100 |
| **medium** | $0.35 \le d < 0.65$ | 0.50 | 0.150 | 0.175 |
| **hard** | $d \ge 0.65$ | 0.80 | 0.060 | 0.250 |

At representative difficulties, predictions and Bayesian updates computed by `PyBKTAdapter` equal those of the `CustomBKT` oracle within $10^{-9}$.

## 7. Fitted Item-Model Profiles (Plan 2, F2, D60)

The engine uses one observation model everywhere (D33): the diagnostic, the planner's projections
and answer updates. `EngineConfig.model_profile` selects it.

| `model_profile` | Model | Guess / slip |
|---|---|---|
| `"heuristic"` (default) | `CustomBKT` | the continuous D6 heuristic above, $g(d) = 0.30(1-d)$, $s(d) = 0.05 + 0.25d$ |
| path to `config/fitted_*.json` | `ClassBKT` (`learner/profiles.py`) | one guess/slip pair per D6 class (easy $d < 0.35$, medium $d < 0.65$, hard otherwise) |

- `ClassBKT` uses the same class maths as `PyBKTAdapter`, without importing pyBKT. A path is resolved
  from the working directory first, then from the repository root.
- **The profile's prior is never used.** Learners start at `p0` (and the sweep at `population_p0`
  when `prior_mode = "population"`).
- **The profile's learn rate** is used only when `use_profile_learn = True`. The engine then runs on
  a copy of the config with `t_exercise` from the profile. The default keeps the D6 learn rate, so
  the effect of guess/slip can be measured on its own.
- **Provenance:** with a fitted profile, `serialize_plan` adds `"model_profile"` (profile name,
  file SHA-256, the fit's code hash and timestamp) next to `config_hash`. With the heuristic the
  serialized plan is unchanged.
- An explicit `model=` argument to `Engine` still wins over `model_profile`.
- The demo API accepts the named profiles `heuristic`, `fitted_assist09` and `fitted_ct` only,
  never a path and never `fitted_sim`.

### Profile files

| File | Data | Prior (unused) | Learn | Guess / slip: easy · medium · hard | Use |
|---|---|---|---|---|---|
| `config/fitted_assist09.json` | ASSISTments 2009–10 skill-builder, 81 maths skills | 0.74 | 0.0725 | 0.369/0.132 · 0.147/0.342 · 0.058/0.646 | **Recommended** fitted profile |
| `config/fitted_ct.json` | Cognitive Tutor, 9 maths skills, 15,935 answers (written from `experiments/results/bkt_fit_ct.json` with `python experiments/fit_bkt.py ct-profile`, no refit) | 0.63 | 0.117 | 0.477/0.111 · 0.277/0.366 · 0.002/0.634 | Robustness cross-check only |
| `config/fitted_sim.json` | our own simulator (world S0) | 0.48 | 0.245 | 0.518/0.008 · 0.548/0.327 · 0.026/0.241 | **Do not use**: circular, and guess > 0.5 makes medium items nearly useless |

`load_profile` rejects a file with a missing class, a guess or slip outside (0, 1), guess + slip
≥ 1, or a learn rate outside [0, 1). It keeps the file's `constraint_warnings` (both maths fits flag
hard `slip>0.5`).

### Caveats

- Both fits come from school **maths** data, not Python programming; the heuristic stays the
  default until a fitted profile beats it on held-out data from this course's learners (D48).
- Difficulties in this repo's curricula are authored, not measured, so the easy/medium/hard mapping
  may be wrong.
- With `fitted_assist09`, one answer carries about 55–60% of the information the heuristic assumes.
  Hard items have slip ≈ 0.65, so a wrong answer on a hard item is weak evidence (odds × 0.69), and
  information-gain item choice prefers easy and medium items. More questions are needed for the
  same certainty.
- θ = 0.85 and k = 2 (D4) are decision rules; no fit estimates them.

### Using a fitted profile from the terminal (Plan 2.5, D89)

Every CLI command accepts `--model-profile <path>` and `--config <file.json>`:

```bash
python -m adaptengine update --curriculum data/curriculum/curriculum_8node.json \
  --activities data/curriculum/activities_8node.json --snapshot snapshot.json \
  --activity E-C1-0.2 --response correct --day 1 --model-profile config/fitted_assist09.json
```

The CLI result equals `Engine.from_files(..., config=replace(DEFAULT_CONFIG,
model_profile="config/fitted_assist09.json"))` in Python. To use the profile's learn rate as well,
put `{"model_profile": "config/fitted_assist09.json", "use_profile_learn": true}` in a file and
pass `--config`. `--model custombkt|pybkt` cannot be combined with a fitted profile.
