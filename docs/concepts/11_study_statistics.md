# 11 — The statistics of the final study

## Idea

The study compares arms on the same simulated learners, so each learner gives a paired difference
and luck in who the learners are cancels out. A difference is reported with a 95 % bootstrap
interval, and called better, no different or worse by where that interval lies relative to 0.
Probabilities the engine gives (such as "70 % chance of a right answer") are scored for accuracy
and calibration, on real students only out of fold. Every hypothesis and its decision rule is fixed
before the run, and a full run cannot start otherwise.

## Notation

| Symbol | Meaning | Code name |
|---|---|---|
| $i$ | a learner (seed), $i = 1 \dots N$ | `per_learner["seed"]` |
| $x_i$, $z_i$ | an outcome of learner $i$ under arm A and arm B (e.g. goal mastered, 0 or 1) | `per_learner[metric]` |
| $\Delta_i = x_i - z_i$ | paired difference | `paired` |
| $\bar\Delta$ | mean paired difference | `diff` |
| $M$ | number of bootstrap resamples | `BOOT_N` |
| $\bar\Delta^{*}_{(j)}$ | $j$-th smallest of the $M$ resampled means | — |
| $p_j$, $y_j$ | a predicted probability of a right answer and the answer (1 right, 0 wrong), $j = 1 \dots n$ | pairs `(p, y)` |
| $n_+$, $n_-$ | number of right / wrong answers | — |
| $R_+$ | sum of the midranks of the right answers when all $p_j$ are ranked | — |
| $b$ | a calibration bin, $b = 0 \dots 9$ | `_bin` |

## Maths

**Paired difference.** Both arms see the same learners (same seeds, checked before every contrast)
and the same keyed draws ([10](10_evaluation.md)):

$$\bar\Delta = \frac{1}{N}\sum_{i=1}^{N} (x_i - z_i).$$

**Paired bootstrap 95 % interval.** Draw $N$ learners with replacement from the $N$ differences,
take the mean, and repeat $M = 2000$ times with `random.Random(20260)` (the same seed for every
contrast). Sort the means; the interval is the percentile interval

$$\big[\bar\Delta^{*}_{(51)},\ \bar\Delta^{*}_{(1950)}\big] \quad (\text{0-based indices } \lfloor 0.025 M \rfloor = 50 \text{ and } \lfloor 0.975 M \rfloor - 1 = 1949),$$

rounded to 4 decimals. Reading: **better** if the lower bound is $> 0$, **worse** if the upper bound
is $< 0$, otherwise **no difference** (the interval includes 0).

**Scores of predicted probabilities** (lower is better except AUC):

$$\text{Brier} = \frac{1}{n}\sum_j (p_j - y_j)^2, \qquad \text{log-loss} = -\frac{1}{n}\sum_j \big[y_j \log q_j + (1-y_j)\log(1-q_j)\big],\ q_j = \min(1-10^{-6}, \max(10^{-6}, p_j)).$$

$$\text{AUC} = \frac{R_+ - n_+(n_+ + 1)/2}{n_+\, n_-}$$

where tied $p_j$ share the average of their ranks (midranks), so a tie counts as one half. AUC is
undefined when all answers are right or all wrong. It measures ranking only: 0.5 is chance.

**Expected calibration error.** Ten equal-width bins, $b = \min(9, \lfloor 10\,p_j \rfloor)$:

$$\text{ECE} = \frac{1}{n}\sum_{b=0}^{9} \Big| \sum_{j \in b} p_j - \sum_{j \in b} y_j \Big| = \sum_b \frac{n_b}{n}\,\big|\bar p_b - \bar y_b\big|.$$

The **reliability diagram** plots, per bin, the mean prediction $\bar p_b$ against the observed
rate $\bar y_b$; a calibrated model lies on the diagonal (figures `F3_reliability_realdata`,
`F3b_reliability_attempts` in `experiments/report/figures/`).

