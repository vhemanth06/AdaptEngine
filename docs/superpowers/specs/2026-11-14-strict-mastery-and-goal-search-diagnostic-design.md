# Strict mastery and goal-search diagnostic — design

- **Date:** 2026-11-14
- **Owner:** Hemanth (`vhemanth06`)
- **Status:** approved by owner 2026-11-14

## 1. Intent

Two product problems, raised by the owner:

1. **Mastery comes too fast.** Under the current rule (`theta=0.85`, `k_responses=2`) with the
   default numbers, a learner is "mastered" after a lesson and two correct medium answers
   (p = 0.39 → 0.79 → 0.956). The owner's position: in reality nobody masters a concept in 2–3
   questions. Practice elsewhere agrees (Cognitive Tutor p ≥ 0.95; ASSISTments 3 correct in a
   row), and W7 found 39–51% of "mastered" concepts truly unmastered (D49).
2. **The diagnostic does not scale.** `n_max=6`, `concept_cap=2`, swept in topological order:
   it reaches at most 3 concepts, always the roots. With 50 concepts the other 47 keep the
   prior; an advanced learner is assumed to know nothing past the first roots.

**What a diagnostic is for** (owner, confirmed by a literature check — ALEKS, IRT CAT,
CD-CAT, BKT individualised priors, Khan Academy): it **estimates how much of each concept the
learner already knows** and uses prerequisite links to cover concepts it does not ask about.
It does not grant mastery; practice confirms. ALEKS asks 16–30 questions for up to hundreds
of topics and re-checks its "Known" topics later (its Known topics are answered correctly
only 83% of the time).

## 2. Goals, non-goals, anti-goals

**Goals**
- Product mastery rule: `p >= 0.95` and at least 4 responses, always.
- Product learner model: `fitted_S1` by default (owner decision).
- Diagnostic budget grows with the number of concepts searched.
- Diagnostic asks where the answer tells the most (goal-side search) and passes estimates
  both ways along prerequisites, so the plan starts every concept from a realistic p.
- W7/W8 behaviour and every existing result stay reproducible.
- A pre-registered evaluation measures the effect and is reported whatever it shows.

**Non-goals**
- No binary "credit" / test-out; nothing is skipped without meeting the mastery rule.
- No change to the BKT update, the fitted profiles, or the planner (its projection already
  starts from the current p and respects the new θ/k).
- No change to lesson scheduling (a concept still gets its lesson; the lesson's projected
  learning just shortens the exercise run).
- No time-based diagnostic limit; no revival of `state_space`.

**Anti-goals**
- Changing `EngineConfig` defaults (breaks W7/W8 reproduction and ≈ 26 tests).
- Existing saved sessions replaying differently after the change.
- Claiming the new settings won a selection rule; the owner chose them, the run measures them.

## 3. Constraints

- Determinism: same answers → same diagnostic, item for item (`frontend/api/app.py:_replay`).
- The frontend gets the state after a prefix of answers by overriding `n_max`
  (`_replay(..., n_max=k)`); the new budget must still stop after `n_max` items.
- Decision log entries D61–D63 in `docs/DECISIONS.md`; pre-registration file with code hash
  in `docs/preregistration/` before the evaluation run.
- 0 executed prerequisite violations.

## 4. Approaches considered

### 4.1 Mastery rule

| | Approach | Trade-off | Picked |
|---|---|---|---|
| A | θ = 0.95, always (k lowered 4 → 1 by owner: θ is the only real condition) | 4–7 items per concept; tight deadlines finish fewer concepts | **Yes** |
| B | Horizon-aware (D51) with strict k | Tight deadlines keep the 2-item rule the owner rejects | No |
| C | 4 correct in a row | Ignores difficulty | No |

**Known cost, accepted by the owner.** W8 B.3 ran θ = 0.95 (F3/F4,
`experiments/results/w8_calibration_select.json`): goal mastery vs `static_loop` −0.255 on
S0 8-node (F5 0.87 → 0.695), mean secondary diff F5 +0.053 → +0.009; S1 4-node improved (+0.185). k = 4 itself was not measured in W8 (F3/F4 used k 2/3). This overrides
the B.3 winner F5 on a product judgment.

### 4.2 Learner model

