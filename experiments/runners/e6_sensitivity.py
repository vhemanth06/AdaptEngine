"""E6 — Sensitivity (report 5.6). Descriptive: no hypotheses.

How much do the results depend on the hand-set numbers, and on the simulator?
Configurations of the adapt arm: one-at-a-time scans (theta, k, half_life_days, p0, t_lesson,
recall_threshold, remediation_threshold), the theta x k factorial, and the mastery rules; static
runs once per cell. Worlds S0, S1 x 4-node, 8-node, 8node_x10 x budget 15 x calm, N = 200; each
cell's horizon is fixed from DEFAULT_CONFIG. Exploratory real-data world: S4-assist09 x 4-node and
8node_x10 x budget 15 x calm and missed_day, arms adapt, no_replan, static.

    python -m experiments.runners.e6_sensitivity [--smoke] [--procs N] [--out PATH]
"""

from __future__ import annotations

from ..core import curricula as C
from ..core.arms import E6_REAL_ARMS, STATIC, e6_configs
from ..core.episode import first_plan, run_episode
from ..core.parallel import pmap
from ..core.scenarios import make_scenario
from . import common

EXP, NAME = "E6", "E6_sensitivity"
WORLDS = ("S0", "S1")
CURRICULA = ("4-node", "8-node", "8node_x10")
REAL = {
    "world": "S4-assist09",
    "curricula": ("4-node", "8node_x10"),
    "scenarios": ("calm", "missed_day"),
}
BUDGET = 15


def run_unit(unit) -> dict:
    world, cur, scen, label, seeds, part = unit
    base = C.engine(cur)
    sc = make_scenario(scen, base, C.goal_of(base), BUDGET)  # horizon from DEFAULT_CONFIG
    arm = (
        STATIC
        if label == "static"
        else (E6_REAL_ARMS[label] if part == "real" else e6_configs()[label])
    )
    e = C.engine(cur, arm.config())
    fp = first_plan(e, e.init_learner(), sc) if arm.mode != "static" else None
    entry = common.arm_entry([run_episode(e, s, sc, arm, world, first=fp) for s in seeds])
    entry["metrics"].pop("attempt_histogram")
    entry["config"] = arm.describe()
    return entry


def main(argv=None) -> dict:
    args = common.parse(EXP, argv)
    run, out = common.start(EXP, NAME, args)
    seeds = common.SMOKE_EPISODE_SEEDS if args.smoke else common.EPISODE_SEEDS
    labels = (
        ["baseline", "theta=0.85", "criterion=n_consecutive_2"]
        if args.smoke
        else list(e6_configs())
    )
    worlds, curricula = (("S1",), ("4-node",)) if args.smoke else (WORLDS, CURRICULA)
    units = [
        (w, c, "calm", lab, seeds, "scan")
        for w in worlds
        for c in curricula
        for lab in labels + ["static"]
    ]
    rcur = ("4-node",) if args.smoke else REAL["curricula"]
    units += [
        (REAL["world"], c, s, a, seeds, "real")
        for c in rcur
        for s in REAL["scenarios"]
        for a in E6_REAL_ARMS
    ]
    entries = pmap(run_unit, units, args.procs)
    cells: dict = {}
    for u, entry in zip(units, entries):
        w, c, s, lab, _, part = u
        cell = cells.setdefault(
            (part, w, c, s),
            {
                "key": {"part": part, "world": w, "curriculum": c, "scenario": s, "budget": BUDGET},
                "arms": {},
            },
        )
        cell["arms"][lab] = entry
    for (part, w, c, s), cell in cells.items():
        base = C.engine(c)
        cell["key"]["deadline"] = make_scenario(s, base, C.goal_of(base), BUDGET).deadline
        arms = cell["arms"]
        if part == "scan":
            cell["contrasts"] = {
                f"{lab}_minus_static": common.contrast(arms[lab], arms["static"])
                for lab in arms
                if lab != "static"
            }
            cell["contrasts"].update(
                {
                    f"{lab}_minus_baseline": common.contrast(arms[lab], arms["baseline"])
                    for lab in arms
                    if lab not in ("static", "baseline")
                }
            )
        else:
            cell["contrasts"] = {
                "adapt_minus_static": common.contrast(arms["adapt"], arms["static"]),
                "adapt_minus_no_replan": common.contrast(arms["adapt"], arms["no_replan"]),
            }
    design = {
        "question": "How much do the results depend on the hand-set numbers, and on the simulator?",
        "configurations": {k: a.describe() for k, a in e6_configs().items()},
        "static_reference": "once per cell",
        "worlds": list(WORLDS),
        "curricula": list(CURRICULA),
        "budget": BUDGET,
        "scenario": "calm",
        "horizon": "fixed per cell from DEFAULT_CONFIG",
        "real_data_world": {
            "label": "exploratory",
            **{k: (list(v) if isinstance(v, tuple) else v) for k, v in REAL.items()},
            "arms": {n: a.describe() for n, a in E6_REAL_ARMS.items()},
        },
        "robustness": "across worlds and stress scenarios: from E1 (no extra runs)",
        "seeds": {"episodes": [1000, 1199]} if not args.smoke else {"episodes": list(seeds)},
    }
    return common.finish(
        run,
        out,
        design=design,
        content_review={c: C.content_review(c) for c in CURRICULA},
        cells=list(cells.values()),
        hypotheses={
            "descriptive": {
                "held": None,
                "evidence": "E6 is descriptive; no hypotheses were registered",
            }
        },
    )


if __name__ == "__main__":
    main()
