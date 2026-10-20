from typing import Sequence, Optional
from ..core.config import EngineConfig, DEFAULT_CONFIG
from ..core.errors import ValidationError, DifficultyError
from ..core.schema import Activity, ActivityType
from ..core.validators import check_probability
from ..learner.adapter import MasteryModel, CustomBKT


def select_exercise(
    exercises: Sequence[Activity],
    p: float,
    target_success: Optional[float] = None,
    model: Optional[MasteryModel] = None,
    cfg: EngineConfig = DEFAULT_CONFIG,
) -> Activity:
    """Select next exercise nearest to target success probability (M4, TC4.2).

    Tie-breaking rule (D10):
    1. Minimize |P_c - target_success| (rounded to 9 decimals)
    2. Minimize |d - 0.50| (rounded to 9 decimals)
    3. Lexicographic activity_id
    """
    if not exercises:
        raise ValidationError("No candidate exercises provided")

    check_probability(p, "p")
    target = target_success if target_success is not None else cfg.target_success
    check_probability(target, "target_success")

    if model is None:
        model = CustomBKT(cfg)

    def sort_key(act: Activity) -> tuple[float, float, str]:
        if act.type != ActivityType.EXERCISE or act.difficulty is None:
            raise DifficultyError(
                f"Candidate activity {act.activity_id} is not an EXERCISE with difficulty"
            )
        pc = model.predict_correct(p, act.difficulty)
        dist = round(abs(pc - target), 9)
        d_dist = round(abs(act.difficulty - 0.50), 9)
        return (dist, d_dist, act.activity_id)

    return min(exercises, key=sort_key)
