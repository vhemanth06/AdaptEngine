# Concepts

One file per idea in AdaptEngine. Each file gives the idea in plain words, the maths, a worked
example whose numbers come from running the code, where it lives in the code, the tests that check
it, the decisions that set it, and what it does not capture.

## Reading order

| # | File | Idea |
|---|---|---|
| 01 | [01_curriculum_graph.md](01_curriculum_graph.md) | Concepts, the prerequisite graph, knowledge states and the safety rule |
| 02 | [02_mastery_bkt.md](02_mastery_bkt.md) | The mastery belief $p$: Bayesian Knowledge Tracing updates and the mastery rule |
| 03 | [03_item_models.md](03_item_models.md) | From item difficulty to guess and slip: the heuristic and fitted profiles |
| 04 | [04_diagnostic_sweep.md](04_diagnostic_sweep.md) | The default diagnostic: information-gain sweep over concepts |
| 05 | [05_diagnostic_bisection.md](05_diagnostic_bisection.md) | The bisection diagnostic over knowledge states, and confirmation checks |
| 06 | [06_planning.md](06_planning.md) | Building the plan: workload, priorities, greedy packing, feasibility |
| 07 | [07_cpsat.md](07_cpsat.md) | The CP-SAT planner and the hybrid planner |
| 08 | [08_review_remediation.md](08_review_remediation.md) | Forgetting, spaced review and remediation |
| 09 | [09_replanning.md](09_replanning.md) | Events and replanning |
| 10 | [10_evaluation.md](10_evaluation.md) | How the engine is evaluated: simulated learners, arms, scenarios, the safety audit |
| 11 | [11_study_statistics.md](11_study_statistics.md) | The statistics of the final study |

Files 01–09 describe the engine (`src/adaptengine/`); 10–11 describe the evaluation harness
(`experiments/`).

## Notation

All files use these symbols. A file may add local symbols in its own notation table.

| Symbol | Meaning | Config key / code name |
|---|---|---|
| $c$, $q$ | a concept; $q$ is usually a prerequisite of $c$ | `concept_id` |
| $\mathrm{pre}(c)$ | the direct prerequisites of $c$ | `graph.prerequisites(c)` |
| $p$, $p_c$ | the engine's belief that the learner has mastered concept $c$ | `LearnerConcept.p` |
| $p_0$ | the prior belief for an untouched concept | `p0` |
| $\theta$ | mastery threshold on $p$ | `theta` |
| $k$ | minimum number of responses before a concept can count as mastered | `k_responses` |
| $d$ | item (exercise) difficulty, in $[d_{\min}, d_{\max}]$ | `Activity.difficulty`, `d_min`, `d_max` |
| $g(d)$, $s(d)$ | guess and slip probabilities of an item of difficulty $d$ | `guess_coef`, `slip_base`, `slip_coef` |
| $t$ | learning transition probability after an activity ($t_{\text{lesson}}$, $t_{\text{exercise}}$) | `t_lesson`, `t_exercise` |
| $P_c$ | predicted probability that the learner answers an item on $c$ correctly | `model.predict_correct` |
| $H(p)$ | binary entropy of $p$, in bits | — |
| $K$ | a knowledge state: a set of concepts closed under prerequisites (a down-set) | — |
| $\pi(K)$ | probability of knowledge state $K$ (prior or posterior) | — |
| $\varepsilon$ | assumed error rate of a confirmation check | `confirm_epsilon` |
| $h$ | memory half-life in days | `half_life_days` |
| $\Delta t$ | days since a concept was last practised | — |
| $r$ | predicted recall of a concept since its last practice | `recall_at` |
| $B$ | daily study budget in minutes | `PlanContext.budget` |
| $D$ | deadline day | `PlanContext.deadline_day` |
| $\theta^{\text{true}}_c$ | the simulated learner's true mastery of $c$ (evaluation only) | `SimLearner.theta` |
| $a$, $b$ | 2PL discrimination and item location (evaluation only) | `Profile.a`, item difficulty |
| $\sigma(x)$ | logistic function $1/(1+e^{-x})$ | — |
| $N$ | number of simulated learners in a cell | — |

Note the two thetas: $\theta$ alone is the engine's mastery threshold on its belief $p$;
$\theta^{\text{true}}_c$ is the simulator's hidden ground truth, which the engine never sees.

## Maths on GitHub

Equations use GitHub Markdown maths: `$…$` inline and `$$…$$` for display. Only standard LaTeX
commands are used (`\frac`, `\sum`, `\log`, `\mathbb{E}`, `\sigma`, `\theta`, `\ge`, `\le`, `\cdot`,
`\text`, `\mathrm`), so the files also render in most local Markdown previews with maths support.

## Checking the numbers

Every default value named in a concept file is listed under "Values checked" at the end of that
file, with the Python expression that reads it from the code (for example
`DEFAULT_CONFIG.theta`). Every worked example states the command that produced its numbers in a
collapsed block, so it can be re-run.
