from typing import Protocol, runtime_checkable, Mapping
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.errors import ValidationError
from ..core.validators import check_probability, check_transition, check_bool
from .mastery import update_mastery, guess, slip


@runtime_checkable
class MasteryModel(Protocol):
    """Protocol for mastery estimation models."""

    def predict_correct(self, p: float, d: float) -> float:
        """Predict the probability of a correct response on an item of difficulty d."""
        ...

    def update(self, p: float, d: float, correct: bool, transition: float) -> float:
        """Compute posterior mastery after observing response on item of difficulty d."""
        ...


class CustomBKT:
    """Exact oracle wrapping continuous BKT equations."""

    def __init__(self, cfg: EngineConfig = DEFAULT_CONFIG):
        self.cfg = cfg

    def predict_correct(self, p: float, d: float) -> float:
        check_probability(p, "p")
        g = guess(d, self.cfg)
        s = slip(d, self.cfg)
        return p * (1.0 - s) + (1.0 - p) * g

    def update(self, p: float, d: float, correct: bool, transition: float) -> float:
        check_probability(p, "p")
        check_bool(correct, "correct")
        check_transition(transition, "transition")
        return update_mastery(p, d, correct, transition, self.cfg)


def get_difficulty_class(d: float) -> str:
    """Map continuous difficulty d in [d_min, d_max] to 3 discrete item classes (D6):
    - easy: d < 0.35 (representative d=0.20, g=0.24, s=0.10)
    - medium: 0.35 <= d < 0.65 (representative d=0.50, g=0.15, s=0.175)
    - hard: d >= 0.65 (representative d=0.80, g=0.06, s=0.25)
    """
    if d < 0.35:
        return "easy"
    elif d < 0.65:
        return "medium"
    else:
        return "hard"


# D6: Default class parameters derived from representative difficulties
DEFAULT_CLASS_PARAMS: Mapping[str, Mapping[str, float]] = {
    "easy": {"rep_d": 0.20, "guess": 0.240, "slip": 0.100},
    "medium": {"rep_d": 0.50, "guess": 0.150, "slip": 0.175},
    "hard": {"rep_d": 0.80, "guess": 0.060, "slip": 0.250},
}


class PyBKTAdapter:
    """Adapter wrapping pyBKT discrete item classes.

    In accordance with D6:
    - 3 item classes: easy, medium, hard.
    - Parameters derived from continuous heuristics at class-representative difficulties.
    - pyBKT is optionally imported only in this file.
    """

    def __init__(
        self,
        cfg: EngineConfig = DEFAULT_CONFIG,
        class_params: Mapping[str, Mapping[str, float]] = DEFAULT_CLASS_PARAMS,
    ):
        self.cfg = cfg
        self.class_params = class_params
        self._pybkt_model = None

        # Attempt to import pyBKT (third-party dependency imported only here)
        try:
            from pyBKT.models import Model  # type: ignore

            self._pybkt_model = Model
            self._pybkt_available = True
        except (ImportError, Exception):
            self._pybkt_available = False

    @property
    def is_library_available(self) -> bool:
        return self._pybkt_available

    def get_class_params(self, cls_name: str) -> Mapping[str, float]:
        if cls_name not in self.class_params:
            raise ValidationError(f"Unknown difficulty class: {cls_name}")
        return self.class_params[cls_name]

    def predict_correct(self, p: float, d: float) -> float:
        check_probability(p, "p")
        cls_name = get_difficulty_class(d)
        params = self.get_class_params(cls_name)
        g = params["guess"]
        s = params["slip"]
        return p * (1.0 - s) + (1.0 - p) * g

    def update(self, p: float, d: float, correct: bool, transition: float) -> float:
        check_probability(p, "p")
        check_bool(correct, "correct")
        check_transition(transition, "transition")
        cls_name = get_difficulty_class(d)
        params = self.get_class_params(cls_name)
        g = params["guess"]
        s = params["slip"]

        if correct:
            num = p * (1.0 - s)
            den = num + (1.0 - p) * g
        else:
            num = p * s
            den = num + (1.0 - p) * (1.0 - g)

        p_bayes = num / den if den > 0 else 0.0
        return p_bayes + (1.0 - p_bayes) * transition
