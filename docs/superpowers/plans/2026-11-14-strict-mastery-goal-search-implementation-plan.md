# Strict Mastery and Goal-Search Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 10-exercise versions of both curricula and ship a product configuration with strict mastery (θ = 0.95, k = 4), `fitted_S1` as the default learner model, and a goal-search diagnostic whose budget scales with curriculum size and passes estimates along prerequisites — without changing W7/W8 defaults — then measure it in a pre-registered run.

**Architecture:** New `EngineConfig` fields default to today's behaviour. A `diagnostic_budget()` helper replaces raw `n_max` checks. A new `selection_scope="goal_search"` loop in `AdaptiveDiagnostic` picks the concept that guarantees the most settled concepts, floors ancestors' p at the result, and settles them as `INFERRED` when p ≥ `known_threshold`. A `PRODUCT_OVERRIDES` dict in `core/profiles.py` is applied on top of any learner-model profile by the frontend and the W9 evaluation arms. The planner is unchanged.

**Tech Stack:** Python 3.11 (frozen dataclasses, pytest), FastAPI + pydantic (frontend/api), React + TypeScript + Vite (frontend/web).

**Spec:** `docs/superpowers/specs/2026-11-14-strict-mastery-and-goal-search-diagnostic-design.md`

## Global Constraints

- `EngineConfig` defaults must not change; `DEFAULT_CONFIG` behaviour and every existing test stay as they are.
- Product values, verbatim: `theta=0.95`, `k_responses=4`, `horizon_aware_mastery=False`, `consolidation=True`, `verification_probe=True`, `feasibility_warning=True`, `selection_scope="goal_search"`, `concept_cap=4`, `n_max=25`, `diag_budget_min=12`, `diag_budget_per_concept=1.0`; product profile `fitted_S1`.
- New field defaults: `known_threshold=0.70`, `diag_budget_min=6`, `diag_budget_per_concept=0.0`.
- Budget: `n_max` if `diag_budget_per_concept == 0`, else `min(n_max, max(diag_budget_min, round(diag_budget_per_concept * N)))`, N = concepts in the searched set.
- Determinism: same answers → same items, same order.
- 0 executed prerequisite violations in every evaluation cell.
- Existing `data/curriculum/*` and `data/content/*` files are never edited; the 10-exercise curricula are new ids `4node_x10` / `8node_x10`.
- No agent runs `scripts/record_review.py`, edits `data/review_manifest.json`, or records a reviewer name (D9 human review gate).
- **Do not run any git commands** (no `git add`, `git commit`, `git checkout`, `git stash`, etc.). Leave all changes uncommitted in the working tree; the owner commits.

## Review Focus

1. **Sessions created before this change** (meta has no `"rules"` key) must replay their recorded diagnostic answers identically — Task 5 test `test_legacy_session_replays_unchanged`.
2. **Prefix replay** (`replace(cfg, n_max=k)` in `frontend/api/app.py:_replay`) under goal search must stop after exactly k items — Task 3 test `test_goal_search_prefix_override_stops_at_n_max`.
3. **Branching DAGs** (8-node: `C3` has two parents, `C7` has two) — upward flooring must touch every open ancestor and the loop must terminate with every concept recorded — Task 3 test `test_goal_search_branching_dag_terminates`.
4. **A concept with no exercises** must settle as `NO_ITEMS` without stalling the loop — Task 3 test `test_goal_search_concept_without_exercises`.
5. **Goal subsets** (`diagnostic_scope="goal_path"` passes a subset): ancestors outside the searched set are never modified — Task 3 test `test_goal_search_leaves_out_of_set_concepts_untouched`.

---

### Task 1: Expanded content drafts (10 exercises per concept)

**Files:**
- Create: `data/drafts/4node_x10/curriculum_4node_x10.json`, `activities_4node_x10.json`, `content_4node_x10.json`, `draft_meta.json`
- Create: `data/drafts/8node_x10/curriculum_8node_x10.json`, `activities_8node_x10.json`, `content_8node_x10.json`, `draft_meta.json`
- Test: `tests/test_w9_content.py` (new)

**Interfaces:**
- Produces: curriculum ids `4node_x10`, `8node_x10` (after the owner promotes them, Step 5). Each concept has 1 lesson and **10 exercises** with ids `E-<concept>-<d>` and difficulties `0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9` (3 easy, 3 medium, 4 hard by `planner/workload._difficulty_class`). Concepts and prerequisites are copied unchanged from `curriculum_4node.json` / `curriculum_8node.json`. The existing activity ids, durations and the existing `content_8node.json` entries are kept verbatim; only the 6 new exercises per concept are added.

