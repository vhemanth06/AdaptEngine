"""Plan 0 regression pins (P0-TC1, P0-TC2; D59).

population_prior.json was recorded before any Plan 0 change; population_prior_config() must reproduce it
exactly. default.json pins the post-D59 defaults for the "default unchanged" tests of later plans.
Re-record default.json only on a deliberate default change: python scripts/record_pins.py default
"""

import dataclasses
import hashlib
import json
import os

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest  # noqa: E402
from adaptengine.api import Engine  # noqa: E402
from adaptengine.core.config import (  # noqa: E402
    DEFAULT_CONFIG,
    EngineConfig,
    config_hash,
    population_prior_config,
)
from scripts.record_pins import PIN_DIR, compute_pins  # noqa: E402

BASELINE_DEFAULT_HASH = "acaccaeea3a2dd649e043a45cf387f73b0f13e5fcdb2f17b55d3e229f6c28252"


def _load(name):
    with open(os.path.join(PIN_DIR, name), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def population_pins():
    return compute_pins(population_prior_config())


@pytest.fixture(scope="module")
def default_pins():
    return compute_pins(DEFAULT_CONFIG)


# "diag_matrix_S0" and "episode" are no longer computed (old harness removed; rename plan R5)
PARTS = ["diagnostic", "plans", "poc_demo"]


@pytest.mark.parametrize("part", PARTS)
def test_population_prior_config_reproduces_baseline_pins(population_pins, part):
    """P0-TC1: population_prior_config() gives byte-identical baseline outputs."""
    assert population_pins[part] == _load("population_prior.json")[part]


def test_population_prior_config_matches_baseline_config_fields():
    """The pinned baseline config hashes to the baseline default hash, and
    population_prior_config() keeps every baseline field at its baseline value (fields added by
    later plans are opt-in, ground rule 2)."""
    baseline = _load("population_prior.json")["config"]
    assert hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest() == (
        BASELINE_DEFAULT_HASH
    )
    now = json.loads(json.dumps(dataclasses.asdict(population_prior_config())))
    assert {k: now[k] for k in baseline} == baseline
    preset = population_prior_config()
    assert preset.prior_mode == "population" and preset.population_p0 == 0.24


@pytest.mark.parametrize("part", PARTS)
def test_default_config_matches_default_pins(default_pins, part):
    assert default_pins[part] == _load("default.json")[part]


def test_default_differs_from_population_prior_only_in_sweep_prior(default_pins):
    """P0-TC2 (D59): the only field change is prior_mode; outputs with no diagnostic match the
    baseline."""
    d, w = dataclasses.asdict(DEFAULT_CONFIG), dataclasses.asdict(population_prior_config())
    assert {k for k in d if d[k] != w[k]} == {"prior_mode"}
    assert DEFAULT_CONFIG.prior_mode == "flat"
    assert config_hash(DEFAULT_CONFIG) != BASELINE_DEFAULT_HASH
    baseline = _load("population_prior.json")
    for name in ("4node", "8node"):
        assert default_pins["plans"][name]["cold_start"] == baseline["plans"][name]["cold_start"]


def test_default_sweep_starts_untouched_concepts_at_p0():
    """D59: concepts the sweep never probes keep the learner's p0 = 0.20 (not 0.24)."""
    eng = Engine.from_files(
        "data/curriculum/curriculum_4node.json",
        "data/curriculum/activities_4node.json",
        config=dataclasses.replace(DEFAULT_CONFIG, n_max=1),
    )
    r = eng.diagnose(eng.init_learner(), lambda a: True, session_id="t")
    unprobed = [c for c, cr in r.concept_results.items() if cr.n_items == 0]
    assert unprobed and all(r.state.concepts[c].p == 0.20 for c in unprobed)
    assert EngineConfig().p0 == 0.20


def test_plan_without_diagnostic_unchanged():
    """D59 only touches the sweep; a plan from the cold-start state is identical."""
    from adaptengine.core.schema import PlanContext

    plans = []
    for cfg in (DEFAULT_CONFIG, population_prior_config()):
        eng = Engine.from_files(
            "data/curriculum/curriculum_8node.json",
            "data/curriculum/activities_8node.json",
            config=cfg,
        )
        ctx = PlanContext(goal="C8", deadline_day=14, budget=15, current_day=1)
        plans.append(eng.plan(eng.init_learner(), ctx))
    assert plans[0].status == plans[1].status
    assert plans[0].days == plans[1].days
