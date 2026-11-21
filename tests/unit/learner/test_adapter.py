import pytest
from adaptengine.learner.adapter import (
    MasteryModel,
    CustomBKT,
    PyBKTAdapter,
    get_difficulty_class,
    DEFAULT_CLASS_PARAMS,
)


def test_mastery_model_protocol_adherence():
    """Verify both CustomBKT and PyBKTAdapter adhere to the MasteryModel protocol."""
    custom = CustomBKT()
    adapter = PyBKTAdapter()

    assert isinstance(custom, MasteryModel)
    assert isinstance(adapter, MasteryModel)


def test_custom_bkt_reference_parity():
    """Verify CustomBKT matches all reference values exactly."""
    oracle = CustomBKT()

    # Reference values:
    # (p, d, correct, T, expected p)
    table = [
        (0.50, 0.5, True, 0, 0.8462),
        (0.50, 0.5, False, 0, 0.1707),
        (0.50, 0.5, True, 0.05, 0.8538),
        (0.50, 0.5, False, 0.05, 0.2122),
        (0.90, 0.5, False, 0, 0.6495),
    ]
    for p, d, correct, T, exp in table:
        assert oracle.update(p, d, correct, T) == pytest.approx(exp, abs=1e-4)


def test_difficulty_class_mapping_d6():
    """Verify discrete class mapping boundaries according to D6."""
    assert get_difficulty_class(0.10) == "easy"
    assert get_difficulty_class(0.34) == "easy"
    assert get_difficulty_class(0.35) == "medium"
    assert get_difficulty_class(0.50) == "medium"
    assert get_difficulty_class(0.64) == "medium"
    assert get_difficulty_class(0.65) == "hard"
    assert get_difficulty_class(0.90) == "hard"


def test_adapter_oracle_parity_at_representative_difficulties():
    """Verify PyBKTAdapter equals CustomBKT within 1e-9 at class representative difficulties (D6)."""
    oracle = CustomBKT()
    adapter = PyBKTAdapter()

    rep_diffs = [
        DEFAULT_CLASS_PARAMS["easy"]["rep_d"],  # 0.20
        DEFAULT_CLASS_PARAMS["medium"]["rep_d"],  # 0.50
        DEFAULT_CLASS_PARAMS["hard"]["rep_d"],  # 0.80
    ]

    for d in rep_diffs:
        # Check predict_correct parity
        for p in (0.20, 0.50, 0.85):
            pred_oracle = oracle.predict_correct(p, d)
            pred_adapter = adapter.predict_correct(p, d)
            assert pred_oracle == pytest.approx(pred_adapter, abs=1e-9)

        # Check update parity for both correct and incorrect
        for p in (0.20, 0.50, 0.90):
            for correct in (True, False):
                for T in (0.0, 0.05, 0.20):
                    up_oracle = oracle.update(p, d, correct, T)
                    up_adapter = adapter.update(p, d, correct, T)
                    assert up_oracle == pytest.approx(up_adapter, abs=1e-9)


def test_adapter_response_sequence_with_surprise_response():
    """Test response sequence including surprise wrong answer at high mastery."""
    adapter = PyBKTAdapter()
    p = 0.20
    T = 0.05

    # Easy correct
    p = adapter.update(p, 0.20, True, T)
    assert p > 0.50

    # Medium correct
    p = adapter.update(p, 0.50, True, T)
    assert p > 0.80

    # Hard correct
    p = adapter.update(p, 0.80, True, T)
    assert p > 0.90

    # Surprise: wrong answer on medium item at p = 0.90
    p_surprise = adapter.update(0.90, 0.50, False, 0.0)
    assert p_surprise == pytest.approx(0.6495, abs=1e-4)
