"""W8 B.2/O.3: the lesson-aware BKT EM recovers parameters from data it generated."""

import os
import random
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from experiments.bkt_lessons import fit, flags  # noqa: E402

TRUE = {
    "prior": 0.2,
    "t_lesson": 0.3,
    "t_exercise": 0.08,
    "guess": (0.4, 0.25, 0.1),
    "slip": (0.05, 0.1, 0.2),
}


def simulate(n=1500, seed=0, forget=0.0):
    r = random.Random(seed)
    seqs = []
    for _ in range(n):
        known = r.random() < TRUE["prior"]
        s = []
        lesson_at = r.randrange(6)  # lessons at varying positions identify T_lesson
        for step in range(14):
            if step == lesson_at:
                s.append((1, 0, 0))
                lesson = True
            else:
                k = step % 3
                p = 1 - TRUE["slip"][k] if known else TRUE["guess"][k]
                s.append((0, k, int(r.random() < p)))
                lesson = False
            t = TRUE["t_lesson"] if lesson else TRUE["t_exercise"]
            if known:
                known = r.random() >= forget
            else:
                known = r.random() < t
        seqs.append(s)
    return seqs


def test_em_recovers_lesson_and_exercise_transitions():
    f = fit(simulate(), num_fits=3)
    assert abs(f["prior"] - 0.2) < 0.06
    assert abs(f["t_lesson"] - 0.3) < 0.08 and abs(f["t_exercise"] - 0.08) < 0.04
    for i, c in enumerate(("easy", "medium", "hard")):
        assert abs(f["guess"][c] - TRUE["guess"][i]) < 0.06
        assert abs(f["slip"][c] - TRUE["slip"][i]) < 0.06
    assert flags(f) == {}


def test_em_with_forgets_finds_forgetting():
    f = fit(simulate(n=1500, seed=1, forget=0.1), forgets=True, num_fits=3)
    assert 0.04 < f["forget"] < 0.2
    assert fit(simulate(n=800, seed=2), forgets=True, num_fits=2)["forget"] < 0.05
