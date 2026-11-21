"""E3 — Calibration of the item model (report 5.3).

Part A, real students: ASSISTments 2009 skill-builder and Cognitive Tutor (data/external/,
verified against CHECKSUMS). Models: heuristic D6 class, fitted class profile, fitted per-skill
BKT; 5-fold CV by student; held-out RMSE, Brier, log-loss, AUC, ECE and reliability bins. The
configs in config/ are not rewritten. A missing or changed file -> "not run: data missing".
Part B, simulated learners: model_profile heuristic, fitted_assist09, fitted_ct with the sweep;
worlds S0-S4 and S4-assist09 x 4-node, 8-node, 8node_x10, synth-20; N = 250 (odd 101-599).

    python -m experiments.runners.e3_calibration [--smoke] [--procs N] [--out PATH]
"""

from __future__ import annotations

from ..core import curricula as C
from ..core import diagnostics as D
from ..core import metrics as M
from ..core import realdata as R
from ..core.arms import E3_ARMS
from ..core.parallel import pmap
from ..core.simulator import ALL_WORLDS, make_learner
from . import common

EXP, NAME = "E3", "E3_calibration"
CURRICULA = ("4-node", "8-node", "8node_x10", "synth-20")
FITTED = ("fitted_assist09", "fitted_ct")


def part_a(name: str, procs: int) -> dict:
    ck = R.checksums(R.DATASETS[name])
    if not all(v.get("matches_CHECKSUMS") for v in ck.values()):
        return {"status": "not run: data missing", "checksums": ck}
    df, steps, dfn = R.load(name)
    d_full = R.assist_difficulty() if name == "assist09" else R.item_difficulty(df)
    cls = R.classify(df.item.map(d_full))
    fit = R.fit_classes(df, cls)
    cv = R.crossvalidate(df, dfn, procs=procs)
    return {
        "status": "run",
        "checksums": ck,
        "cleaning": steps,
        "answers_per_class": {k: int((cls == k).sum()) for k in R.CLASSES},
        "class_fit_full_data": fit,
        "heldout": cv,
    }


def part_b_cell(unit) -> dict:
    world, cur, seeds = unit
    arms, rows = {}, {}
    for name, arm in E3_ARMS.items():
        e = C.engine(cur, arm.config())
        rs = []
        for s in seeds:
            st, k, _ = D.run_engine_diagnostic(e, D.sim_answer(make_learner(e, s, world)), s)
            truth = {c: v >= 0.70 for c, v in make_learner(e, s, world).initial.items()}
            rs.append(D.score(e, st, truth, k, make_learner(e, s, world)))
        rows[name] = rs
        probe = [p for r in rs for p in r["probe"]]
        pairs = [p for r in rs for p in r["pairs"]]
        arms[name] = {
            "n": len(rs),
            "metrics": {
                "next_answer": M.score_all(probe),
                "next_answer_reliability": M.reliability_bins(probe),
                "diag_brier": M.mean([r["brier"] for r in rs]),
                "diag_auc": M.auc(pairs),
                "questions": M.mean([r["items"] for r in rs]),
            },
            "per_learner": {
                "seed": list(seeds),
                "next_brier": [r["next_brier"] for r in rs],
                "diag_brier": [r["brier"] for r in rs],
                "questions": [r["items"] for r in rs],
            },
        }
    contrasts = {
        f"{f}_minus_heuristic": {
            k: M.paired(arms[f]["per_learner"][k], arms["heuristic"]["per_learner"][k])
            for k in ("next_brier", "diag_brier", "questions")
        }
        for f in FITTED
    }
    return {
        "key": {"part": "B", "world": world, "curriculum": cur},
        "arms": arms,
        "contrasts": contrasts,
    }


def _ci(c):
    return f"{c['diff']:+.4f} [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]"


