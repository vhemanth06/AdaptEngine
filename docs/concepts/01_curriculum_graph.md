# 01 · The curriculum graph

## Idea

A course is a set of concepts. Some concepts need others first: list comprehensions need lists,
and lists need data types and loops. AdaptEngine stores these "needs" as a directed acyclic graph
(DAG) and uses it for three things: a fixed study order, the set of knowledge states a learner
can be in, and a safety rule: the learner never works on a concept whose prerequisites have no
evidence of mastery.

## Notation

| Symbol | Meaning | Code name |
|---|---|---|
| $V$ | the set of concepts in the curriculum | `graph.concepts()` |
| $q \to c$ | an edge: $q$ is a direct prerequisite of $c$ | `Concept.prerequisites` |
| $\mathrm{pre}(c)$ | direct prerequisites of $c$ | `graph.prerequisites(c)` |
| $\mathrm{anc}(c)$, $\mathrm{desc}(c)$ | all ancestors / all descendants of $c$ (transitive) | `graph.ancestors(c)`, `graph.descendants(c)` |
| $\mathrm{depth}(c)$ | length of the longest prerequisite chain ending at $c$ | `graph.depth(c)` |
| $S$ | the scope: the concepts being reasoned about | `select_scope(...)` |
| $K$ | a knowledge state: a down-set of $S$ | `frozenset` of concept ids |
| $\mathcal{K}(S)$ | the set of all knowledge states of $S$ | `enumerate_states(graph, S, limit)` |
| $\mathrm{EM}(c)$ | "$c$ is evidence-mastered" (see [02](02_mastery_bkt.md)) | `is_evidence_mastered(concept, cfg)` |

## Maths

**Graph and acyclicity.** The graph has one node per concept and an edge $q \to c$ for every
$q \in \mathrm{pre}(c)$. It must contain no directed cycle; a self-prerequisite ($c \in \mathrm{pre}(c)$)
counts as a cycle. A prerequisite that names an unknown concept is rejected.

**Depth.**

$$\mathrm{depth}(c) = \begin{cases} 0 & \text{if } \mathrm{pre}(c) = \emptyset \text{ (a root)} \\ 1 + \max_{q \in \mathrm{pre}(c)} \mathrm{depth}(q) & \text{otherwise} \end{cases}$$

**Topological order.** A list of all concepts in which every $q \in \mathrm{pre}(c)$ comes before
$c$. When several concepts are ready at once, the one with the smallest `concept_id` in plain
string order comes first (NetworkX `lexicographical_topological_sort`). String order means
`"C10"` sorts before `"C2"`. The order is computed once and is the same on every call.

**Knowledge states (down-sets).** A set $K \subseteq S$ is a knowledge state when it is closed
under prerequisites inside the scope:

$$c \in K \;\Rightarrow\; q \in K \quad \text{for every } q \in \mathrm{pre}(c) \cap S.$$

The empty set and $S$ itself are always knowledge states. The scope $S$ is the goal plus its
ancestors (`bisection_scope = "goal_ancestors"`), or all concepts (`"all"`, or when there is no goal).

**Enumeration.** Walk $S$ in topological order, starting from $\mathcal{K} = \{\emptyset\}$. For each
concept $c$, add $K \cup \{c\}$ for every $K$ already in $\mathcal{K}$ that contains all of
$\mathrm{pre}(c) \cap S$. Because prerequisites are decided first, each down-set is produced exactly
once. If $|\mathcal{K}|$ passes `bisection_exact_state_limit` (5,000) the enumeration stops and the
bisection diagnostic switches to sampling ([05](05_diagnostic_bisection.md)). An upper bound on
$\log_2 |\mathcal{K}|$ is $\sum_j \log_2(L_j + 1)$ over a minimum chain cover with chain lengths $L_j$.

**Safety invariant.** Whenever the learner does an activity (lesson or exercise) on concept $c$,
every direct prerequisite must already be evidence-mastered in the learner state at that moment:

$$\text{activity on } c \text{ executed} \;\Rightarrow\; \mathrm{EM}(q) \text{ for every } q \in \mathrm{pre}(c).$$

Direct prerequisites are enough: each $q$ was itself only studied once its own prerequisites
were mastered. The planner enforces the rule by gating: a concept gets no activity while a direct
prerequisite still has queued work or was neither evidence-mastered at plan start nor finished
in the plan's projection. `Engine.record` does not refuse an out-of-order event; the rule is
checked by replaying the real execution log (the executed-state audit, D46).

