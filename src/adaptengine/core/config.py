import json
import hashlib
from dataclasses import dataclass, asdict
from . import constants


@dataclass(frozen=True)
class EngineConfig:
    p0: float = constants.P0
    theta: float = constants.THETA
    t_diag: float = constants.T_DIAG
    t_exercise: float = constants.T_EXERCISE
    t_lesson: float = constants.T_LESSON
    guess_coef: float = constants.GUESS_COEF
    slip_base: float = constants.SLIP_BASE
    slip_coef: float = constants.SLIP_COEF
    d_min: float = constants.D_MIN
    d_max: float = constants.D_MAX


DEFAULT_CONFIG = EngineConfig()


def config_hash(cfg: EngineConfig) -> str:
    cfg_json = json.dumps(asdict(cfg), sort_keys=True)
    return hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
