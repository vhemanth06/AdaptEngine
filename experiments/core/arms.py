"""Arms: a named set of EngineConfig overrides plus a harness mode (D99: everything else is
DEFAULT_CONFIG). Modes: "closed" (replan at the start of each day and after every wrong answer),
"no_replan" (first plan only), "static" (no engine; fixed topological sequence).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from adaptengine.core.config import DEFAULT_CONFIG, EngineConfig, bisection_config

ASSIST09 = "config/fitted_assist09.json"
FITTED_CT = "config/fitted_ct.json"
MODES = ("closed", "no_replan", "static")


@dataclass(frozen=True)
class Arm:
    name: str
    overrides: dict = field(default_factory=dict, hash=False, compare=False)
    mode: str = "closed"
    bisection: bool = False  # start from bisection_config() instead of DEFAULT_CONFIG
    no_review: bool = False  # review urgency 0 for every concept
    diagnose: bool = False  # run the engine's diagnostic first (goal and its ancestors, D54)

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"unknown mode {self.mode!r}")

    def config(self) -> EngineConfig:
        base = bisection_config() if self.bisection else DEFAULT_CONFIG
        return replace(base, **self.overrides)

    def describe(self) -> dict:
        return {
            "base": "bisection_config()" if self.bisection else "DEFAULT_CONFIG",
            "overrides": dict(self.overrides),
            "mode": self.mode,
            "no_review": self.no_review,
            "diagnose": self.diagnose,
        }


def table(arms) -> dict:
    return {a.name: a for a in arms}


# E1: no diagnostic; learners start at the engine's prior p0
E1_ARMS = table(
    [
        Arm("adapt"),
        Arm("no_review", no_review=True),
        Arm("no_replan", mode="no_replan"),
        Arm("static", mode="static"),
    ]
)
E1_H7_ARMS = table(
    [
        Arm("adapt_h7", {"half_life_days": 7.0}),
        Arm("no_review_h7", {"half_life_days": 7.0}, no_review=True),
    ]
)

# E2: diagnostic arms (prior_only, fixed@n and the IRT-CATs are harness-side, see diagnostics.py)
E2_ENGINE_ARMS = table([Arm("sweep"), Arm("bisection", bisection=True)])

# E3 Part B: item-model profiles with the sweep diagnostic
E3_PROFILES = {"heuristic": "heuristic", "fitted_assist09": ASSIST09, "fitted_ct": FITTED_CT}
E3_ARMS = table(Arm(k, {"model_profile": v}) for k, v in E3_PROFILES.items())

# E4: the diagnostic runs first; each with heuristic and fitted_assist09 item models
_E4 = []
for _suffix, _prof in (("", {}), ("_fitted", {"model_profile": ASSIST09})):
    _E4 += [
        Arm("sweep" + _suffix, dict(_prof), diagnose=True),
        Arm(
            "bisect_noconfirm" + _suffix,
            {"confirm_diag_confident": False, **_prof},
            bisection=True,
            diagnose=True,
        ),
        Arm("bisect_confirm" + _suffix, dict(_prof), bisection=True, diagnose=True),
    ]
E4_ARMS = table(_E4)

# E5: planners, closed loop, no diagnostic; plus each planner with bisection_config()
PLANNERS = ("greedy", "hybrid", "cpsat")
E5_ARMS = table(Arm(p, {"planner_method": p}) for p in PLANNERS)
E5_CONFIRM_ARMS = table(
    Arm(f"{p}_bisect_confirm", {"planner_method": p}, bisection=True, diagnose=True)
    for p in PLANNERS
)

# E6: sensitivity configurations of the adapt arm
E6_SCANS = {
    "theta": (0.70, 0.75, 0.80, 0.85, 0.90, 0.95),
    "k_responses": (1, 2, 3, 4),
    "half_life_days": (7.0, 14.0, 30.0, 60.0),
    "p0": (0.10, 0.20, 0.30, 0.40),
    "t_lesson": (0.10, 0.20, 0.30),
    "recall_threshold": (0.70, 0.80, 0.90),
    "remediation_threshold": (0.30, 0.40, 0.50),
}
E6_FACTORIAL = [(t, k) for t in (0.75, 0.85, 0.95) for k in (1, 2, 3)]
E6_CRITERIA = {
    "bkt_threshold": {"mastery_criterion": "bkt_threshold"},
    "n_consecutive_2": {"mastery_criterion": "n_consecutive", "n_consecutive": 2},
    "n_consecutive_3": {"mastery_criterion": "n_consecutive", "n_consecutive": 3},
    "two_threshold": {"mastery_criterion": "two_threshold"},
}


def e6_configs() -> dict:
    """label -> Arm (closed loop) for every sensitivity configuration, baseline first."""
    out = {"baseline": Arm("baseline")}
    for name, values in E6_SCANS.items():
        for v in values:
            out[f"{name}={v}"] = Arm(f"{name}={v}", {name: v})
    for t, k in E6_FACTORIAL:
        out[f"theta={t}|k={k}"] = Arm(f"theta={t}|k={k}", {"theta": t, "k_responses": k})
    for name, kw in E6_CRITERIA.items():
        out[f"criterion={name}"] = Arm(f"criterion={name}", dict(kw))
    return out


STATIC = Arm("static", mode="static")
E6_REAL_ARMS = table([Arm("adapt"), Arm("no_replan", mode="no_replan"), STATIC])