def hypotheses(real: dict, cells: list) -> dict:
    ran = {k: v for k, v in real.items() if v["status"] == "run"}
    ev1 = []
    held1 = len(ran) == 2
    for name, v in ran.items():
        h, f = (
            v["heldout"]["pooled_oof"][m] for m in ("heuristic_class_D6", "fitted_class_profile")
        )
        ok = f["brier"] < h["brier"] and f["ece"] < h["ece"]
        held1 &= ok
        ev1.append(
            f"{name}: Brier fitted {f['brier']:.4f} vs heuristic {h['brier']:.4f}, ECE {f['ece']:.4f} vs {h['ece']:.4f}"
        )
    for name, v in real.items():
        if v["status"] != "run":
            ev1.append(f"{name}: {v['status']}")
    h2 = [c for c in cells if c["key"]["world"] == "S4-assist09"]
    q = {
        f: [c["contrasts"][f"{f}_minus_heuristic"]["questions"]["diff"] for c in cells]
        for f in FITTED
    }
    return {
        "H1": {
            "held": held1,
            "evidence": "; ".join(ev1),
            "rule": "pooled out-of-fold Brier and ECE both lower, on both datasets",
        },
        "H2": {
            "held": bool(h2)
            and all(
                c["contrasts"]["fitted_assist09_minus_heuristic"]["next_brier"]["ci95"][1] < 0
                for c in h2
            ),
            "evidence": "; ".join(
                f"{c['key']['curriculum']} {_ci(c['contrasts']['fitted_assist09_minus_heuristic']['next_brier'])}"
                for c in h2
            ),
            "rule": "paired next-answer Brier difference with CI entirely below 0 on every curriculum",
        },
        "H3": {
            "held": all(sum(v) / len(v) >= 0 for v in q.values()) if cells else None,
            "evidence": "; ".join(
                f"{f}: mean questions difference vs heuristic over {len(v)} cells {sum(v) / len(v):+.4f}"
                for f, v in q.items()
            ),
            "rule": "average over all Part B cells of the paired questions difference >= 0, per fitted profile",
        },
        "S0-S4": {
            "held": None,
            "evidence": "descriptive (no direction predicted); see the S0-S4 cells' contrasts",
        },
    }


def main(argv=None) -> dict:
    args = common.parse(EXP, argv)
    run, out = common.start(EXP, NAME, args)
    for c in CURRICULA:
        C.paths(c)
    if args.smoke:
        units = [
            ("S0", "4-node", common.SMOKE_DIAG_SEEDS),
            ("S4-assist09", "4-node", common.SMOKE_DIAG_SEEDS),
        ]
        real = {
            "assist09": {"status": "not run: skipped in --smoke"},
            "ct": part_a("ct", args.procs),
        }
    else:
        units = [(w, c, common.DIAG_SEEDS) for w in ALL_WORLDS for c in CURRICULA]
        real = {name: part_a(name, args.procs) for name in R.DATASETS}
    cells = pmap(part_b_cell, units, args.procs)
    design = {
        "question": "Are the engine's probabilities trustworthy, and do fitted guess/slip numbers make them more trustworthy?",
        "part_a": {
            "datasets": {k: v for k, v in R.DATASETS.items()},
            "models": list(R.MODELS),
            "fitting": "fast EM, best of 5 random starts, seed 42, |dLL| <= 0.005, at most 100 iterations",
            "evaluation": "5-fold CV by student; difficulty recomputed per fold from training students",
        },
        "arms": {n: a.describe() for n, a in E3_ARMS.items()},
        "worlds": list(ALL_WORLDS),
        "curricula": list(CURRICULA),
        "seeds": {"diagnostic": [101, 599, "odd"], "cv": R.SEED}
        if not args.smoke
        else {"diagnostic": list(common.SMOKE_DIAG_SEEDS)},
    }
    return common.finish(
        run,
        out,
        design=design,
        content_review={c: C.content_review(c) for c in CURRICULA},
        cells=cells,
        hypotheses=hypotheses(real, cells),
        realdata=real,
    )


if __name__ == "__main__":
    main()
