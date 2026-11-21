"""V2-TC4: identical results apart from timing fields, whatever the worker count."""

import json

import pytest

from experiments.core.results import strip_timing
from experiments.tests.test_runners_smoke import RUNNERS, run_smoke


def _canon(doc):
    return json.dumps(strip_timing(doc), sort_keys=True)


@pytest.mark.parametrize("module", sorted(RUNNERS))
def test_two_runs_identical_and_procs_independent(module, tmp_path):
    a = run_smoke(module, str(tmp_path / "a" / "r.json"), procs=1)
    b = run_smoke(module, str(tmp_path / "b" / "r.json"), procs=4)
    c = run_smoke(module, str(tmp_path / "c" / "r.json"), procs=4)
    assert _canon(a) == _canon(b) == _canon(c)