- [ ] **Step 1: Write the failing tests**

```python
import json, pytest
from adaptengine.curriculum import load_content
from adaptengine.planner.workload import _difficulty_class

DIFFS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9]

@pytest.mark.parametrize("name,base", [("4node_x10", "4node"), ("8node_x10", "8node")])
def test_x10_drafts(name, base):
    d = f"data/drafts/{name}"
    cur = json.load(open(f"{d}/curriculum_{name}.json"))
    assert cur["concepts"] == json.load(open(f"data/curriculum/curriculum_{base}.json"))["concepts"]
    acts = json.load(open(f"{d}/activities_{name}.json"))
    acts = acts["activities"] if isinstance(acts, dict) else acts
    for c in cur["concepts"]:
        ex = sorted(a["difficulty"] for a in acts if a["target_concept"] == c["concept_id"] and a["type"] == "EXERCISE")
        assert ex == DIFFS
        assert [_difficulty_class(x) for x in ex].count("hard") == 4
    old = json.load(open(f"data/curriculum/activities_{base}.json"))
    old = old["activities"] if isinstance(old, dict) else old
    by_id = {a["activity_id"]: a for a in acts}
    assert all(by_id[a["activity_id"]] == a for a in old)          # old activities kept verbatim
    content = json.load(open(f"{d}/content_{name}.json"))["activities"]
    assert set(content) == set(by_id)                                  # content covers every activity
```

