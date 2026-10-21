import warnings
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from ..core.config import DEFAULT_CONFIG, EngineConfig
from ..core.errors import ValidationError
from ..core.validators import check_bool, check_difficulty, check_probability, check_transition
from .mastery import guess, slip, update_mastery

_PYBKT_MODEL_CACHE: dict[tuple, Any] = {}


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


def derive_class_params(cfg: EngineConfig = DEFAULT_CONFIG) -> dict[str, dict[str, float]]:
    """Derive discrete item class parameters from continuous heuristics at class-representative difficulties."""
    rep_d = {"easy": 0.20, "medium": 0.50, "hard": 0.80}
    params = {}
    for cname, d in rep_d.items():
        g = cfg.guess_coef * (1.0 - d)
        s = cfg.slip_base + cfg.slip_coef * d
        params[cname] = {"rep_d": d, "guess": g, "slip": s}
    return params


# D6: Default class parameters derived from representative difficulties
DEFAULT_CLASS_PARAMS: Mapping[str, Mapping[str, float]] = derive_class_params(DEFAULT_CONFIG)


def get_difficulty_class(d: float, cfg: EngineConfig = DEFAULT_CONFIG) -> str:
    """Map continuous difficulty d in [d_min, d_max] to 3 discrete item classes (D6):
    - easy: d < 0.35 (representative d=0.20, g=0.24, s=0.10)
    - medium: 0.35 <= d < 0.65 (representative d=0.50, g=0.15, s=0.175)
    - hard: d >= 0.65 (representative d=0.80, g=0.06, s=0.25)
    """
    check_difficulty(d, cfg.d_min, cfg.d_max, "d")
    if d < 0.35:
        return "easy"
    elif d < 0.65:
        return "medium"
    else:
        return "hard"


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
        class_params: Optional[Mapping[str, Mapping[str, float]]] = None,
    ):
        self.cfg = cfg
        self.class_params = class_params if class_params is not None else derive_class_params(cfg)
        self._pybkt_instance = None
        self._pybkt_available = False

        cache_key = (
            float(self.cfg.p0),
            float(self.cfg.t_exercise),
            float(self.cfg.guess_coef),
            float(self.cfg.slip_base),
            float(self.cfg.slip_coef),
        )
        if cache_key in _PYBKT_MODEL_CACHE:
            self._pybkt_instance = _PYBKT_MODEL_CACHE[cache_key]
            self._pybkt_available = self._pybkt_instance is not None
            return

        # Attempt to initialize genuine pyBKT model
        try:
            import numpy as np  # type: ignore
            import pandas as pd  # type: ignore
            from pyBKT.models import Model  # type: ignore

            df = pd.DataFrame(
                [
                    {"user_id": 1, "skill_name": "easy", "correct": 1, "order_id": 1},
                    {"user_id": 1, "skill_name": "medium", "correct": 1, "order_id": 1},
                    {"user_id": 1, "skill_name": "hard", "correct": 1, "order_id": 1},
                ]
            )
            m = Model(seed=42)
            fixed_params = {
                c: {
                    "prior": float(self.cfg.p0),
                    "learns": np.array([float(self.cfg.t_exercise)]),
                    "guesses": np.array([float(self.class_params[c]["guess"])]),
                    "slips": np.array([float(self.class_params[c]["slip"])]),
                    "forgets": np.array([0.0]),
                }
                for c in ("easy", "medium", "hard")
            }
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyBKT.*")
                m.fit(data=df, fixed=fixed_params)
            _PYBKT_MODEL_CACHE[cache_key] = m
            self._pybkt_instance = m
            self._pybkt_available = True
        except (ImportError, Exception):
            _PYBKT_MODEL_CACHE[cache_key] = None
            self._pybkt_instance = None
            self._pybkt_available = False

    @property
    def is_library_available(self) -> bool:
        return self._pybkt_available

    @property
    def pybkt_model(self):
        return self._pybkt_instance

    def get_class_params(self, cls_name: str) -> Mapping[str, float]:
        if cls_name not in self.class_params:
            raise ValidationError(f"Unknown difficulty class: {cls_name}")
        return self.class_params[cls_name]

    def predict_correct(self, p: float, d: float) -> float:
        check_probability(p, "p")
        cls_name = get_difficulty_class(d, self.cfg)
        params = self.get_class_params(cls_name)
        g = params["guess"]
        s = params["slip"]
        return p * (1.0 - s) + (1.0 - p) * g

    def update(self, p: float, d: float, correct: bool, transition: float) -> float:
        check_probability(p, "p")
        check_bool(correct, "correct")
        check_transition(transition, "transition")
        cls_name = get_difficulty_class(d, self.cfg)
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