## Worked example

The 4-node curriculum (`data/curriculum/curriculum_4node.json`): C1 Basic Data Types, C2 For & While
Loops, C3 Lists & Arrays, C4 List Comprehensions.

```
C1 ──┐
     ├──> C3 ──> C4
C2 ──┘
```

| Concept | $\mathrm{pre}(c)$ | depth | $\mathrm{desc}(c)$ |
|---|---|---|---|
| C1 | — | 0 | C3, C4 |
| C2 | — | 0 | C3, C4 |
| C3 | C1, C2 | 1 | C4 |
| C4 | C3 | 2 | — |

Roots: C1, C2. Topological order: **C1, C2, C3, C4** (C1 and C2 are both ready at the start; C1 wins
the tie by string order).

With scope = all four concepts there are **6 knowledge states**:

| # | $K$ |
|---|---|
| 1 | $\emptyset$ |
| 2 | {C1} |
| 3 | {C2} |
| 4 | {C1, C2} |
| 5 | {C1, C2, C3} |
| 6 | {C1, C2, C3, C4} |

Of the $2^4 = 16$ subsets, 10 are ruled out: for example {C3} (C3 without C1 and C2) or {C1, C3}.
Under the safety rule a learner with evidence of mastery on C1 only may study C2 (no prerequisites)
but not C3, because C2 is not yet evidence-mastered.

Two side checks: two roots named `C2` and `C10` come out as `('C10', 'C2')`, and the cycle
C1 → C2 → C1 raises `CycleError: Cycle detected: [('C1', 'C2', 'forward'), ('C2', 'C1', 'forward')]`.

<details><summary>How these numbers were produced</summary>

The script below, saved as `c01_graph.py` outside the repository and run from the repository root:

```bash
.venv/bin/python <path-to>/c01_graph.py
```

```python
from adaptengine.curriculum.loader import load_curriculum
from adaptengine.curriculum.graph import CurriculumGraph
from adaptengine.diagnostic.knowledge_space import enumerate_states
from adaptengine.core.config import DEFAULT_CONFIG
from adaptengine.core.schema import Concept
from adaptengine.core.errors import CycleError

g = CurriculumGraph.from_concepts(load_curriculum("data/curriculum/curriculum_4node.json"))
for c in g.concepts():
    print(c, "pre =", g.prerequisites(c), "depth =", g.depth(c), "descendants =", sorted(g.descendants(c)))
print("roots:", g.roots())
print("topological order:", g.topological_order())
states = enumerate_states(g, g.topological_order(), DEFAULT_CONFIG.bisection_exact_state_limit)
print(len(states), "knowledge states:")
for k in states:
    print(" ", sorted(k))
print("tie rule:", CurriculumGraph((Concept("C2"), Concept("C10"))).topological_order())
try:
    CurriculumGraph((Concept("C1", ("C2",)), Concept("C2", ("C1",))))
except CycleError as e:
    print("CycleError:", e)
```

Output:

```
C1 pre = () depth = 0 descendants = ['C3', 'C4']
C2 pre = () depth = 0 descendants = ['C3', 'C4']
C3 pre = ('C1', 'C2') depth = 1 descendants = ['C4']
C4 pre = ('C3',) depth = 2 descendants = []
roots: ('C1', 'C2')
topological order: ('C1', 'C2', 'C3', 'C4')
6 knowledge states:
  []
  ['C1']
  ['C2']
  ['C1', 'C2']
  ['C1', 'C2', 'C3']
  ['C1', 'C2', 'C3', 'C4']
tie rule: ('C10', 'C2')
CycleError: Cycle detected: [('C1', 'C2', 'forward'), ('C2', 'C1', 'forward')]
```

</details>

## In the code