(Adapt the key names — `concepts`, `concept_id`, `activities` — to the exact schema of the existing files; the assertions stay.)

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_w9_content.py -v`
Expected: FAIL — files not found.

- [ ] **Step 3: Write the drafts.** Follow the schema of `data/curriculum/*` and `data/content/content_8node.json` (see `data/content/README.md`) and the layout of `data/drafts/py_dicts/`. New exercises are Python multiple-choice questions on the concept, written to their difficulty; new lessons for `4node_x10` follow the `content_8node.json` lesson style. `draft_meta.json` states `"ai_assisted": true` and that a human review is pending. Then run the authoring checks on the new content (`adaptengine.authoring` `check_duplicates`, `check_answer_position`, `check_difficulty_spread`) and fix what they flag.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_w9_content.py -v`
Expected: PASS.

- [ ] **Step 5: OWNER STEP — human review and promotion (no agent runs this).** The owner reviews both drafts and runs `python scripts/record_review.py --promote-draft 4node_x10 --reviewer <name>` and the same for `8node_x10`. This copies the files into `data/curriculum/` and `data/content/` and records them in `data/review_manifest.json`. Agents must not run `record_review.py`, edit `data/review_manifest.json`, or write a reviewer name. Task 6 Step 4 and Task 8 need this step done; Tasks 2–5 and 7 do not (Task 7's smoke run uses the old 4-node files).

---

### Task 2: Budget and new config fields

**Files:**
- Modify: `src/adaptengine/core/config.py` (fields after `selection_scope` ~line 34; validation ~lines 123–135)
- Modify: `src/adaptengine/diagnostic/engine.py` (sweep `run()` ~lines 236–326; `_run_frontier` ~lines 148–174)
- Modify: `src/adaptengine/diagnostic/__init__.py` (export `diagnostic_budget`)
- Test: `tests/test_w9_diagnostic.py` (new)

**Interfaces:**
- Produces: `EngineConfig.known_threshold: float = 0.70`, `EngineConfig.diag_budget_min: int = 6`, `EngineConfig.diag_budget_per_concept: float = 0.0`; `"goal_search"` accepted by `selection_scope` validation; `diagnostic_budget(cfg: EngineConfig, n_concepts: int) -> int` in `adaptengine.diagnostic.engine`, re-exported from `adaptengine.diagnostic`.

- [ ] **Step 1: Write the failing tests**

```python
from dataclasses import replace
import pytest
from adaptengine.core.config import DEFAULT_CONFIG, EngineConfig
from adaptengine.core.errors import ValidationError
from adaptengine.diagnostic import diagnostic_budget
from adaptengine.api import Engine

PRODUCT_DIAG = dict(n_max=25, diag_budget_min=12, diag_budget_per_concept=1.0)

@pytest.mark.parametrize("n,expected", [(4, 12), (8, 12), (12, 12), (20, 20), (25, 25), (50, 25)])
def test_budget_table(n, expected):
    assert diagnostic_budget(replace(DEFAULT_CONFIG, **PRODUCT_DIAG), n) == expected

def test_budget_default_is_n_max():
    assert diagnostic_budget(DEFAULT_CONFIG, 50) == DEFAULT_CONFIG.n_max == 6

def test_budget_n_max_override_truncates():
    assert diagnostic_budget(replace(DEFAULT_CONFIG, **{**PRODUCT_DIAG, "n_max": 3}), 50) == 3

@pytest.mark.parametrize("kw", [dict(known_threshold=0.30), dict(known_threshold=1.0),
                                dict(diag_budget_min=0), dict(diag_budget_per_concept=-0.1),
                                dict(selection_scope="nope")])
def test_new_fields_validated(kw):
    with pytest.raises(ValidationError):
        EngineConfig(**kw)

def test_goal_search_scope_accepted():
    assert EngineConfig(selection_scope="goal_search").selection_scope == "goal_search"

def test_sweep_uses_scaled_budget():
    cfg = replace(DEFAULT_CONFIG, **PRODUCT_DIAG)
    e = Engine.from_files("data/curriculum/curriculum_8node.json",
                          "data/curriculum/activities_8node.json", config=cfg)
    res = e.diagnose(e.init_learner(), lambda a: True)
    assert 6 < res.total_items <= 12
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_w9_diagnostic.py -v`
Expected: FAIL — `ImportError: cannot import name 'diagnostic_budget'`.

- [ ] **Step 3: Implement**
  - `config.py`: add the three fields with the defaults above; add `"goal_search"` to the `selection_scope` allowed tuple; validate `skip_threshold < known_threshold < 1.0`, `check_positive_int(diag_budget_min)`, `diag_budget_per_concept` finite and ≥ 0.
  - `engine.py`: `diagnostic_budget(cfg, n_concepts)` implements the Global Constraints formula. In `run()` compute `budget = diagnostic_budget(self.config, len(ordered_concepts))` once and use it everywhere the sweep reads `self.config.n_max`; pass `budget` into `_run_frontier` and use it in place of `cfg.n_max` there.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_w9_diagnostic.py tests/test_diagnostic.py -v`
Expected: all PASS (existing diagnostic tests unchanged).

---

### Task 3: Goal-search selection with estimate passing

**Files:**
- Modify: `src/adaptengine/diagnostic/engine.py` (`StopReason`, `ConceptDiagnosticResult`, new `_run_goal_search`, dispatch in `run()` next to the `frontier` branch ~line 213)
- Test: `tests/test_w9_diagnostic.py`

**Interfaces:**
- Consumes: `diagnostic_budget`, `EngineConfig.known_threshold` (Task 2).
- Produces: `StopReason.INFERRED = "INFERRED"`; `ConceptDiagnosticResult.inferred_from: Optional[str] = None` (last field, default keeps existing constructors valid); `AdaptiveDiagnostic._run_goal_search(self, ordered, goal_set, concepts, response_provider, model, sid, budget) -> DiagnosticResult`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_w9_diagnostic.py`)

```python
from adaptengine.core.profiles import load_profile
from adaptengine.core.schema import Activity, ActivityType, Concept
from adaptengine.diagnostic import StopReason

GS = dict(selection_scope="goal_search", concept_cap=4, **PRODUCT_DIAG)

def chain_engine(cfg, n=8, no_exercises=()):
    concepts = tuple(Concept(f"K{i}", (f"K{i-1}",) if i > 1 else ()) for i in range(1, n + 1))
    acts = []
    for i in range(1, n + 1):
        acts.append(Activity(f"L-K{i}", ActivityType.LESSON, f"K{i}", 4))
        if f"K{i}" not in no_exercises:
            acts += [Activity(f"E-K{i}-{d}", ActivityType.EXERCISE, f"K{i}", 1, d)
                     for d in (0.2, 0.4, 0.6, 0.8)]
    return Engine(concepts, tuple(acts), cfg)

S1_GS = lambda **kw: load_profile("fitted_S1", **{**GS, **kw})
knows = lambda known: (lambda a: a.target_concept in known)

def test_goal_search_first_question_is_chain_middle():
    e = chain_engine(S1_GS())
    res = e.diagnose(e.init_learner(), lambda a: True)
    assert res.item_log[0].concept_id == "K4"

def test_goal_search_advanced_learner_finds_gap():
    e = chain_engine(S1_GS())
    res = e.diagnose(e.init_learner(), knows({"K1", "K2", "K3", "K4", "K5"}))
    r = res.concept_results
    assert {c for c in r if r[c].stop_reason == StopReason.INFERRED} == {"K1", "K2", "K3"}
    assert all(r[c].inferred_from == "K4" for c in ("K1", "K2", "K3"))
    assert r["K6"].p < 0.40
    assert {r["K7"].stop_reason, r["K8"].stop_reason} == {StopReason.SKIPPED_ANCESTOR_UNMASTERED}
    assert r["K4"].p == pytest.approx(0.77, abs=0.01) and r["K5"].p == pytest.approx(0.77, abs=0.01)
    assert res.total_items <= 12

def test_goal_search_novice_stops_fast():
    e = chain_engine(S1_GS())
    res = e.diagnose(e.init_learner(), lambda a: False)
    assert res.total_items <= 6
    assert all(x.p < 0.40 for x in res.state.concepts.values())

def test_goal_search_floors_ancestors_without_settling():
    e = chain_engine(S1_GS())
    res = e.diagnose(e.init_learner(), lambda a: a.difficulty != 0.2)  # misses every easy item
    r = res.concept_results
    assert r["K4"].p < 0.70
    assert all(res.state.concepts[a].p >= r["K4"].p - 1e-12 for a in ("K1", "K2", "K3"))
    assert r["K2"].stop_reason != StopReason.INFERRED

def test_goal_search_deterministic():
    e = chain_engine(S1_GS())
    run = lambda: e.diagnose(e.init_learner(), knows({"K1", "K2"})).item_log
    assert run() == run()

def test_goal_search_prefix_override_stops_at_n_max():
    e = chain_engine(S1_GS(n_max=3))
    assert e.diagnose(e.init_learner(), lambda a: True).total_items == 3

def test_goal_search_branching_dag_terminates():
    cfg = load_profile("fitted_S1", **GS)
    e = Engine.from_files("data/curriculum/curriculum_8node.json",
                          "data/curriculum/activities_8node.json", config=cfg)
    res = e.diagnose(e.init_learner(), lambda a: a.target_concept in {"C1", "C2", "C3", "C6"})
    assert set(res.concept_results) == set(e.graph.concepts())
    assert res.total_items <= 12

def test_goal_search_concept_without_exercises():
    e = chain_engine(S1_GS(), no_exercises=("K4",))
    res = e.diagnose(e.init_learner(), lambda a: True)
    assert res.concept_results["K4"].stop_reason == StopReason.NO_ITEMS
    assert set(res.concept_results) == {f"K{i}" for i in range(1, 9)}

def test_goal_search_leaves_out_of_set_concepts_untouched():
    e = chain_engine(S1_GS())
    init = e.init_learner()
    res = e.diagnose(init, lambda a: True, goal_concepts=["K5", "K6", "K7", "K8"])
    assert all(res.state.concepts[c] == init.concepts[c] for c in ("K1", "K2", "K3", "K4"))
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_w9_diagnostic.py -k goal_search -v`
Expected: FAIL — `AttributeError: INFERRED` / validation passes but the sweep runs instead.

- [ ] **Step 3: Implement `_run_goal_search`** in `engine.py`, reusing `_ask`, `_prune`, `compute_eig`, `candidate_sort_key`, and the exercise index pattern from `_run_frontier`. Selection and settling (the part the tests do not fully determine):

```text
open = goal-set concepts not yet in results
loop:
  record SKIPPED for open concepts in `skipped`; record NO_ITEMS for open concepts with no unasked exercise
  if no open concepts or total >= budget: break
  c = argmax over open of min(|open ∩ ancestors(c)| + 1, |open ∩ descendants(c)| + 1),
      ties -> earlier index in `ordered` (topological), then concept_id
  ask items on c (max-EIG unasked item each time) until the existing per-concept stop
      (min_items_per_concept + entropy <= h_stop -> ENTROPY; concept_cap -> CONCEPT_CAP;
       no unasked items -> NO_ITEMS) or total >= budget (-> GLOBAL_CAP, stop the run)
  p_c = final p; record c
  for a in open ∩ goal_set ∩ ancestors(c): concepts[a] = replace(concepts[a], p=max(concepts[a].p, p_c))
      and if p_c >= known_threshold: record a as INFERRED with inferred_from=c (n_items=0)
  self._prune(c, p_c, ...)   # existing downward rule
after loop: open concepts -> GLOBAL_CAP if total >= budget else NOT_REACHED
```

Dispatch in `run()`: `if self.config.selection_scope == "goal_search": return self._run_goal_search(..., budget)`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_w9_diagnostic.py tests/test_diagnostic.py -v`
Expected: all PASS.

---

### Task 4: Product preset

**Files:**
- Modify: `src/adaptengine/core/profiles.py`
- Test: `tests/test_w9_product.py` (new)

**Interfaces:**
- Produces in `adaptengine.core.profiles`: `STRICT_MASTERY: dict` (`theta`, `k_responses`, `horizon_aware_mastery`), `GOAL_SEARCH_DIAGNOSTIC: dict` (`selection_scope`, `concept_cap`, `n_max`, `diag_budget_min`, `diag_budget_per_concept`), `PRODUCT_OVERRIDES: dict = {**STRICT_MASTERY, **GOAL_SEARCH_DIAGNOSTIC, "consolidation": True, "verification_probe": True, "feasibility_warning": True}`, `PRODUCT_PROFILE = "fitted_S1"`, `product_config(profile: str = PRODUCT_PROFILE) -> EngineConfig` = `load_profile(profile, **PRODUCT_OVERRIDES)`.

- [ ] **Step 1: Write the failing tests**

```python
from adaptengine.core.config import DEFAULT_CONFIG
from adaptengine.core.profiles import PRODUCT_PROFILE, load_profile, product_config
from adaptengine.learner.state import mastered_by

def test_product_config_values():
    c = product_config()
    assert (c.theta, c.k_responses, c.horizon_aware_mastery) == (0.95, 4, False)
    assert (c.selection_scope, c.concept_cap, c.n_max, c.diag_budget_min, c.diag_budget_per_concept) == ("goal_search", 4, 25, 12, 1.0)
    assert c.consolidation and c.verification_probe and c.feasibility_warning
    assert c.class_params == load_profile("fitted_S1").class_params and PRODUCT_PROFILE == "fitted_S1"

def test_product_rules_on_any_profile():
    c = product_config("w7_default")
    assert c.theta == 0.95 and c.class_params == DEFAULT_CONFIG.class_params

def test_k_floor_binds_under_w7_numbers():
    c = product_config("w7_default")
    assert not mastered_by(0.99, 3, 3, c) and mastered_by(0.99, 4, 4, c)

def test_defaults_untouched():
    assert (DEFAULT_CONFIG.theta, DEFAULT_CONFIG.k_responses, DEFAULT_CONFIG.selection_scope) == (0.85, 2, "concept_sweep")
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_w9_product.py -v`
Expected: FAIL — `ImportError: cannot import name 'product_config'`.

- [ ] **Step 3: Add the dicts and `product_config` to `profiles.py`** with the values from Global Constraints.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_w9_product.py -v && pytest -q`
Expected: new tests PASS; full suite PASS (no existing test changes).

---

### Task 5: Frontend API uses the product rules

**Files:**
- Modify: `frontend/api/app.py` (`_profile_engine` ~lines 122–129; session load ~286; session out ~362; create ~381–388; `_diagnostic_view` rows ~244–252; health `default_profile` ~663)
- Modify: `frontend/api/schemas.py` (`CreateSession.profile` default ~59; add `rules`; `profile` default ~185; diagnostic row model gains `inferred_from`)
- Test: `frontend/api/tests/test_api.py`

**Interfaces:**
- Consumes: `product_config`, `PRODUCT_PROFILE` (Task 4); `ConceptDiagnosticResult.inferred_from` (Task 3).
- Produces: `CreateSession.rules: Literal["product", "legacy"] = "product"`; `CreateSession.profile` default `"fitted_S1"`; session meta key `"rules"`; `_profile_engine(cid: str, profile: str, rules: str) -> Engine` (cached); concept-result rows include `"inferred_from"`; health `default_profile == "fitted_S1"`; `SessionOut` exposes `rules`.

- [ ] **Step 1: Write the failing tests**

```python
def test_new_session_defaults_to_product_rules(client):
    v = _new(client)                         # no profile / rules given
    assert v["profile"] == "fitted_S1" and v["rules"] == "product"
    assert client.get("/api/health").json()["default_profile"] == "fitted_S1"

def test_product_engine_config(client):
    e = app_module._profile_engine("8node", "fitted_S1", "product")
    assert (e.config.theta, e.config.k_responses, e.config.selection_scope) == (0.95, 4, "goal_search")

def test_legacy_rules_keep_w7_engine(client):
    assert app_module._profile_engine("8node", "w7_default", "legacy").config == app_module._bundle("8node").engine.config

def test_legacy_session_replays_unchanged(client, tmp_path):
    # a session written before this change: meta without "rules"
    v = _new(client, profile="w7_default", rules="legacy")
    ...answer the diagnostic through the API, then delete "rules" from <sid>.meta.json on disk...
    reloaded = client.get(f"/api/sessions/{v['session_id']}").json()
    assert reloaded["diagnostic"] == v_after_answers["diagnostic"] and reloaded["rules"] == "legacy"
```

(The `...` lines use the file's existing helpers for answering the diagnostic and the store's meta path; follow `test_profile_session_and_feasibility_warning` for the pattern.)

- [ ] **Step 2: Run to verify failure**

Run: `pytest frontend/api/tests/test_api.py -v`
Expected: the four new tests FAIL.

- [ ] **Step 3: Implement**
  - `_profile_engine(cid, profile, rules)`: `rules == "legacy"` → today's behaviour (bundle engine for `w7_default`, else `load_profile(profile)`); `rules == "product"` → `Engine(b.concepts, acts, product_config(profile))`.
  - Create session: store `meta["rules"] = req.rules`. Loading: `meta.get("rules", "legacy")` (missing key = pre-change session).
  - Health: `default_profile = PRODUCT_PROFILE`. Concept-result rows add `"inferred_from": r.inferred_from`.
  - Existing tests that assert W7-specific diagnostic/plan numbers: create their sessions with `rules="legacy"` (add a `rules` kwarg to the `_new` helper) rather than changing their expected values.

- [ ] **Step 4: Run tests**

Run: `pytest frontend/api/tests/test_api.py -v`
Expected: all PASS.

---

### Task 6: Web UI

**Files:**
- Modify: `frontend/web/src/pages/Setup.tsx` (default profile line 9; rules control next to "Learner model" ~line 72)
- Modify: `frontend/web/src/ctx.ts` (`DEMO_SETUP.curriculum` line 37: `"8node"` → `"8node_x10"`)
- Modify: `frontend/web/src/pages/Diagnostic.tsx` (`STOP_TEXT` line 8; stop-reason table ~120–130)
- Regenerate: `frontend/web/openapi.json` and generated types via `npm run gen:types`

**Interfaces:**
- Consumes: `rules`, `inferred_from`, `default_profile` from Task 5.

- [ ] **Step 1: Regenerate API types**

Run: `cd frontend/web && npm run gen:types`
Expected: generated types include `rules` and `inferred_from`.

- [ ] **Step 2: Implement**
  - `DEMO_SETUP.curriculum = "8node_x10"` (the 10-exercise curriculum from Task 1).
  - Setup: default `profile` = `health.data?.default_profile ?? "fitted_S1"`; a `Segmented` control "Rules" with options `product` / `legacy (W7)` sent as `rules` in `createSession`.
  - Diagnostic: `STOP_TEXT.INFERRED = "inferred from a later concept"`, appending ` (${r.inferred_from})` when present; a "Level" column: `Known` if p ≥ 0.70, `Unknown` if p < 0.40, else `Uncertain`.

- [ ] **Step 3: Build**

Run: `cd frontend/web && npm run build`
Expected: `tsc` and `vite build` succeed with no errors.

- [ ] **Step 4: Check it in the running app** (needs Task 1 Step 5 done) — start the API and web dev server, create a session with defaults, answer the diagnostic as a learner who knows `C1 C2 C3 C6`; confirm the Level column and an `inferred from` row appear and the plan schedules ≥ 4 exercises per required concept.

---

### Task 7: Evaluation runners

**Files:**
- Modify: `experiments/run_final_grid.py` (`arm_engine` lines 49–59; `main` uses `ARMS` line 192; CLI ~303)
- Create: `experiments/run_w9_diag.py`
- Test: `tests/test_w9_eval.py` (new)

**Interfaces:**
- Consumes: `STRICT_MASTERY`, `GOAL_SEARCH_DIAGNOSTIC` (Task 4); `experiments.w8_common.curriculum_paths` (supports `synth-N`); `experiments.diag_eval.binary_score`; `experiments.sim.make_sim`, `PROFILES`.
- Produces: arms `adapt_strict_dx` (= `adapt_final_dx` overrides + `STRICT_MASTERY`) and `adapt_strict_gs` (+ `GOAL_SEARCH_DIAGNOSTIC`), both run as `"adapt_dx"`; CLI `--arms` (default `ARMS`, unchanged); `run_w9_diag.main(out_path: str, n: int, curricula: list[str]) -> dict` with arms `prior_only`, `w6_shipped`, `default_t33`, `goal_search` (= `GOAL_SEARCH_DIAGNOSTIC` on `DEFAULT_CONFIG` numbers) per world S0/S2/S4 per curriculum. Curriculum names resolve through `curriculum_paths` (`4node_x10` → `data/curriculum/curriculum_4node_x10.json`).

- [ ] **Step 1: Write the failing tests**

```python
from experiments.run_final_grid import arm_engine, winner_spec

def test_strict_arms_config():
    spec = winner_spec()
    e, run_arm = arm_engine("adapt_strict_gs", "S1", "4-node", spec)
    assert run_arm == "adapt_dx"
    assert (e.config.theta, e.config.k_responses, e.config.selection_scope, e.config.concept_cap) == (0.95, 4, "goal_search", 4)
    assert e.config.consolidation and e.config.diagnostic_scope == "goal_path"
    e2, _ = arm_engine("adapt_strict_dx", "S1", "4-node", spec)
    assert e2.config.selection_scope == "concept_sweep" and e2.config.theta == 0.95

def test_w9_diag_smoke(tmp_path):
    from experiments.run_w9_diag import main
    r = main(str(tmp_path / "d.json"), n=3, curricula=["4-node", "synth-20"])
    assert set(r["curricula"]["synth-20"]["S0"]) >= {"prior_only", "goal_search"}
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_w9_eval.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement** the two `arm_engine` branches and `--arms`; write `run_w9_diag.py` following `run_diag_matrix.run_world` (same odd seeds `range(101, 101 + 2n, 2)`, same scoring and `paired_summary` vs `prior_only` and `w6_shipped`, `stamp()` metadata), looping over `curricula`. Default output `experiments/results/w9_diag_matrix.json`.

- [ ] **Step 4: Run tests and a grid smoke**

Run: `pytest tests/test_w9_eval.py -v && python experiments/run_final_grid.py --smoke --arms adapt_final_dx adapt_strict_dx adapt_strict_gs static_loop --out experiments/results/w9_grid.json --checkpoint experiments/results/w9_grid.ckpt.jsonl`
Expected: tests PASS; smoke writes `w9_grid_smoke.json` with 0 executed violations in every arm.

---

### Task 8: Decisions, pre-registration, run, report

**Files:**
- Modify: `docs/DECISIONS.md` (append D61–D63, wording from spec §5.6)
- Create: `docs/preregistration/W9_STRICT_GOALSEARCH_2026-11-14.md`
- Create (by running): `experiments/results/w9_grid.json`, `experiments/results/w9_diag_matrix.json`
- Modify: next report notes file (a "W9" section)

- [ ] **Step 1: Write D61–D63** in `docs/DECISIONS.md`, each with rationale and the caveats from spec §4.1–4.2.
- [ ] **Step 2: Write the pre-registration** (before running anything; Task 1 Step 5 must be done) — arms, cells, seeds, metrics from spec §6, the curricula `4node_x10`/`8node_x10` (10 exercises per concept; W8 used 4, so W8 numbers are not directly comparable and the W8 reference arms are re-run here), the statement that the run measures and does not select, and the code hash from `python experiments/provenance.py`.
- [ ] **Step 3: Run**

Run: `python experiments/run_final_grid.py --arms adapt_final adapt_final_dx adapt_strict_dx adapt_strict_gs static_loop --curricula 4node_x10 8node_x10 --out experiments/results/w9_grid.json --checkpoint experiments/results/w9_grid.ckpt.jsonl && python experiments/run_w9_diag.py --curricula 4node_x10 8node_x10 synth-20 synth-50`
Expected: both files written; `code_hash` in their metadata equals the pre-registered hash; 0 executed violations.

- [ ] **Step 4: Report** goal mastery, false-mastery rate, items per mastered concept, diagnostic items, utilisation per arm, and the diagnostic matrix, as measured, in the report notes.
