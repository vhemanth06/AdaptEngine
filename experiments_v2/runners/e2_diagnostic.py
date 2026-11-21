"""E2 — Diagnostic accuracy (report 5.2).

How well does each diagnostic estimate what the learner knows, and at what question cost?
Arms: prior_only, sweep (DEFAULT_CONFIG), bisection (bisection_config()), fixed@n,
irt_cat_global@n, irt_cat_per_concept@n (n = bisection's count for the same learner).
Worlds S0, S2, S4 x 4-node, 8-node, 8node_x10, synth-20, synth-50; all concepts in scope (no
goal); heuristic item model; N = 250 (odd seeds 101-599). Scripted learners (advanced,
advanced_minus_goal, mid, novice) for sweep and bisection on 4-node, 8-node, 8node_x10, N = 100.

    python -m experiments_v2.runners.e2_diagnostic [--smoke] [--procs N] [--out PATH]
"""

from __future__ import annotations

from adaptengine.core.config import bisection_config

from ..core import curricula as C
from ..core import diagnostics as D
from ..core import metrics as M
from ..core.parallel import pmap
from . import common

EXP, NAME = "E2", "E2_diagnostic"
WORLDS = ("S0", "S2", "S4")
CURRICULA = ("4-node", "8-node", "8node_x10", "synth-20", "synth-50")
SCRIPTED_CURRICULA = ("4-node", "8-node", "8node_x10")
ARMS = ("prior_only", "sweep", "bisection", "fixed@n", "irt_cat_global@n", "irt_cat_per_concept@n")


def summarise(rows: list, with_probe: bool = True) -> dict:
    pairs = [p for r in rows for p in r["pairs"]]
    conf = sum(r["confirmed"] for r in rows)
    dconf = sum(r["confident"] for r in rows)
    m = {
        "brier": M.mean([r["brier"] for r in rows]),
        "log_loss": M.log_loss(pairs),
        "auc": M.auc(pairs),
        "questions": M.mean([r["items"] for r in rows]),
        "reliability": M.reliability_bins(pairs),
        "confirmed": conf,
        "false_confirm_rate": round(sum(r["false_confirm"] for r in rows) / conf, 4)
        if conf
        else None,
        "diag_confident": dconf,
        "false_confident_rate": round(sum(r["false_confident"] for r in rows) / dconf, 4)
        if dconf
        else None,
    }
    if with_probe:
        probe = [p for r in rows for p in r["probe"]]
        m["next_answer_brier"] = M.mean([r["next_brier"] for r in rows])
        m["next_answer"] = M.score_all(probe)
    return m


def entry(rows, seeds, with_probe=True) -> dict:
    pl = {
        "seed": list(seeds),
        "brier": [r["brier"] for r in rows],
        "questions": [r["items"] for r in rows],
    }
    if with_probe:
        pl["next_brier"] = [r["next_brier"] for r in rows]
    return {"n": len(rows), "metrics": summarise(rows, with_probe), "per_learner": pl}


def pair(a, b, keys=("brier", "questions")) -> dict:
    return {k: M.paired(a["per_learner"][k], b["per_learner"][k]) for k in keys}


def world_cell(unit) -> dict:
    world, cur, seeds = unit
    engines = {"sweep": C.engine(cur), "bisection": C.engine(cur, bisection_config())}
    base = C.engine(cur)
    per = {a: [] for a in ARMS}
    for s in seeds:
        for arm, r in D.simulated_arms(engines, base, s, world).items():
            per[arm].append(r)
    arms = {a: entry(per[a], seeds) for a in ARMS}
    contrasts = {f"{a}_minus_prior_only": pair(arms[a], arms["prior_only"]) for a in ARMS[1:]}
    contrasts["bisection_minus_sweep"] = pair(
        arms["bisection"], arms["sweep"], ("brier", "questions", "next_brier")
    )
    return {
        "key": {"part": "simulated", "world": world, "curriculum": cur},
        "arms": arms,
        "contrasts": contrasts,
    }


def scripted_cell(unit) -> dict:
    cur, profile, seeds = unit
    engines = {"sweep": C.engine(cur), "bisection": C.engine(cur, bisection_config())}
    arms = {}
    for name, e in engines.items():
        rows = [D.run_scripted(e, s, profile, C.goal_of(e)) for s in seeds]
        arms[name] = entry(rows, seeds, with_probe=False)
    return {
        "key": {"part": "scripted", "curriculum": cur, "profile": profile},
        "arms": arms,
        "contrasts": {"bisection_minus_sweep": pair(arms["bisection"], arms["sweep"])},
    }


