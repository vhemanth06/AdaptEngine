"""Knowledge-space inference for the bisection diagnostic (Plan 3, F1.3, D50-D53).

A knowledge state K is a set of in-scope concepts closed under in-scope prerequisites (a down-set
of the DAG). The prior is uniform over knowledge states (D51), optionally times per-concept
factors. Every piece of evidence is also a per-concept factor: weight a_c if c is in K, b_c if not.
This covers
- an answer y on an item of concept c: a_c = P(y | known), b_c = P(y | not known);
- earlier evidence folded in from the input state: a_c = p_c / p0, b_c = (1 - p_c) / (1 - p0)
  (posterior odds over prior odds, i.e. the likelihood ratio of the past answers);
- the "independent_p0" comparison prior: a_c = p0, b_c = 1 - p0.

Two posteriors share that representation: ExactPosterior enumerates the states while there are at
most `limit` of them; SamplingPosterior keeps seeded weighted samples moved by a Markov chain on
down-sets (add a concept whose prerequisites are in K, or remove one with no dependants in K).
The proposal is symmetric, so with Metropolis acceptance on the factor ratio of the toggled
concept the chain targets the posterior exactly.
"""

from __future__ import annotations

import hashlib
import math
from typing import Mapping, Optional, Sequence

from ..curriculum.graph import CurriculumGraph


class _Rng:
    """SplitMix64: a small seeded generator (the architecture rules keep `random` out of src)."""

    _MASK = (1 << 64) - 1

    def __init__(self, seed) -> None:
        self.state = int.from_bytes(hashlib.sha256(str(seed).encode()).digest()[:8], "big")

    def _next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & self._MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & self._MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & self._MASK
        return z ^ (z >> 31)

    def random(self) -> float:
        return (self._next() >> 11) / float(1 << 53)

    def randrange(self, n: int) -> int:
        return self._next() % n


def select_scope(graph: CurriculumGraph, goal_concepts, scope_mode: str) -> list[str]:
    """Concepts to diagnose, in topological order (D54)."""
    if goal_concepts is None:
        chosen = set(graph.concepts())
    elif scope_mode == "goal_ancestors":
        chosen = set()
        for g in goal_concepts:
            chosen |= {g} | set(graph.ancestors(g))
    else:
        chosen = set(goal_concepts)
    return [c for c in graph.topological_order() if c in chosen]


def _in_scope_links(graph: CurriculumGraph, scope: Sequence[str]):
    s = set(scope)
    pre = {c: [q for q in graph.prerequisites(c) if q in s] for c in scope}
    kids: dict[str, list[str]] = {c: [] for c in scope}
    for c, ps in pre.items():
        for q in ps:
            kids[q].append(c)
    return pre, kids


def enumerate_states(
    graph: CurriculumGraph, scope: Sequence[str], limit: int
) -> Optional[list[frozenset]]:
    """All knowledge states of `scope`, or None as soon as there are more than `limit`."""
    pre, _ = _in_scope_links(graph, scope)
    states: list[frozenset] = [frozenset()]
    for c in scope:  # topological order: prerequisites are decided first
        states += [k | {c} for k in states if all(q in k for q in pre[c])]
        if len(states) > limit:
            return None
    return states


def chain_cover_bits(graph: CurriculumGraph, scope: Sequence[str]) -> float:
    """Upper bound on log2(#states): sum of log2(L_j + 1) over a minimum chain cover (F1.3.7).

    Each chain of length L contributes at most L + 1 choices to a down-set.
    """
    return sum(math.log2(len(ch) + 1) for ch in graph.min_chain_cover(scope))


class ExactPosterior:
    """Weights over every knowledge state of the scope."""

    mode = "exact"

    def __init__(self, scope: Sequence[str], states: list[frozenset], factors: Mapping):
        self.scope = list(scope)
        self.states = states
        w = [1.0] * len(states)
        for c, (a, b) in factors.items():
            w = [x * (a if c in k else b) for x, k in zip(w, states)]
        self.w = self._norm(w)
        self.n_states = len(states)
        self.bits = math.log2(len(states))

    @staticmethod
    def _norm(w):
        z = sum(w)
        return [x / z for x in w]

    def update(self, concept: str, a: float, b: float) -> None:
        self.w = self._norm([x * (a if concept in k else b) for x, k in zip(self.w, self.states)])

    def marginal(self, concept: str) -> float:
        return sum(x for x, k in zip(self.w, self.states) if concept in k)

    def top_state(self) -> tuple[frozenset, float]:
        i = max(range(len(self.w)), key=lambda j: (self.w[j], -j))
        return self.states[i], self.w[i]


