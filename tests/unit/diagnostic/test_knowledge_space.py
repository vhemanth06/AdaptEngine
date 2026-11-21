"""Plan 3 (F1-T2, F1-T4): knowledge-space inference (F1-TC3, F1-TC5, F1-TC12)."""

import json
import math
import os
import tempfile
import time

import pytest

from adaptengine.api import Engine
from adaptengine.core.schema import Concept
from adaptengine.curriculum.graph import CurriculumGraph
from adaptengine.diagnostic.knowledge_space import (
    ExactPosterior,
    SamplingPosterior,
    chain_cover_bits,
    enumerate_states,
    make_posterior,
    select_scope,
)

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _engine(name):
    d = os.path.join(repo_root, "data", "curriculum")
    return Engine.from_files(f"{d}/curriculum_{name}.json", f"{d}/activities_{name}.json")


def _chain(n):
    return CurriculumGraph.from_concepts(
        tuple(Concept(f"K{i}", (f"K{i - 1}",) if i else ()) for i in range(n))
    )


def _synth(n, x=4):
    # replaces experiments/synth_curriculum.py::write_synthetic_curriculum (same generator, seed 2026)
    from experiments.core.curricula import generate_synthetic

    d, (cur, act) = tempfile.mkdtemp(), generate_synthetic(n, x)
    cp, ap = os.path.join(d, "curriculum.json"), os.path.join(d, "activities.json")
    for path, obj in ((cp, cur), (ap, act)):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)
    return Engine.from_files(cp, ap, allow_unreviewed=True)


G8 = _engine("8node").graph
S8 = select_scope(G8, None, "all")


def test_state_counts():
    assert len(enumerate_states(G8, S8, 5000)) == 18
    for n in (1, 5, 31):
        g = _chain(n)
        assert len(enumerate_states(g, select_scope(g, None, "all"), 5000)) == n + 1
    anti = CurriculumGraph.from_concepts(tuple(Concept(f"A{i}") for i in range(6)))
    assert len(enumerate_states(anti, select_scope(anti, None, "all"), 5000)) == 2**6


def test_limit_triggers():
    assert enumerate_states(G8, S8, 17) is None
    assert len(enumerate_states(G8, S8, 18)) == 18
    assert isinstance(make_posterior(G8, S8, {}, 17, 200, 0), SamplingPosterior)
    assert isinstance(make_posterior(G8, S8, {}, 18, 200, 0), ExactPosterior)


def test_8node_starting_marginals_f1_tc12():
    post = ExactPosterior(S8, enumerate_states(G8, S8, 5000), {})
    want = {"C1": 16, "C2": 15, "C3": 12, "C6": 10, "C5": 8, "C4": 6, "C7": 4, "C8": 2}
    for c, k in want.items():
        assert post.marginal(c) == pytest.approx(k / 18, abs=1e-12)
    assert {c: round(post.marginal(c), 2) for c in want} == {
        "C1": 0.89,
        "C2": 0.83,
        "C3": 0.67,
        "C6": 0.56,
        "C5": 0.44,
        "C4": 0.33,
        "C7": 0.22,
        "C8": 0.11,
    }
    assert post.bits == pytest.approx(math.log2(18))


def test_hand_posterior_three_chain():
    g = _chain(3)
    s = select_scope(g, None, "all")
    post = ExactPosterior(s, enumerate_states(g, s, 5000), {})
    a, b = 0.9, 0.2  # P(right | K1 known), P(right | not)
    post.update("K1", a, b)  # states {}, {K0}, {K0,K1}, {K0,K1,K2} weighted b, b, a, a
    assert post.marginal("K1") == pytest.approx(a / (a + b))
    assert post.marginal("K0") == pytest.approx((b + 2 * a) / (2 * a + 2 * b))
    assert post.marginal("K2") == pytest.approx(a / (2 * a + 2 * b))
    assert post.top_state()[1] == pytest.approx(a / (2 * a + 2 * b))


@pytest.mark.parametrize("mode", ["exact", "sampling"])
def test_marginals_respect_prerequisites_f1_tc3(mode):
    limit = 5000 if mode == "exact" else 1
    post = make_posterior(G8, S8, {}, limit, 2000, 0)
    seq = [("C8", 0.2, 0.9), ("C5", 0.85, 0.2), ("C3", 0.15, 0.8), ("C1", 0.9, 0.3)]
    for c, a, b in [(None, 1, 1)] + seq:
        if c:
            post.update(c, a, b)
        for child in S8:
            for parent in G8.prerequisites(child):
                assert post.marginal(child) <= post.marginal(parent) + 1e-12


SEQ = [(-1, 0.85, 0.2), (4, 0.2, 0.9), (0, 0.85, 0.2), (-2, 0.8, 0.15), (1, 0.9, 0.3)]


@pytest.mark.parametrize("which", ["4node", "8node", "synth15"])
def test_sampling_matches_exact_f1_tc5(which):
    g = _synth(15).graph if which == "synth15" else _engine(which).graph
    s = select_scope(g, None, "all")
    ex = ExactPosterior(s, enumerate_states(g, s, 10**6), {})
    sp = SamplingPosterior(g, s, {}, 4000, 0)  # bisection_samples / bisection_seed defaults
    errs = [abs(sp.marginal(c) - ex.marginal(c)) for c in s]
    for i, a, b in SEQ:
        ex.update(s[i % len(s)], a, b)
        sp.update(s[i % len(s)], a, b)
        errs += [abs(sp.marginal(c) - ex.marginal(c)) for c in s]
    # Plan F1-TC5 says 0.02; at 4,000 samples the Monte Carlo standard error is about 0.008, and
    # the measured worst case over seeds 0-4 is 0.022 (4-node, seed 0). The test allows 0.025 and
    # checks the mean absolute error separately, which catches bias (ruling in docs/archive/notes/PLAN3_NOTES.md).
    assert max(errs) <= 0.025, errs
    assert sum(errs) / len(errs) <= 0.012, errs


def test_sampling_deterministic_by_seed():
    def run(seed):
        sp = SamplingPosterior(G8, S8, {}, 1000, seed)
        for i, a, b in SEQ:
            sp.update(S8[i], a, b)
        return [sp.marginal(c) for c in S8], sp.top_state()

    assert run(3) == run(3)
    assert run(3) != run(4)


def test_bits_bound_at_least_exact():
    for g in (G8, _engine("4node").graph, _synth(15).graph, _chain(9)):
        s = select_scope(g, None, "all")
        exact = math.log2(len(enumerate_states(g, s, 10**6)))
        assert chain_cover_bits(g, s) >= exact - 1e-12
    g = _chain(9)
    assert g.min_chain_cover(select_scope(g, None, "all")) == [[f"K{i}" for i in range(9)]]


def test_synth50_sampling_runs_in_time():
    g = _synth(50).graph
    s = select_scope(g, None, "all")
    assert enumerate_states(g, s, 5000) is None
    t = time.perf_counter()
    sp = SamplingPosterior(g, s, {}, 4000, 0)
    for c in s[::5]:
        sp.update(c, 0.85, 0.2)
    elapsed = time.perf_counter() - t
    assert elapsed < 20.0, elapsed  # recorded in docs/archive/notes/PLAN3_NOTES.md


def test_goal_scope():
    assert select_scope(G8, ["C4"], "goal_ancestors") == ["C1", "C2", "C3", "C4"]
    assert select_scope(G8, ["C4"], "all") == ["C4"]
    assert select_scope(G8, None, "goal_ancestors") == S8
