"""E4 — The new features end to end (report 5.4).

Does bisection with confirmation checks reach the goal as often as the sweep, in fewer total
minutes, safely? How much do the diagnostic and the item model each contribute?
Arms (the diagnostic runs first on the goal and its ancestors, D54): sweep, bisect_noconfirm,
bisect_confirm, each with model_profile heuristic and fitted_assist09. Worlds S0-S4 and
S4-assist09 x 4-node, 8-node, 8node_x10, synth-20, synth-20-x10 x budget 15 x calm, N = 200.
Each cell's horizon is fixed from DEFAULT_CONFIG so every arm has the same deadline.

    python -m experiments.runners.e4_features [--smoke] [--procs N] [--out PATH]
"""

from __future__ import annotations

from ..core import curricula as C
from ..core import metrics as M
from ..core.arms import E4_ARMS
from ..core.episode import run_episode
from ..core.parallel import pmap
from ..core.scenarios import make_scenario
from ..core.simulator import ALL_WORLDS
from . import common

EXP, NAME = "E4", "E4_features"
CURRICULA = ("4-node", "8-node", "8node_x10", "synth-20", "synth-20-x10")
BUDGET, SCENARIO = 15, "calm"
KEYS = ("goal_mastered", "all_required", "total_minutes")
PAIRS = (
    ("bisect_confirm", "sweep"),
    ("bisect_noconfirm", "sweep"),
    ("bisect_confirm", "bisect_noconfirm"),
    ("bisect_confirm_fitted", "sweep_fitted"),
    ("sweep_fitted", "sweep"),
    ("bisect_confirm_fitted", "bisect_confirm"),
)


def run_cell(unit) -> dict:
    world, cur, seeds = unit
    base = C.engine(cur)
    sc = make_scenario(SCENARIO, base, C.goal_of(base), BUDGET)
    arms = {}
    for name, arm in E4_ARMS.items():
        e = C.engine(cur, arm.config())
        arms[name] = common.arm_entry([run_episode(e, s, sc, arm, world) for s in seeds])
    con = {f"{a}_minus_{b}": common.contrast(arms[a], arms[b], KEYS) for a, b in PAIRS}
    pl = {n: a["per_learner"] for n, a in arms.items()}
    two = {}
    for k in KEYS:
        sh, sf = pl["sweep"][k], pl["sweep_fitted"][k]
        bh, bf = pl["bisect_confirm"][k], pl["bisect_confirm_fitted"][k]
        two[k] = {
            "main_diagnostic": M.paired(
                [(a + b) / 2 for a, b in zip(bh, bf)], [(a + b) / 2 for a, b in zip(sh, sf)]
            ),
            "main_item_model": M.paired(
                [(a + b) / 2 for a, b in zip(sf, bf)], [(a + b) / 2 for a, b in zip(sh, bh)]
            ),
            "interaction": M.paired(
                [b - a for a, b in zip(sf, bf)], [b - a for a, b in zip(sh, bh)]
            ),
        }
    con["two_by_two"] = two
    key = {
        "world": world,
        "curriculum": cur,
        "budget": BUDGET,
        "scenario": SCENARIO,
        "deadline": sc.deadline,
    }
    return {"key": key, "arms": arms, "contrasts": con}


def _ci(c):
    return f"{c['diff']:+.4f} [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]"


def hypotheses(cells: list) -> dict:
    ex = sum(a["metrics"]["executed_prereq_violations"] for c in cells for a in c["arms"].values())
    h2 = [
        c
        for c in cells
        if c["key"]["world"] == "S0" and c["key"]["curriculum"] in ("8-node", "8node_x10")
    ]

    def h2_ok(c):
        d = c["contrasts"]["bisect_confirm_minus_sweep"]
        return d["total_minutes"]["ci95"][1] < 0 and d["goal_mastered"]["ci95"][0] >= -0.05

    h3, bad3 = 0, []
    for c in cells:
        if c["key"]["world"] in ("S0", "S1", "S2", "S3"):
            for a in ("bisect_confirm", "bisect_confirm_fitted"):
                r = c["arms"][a]["metrics"]["confirmation_false_pass_rate"]
                if r is not None:
                    h3 += 1
                    if r > 0.10:
                        bad3.append(f"{c['key']['world']}|{c['key']['curriculum']}|{a} {r}")
    return {
        "H1": {
            "held": ex == 0,
            "evidence": f"executed violations, all arms, {len(cells)} cells: {ex}",
        },
        "H2": {
            "held": bool(h2) and all(h2_ok(c) for c in h2),
            "evidence": "; ".join(
                f"{c['key']['curriculum']}: total minutes {_ci(c['contrasts']['bisect_confirm_minus_sweep']['total_minutes'])}, "
                f"goal mastery {_ci(c['contrasts']['bisect_confirm_minus_sweep']['goal_mastered'])}"
                for c in h2
            ),
            "rule": "S0, 8-node and 8node_x10: total-minutes CI entirely below 0 and goal-mastery CI lower bound >= -0.05",
        },
        "H3": {
            "held": not bad3,
            "evidence": f"{h3} (cell, confirm arm) rates in S0-S3; above 0.10: "
            + (", ".join(bad3) or "none"),
            "rule": "confirmation false-pass rate <= 0.10 for bisect_confirm and bisect_confirm_fitted in every S0-S3 cell with confirmations",
        },
        "2x2": {
            "held": None,
            "evidence": "descriptive (no direction predicted); see contrasts.two_by_two",
        },
    }


def bisection_losses(cells: list) -> list:
    """Cells where bisect_confirm loses to sweep on a primary metric; explained in NOTES.md."""
    out = []
    for c in cells:
        d = c["contrasts"]["bisect_confirm_minus_sweep"]
        lost = [k for k in ("goal_mastered", "all_required") if d[k]["ci95"][1] < 0]
        if d["total_minutes"]["ci95"][0] > 0:
            lost.append("total_minutes")
        if lost:
            out.append(
                {
                    "world": c["key"]["world"],
                    "curriculum": c["key"]["curriculum"],
                    "lost_on": lost,
                    **{k: d[k] for k in KEYS},
                }
            )
    return out


def main(argv=None) -> dict:
    args = common.parse(EXP, argv)
    run, out = common.start(EXP, NAME, args)
    for c in CURRICULA:
        C.paths(c)
    if args.smoke:
        units = [("S0", "8-node", common.SMOKE_EPISODE_SEEDS)]
    else:
        units = [(w, c, common.EPISODE_SEEDS) for w in ALL_WORLDS for c in CURRICULA]
    cells = pmap(run_cell, units, args.procs)
    for c in cells:
        for a in c["arms"].values():
            a["metrics"].pop("attempt_histogram")
    design = {
        "question": "Does bisection with confirmation reach the goal as often as the sweep, in fewer total minutes, safely?",
        "arms": {n: a.describe() for n, a in E4_ARMS.items()},
        "worlds": list(ALL_WORLDS),
        "curricula": list(CURRICULA),
        "budget": BUDGET,
        "scenario": SCENARIO,
        "total_minutes": "diagnostic minutes + executed study minutes",
        "horizon": "fixed per cell from DEFAULT_CONFIG",
        "seeds": {"episodes": [1000, 1199]}
        if not args.smoke
        else {"episodes": list(common.SMOKE_EPISODE_SEEDS)},
    }
    return common.finish(
        run,
        out,
        design=design,
        content_review={c: C.content_review(c) for c in CURRICULA},
        cells=cells,
        hypotheses=hypotheses(cells),
        bisection_losses=bisection_losses(cells),
    )


if __name__ == "__main__":
    main()