`fitted_S1` (owner pick) over `w7_default` and an ASSISTments-based profile. Caveat: fitted on
simulated S1 learners; its high guess rates (medium 0.43) mostly reflect partial knowledge
under the simulator's continuous-ability / 0.70-cutoff definition. With `fitted_S1`, θ = 0.95
alone needs ≈ 5 medium correct answers. k = 1 (owner decision): θ is the only real condition;
the one-answer minimum only stops an inferred estimate with zero answers from counting as mastered.
Under `w7_default` numbers θ = 0.95 is reached after 2 correct answers.

### 4.3 Diagnostic

| | Approach | Trade-off | Picked |
|---|---|---|---|
| D1 | Scaled budget, keep top-down sweep | Budget spent on roots | No |
| D2-credit | Goal search + binary credit + plan-time credit check | Under `fitted_S1` with 4 exercises per concept, 4/4 correct gives p ≈ 0.77, so credit (0.85) never fires; extra machinery | No (superseded) |
| **D2-estimate** | Goal search + scaled budget + estimates passed up/down; practice confirms | Known concepts still need 3–4 practice items | **Yes** |
| D3 | Learner-driven test-out | New UI, self-assessment | No |

## 5. Design

### 5.1 Where settings live

`EngineConfig` defaults are **unchanged**. New fields get defaults that reproduce today's
behaviour. The product settings are one dict, applied on top of any learner-model profile:

```python
PRODUCT_OVERRIDES = {
    "theta": 0.95, "k_responses": 1, "horizon_aware_mastery": False,
    "consolidation": True, "verification_probe": True, "feasibility_warning": True,
    "selection_scope": "goal_search", "concept_cap": 4, "diagnostic_scope": "goal_path",
    "n_max": 25, "diag_budget_min": 12, "diag_budget_per_concept": 1.0,
}
PRODUCT_PROFILE = "fitted_S1"
```

Frontend sessions:
- New sessions store `"rules": "product"` in their meta and build their engine as
  `load_profile(profile, **PRODUCT_OVERRIDES)`; default profile `fitted_S1`
  (Setup page, API `default_profile`, schema defaults).
- Sessions whose meta has no `"rules"` key (created before this change) keep today's engine,
  so their recorded diagnostic answers replay identically.
- The Setup page offers "Rules: product / legacy (W7)"; legacy = today's engine.

### 5.2 Diagnostic budget

```
budget = n_max                                                     if diag_budget_per_concept == 0
budget = min(n_max, max(diag_budget_min, round(diag_budget_per_concept * N)))   otherwise
N = number of concepts in the searched set
```

Product (min 12, 1 per concept, max 25): N ≤ 12 → 12; N = 20 → 20; N ≥ 25 → 25.
Every selection scope uses `budget` in place of `n_max`.

### 5.3 Goal-search selection (`selection_scope="goal_search"`)

Each concept in the searched set is **open** until **settled**:
- **asked** — it stopped by the existing per-concept rule (entropy ≤ `h_stop` after
  `min_items_per_concept`, or `concept_cap` reached, or no unasked items);
- **skipped** — an ancestor ended with p < `skip_threshold` (existing hard pruning, D8);
- **inferred** — a descendant ended with p ≥ `known_threshold` (new, default 0.70).

**Next concept:** the open concept maximising

```
score(c) = min(|open ancestors of c| + 1, |open descendants of c| + 1)
```

ties → earlier in topological order, then `concept_id`. (A high result settles c and its
ancestors; a low one settles c and its descendants; on a chain this is binary search.) Within
the concept the item is chosen as today (max EIG, `candidate_sort_key`).

**After concept c is asked** (final p = p_c):
- **Upward:** every open in-set ancestor a gets `p_a = max(p_a, p_c)`. If p_c ≥
  `known_threshold`, those ancestors are settled as **inferred** (`StopReason.INFERRED`,
  `inferred_from = c`).
- **Downward:** existing `_prune` (hard: p_c < `skip_threshold` skips open descendants).

**Stop** at the first of: every concept settled; `budget` items asked; no unasked items for any
open concept. Concepts still open are recorded `GLOBAL_CAP` / `NO_ITEMS` with their current p.