| Function or class | File | Config key | Default value |
|---|---|---|---|
| `load_curriculum` (schema, unique ids, unknown prerequisites, review gate with `edges_reviewed`) | `src/adaptengine/curriculum/loader.py` | — | — |
| `CurriculumGraph` (edges, `CycleError`, `UnknownConceptError`, precomputed queries) | `src/adaptengine/curriculum/graph.py` | — | — |
| `CurriculumGraph.topological_order` | `src/adaptengine/curriculum/graph.py` | — | lexicographic ties |
| `CurriculumGraph.depth`, `descendant_count`, `min_chain_cover` | `src/adaptengine/curriculum/graph.py` | — | — |
| `select_scope` | `src/adaptengine/diagnostic/knowledge_space.py` | `bisection_scope` | `"goal_ancestors"` |
| `enumerate_states`, `chain_cover_bits` | `src/adaptengine/diagnostic/knowledge_space.py` | `bisection_exact_state_limit` | 5000 |
| `run_greedy_schedule` gating (`gated()`) | `src/adaptengine/planner/schedule.py` | — | — |
| CP-SAT prerequisite gating | `src/adaptengine/planner/cpsat_planner.py` | — | — |
| `is_evidence_mastered` (the test in the safety rule) | `src/adaptengine/learner/state.py` | `theta`, `k_responses` | 0.85, 2 |
| `executed_violations` (executed-state audit) | `experiments/core/audit.py` | — | — |

## Tests

- `tests/unit/curriculum/test_graph.py` — roots, ancestors, depth, topological order and its
  stability, cycle and self-loop rejection, precomputed queries equal NetworkX.
- `tests/unit/curriculum/test_loader_review_gate.py` — the review gate (manifest entry, named reviewer, `edges_reviewed`, hash).
- `tests/regression/test_defects_repro.py` — `test_repro_dc_unknown_prereq_phantom_node`.
- `tests/unit/diagnostic/test_knowledge_space.py` — state counts (`test_state_counts`, 18 states for
  the 8-node curriculum), the enumeration limit, goal scope, marginals that respect prerequisites.
- `tests/unit/planner/test_planner.py` — `test_prerequisite_safety_tc31`.
- `tests/unit/planner/test_planner_projection.py`, `tests/unit/planner/test_cpsat_reviews.py` —
  reviews wait for unfinished or unmastered prerequisites.
- `tests/integration/test_closed_loop_planners.py` — confirmation checks gate dependants.
- `experiments/tests/unit/test_audit.py` — executed and plan-level violation counts.

## Decisions

- [D9](../project/DECISIONS.md#d9) — named human reviewer required before live loading (review gate).
- [D11](../project/DECISIONS.md#d11), [D12](../project/DECISIONS.md#d12) — prerequisites finish
  before a concept is scheduled; same-day unlock respects prerequisite order.
- [D13](../project/DECISIONS.md#d13) — unlock count is the transitive descendant count.
- [D4](../project/DECISIONS.md#d4), [D31](../project/DECISIONS.md#d31) — what "evidence-mastered" means.
- [D46](../project/DECISIONS.md#d46) — the executed-state audit is the primary safety metric.
- [D50](../project/DECISIONS.md#d50), [D53](../project/DECISIONS.md#d53),
  [D54](../project/DECISIONS.md#d54) — knowledge states as down-sets, exact enumeration up to the
  limit, scope.

The tie rule of the topological order has no D-number; it is fixed by the code.

## Limitations

- Edges are hard and binary: a prerequisite is either required in full or not at all. Partial or
  "helpful but not required" links are not modelled.
- Edges are authored, not learned from data. A wrong or missing edge directly changes what the
  planner allows.
- Only direct prerequisites are checked at execution time. If an ancestor's mastery later drops
  (for example after a wrong review answer), dependants already started are not undone.
- The safety rule is strict, and it costs time. In the final study adapt had 0 executed
  violations (E1 H1) while static broke prerequisite order for most learners; but holding the goal
  back until prerequisites have evidence is also why static sometimes reaches higher goal mastery
  on short budgets. See the Outcomes section of [`experiments/NOTES.md`](../../experiments/NOTES.md)
  ("Mechanism check behind the static-wins list").
- The number of knowledge states grows quickly on wide graphs; above 5,000 the bisection diagnostic
  samples instead of enumerating.

## Values checked

All read with `.venv/bin/python` from the repository root on the current code:

- `DEFAULT_CONFIG.bisection_exact_state_limit` → 5000
- `DEFAULT_CONFIG.bisection_scope` → `"goal_ancestors"`
- `DEFAULT_CONFIG.theta` → 0.85
- `DEFAULT_CONFIG.k_responses` → 2

(via `from adaptengine.core.config import DEFAULT_CONFIG`). The topological order, depths and the
6 knowledge states come from the script above, run on 2026-11-21.