def _ci(c):
    return f"{c['diff']:+.4f} [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]"


def hypotheses(cells: list) -> dict:
    h1 = [
        c
        for c in cells
        if c["key"]["part"] == "scripted"
        and c["key"]["profile"] in ("advanced", "advanced_minus_goal")
    ]
    sim = [c for c in cells if c["key"]["part"] == "simulated"]

    def lab(c):
        k = c["key"]
        return "|".join(str(k[x]) for x in ("world", "curriculum", "profile") if x in k)

    beats = {
        a: sum(c["contrasts"][f"{a}_minus_prior_only"]["brier"]["ci95"][1] < 0 for c in sim)
        for a in ARMS[1:]
    }
    return {
        "H1": {
            "held": bool(h1)
            and all(c["contrasts"]["bisection_minus_sweep"]["brier"]["ci95"][1] < 0 for c in h1),
            "evidence": "; ".join(
                f"{lab(c)} bisection-sweep Brier {_ci(c['contrasts']['bisection_minus_sweep']['brier'])}"
                for c in h1
            ),
            "rule": "paired Brier difference with 95% CI entirely below 0 in every advanced and advanced_minus_goal cell",
        },
        "H2": {
            "held": None,
            "evidence": "descriptive (no direction predicted): bisection-sweep questions and Brier per simulated cell are in the cells' contrasts",
        },
        "H3": {
            "held": True,
            "evidence": f"every arm reported against prior_only in {len(sim)} simulated cells; cells where the arm's Brier is lower (CI below 0): "
            + ", ".join(f"{a} {n}/{len(sim)}" for a, n in beats.items()),
        },
    }


def main(argv=None) -> dict:
    args = common.parse(EXP, argv)
    run, out = common.start(EXP, NAME, args)
    for c in CURRICULA:
        C.paths(c)
    if args.smoke:
        units = [("S0", "4-node", common.SMOKE_DIAG_SEEDS)]
        sunits = [("4-node", p, common.SMOKE_DIAG_SEEDS) for p in ("advanced", "novice")]
    else:
        units = [(w, c, common.DIAG_SEEDS) for w in WORLDS for c in CURRICULA]
        sunits = [(c, p, common.SCRIPTED_SEEDS) for c in SCRIPTED_CURRICULA for p in D.SCRIPTED]
    tagged = [("w", u) for u in units] + [("s", u) for u in sunits]
    cells = pmap(_dispatch, tagged, args.procs)
    design = {
        "question": "How well does each diagnostic estimate what the learner knows, and at what question cost?",
        "arms": {
            "prior_only": "no questions; p = p0",
            "sweep": "DEFAULT_CONFIG, Engine.diagnose(goal_concepts=None)",
            "bisection": "bisection_config() at its defaults, Engine.diagnose(goal_concepts=None)",
            "fixed@n": "round-robin over concepts at bisection's question count for the learner",
            "irt_cat_global@n": "2PL CAT (a = 3), one ability, max Fisher information, EAP on 201 points",
            "irt_cat_per_concept@n": "the same with one ability per concept",
        },
        "worlds": list(WORLDS),
        "curricula": list(CURRICULA),
        "scripted": {
            "curricula": list(SCRIPTED_CURRICULA),
            "profiles": list(D.SCRIPTED),
            "arms": ["sweep", "bisection"],
        },
        "truth": "1[theta >= 0.70] at diagnostic time; scripted: the scripted known set",
        "item_model": "heuristic",
        "seeds": {"diagnostic": [101, 599, "odd"], "scripted": [101, 299, "odd"]}
        if not args.smoke
        else {"diagnostic": list(common.SMOKE_DIAG_SEEDS)},
    }
    return common.finish(
        run,
        out,
        design=design,
        content_review={c: C.content_review(c) for c in CURRICULA},
        cells=cells,
        hypotheses=hypotheses(cells),
    )


def _dispatch(tagged):
    kind, unit = tagged
    return world_cell(unit) if kind == "w" else scripted_cell(unit)


if __name__ == "__main__":
    main()
