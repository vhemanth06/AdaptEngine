import pytest
from adaptengine.learner.mastery import guess, slip, bayes_update, learn, update_mastery, entropy
from adaptengine.core.errors import ValidationError

def test_guess_slip_table():
    # d, g(d), s(d)
    table = [
        (0.05, 0.285, 0.0625),
        (0.20, 0.240, 0.1000),
        (0.40, 0.180, 0.1500),
        (0.50, 0.150, 0.1750),
        (0.60, 0.120, 0.2000),
        (0.80, 0.060, 0.2500),
        (0.95, 0.015, 0.2875),
    ]
    for d, ex_g, ex_s in table:
        assert guess(d) == pytest.approx(ex_g, abs=1e-4)
        assert slip(d) == pytest.approx(ex_s, abs=1e-4)

# TC4.1: A learner gives an incorrect response on a low-mastery concept. The mastery estimate updates downward according to the response model.
def test_update_values():
    # p, d, correct, T, expected p
    table = [
        (0.50, 0.5, True, 0, 0.8462),
        (0.50, 0.5, False, 0, 0.1707),
        (0.50, 0.5, True, 0.05, 0.8538),
        (0.50, 0.5, False, 0.05, 0.2122),
        (0.90, 0.5, False, 0, 0.6495),
    ]
    for p, d, correct, T, exp in table:
        assert update_mastery(p, d, correct, T) == pytest.approx(exp, abs=1e-4)
        
def test_lesson_transition():
    # 0.20 -> lesson -> 0.36
    assert learn(0.20, 0.20) == pytest.approx(0.3600, abs=1e-4)

def test_entropy_values():
    assert entropy(0.5) == pytest.approx(1.0, abs=1e-4)
    assert entropy(0.2) == pytest.approx(0.7219, abs=1e-4)
    assert entropy(0.9) == pytest.approx(0.4690, abs=1e-4)
    assert entropy(0.6495) == pytest.approx(0.9345, abs=1e-4)
    assert entropy(0) == 0.0
    assert entropy(1) == 0.0

def test_uncertainty_can_increase():
    h_before = entropy(0.9)
    p_after = update_mastery(0.9, 0.5, False, 0)
    h_after = entropy(p_after)
    assert h_before == pytest.approx(0.4690, abs=1e-4)
    assert h_after == pytest.approx(0.9345, abs=1e-4)
    assert h_after > h_before

def test_bounds_validation():
    with pytest.raises(ValidationError):
        guess(0.01)
    with pytest.raises(ValidationError):
        guess(0.96)
    with pytest.raises(ValidationError):
        entropy(-0.1)
    with pytest.raises(ValidationError):
        entropy(1.1)

def test_smoke_sequence():
    p = 0.20
    T = 0.05
    steps = [
        (0.4, True, 0.5643, 0.9880),
        (0.6, True, 0.9014, 0.4645),
        (0.6, False, 0.6913, 0.8916),
        (0.4, True, 0.9179, 0.4094),
        (0.6, True, 0.9874, 0.0974),
        (0.8, True, 0.9990, 0.0111),
    ]
    for d, correct, exp_p, exp_h in steps:
        p = update_mastery(p, d, correct, T)
        h = entropy(p)
        assert p == pytest.approx(exp_p, abs=1e-3)
        assert h == pytest.approx(exp_h, abs=1e-3)

def test_correct_hard_raises_more():
    p = 0.5
    T = 0.05
    p_easy = update_mastery(p, 0.2, True, T)
    p_hard = update_mastery(p, 0.8, True, T)
    assert p_hard > p_easy