**Held-out evaluation on real students (E3 Part A).** Students (not answers) are shuffled with
`np.random.RandomState(42)` and split into 5 folds with `np.array_split`. For fold $k$, the models
are fitted on the other four folds with EM seed $42 + k$; item difficulty and its D6 class are
recomputed from training students only (items with fewer than 20 answers form an "unrated"
class). Predictions on the held-out students of all 5 folds are pooled and scored once ("pooled
out-of-fold"). No student is ever in both the training and the test part of a fold.

**Pre-registration.** Each experiment has `experiments/preregistration/E<n>_<date>.md` with three
lines the guard reads: `Status: Registered`, `Registered UTC: <time>`, `Code hash: <SHA-256 over
src/**/*.py>` (an amendment may add a later `Code hash:` line; the last one counts). A full run
refuses to start unless the status is Registered, the code hash equals the current one, and the
time is present; `--smoke` runs are always allowed. The file states the arms, cells, seeds, metrics
and, per hypothesis, a decision rule written in terms of the intervals above (for example E1 H2:
"the upper bound of the adapt − static CI is ≥ 0 in both" S1 headline cells). After the run the
runner applies that rule and writes `held: true` or `false` with an evidence string into the
results file (`null` for descriptive questions); `experiments/report/tables/H.md` lists them. A
failed hypothesis is reported as failed, not re-run or re-tuned (D99: improvement is claimed only
where a pre-registered paired contrast shows it).

## Worked example

**Calibration on real students: ASSISTments 2009, E3 Part A.** 297 016 held-out answers, 5 folds by
student, pooled out of fold.

| Item model | Brier | Log-loss | AUC | ECE |
|---|---|---|---|---|
| `heuristic_class_D6` (engine default $g(d)$, $s(d)$ by D6 class) | 0.2252 | 0.6438 | 0.6858 | 0.1324 |
| `fitted_class_profile` (guess/slip per class fitted on training folds) | 0.1948 | 0.5753 | 0.7072 | 0.0086 |

Recomputing ECE as $\sum_b n_b\,|\bar p_b - \bar y_b| / n$ from the stored reliability bins gives
0.1324 and 0.0086, equal to the stored values (0.132 vs 0.009 in table T5). The bins show why the
heuristic is off: in $[0.2, 0.3)$ it predicts 0.264 on average while students answered 0.517 right
(57 192 answers); in $[0.8, 0.9)$ it predicts 0.846 against 0.792 (105 917 answers). The fitted
profile stays within 0.03 of the diagonal in every bin with data, for example 0.655 vs 0.662 in
$[0.6, 0.7)$. This is E3 H1 (rule: pooled out-of-fold Brier and ECE both lower on both datasets):
held.

**Paired interval: adapt − static, S1 | `8node_x10` | B15 | calm (E1 headline cell).** $N = 1000$
learners, seeds 1000–1999. Goal-mastery rate: adapt 0.263, static 0.227. Of the 1000 paired
differences, 36 are $+1$ (adapt mastered the goal, static did not), 0 are $-1$, and 964 are 0.
So $\bar\Delta = 36/1000 = +0.036$. The bootstrap from the per-learner vectors gives
$[+0.025, +0.048]$, identical to the stored contrast. The interval lies entirely above 0, so the
reading is **better**. With the 4-node S1 cell ($+0.004$ $[-0.007, +0.015]$, no difference), both
upper bounds are $\ge 0$, so E1 H2 held.

<details><summary>How these numbers were produced</summary>

`PYTHONPATH=. .venv/bin/python s11_stats.py` from the repository root (reads the stored results;
nothing is re-run):

```python
import json
from experiments.core import metrics as M

h = json.load(open("experiments/results/E3_calibration.json"))["realdata"]["assist09"]["heldout"]
print("folds", h["folds"], "by", h["fold_unit"])
for m in ("heuristic_class_D6", "fitted_class_profile"):
    r = h["pooled_oof"][m]
    ece = sum(b["n"] * abs(b["mean_p"] - b["freq"]) for b in r["reliability"] if b["n"]) / r["n"]
    print(m, "n", r["n"], "ECE recomputed %.4f stored %.4f" % (ece, r["ece"]),
          "Brier %.4f log-loss %.4f AUC %.4f" % (r["brier"], r["log_loss"], r["auc"]))
    # (also prints each non-empty reliability bin: lo, hi, n, mean_p, freq)

e1 = json.load(open("experiments/results/E1_safety_outcomes.json"))  # 64 MB, loaded once
cell = next(c for c in e1["cells"] if (c["key"]["world"], c["key"]["curriculum"],
            c["key"]["budget"], c["key"]["scenario"]) == ("S1", "8node_x10", 15, "calm"))
a, s = cell["arms"]["adapt"]["per_learner"], cell["arms"]["static"]["per_learner"]
assert a["seed"] == s["seed"]
d = [x - y for x, y in zip(a["goal_mastered"], s["goal_mastered"])]
print("differences +1:", d.count(1.0), " -1:", d.count(-1.0), " 0:", d.count(0.0))
p = M.paired(a["goal_mastered"], s["goal_mastered"])
print("recomputed", p, M.direction(p))
print("stored    ", cell["contrasts"]["adapt_minus_static"]["goal_mastered"])
```

Output (bins abridged):

```
folds 5 by student
heuristic_class_D6 n 297016 ECE recomputed 0.1324 stored 0.1324 Brier 0.2252 log-loss 0.6438 AUC 0.6858
   [0.2, 0.3) n= 57192 mean_p=0.264 freq=0.517
   [0.8, 0.9) n=105917 mean_p=0.846 freq=0.792
fitted_class_profile n 297016 ECE recomputed 0.0086 stored 0.0086 Brier 0.1948 log-loss 0.5753 AUC 0.7072
   [0.6, 0.7) n= 73994 mean_p=0.655 freq=0.662
N 1000 seeds 1000 - 1999 adapt 0.263 static 0.227
differences +1: 36  -1: 0  0: 964
recomputed {'diff': 0.036, 'ci95': [0.025, 0.048], 'n': 1000} better
stored     {'ci95': [0.025, 0.048], 'diff': 0.036, 'n': 1000}
```

</details>

## In the code

| Function or class | File | Config key | Default value |
|---|---|---|---|
| `bootstrap_ci`, `paired`, `direction` | `experiments/core/metrics.py` | `BOOT_N`, `BOOT_SEED` | 2000, 20260 |
| `brier`, `log_loss`, `auc`, `ece`, `reliability_bins`, `score_all`, `score_histogram` | `experiments/core/metrics.py` | `n_bins`, `eps` | 10, 1e-6 |
| `contrast` (checks seeds match, then `paired`) | `experiments/runners/common.py` | — | — |
| `crossvalidate`, `fold_students`, `heldout_metrics` | `experiments/core/realdata.py` | `folds`, `SEED` | 5, 42 |
| `fast_em`, `fit_classes`, `fit_per_skill`, `heuristic_class` | `experiments/core/realdata.py` | `MIN_ITEM_ANSWERS` | 20 |
| `guard`, `read`, `find`, `NotRegistered` | `experiments/core/prereg.py` | — | — |
| `code_hash` | `experiments/core/provenance.py` | — | SHA-256 over `src/**/*.py` |
| hypothesis rules (`"held"`) | `experiments/runners/e1_safety_outcomes.py` … `e6_sensitivity.py` | — | — |

## Tests

- `experiments/tests/unit/test_metrics.py` — scores by hand; paired bootstrap deterministic.
- `experiments/tests/unit/test_realdata.py` — EM recovers known parameters; folds never share a
  student; cross-validated metrics in range.
- `experiments/tests/tooling/test_prereg_guard.py` — draft refused, other hash refused, registered
  with current hash runs, smoke allowed, amendment hash counts.
- `experiments/tests/integration/test_runners_smoke.py` — smoke results valid; a full run refuses
  without registration.
- `experiments/tests/tooling/test_results_schema.py`, `experiments/tests/tooling/test_report.py` —
  results format and the report pipeline.

## Decisions

- [D47](../project/DECISIONS.md#d47) — every world, metric and rule is pre-registered with a
  timestamp and code hash before running.
- [D48](../project/DECISIONS.md#d48) — fitted profiles replace the heuristic only if they beat it
  on held-out data.
- [D98](../project/DECISIONS.md#d98) — one final study on one code hash, with its own
  pre-registrations.
- [D99](../project/DECISIONS.md#d99) — improvement is claimed only where a pre-registered paired
  contrast shows it.
- [D100](../project/DECISIONS.md#d100) — results JSON → data files → tables and figures.

## Limitations

- The bootstrap resamples learners only; cells, curricula and scenarios are fixed, so an interval
  says nothing about other curricula. No correction is made for the many cells compared (E1 has 560
  cells), so a few "better" or "worse" cells are expected by chance.
- The percentile interval is slightly narrow for small $N$ and for rare binary outcomes (for
  example 36 discordant pairs out of 1000).
- Real-data calibration uses school-maths data (ASSISTments, Cognitive Tutor), not Python learners;
  see [T5](../../experiments/report/tables/T5.md). On simulated learners the engine's $P(\text{correct})$
  is far less calibrated (E1 S1 `8node_x10` B15 calm, adapt: ECE 0.150, AUC 0.551 on 19 603 executed
  exercises; pooled per world in [T6b](../../experiments/report/tables/T6b.md)).
- Four hypotheses failed (E1 H3, E4 H2, E4 H3, E5 H3); see
  [experiments/NOTES.md](../../experiments/NOTES.md#outcomes) and
  [H](../../experiments/report/tables/H.md).
- The pre-registration files still name `experiments_v2/` paths (the folder was renamed after the
  runs, D102).

## Values checked

Run with `PYTHONPATH=. .venv/bin/python` from the repository root; all were run and match.

- `experiments.core.metrics.BOOT_N` → 2000; `BOOT_SEED` → 20260
- `inspect.signature(metrics.ece).parameters["n_bins"].default` → 10
- `inspect.signature(metrics.log_loss).parameters["eps"].default` → 1e-06
- `experiments.core.realdata.SEED` → 42; `inspect.signature(realdata.crossvalidate).parameters["folds"].default` → 5
- `experiments.core.realdata.MIN_ITEM_ANSWERS` → 20; `CLASSES` → ['easy', 'medium', 'hard', 'unrated']
- `experiments.core.realdata.MODELS` → ('heuristic_class_D6', 'fitted_class_profile', 'fitted_per_skill')
- `experiments.runners.common.HEADLINE_SEEDS` → 1000–1999
- E3 stored: `realdata.assist09.heldout.folds` → 5, `fold_unit` → "student"; ECE 0.1324 / 0.0086 (recomputed from bins)
- E1 stored: `adapt_minus_static.goal_mastered` for S1 | `8node_x10` | 15 | calm → diff 0.036, ci95 [0.025, 0.048], n 1000 (recomputed with `metrics.paired`)
- E1 stored: `cells[...].arms.adapt.metrics.attempts` for the same cell → ECE 0.1498, AUC 0.5507
- `experiments/preregistration/E1_2026-11-21.md` → Status Registered, Registered UTC 2026-11-20T23:37:19+00:00, Code hash 9a40c4d8…66e6ef
  (the engine's code hash has been `03297fad…` since 21 Nov 2026, after a docstring-only change in `src/`; a new full run would need to be registered again under that hash)