class SamplingPosterior:
    """Seeded weighted samples of knowledge states for wide DAGs (D53), as sequential Monte Carlo.

    States are bitmasks over the scope. Initial particles run independent chains from the empty
    set for BURN_IN * n moves (n = scope size) on the prior times the folded-in factors; they are
    cached per (scope, factors, count, seed) because every fresh learner starts the same way.
    After each answer the particles are reweighted; when the effective sample size falls below
    half they are resampled (systematic) and each runs REJUVENATE * n further moves on the current
    posterior. Marginals are Rao-Blackwellised: per state, the exact P(c in K | the rest of K).
    """

    mode = "sampling"
    BURN_IN = 40
    REJUVENATE = 3

    def __init__(self, graph, scope, factors, n_samples: int, seed: int):
        self.scope = list(scope)
        self.index = {c: i for i, c in enumerate(self.scope)}
        pre, kids = _in_scope_links(graph, scope)
        self.pre_mask = [sum(1 << self.index[q] for q in pre[c]) for c in self.scope]
        self.kid_mask = [sum(1 << self.index[q] for q in kids[c]) for c in self.scope]
        self.rng = _Rng(seed)
        self.factors = {self.index[c]: f for c, f in factors.items()}
        self.n_states = None
        self.bits = chain_cover_bits(graph, scope)
        key = (
            tuple(self.scope),
            tuple(self.pre_mask),
            tuple(sorted(self.factors.items())),
            n_samples,
            seed,
        )
        if key not in _INITIAL_CACHE:
            moves = self.BURN_IN * len(self.scope)
            _INITIAL_CACHE[key] = tuple(self._run(0, moves) for _ in range(n_samples))
        self.samples = list(_INITIAL_CACHE[key])
        self.w = [1.0 / n_samples] * n_samples
        self.rng = _Rng(f"{seed}-posterior")
        self._weights_by_state = None

    def _accept(self, i: int) -> tuple[float, float]:
        a, b = self.factors.get(i, (1.0, 1.0))
        return min(1.0, a / b), min(1.0, b / a)  # P(accept add), P(accept remove)

    def _run(self, k: int, moves: int) -> int:
        """`moves` chain steps from state k; one SplitMix64 draw per step gives the concept (low
        32 bits) and the acceptance uniform (high 32 bits)."""
        n, pre, kid = len(self.scope), self.pre_mask, self.kid_mask
        acc = [self._accept(i) for i in range(n)]
        mask, x = _Rng._MASK, self.rng.state
        for _ in range(moves):
            x = (x + 0x9E3779B97F4A7C15) & mask
            z = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & mask
            z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & mask
            z ^= z >> 31
            i = (z & 0xFFFFFFFF) % n
            u = (z >> 32) * 2.3283064365386963e-10  # / 2**32
            bit = 1 << i
            if k & bit:
                if not k & kid[i] and u < acc[i][1]:
                    k ^= bit
            elif k & pre[i] == pre[i] and u < acc[i][0]:
                k |= bit
        self.rng.state = x
        return k

    def update(self, concept: str, a: float, b: float) -> None:
        i = self.index[concept]
        fa, fb = self.factors.get(i, (1.0, 1.0))
        self.factors[i] = (fa * a, fb * b)
        bit = 1 << i
        w = [x * (a if k & bit else b) for x, k in zip(self.w, self.samples)]
        z = sum(w)
        self.w = [x / z for x in w]
        self._weights_by_state = None
        if 1.0 / sum(x * x for x in self.w) < len(self.w) / 2:
            n = len(self.samples)
            step, u = 1.0 / n, self.rng.random() / n  # systematic resampling
            out, cum, j = [], self.w[0], 0
            for t in range(n):
                while u + t * step > cum and j < n - 1:
                    j += 1
                    cum += self.w[j]
                out.append(self.samples[j])
            moves = self.REJUVENATE * len(self.scope)
            self.samples = [self._run(k, moves) for k in out]
            self.w = [1.0 / n] * n

    def _states(self) -> dict:
        if self._weights_by_state is None:
            agg: dict[int, float] = {}
            for x, k in zip(self.w, self.samples):
                agg[k] = agg.get(k, 0.0) + x
            self._weights_by_state = agg
        return self._weights_by_state

    def marginal(self, concept: str) -> float:
        i = self.index[concept]
        a, b = self.factors.get(i, (1.0, 1.0))
        free, pm, km = a / (a + b), self.pre_mask[i], self.kid_mask[i]
        total = 0.0
        for k, x in self._states().items():
            if k & km:
                total += x  # forced in: a dependant is known
            elif k & pm == pm:
                total += x * free  # both configurations are down-sets
        return total

    def top_state(self) -> tuple[frozenset, float]:
        k, x = max(self._states().items(), key=lambda kv: (kv[1], -kv[0]))
        return frozenset(c for i, c in enumerate(self.scope) if k >> i & 1), x


_INITIAL_CACHE: dict = {}


def make_posterior(graph, scope, factors, limit, n_samples, seed):
    states = enumerate_states(graph, scope, limit)
    if states is not None:
        return ExactPosterior(scope, states, factors)
    return SamplingPosterior(graph, scope, factors, n_samples, seed)
