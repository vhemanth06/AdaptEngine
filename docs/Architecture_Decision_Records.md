# Architecture Decision Records

This log has one short record per significant choice in AdaptEngine: architecture, framework reuse, data model, security, deployment model and methodology.Detailed rules and parameter values live in [`project/DECISIONS.md`](project/DECISIONS.md). Each ADR lists the D-records it covers.

- **Status** is *Accepted* or *Superseded*. Superseded records are kept, never deleted.
- **Decision dates** are taken from the evidence cited in each ADR: commits, weekly reports and decision records.
- **Commit IDs** are short SHAs from the `main` history.
- **Study results** refer to tables in [`experiments/report/tables/`](../experiments/report/tables/).

## Index

| ADR | Title | Status | Milestones | Decided |
|---|---|---|---|---|
| [001](#adr-001) | Layered, deterministic engine library with CLI and Python API | Accepted | M1–M7 | 2026-10-04 |
| [002](#adr-002) | Curriculum as a prerequisite DAG; learner state with uncertainty and evidence | Accepted | M1 | 2026-10-04 |
| [003](#adr-003) | Mastery model: BKT with difficulty-based (heuristic) guess and slip | Accepted | M1, M4 | 2026-10-04 |
| [004](#adr-004) | Diagnostic: bounded adaptive sweep by expected information gain | Accepted | M2 | 2026-10-04 |
| [005](#adr-005) | Planner: deterministic greedy scheduler with an exact feasibility oracle | Accepted | M3 | 2026-10-04 |
| [006](#adr-006) | Online update and difficulty policy: evidence rule and target success probability | Accepted | M4 | 2026-10-04 |
| [007](#adr-007) | Spaced review and remediation with half-life decay inside the daily budget | Accepted | M5 | 2026-10-04 |
| [008](#adr-008) | Event-driven replanning from current state | Accepted | M6 | 2026-10-04 |
| [009](#adr-009) | Structured decision traces for every planning decision | Accepted | M7 | 2026-10-04 |
| [010](#adr-010) | Content review gate: human reviewer and SHA-256 in a manifest | Accepted | M1 | 2026-10-04 |
| [011](#adr-011) | Evaluation by simulated learners against static and greedy baselines | Accepted | M8 | 2026-09-26 |
| [012](#adr-012) | Bisection diagnostic over knowledge states, with confirmation checks (opt-in) | Accepted | M2, M3 | 2026-11-14 |
| [013](#adr-013) | Fitted item-model profiles from real data (opt-in) | Accepted | M1, M4, M8 | 2026-11-14 |
| [014](#adr-014) | CP-SAT and hybrid planners (opt-in) | Accepted | M3, M6 | 2026-11-14 |
| [015](#adr-015) | Demo deployment: local FastAPI + React web app | Accepted | M7 (presentation) | 2026-11-09 |

## Mandatory methodology record

**Status at 9 October 2026, 11:59 PM IST: Reaffirmed.**

**The approach in place by 9 October 2026:**
- **Sources:**
  - Week 1 report (26 Sep 2026, `docs/archive/submissions/Week1_report.pdf`): M1–M8, the simulator decision, static and greedy baselines;
  - Week 2 report (4 Oct 2026, `Week2_report.pdf`): the revised design, the test register TC1.1–TC8.x, and the implementation in commit `290dcdd` (4 Oct 2026).
- **Later write-up:** the Assignment 2 report (10 Oct 2026, `Project3_Group15_Assignment2.pdf`) writes out the same approach in full, with the formulas.
- **Week 1 to Week 2:** the Week 2 revision replaced the Week 1 sketch (constrained A\* search, a CAT-style diagnostic, Half-Life Regression, several mastery models) with the design below. That change happened before 9 October, and it is the design reaffirmed here.

Milestones as defined for the project:

- **M1 – Curriculum and learner-state model:** concepts, lessons, exercises, durations, prerequisites and mastery estimates are represented in a queryable model with uncertainty.
- **M2 – Short adaptive diagnostic:** a new learner receives a bounded diagnostic and a calibrated initial skill estimate; adaptive selection is compared against fixed/random question selection.
- **M3 – Time-budgeted path generation:** given a goal, deadline and daily budget such as 5/10/15/30 minutes, the engine generates a prerequisite-valid day-by-day plan.
- **M4 – Online mastery update and difficulty adaptation:** quiz/exercise evidence updates per-skill mastery, and the next content difficulty changes according to an explicit policy.
- **M5 – Spaced review and remediation:** previously learned concepts are scheduled for review according to forgetting risk, prerequisite importance and the remaining daily time budget.
- **M6 – Dynamic replanning:** missed days, failed assessments, changed deadlines or changed daily budgets trigger a valid revised plan without losing completed progress.
- **M7 – Explainability and constraints:** each inclusion, omission, review or difficulty change can be traced to observable learner state, graph constraints or a policy score.
- **M8 – Comparative evaluation:** diagnostic accuracy, path feasibility, runtime, mastery prediction/calibration and simulated learning outcomes are compared with static/greedy baselines.

**Done when:** multiple synthetic learner profiles with different skills and constraints receive different valid plans, the plans adapt after new evidence or missed work, and the system demonstrates measurable improvement over non-adaptive baselines while explaining its decisions.

**Methods:**
- heuristic BKT ([ADR-003](#adr-003));
- the entropy-based adaptive sweep diagnostic ([ADR-004](#adr-004));
- the deterministic greedy scheduler with an exact feasibility oracle ([ADR-005](#adr-005));
- the target-probability difficulty policy ([ADR-006](#adr-006));
- half-life review ([ADR-007](#adr-007));
- event-driven replanning ([ADR-008](#adr-008));
- decision traces ([ADR-009](#adr-009));
- the review gate ([ADR-010](#adr-010));
- evaluation by simulated learners against baselines ([ADR-011](#adr-011)).

**After 9 October** the approach was not replaced. `DEFAULT_CONFIG` still selects:
- `diagnostic_method="sweep"`
- `model_profile="heuristic"`
- `planner_method="greedy"`

Later work added optional methods behind configuration switches:
- bisection diagnostic ([ADR-012](#adr-012));
- fitted item-model profiles ([ADR-013](#adr-013));
- CP-SAT and hybrid planners ([ADR-014](#adr-014));
- a demo web app ([ADR-015](#adr-015)).

None of these changes a default or a milestone.

**Refinements of the M8 evaluation** (same method, better implementation):
- **2 Nov:** the Week 6 evaluation suite (`49b0fd7`).
- **9 Nov:** Week 7 corrections (`cae9291`): executed-state prerequisite audit ([D46](project/DECISIONS.md#d46)), closed-loop harness, simulator worlds and pre-registration ([D47](project/DECISIONS.md#d47)).
- **21 Nov:** one final pre-registered study on the final engine (`5134a24`–`39cfe1f`, [D98](project/DECISIONS.md#d98)).

The comparison itself is unchanged: adaptive vs static and greedy baselines on simulated learners with a model mismatch, as planned in the Week 1 report and Assignment 2.

**Diagnostic baselines (M2):** the final study compares the adaptive diagnostic with fixed selection and IRT-CAT at the same number of questions. The random-selection baseline named in M2 is not part of the final study.

**Parameter tuning** within the same methods: diagnostic caps 8/3 → 6/2 ([D1](project/DECISIONS.md#d1), [D2](project/DECISIONS.md#d2)) and the sweep prior record ([D59](project/DECISIONS.md#d59)).

**Impact on milestones and tests:** none removed or redefined. New test cases were added for the optional methods (TRACEABILITY F1, F2, F3 and V2 rows).

---

<a id="adr-001"></a>
## ADR-001 — Layered, deterministic engine library with CLI and Python API

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-001 — Layered, deterministic engine library with CLI and Python API |
| **Date, status & scope** | Decided 2026-10-04; **Accepted**; M1–M7; all of `src/adaptengine/`. |
| **Context & decision drivers** | The engine must decide what a learner may and should do next, and it must be safe: prerequisites and daily budgets are never broken. It must also be traceable, testable and reproducible, so that M8 can compare it with baselines on identical inputs. The Week 1 prototype (`627cfbf`, 26 Sep) mixed planning, search, diagnosis and simulation in one package. That made correctness hard to show. |
| **Options considered** | **(a) Keep the Week 1 structure:** search-based planner, simulator and baselines in one package. Fast to extend; weak separation; hard to test layer by layer. **(b) Web service first:** a deployable product early, but HTTP, persistence and UI concerns enter the core and slow testing. **(c) Layered library:** `core ← curriculum ← learner ← diagnostic / planner / review ← replanner ← session / api / cli`, deterministic, few dependencies (`networkx`; OR-Tools and pyBKT optional). More up-front structure; every layer testable alone. |
| **Decision & rationale** | **(c)**. *Judgment:* layering keeps hard constraints in one place and lets mastery, review and planning parts be replaced behind interfaces (quality attributes Q1–Q7, Assignment 2 §3.1). *Measured:* the layering is checked automatically, and the same inputs give the same plans (pins in `tests/regression/test_baseline_pins.py`; determinism test in the study). |
| **Consequences & trade-offs** | Benefits: one engine serves the CLI, the Python API, the simulator and later the web demo without duplicated logic. Costs: more modules and interfaces. Rejected: learned or agentic components inside the core (kept as optional layers above it). Rollback: none needed; later features (ADR-012–015) fit as options. |
| **Evidence & validation** | Commit `290dcdd` (Week 2 implementation). Architecture doc [`reference/ARCHITECTURE.md`](reference/ARCHITECTURE.md). Test `tests/tooling/test_architecture.py` (layer order, banned libraries). Determinism: [D36](project/DECISIONS.md#d36); study determinism test `experiments/tests/integration/test_determinism.py`. |
| **Revisit trigger** | A required feature needs an import against the layer order, so the architecture test would have to be relaxed, or the engine must serve several users concurrently (see ADR-015). |

<a id="adr-002"></a>
## ADR-002 — Curriculum as a prerequisite DAG; learner state with uncertainty and evidence

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-002 — Curriculum as a prerequisite DAG; learner state with uncertainty and evidence |
| **Date, status & scope** | Decided 2026-10-04; **Accepted**; M1; `core/schema.py`, `curriculum/graph.py`, `curriculum/loader.py`, `learner/state.py`, `learner/evidence.py`. |
| **Context & decision drivers** | M1 needs concepts, lessons, exercises, durations, prerequisites and mastery estimates in a queryable model with uncertainty. Prerequisites must be strict, durations indivisible, and lesson completion must not count as assessed mastery. |
| **Options considered** | **(a) Flat skill list** with tags: simple, but cannot express or enforce prerequisites. **(b) Knowledge-space model** (sets of known concepts) as the main state: elegant, but the state space grows exponentially and planning needs per-concept quantities anyway. **(c) DAG of concepts with lessons and exercises** (integer minutes; exercise difficulty in [0.05, 0.95]), plus per-concept state: mastery probability $p$, entropy $H(p)$, responses with unique attempt IDs, last practice day. |
| **Decision & rationale** | **(c)**. *Judgment:* a DAG matches how course content depends on itself; per-concept state is what the planner and review use. *Measured:* cycles, unknown references and invalid fields are rejected at load (TC1.1, TC1.2); uncertainty is separate from mastery ($H(0.5)=1.0$, $H(0.9)\approx0.469$). |
| **Consequences & trade-offs** | Benefits: prerequisite checks are simple graph queries; state is small and serialisable. Costs: relations other than "must come before" (alternatives, soft hints) cannot be expressed. Lessons-vs-evidence split adds bookkeeping ([D31](project/DECISIONS.md#d31)). The knowledge-space view was later added only where it helps (ADR-012). |
| **Evidence & validation** | Commit `290dcdd`. Tests `tests/unit/core/test_schema.py`, `tests/unit/curriculum/test_graph.py`, `tests/integration/test_state_session.py`, `tests/regression/test_feedback_fixes.py` (lessons are not evidence). [D31](project/DECISIONS.md#d31), [D34](project/DECISIONS.md#d34). Concept docs [`concepts/01_curriculum_graph.md`](concepts/01_curriculum_graph.md), [`concepts/02_mastery_bkt.md`](concepts/02_mastery_bkt.md). |
| **Revisit trigger** | A curriculum needs alternative paths or soft dependencies that a DAG cannot express, or more than a few hundred concepts make per-concept state slow (planning latency above 1 s). |

<a id="adr-003"></a>
## ADR-003 — Mastery model: BKT with difficulty-based (heuristic) guess and slip

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-003 — Mastery model: BKT with difficulty-based (heuristic) guess and slip |
| **Date, status & scope** | Decided 2026-10-04; **Accepted**; M1, M4; `learner/mastery.py`, `learner/adapter.py`, `core/constants.py`. |
| **Context & decision drivers** | A learner gives only a few binary responses. The model must update after each one, explain itself, and drive diagnosis, planning and review from one state. There was no project data to fit parameters at the start. The Week 1 plan considered several mastery models at once. |
| **Options considered** | **(a) Keep several models** (Week 1): more comparisons, but no single state for decisions. **(b) IRT ability:** a well-known testing model, but it measures ability on a different scale from per-concept mastery and has no learning transition. **(c) Deep knowledge tracing:** strong with large data; opaque and data-hungry. **(d) BKT with fitted parameters:** needs data not available at the start. **(e) BKT with heuristic parameters:** $g(d)=0.30(1-d)$, $s(d)=0.05+0.25d$, learning transitions $T_{\text{diag}}=0$, $T_{\text{exercise}}=0.05$, $T_{\text{lesson}}=0.20$, prior $p_0=0.20$. |
| **Decision & rationale** | **(e)**, with a thin adapter so a fitted or library model can be swapped in. *Judgment:* small, explainable, suits sparse evidence (Assignment 2 §2.3). *Measured:* reference update for $p=0.5$, $d=0.5$, wrong answer gives $p'\approx0.1707$ (TC4.1). pyBKT parity check (FB001; CI job). |
| **Consequences & trade-offs** | Benefits: one consistent state; transparent updates. Costs: the heuristic numbers are not calibrated to real students. Study E3: held-out calibration error (ECE) 0.132 on ASSISTments and 0.145 on Cognitive Tutor (T5). Accepted as the default because it needs no data; addressed by ADR-013. |
| **Evidence & validation** | Commits `290dcdd` (model and constants), `0ef57ba` (difficulty-to-guess/slip adapter, 11 Oct), `0f67c71` (pyBKT integration, 21 Oct). Tests `tests/unit/learner/test_mastery.py`, `tests/unit/learner/test_adapter.py`, `tests/regression/test_feedback_fixes.py` (pyBKT parity). [D4](project/DECISIONS.md#d4)–[D7](project/DECISIONS.md#d7), [D33](project/DECISIONS.md#d33). Study table T5, T6b. |
| **Revisit trigger** | Held-out ECE on the target learners' own data above 0.05. Already true for ASSISTments and Cognitive Tutor, so ADR-013 adds fitted profiles as an option. |

<a id="adr-004"></a>
## ADR-004 — Diagnostic: bounded adaptive sweep by expected information gain

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-004 — Diagnostic: bounded adaptive sweep by expected information gain |
| **Date, status & scope** | Decided 2026-10-04; **Accepted**; M2; `diagnostic/engine.py`, `diagnostic/scoring.py`, `diagnostic/state_space.py`. |
| **Context & decision drivers** | A new learner needs a calibrated starting estimate from very few questions. The estimate must carry uncertainty, the run must be bounded, and adaptive selection must be compared with fixed and random selection (M2). |
| **Options considered** | **(a) Fixed test** (same questions for everyone): simplest; wastes questions. Kept as a baseline. **(b) Random questions:** baseline only. **(c) IRT-based CAT** (Week 1 sketch): established, but on an ability scale that does not match per-concept BKT mastery. **(d) Concept-by-concept sweep in topological order:** pick the item with the largest expected entropy reduction $\mathrm{EIG}=H(p)-[P_c H(p'_{\text{correct}})+(1-P_c)H(p'_{\text{wrong}})]$; stop at the item caps or when $H(p)\le0.50$; skip descendants of concepts below 0.40. |
| **Decision & rationale** | **(d)**. Current caps: 6 items in total, 2 per concept ([D1](project/DECISIONS.md#d1), [D2](project/DECISIONS.md#d2)). *Judgment:* uses the same model as the rest of the engine; deterministic tie-breaks ([D10](project/DECISIONS.md#d10)). *Measured* (study E2, T3): about 3 questions per learner. Brier 0.206 / 0.161 / 0.133 in worlds S0 / S2 / S4, no worse than fixed selection with about 16 questions in S0 and S2. |
| **Consequences & trade-offs** | Benefits: short, explainable diagnostic. Costs: few questions leave advanced learners at the low prior. Scripted advanced learners: Brier 0.42–0.51 (T4). Beats the prior alone only in S4 (T3). This weakness motivated ADR-012. |
| **Evidence & validation** | Commit `0ef57ba`. Tests `tests/unit/diagnostic/test_diagnostic.py`. [D1](project/DECISIONS.md#d1)–[D3](project/DECISIONS.md#d3), [D8](project/DECISIONS.md#d8), [D10](project/DECISIONS.md#d10), [D44](project/DECISIONS.md#d44), [D59](project/DECISIONS.md#d59). Study T3, T4. Concept doc [`concepts/04_diagnostic_sweep.md`](concepts/04_diagnostic_sweep.md). |
| **Revisit trigger** | Diagnostic Brier worse than the prior alone in most simulated worlds or on real data, or advanced learners mis-estimated (scripted Brier above 0.4). Both are observed; see ADR-012. |

<a id="adr-005"></a>
## ADR-005 — Planner: deterministic greedy scheduler with an exact feasibility oracle

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-005 — Planner: deterministic greedy scheduler with an exact feasibility oracle |
| **Date, status & scope** | Decided 2026-10-04; **Accepted**; M3; `planner/workload.py`, `schedule.py`, `plan.py`, `oracle.py`, `feasibility.py`. |
| **Context & decision drivers** | Given goal, deadline and daily budget (5/10/15/30 min), produce a day-by-day plan that never breaks prerequisites or the budget. Report clearly when the goal cannot fit, with the shortfall. The planner must be fast enough to replan after every event. |
| **Options considered** | **(a) Constrained A\* search** (Week 1 prototype `627cfbf`): optimal in principle; custom search was a delivery risk and harder to verify. **(b) ILP/CP solver from the start:** exact; heavier dependency, slower, harder to trace. **(c) Greedy only:** fast; cannot prove infeasibility. **(d) Greedy + oracle:** hard filter (prerequisites evidence-mastered, duration fits), ranking by review urgency, unlock count and difficulty fit, day packing; cheap bounds plus a small exact oracle returning FEASIBLE / INFEASIBLE / UNKNOWN. |
| **Decision & rationale** | **(d)**. *Judgment:* validity is enforced by the filter, never by a score (Week 2 §2.2). *Measured* (study E5, T12, T13): 0 invalid plans; the same first-plan verdicts as hybrid and CP-SAT on all 86,800 first plans; cold start 0.24 ms (4 concepts) to 5.1 ms (50 concepts). |
| **Consequences & trade-offs** | Benefits: fast, deterministic, traceable. Costs: not optimal in every case. The oracle returns UNKNOWN when its node limit is reached, never a false INFEASIBLE ([D17](project/DECISIONS.md#d17)). In E5, greedy said UNKNOWN on two synth-20 probes that CP-SAT proved feasible (T2). Addressed optionally by ADR-014. |
| **Evidence & validation** | Commit `fbe3ab1`. Tests `tests/unit/planner/test_planner.py`, `tests/unit/planner/test_planner_projection.py`. [D11](project/DECISIONS.md#d11)–[D18](project/DECISIONS.md#d18), [D29](project/DECISIONS.md#d29), [D41](project/DECISIONS.md#d41)–[D43](project/DECISIONS.md#d43). Study T2, T12, T13. Concept doc [`concepts/06_planning.md`](concepts/06_planning.md). |
| **Revisit trigger** | UNKNOWN or worse-than-exact outcomes in a measurable share of real requests (more than 1 %), or planning latency above 1 s. |

<a id="adr-006"></a>
## ADR-006 — Online update and difficulty policy: evidence rule and target success probability

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-006 — Online update and difficulty policy: evidence rule and target success probability |
| **Date, status & scope** | Decided 2026-10-04; **Accepted**; M4; `learner/evidence.py`, `planner/difficulty.py`. |
| **Context & decision drivers** | Every exercise response must update mastery. The next exercise's difficulty must change by an explicit rule. Gating must rely on assessed evidence, not on lessons, and retries must not inflate mastery. |
| **Options considered** | **(a) Fixed difficulty ladder:** simple; ignores the learner. **(b) Difficulty equal to mastery** (Week 2 wording): difficulty and mastery are on different scales under this model. **(c) Mastery threshold only:** no difficulty adaptation. **(d) Target predicted success:** choose the exercise whose $P_c(p,d)$ is closest to 0.75. A concept is evidence-mastered when $p\ge\theta=0.85$ with at least $k=2$ responses; lessons raise $p$ but never count as evidence. |
| **Decision & rationale** | **(d)**. *Judgment:* challenging but achievable items, using the model itself. *Measured* (study E6, F8, F9): stricter rules (θ = 0.95, k = 4, three in a row) lower goal mastery by up to 0.13; looser rules change it by at most 0.015. The defaults sit where outcomes are stable. |
| **Consequences & trade-offs** | Benefits: explicit, testable policy. Costs: 0.75 and the mastery rule are hand-set. The evidence rule makes the engine slower to reach the goal under tight budgets, because it proves prerequisites first. This is the main reason a fixed order sometimes wins on goal mastery (study mechanism check, §5.5 of the report). |
| **Evidence & validation** | Commits `fbe3ab1` (difficulty policy, 20 Oct), `0f67c71` (evidence module, 21 Oct). Tests `tests/unit/planner/test_planner.py` (difficulty), `tests/regression/test_feedback_fixes.py` (lessons vs evidence). [D4](project/DECISIONS.md#d4), [D14](project/DECISIONS.md#d14), [D16](project/DECISIONS.md#d16), [D31](project/DECISIONS.md#d31). Study F8, F9. |
| **Revisit trigger** | Real learners' pass rate on targeted exercises outside 0.65–0.85, or a scan on real data showing another θ/k raises goal mastery by more than 0.05 without prerequisite violations. |

<a id="adr-007"></a>
## ADR-007 — Spaced review and remediation with half-life decay inside the daily budget

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-007 — Spaced review and remediation with half-life decay inside the daily budget |
| **Date, status & scope** | Decided 2026-10-04; **Accepted**; M5; `review/forgetting.py`, `planner/workload.py`. |
| **Context & decision drivers** | New lessons, remediation and review compete for the same few minutes a day. Review must follow forgetting risk and prerequisite importance. Failed prerequisites must be repaired before moving on. |
| **Options considered** | **(a) Fixed review intervals:** simple; ignores forgetting. **(b) Half-Life Regression** (Week 1 plan): learned per feature; needs large training data that was not available. **(c) SM-2 / Leitner:** card-based; does not fit concept-level planning under a minute budget. **(d) Exponential decay** $r=2^{-\Delta t/h}$ ($h=30$ days), review when $r<0.80$, urgency weighted by unlock count. Remediation when $p<0.40$ after a failed exercise. Priority: remediation, then reviews, then new lessons. |
| **Decision & rationale** | **(d)**. *Judgment:* transparent and data-free; HLR kept as a future option (Assignment 2 §2.2.7). *Measured* (study E1 H4): adding review changes at least one outcome in 49 of 80 21-day forgetting cells. |
| **Consequences & trade-offs** | Benefits: review competes fairly inside the budget. Costs: the effect on retention itself is small. Retention ratio ≈ 0.43 with or without review (F5). $h$ and the threshold are hand-set. |
| **Evidence & validation** | Commit `cacd099`. Tests `tests/unit/review/test_review.py`, `tests/integration/test_plan_replan_scenarios.py` (TC5.x). [D20](project/DECISIONS.md#d20)–[D27](project/DECISIONS.md#d27), [D40](project/DECISIONS.md#d40), [D43](project/DECISIONS.md#d43). Study F5. Concept doc [`concepts/08_review_remediation.md`](concepts/08_review_remediation.md). |
| **Revisit trigger** | Measured retention with review not better than without on real data or a more realistic forgetting simulation (difference below 0.02), or practice-history data large enough to fit HLR. |

<a id="adr-008"></a>
## ADR-008 — Event-driven replanning from current state

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-008 — Event-driven replanning from current state |
| **Date, status & scope** | Decided 2026-10-04; **Accepted**; M6; `replanner/replan.py`, `session.py`, `api.py`. |
| **Context & decision drivers** | Missed days, failed assessments and changed deadlines or budgets must give a valid revised plan without losing or duplicating completed work. Every event goes through one boundary, `Engine.record(state, log, event)`. |
| **Options considered** | **(a) Keep the first plan** and skip missed items: no work, but the plan drifts from the learner's real state. **(b) Patch the old plan locally:** cheaper, but must re-prove validity around each patch. **(c) Full re-plan from current state** and the effective context (remaining days, budget, minutes already used), keeping completed attempts. Every replan is checked like a first plan. |
| **Decision & rationale** | **(c)**. *Judgment:* one planning path means one set of guarantees. *Measured* (study E1): 0 executed prerequisite violations and 0 invalid plans among about 3.9 million plans and replans. The keep-the-first-plan arm violated prerequisites for 94 % of learners (T1, T1b). |
| **Consequences & trade-offs** | Benefits: validity after every event. Costs: replanning re-checks prerequisites that lack evidence, which costs budget. In E1, replanning beat keeping the first plan on goal mastery in only 6 of 40 missed-day cells (H3 failed; T11). Full re-plans cost a few milliseconds with the greedy planner. |
| **Evidence & validation** | Commits `cacd099`, `d7f1281` (working ahead). Tests `tests/integration/test_plan_replan_scenarios.py`, `tests/unit/replanner/test_replan_frontier.py`. [D28](project/DECISIONS.md#d28)–[D30](project/DECISIONS.md#d30), [D35](project/DECISIONS.md#d35), [D96](project/DECISIONS.md#d96). Study T1, T1b, T11. |
| **Revisit trigger** | Replanning latency noticeable to users (above 1 s), or a study showing plan repair matches full re-planning on validity and beats it on goal mastery. |

<a id="adr-009"></a>
## ADR-009 — Structured decision traces for every planning decision

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-009 — Structured decision traces for every planning decision |
| **Date, status & scope** | Decided 2026-10-04; **Accepted**; M7; `planner/plan.py`, `planner/cpsat_trace.py`. |
| **Context & decision drivers** | Each inclusion, omission, review or difficulty change must be traceable to observable learner state, a graph constraint or a policy score, so that a learner can trust the plan and the evaluation can measure explanation coverage. |
| **Options considered** | **(a) Free-text explanations:** readable; not checkable. **(b) Logs only:** cheap; not linked to each decision. **(c) A structured trace record per activity:** reason code, learner state at decision time, applied constraint, score components. Serialised with the plan. |
| **Decision & rationale** | **(c)**. *Judgment:* machine-readable traces can be tested and shown in any interface. *Measured:* one SELECTED record per planned activity on every planner path, including the oracle and CP-SAT ([D38](project/DECISIONS.md#d38), [D71](project/DECISIONS.md#d71)). |
| **Consequences & trade-offs** | Benefits: every decision explainable; the web demo's trace view reuses it. Costs: trace size grows with plan length, and every new planner must emit matching records. |
| **Evidence & validation** | Commit `fbe3ab1`. Tests `tests/integration/test_plan_replan_scenarios.py` (TC7.1), `tests/unit/planner/test_cpsat_planner.py` (trace), `frontend/api/tests/test_sessions.py::test_trace_filters_one_activity`. [D38](project/DECISIONS.md#d38), [D71](project/DECISIONS.md#d71). |
| **Revisit trigger** | Any planned activity without a matching trace record (a test fails), or users unable to explain a plan from its traces in a usability check. |

<a id="adr-010"></a>
## ADR-010 — Content review gate: human reviewer and SHA-256 in a manifest

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-010 — Content review gate: human reviewer and SHA-256 in a manifest |
| **Date, status & scope** | Decided 2026-10-04; **Accepted**; M1 (data integrity / security); `curriculum/loader.py`, `data/review_manifest.json`, `scripts/content/record_review.py`. |
| **Context & decision drivers** | Curriculum content drives every decision. Altered or unreviewed content, including AI-drafted content, must not reach the decision logic. |
| **Options considered** | **(a) Trust curriculum files:** no overhead; no protection. **(b) Schema validation only:** catches malformed files, not unreviewed changes. **(c) Validation plus a review manifest:** each live file has a human reviewer and its SHA-256. The loader rejects a file whose hash differs or whose reviewer is pending or an AI. |
| **Decision & rationale** | **(c)**. *Judgment:* "draft → human review → hash recorded → live" makes review a hard precondition. *Measured:* modified, unreviewed and AI-reviewed files are rejected at every entry point (tests below). |
| **Consequences & trade-offs** | Benefits: content integrity at load time. Costs: every content edit needs a new review entry. Regenerating a reviewed file breaks loading by design (the fixture generator was removed for this reason, [D105](project/DECISIONS.md#d105)). |
| **Evidence & validation** | Commit `290dcdd`. Tests `tests/unit/curriculum/test_loader_review_gate.py`, `tests/regression/test_defects_repro.py`. [D9](project/DECISIONS.md#d9), [D83](project/DECISIONS.md#d83), [D88](project/DECISIONS.md#d88), [D93](project/DECISIONS.md#d93). Review record [`project/content_reviews/8node_x10_ai_review.md`](project/content_reviews/8node_x10_ai_review.md). |
| **Revisit trigger** | Content volume makes per-file human review impractical (more than about 20 files changed per week), or several reviewers must sign off one file. |

<a id="adr-011"></a>
## ADR-011 — Evaluation by simulated learners against static and greedy baselines

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-011 — Evaluation by simulated learners against static and greedy baselines |
| **Date, status & scope** | Decided 2026-09-26; **Accepted**; M8; `experiments/`. |
| **Context & decision drivers** | M8 must compare diagnostic accuracy, feasibility, runtime, calibration and learning outcomes with non-adaptive baselines. Public datasets lack prerequisite graphs, durations, missed days and impossible deadlines. A simulator built on the engine's own model would flatter the engine. |
| **Options considered** | **(a) Real-learner pilot:** most convincing; not feasible within the project's time and scope. **(b) Offline dataset replay only** (ASSISTments, Junyi): real behaviour, but cannot test planning, budgets or replanning. **(c) Transparent simulator** whose learning differs from the engine's model, with several learner profiles. Engine compared with static order, greedy without review, and no replanning on the same profiles, goals, budgets and seeds. Real data used for offline calibration checks. |
| **Decision & rationale** | **(c)**, with real-data checks (ASSISTments, Cognitive Tutor). *Judgment:* the only option that covers all M8 metrics. *Measured* (final study): 0 executed prerequisite violations for the engine vs 87 % of learners for a static order and 94 % for an un-updated plan (T1). Adapt vs static depends on the curriculum: never worse on the 10-exercise curriculum, often worse on small ones under tight budgets (T7, T8). 13 of 17 pre-registered hypotheses held. |
| **Consequences & trade-offs** | Benefits: every metric measurable under controlled disruptions. Costs: closed-loop results come from simulated learners only. Low attempt-level AUC in mismatched worlds reflects the deliberate mismatch (T6b). Later refinements of the same method: executed-state audit, simulator worlds and pre-registration ([D46](project/DECISIONS.md#d46), [D47](project/DECISIONS.md#d47)), one final study ([D98](project/DECISIONS.md#d98)–[D101](project/DECISIONS.md#d101)). |
| **Evidence & validation** | Commits `627cfbf` (learner simulator and static/greedy baselines, 26 Sep), `0f67c71` (evaluation suite, 21 Oct), `49b0fd7` (2 Nov), `cae9291` (Week 7 evaluation, 9 Nov), `5134a24`–`39cfe1f` (final study, 21 Nov). [`experiments/README.md`](../experiments/README.md), [`experiments/NOTES.md`](../experiments/NOTES.md). Tests `experiments/tests/`. [D36](project/DECISIONS.md#d36), [D37](project/DECISIONS.md#d37), [D39](project/DECISIONS.md#d39), [D46](project/DECISIONS.md#d46), [D47](project/DECISIONS.md#d47). Study T1, T6b, T7, T8. |
| **Revisit trigger** | A real-learner pilot becomes possible, or a real-data check (such as world S4-assist09) disagrees with the simulated results by more than the reported effect sizes (about 0.05 in goal mastery). |

<a id="adr-012"></a>
## ADR-012 — Bisection diagnostic over knowledge states, with confirmation checks (opt-in)

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-012 — Bisection diagnostic over knowledge states, with confirmation checks (opt-in) |
| **Date, status & scope** | Decided 2026-11-14; **Accepted**; extends ADR-004, default unchanged; M2, M3; `diagnostic/bisection.py`, `diagnostic/knowledge_space.py`, `planner/confirmation.py`. |
| **Context & decision drivers** | ADR-004's sweep leaves advanced or returning learners at the low prior after 3–5 questions. They are then re-taught what they know (scripted advanced learners: Brier 0.42–0.51, T4). |
| **Options considered** | **(a) Keep the sweep only:** no extra cost; advanced learners poorly served. **(b) IRT-CAT:** established; scale mismatch with BKT. **(c) Bisection over prerequisite-consistent knowledge states:** uniform prior; pick questions that split the posterior; stop at 80 % on one state or a budget of 6–40; exact enumeration up to 5000 states, else 4000 samples. Optionally, planner confirmation checks at $1-\varepsilon=0.98$ when $T_{\text{checks}}<P_{\text{pass}}\cdot T_{\text{full}}$. |
| **Decision & rationale** | **(c)** as an option. *Measured* (study E2, T4): Brier 0.03–0.05 for scripted advanced learners, 0.23–0.48 better than the sweep. *Measured* (E4, T9): goal mastery up to +0.18 with confirmation checks. |
| **Consequences & trade-offs** | Costs: more questions (6–9 vs 2–5). Never better than the prior on simulated populations (0 of 15 cells, T3). No total-time saving on small curricula (E4 H2 failed). Confirmation checks wrongly pass 60–73 % of learners in the 2PL simulator (E4 H3 failed). Kept opt-in for these reasons. |
| **Evidence & validation** | Commit `3d9d36f`. Tests `tests/unit/diagnostic/test_bisection.py`, `tests/unit/diagnostic/test_knowledge_space.py`, `tests/unit/planner/test_confirmation.py`. [D49](project/DECISIONS.md#d49)–[D58](project/DECISIONS.md#d58). Study T3, T4, T9. Concept doc [`concepts/05_diagnostic_bisection.md`](concepts/05_diagnostic_bisection.md). |
| **Revisit trigger** | To make it the default: it beats the sweep on population-like or real learners and confirmation false-pass falls below 10 %. |

<a id="adr-013"></a>
## ADR-013 — Fitted item-model profiles from real data (opt-in)

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-013 — Fitted item-model profiles from real data (opt-in) |
| **Date, status & scope** | Decided 2026-11-14; **Accepted**; extends ADR-003, default unchanged; M1, M4, M8; `learner/profiles.py`, `config/fitted_assist09.json`, `config/fitted_ct.json`. |
| **Context & decision drivers** | ADR-003's heuristic guess/slip values are badly calibrated on real students (ECE 0.13–0.15). The revisit trigger of ADR-003 fired. |
| **Options considered** | **(a) Keep the heuristic only:** no data needed; poor calibration. **(b) Per-skill fits:** best fit; cannot transfer to new curricula without matching skills. **(c) Per-difficulty-class profiles** fitted on real data (ASSISTments 2009, Cognitive Tutor), selected by `model_profile`. |
| **Decision & rationale** | **(c)** as an option. *Measured* (study E3, T5): held-out ECE 0.132 → 0.009 (ASSISTments) and 0.145 → 0.011 (Cognitive Tutor); Brier and AUC also better. Next-answer Brier lower in the real-data world S4-assist09 (all four curricula). |
| **Consequences & trade-offs** | Costs: fitted models make the sweep ask more questions (+0.48 and +1.30 on average). They fit their source datasets, not this project's learners. The profile fitted to the project's own simulator (`fitted_sim.json`) is excluded from use. Heuristic remains default because it needs no data. |
| **Evidence & validation** | Commits `cae9291`, `a0ecf0a`. Tests `tests/unit/learner/test_profiles.py`, `tests/integration/test_cli_config.py`. [D48](project/DECISIONS.md#d48), [D60](project/DECISIONS.md#d60), [D61](project/DECISIONS.md#d61). Study T5, T6. Concept doc [`concepts/03_item_models.md`](concepts/03_item_models.md). |
| **Revisit trigger** | Data from the project's own learners becomes available. Refit, and make the fitted profile the default if its held-out ECE stays below the heuristic's. |

<a id="adr-014"></a>
## ADR-014 — CP-SAT and hybrid planners (opt-in)

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-014 — CP-SAT and hybrid planners (opt-in) |
| **Date, status & scope** | Decided 2026-11-14; **Accepted**; extends ADR-005, default unchanged; M3, M6; `planner/cpsat_model.py`, `cpsat_planner.py`, `cpsat_trace.py`. |
| **Context & decision drivers** | ADR-005's greedy planner can return UNKNOWN where an exact solver could prove feasibility, and it is not optimal. The question was whether an exact planner improves verdicts or learner outcomes, and at what latency. |
| **Options considered** | **(a) Keep greedy only:** fastest; inexact verdicts in rare cases. **(b) Pure CP-SAT** (OR-Tools): exact verdicts; lexicographic objectives (goal finish day, remediation days, weighted concept finish, review reward, peak load); slow on larger curricula. **(c) Hybrid:** greedy first, CP-SAT for exact verdicts and budget changes. |
| **Decision & rationale** | **(b)** and **(c)** as options behind `planner_method`; OR-Tools as an optional dependency ([D69](project/DECISIONS.md#d69)). *Measured* (study E5, T12, T13): the same first-plan verdicts as greedy on all 86,800 first plans. Hybrid resolves greedy's UNKNOWN cases. Hybrid equals greedy on outcomes except 2 of 434 cells (+0.02). |
| **Consequences & trade-offs** | Costs: CP-SAT cold start 10 ms (4 concepts), 3.2 s (20) and 35 s (50); pure CP-SAT used slightly more study minutes in 56 of 94 cells. Greedy stays default; every planner must emit matching traces ([D71](project/DECISIONS.md#d71)). |
| **Evidence & validation** | Commit `256fcf8`. Tests `tests/unit/planner/test_cpsat_planner.py`, `tests/unit/planner/test_cpsat_reviews.py`, `tests/integration/test_closed_loop_planners.py`. [D62](project/DECISIONS.md#d62)–[D72](project/DECISIONS.md#d72). Study T2, T12, T13, T13b. Concept doc [`concepts/07_cpsat.md`](concepts/07_cpsat.md). |
| **Revisit trigger** | Exact verdicts needed interactively on curricula above about 20 concepts (CP-SAT too slow), or greedy shown worse on learner outcomes than CP-SAT by more than 0.02 in goal mastery. |

<a id="adr-015"></a>
## ADR-015 — Demo deployment: local FastAPI + React web app

| Field | Record |
|---|---|
| **ADR-ID & title** | ADR-015 — Demo deployment: local FastAPI + React web app |
| **Date, status & scope** | Decided 2026-11-09; **Accepted**; extends ADR-001; M7 (presentation); `frontend/api/`, `frontend/web/`, `scripts/demo/demo.py`. |
| **Context & decision drivers** | The engine's behaviour (diagnostic, plan, study days, replanning, traces) needs to be shown to a non-technical audience. The CLI is hard to demo. |
| **Options considered** | **(a) CLI only:** no extra code; poor demonstration. **(b) Hosted multi-user service:** realistic; needs authentication, a database and hosting, which are out of scope. **(c) Local single-user web app:** a FastAPI adapter over the engine API, a React UI and file-based sessions, started with `make demo`. |
| **Decision & rationale** | **(c)**. *Judgment:* shows every engine feature without changing the engine. *Measured:* API results equal direct engine calls (parity tests); browser tests cover all six screens. |
| **Consequences & trade-offs** | Benefits: a one-command demo; traces visible per activity. Costs: a second code base (TypeScript) to maintain; no multi-user support; sessions stored as local files. The first UI was reduced to six screens ([D97](project/DECISIONS.md#d97)). |
| **Evidence & validation** | Commits `cae9291`, `bd99f73`, `fb5663a`, `b3e0876`. Tests `frontend/api/tests/` (parity, sessions, health), `frontend/web/e2e/`. [D45](project/DECISIONS.md#d45), [D92](project/DECISIONS.md#d92), [D94](project/DECISIONS.md#d94)–[D97](project/DECISIONS.md#d97). [`frontend/README.md`](../frontend/README.md). |
| **Revisit trigger** | Need for several simultaneous users or remote access, which would require authentication, a database and hosting. |

---
<!-- 
## How to add an ADR

Use the next number, copy the eight-row table, and fill every field. Never delete a superseded record. Set its status to *Superseded by ADR-0NN* and say what replaced it. List the D-records the decision covers in *Evidence & validation*. -->