**Under `fitted_S1`** with the bundled content (4 exercises per concept, d = 0.2/0.4/0.6/0.8;
`t_diag = 0`, so order does not matter): 4/4 correct → p ≈ 0.77 (≥ 0.70, so ancestors are
inferred); two wrong answers → p ≈ 0.08, H ≤ 0.5 → stop, descendants skipped. A known concept
costs 4 items, an unknown one ≈ 2. The 7/8 chain example costs ≈ 12 items.

**Under `w7_default`** 4 correct answers give p > 0.99 with 4 responses, which meets the
product mastery rule; that concept is then evidence-mastered by real evidence.

### 5.4 What the plan does with it

Nothing new. `compute_workload` already projects from each concept's current p and responses
to `p >= theta and responses >= k`. Under `fitted_S1`:

| after diagnostic | practice planned |
|---|---|
| unknown (p ≈ 0.24) | lesson + ≈ 5 exercises |
| asked, 4/4 (p ≈ 0.77, 4 responses) | lesson + ≈ 2–3 exercises |
| inferred (p ≥ 0.77, 0 responses) | lesson + 4 exercises (k floor) |

### 5.4b Content: 10 exercises per concept (owner decision)

The bundled curricula have 4 exercises per concept (d = 0.2/0.4/0.6/0.8, one hard). New
curricula `4node_x10` and `8node_x10` keep the same concepts and prerequisites, keep every
existing activity verbatim, and add 6 exercises per concept at d = 0.1, 0.3, 0.5, 0.7, 0.85,
0.9 (3 easy, 3 medium, 4 hard). The old files are untouched so W7/W8 results stay
reproducible. The drafts go through the existing human review gate (`data/drafts/`, then the
owner runs `scripts/record_review.py --promote-draft`). The web app's default curriculum and the
W9 evaluation use the `_x10` curricula.

### 5.5 Reporting and UI

- `StopReason.INFERRED`; `ConceptDiagnosticResult.inferred_from: Optional[str] = None`.
- `frontend/web/src/pages/Diagnostic.tsx`: `STOP_TEXT.INFERRED = "inferred from a later concept"`
  (the API row gains `inferred_from`, shown when present), and an ALEKS-style label per concept
  from its p: **Known** (p ≥ 0.70), **Unknown** (p < 0.40), **Uncertain** otherwise.

### 5.6 Decisions to log

- **D61** Product mastery θ = 0.95, k = 1 (θ only) always; owner judgment; overrides B.3 winner F5;
  F3/F4 cost cited.
- **D62** Goal-search diagnostic, scaled budget, upward estimate passing and `INFERRED`
  settling; literature basis (§1).
- **D63** `PRODUCT_OVERRIDES` + `fitted_S1` default learner model; `EngineConfig` defaults keep
  W7; old sessions keep their rules. Caveat from §4.2.

## 6. Evaluation (pre-registered, measurement only)

Register `docs/preregistration/W9_STRICT_GOALSEARCH_<date>.md` with the code hash
(`python experiments/provenance.py`) before running. Odd report seeds, 200 per cell (FINAL_A5).

**Full grid** — FINAL_A5 final-grid cells (worlds S0/S1/S4/S4F, curricula `4node_x10`/`8node_x10`
instead of 4-node/8-node, B 10/15, calm/missed_day/missed_2days, horizons w7/7/14/21), each world's fitted profile:
- `adapt_final`, `adapt_final_dx` — W8 reference (existing arms);
- `adapt_strict_dx` — `adapt_final_dx` + θ 0.95, k 1, horizon-aware off; current diagnostic;
- `adapt_strict_gs` — `adapt_strict_dx` + goal search, `concept_cap` 4, budget fields;
- `static_loop` — baseline.

Metrics: goal mastery (true), false-mastery rate, items per mastered concept, diagnostic items,
utilisation, executed prerequisite violations (must be 0). Output
`experiments/results/w9_grid.json`.

**Diagnostic-only** (`experiments/run_diag_matrix.py`): new `goal_search` arm (product
diagnostic settings), curricula `4node_x10`, `8node_x10`, synth-20, synth-50; Brier/AUC vs `prior_only`
and `w6_shipped`; items used. Output `experiments/results/w9_diag_matrix.json`.

## 7. Left to the builder

- Internal structure of the goal-search loop (new method beside `_run_frontier`).
- How `run_final_grid.py` is parameterised for the W9 arms and output path.
