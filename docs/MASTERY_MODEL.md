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
