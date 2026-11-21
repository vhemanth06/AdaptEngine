"""Shared runner plumbing: command line, pre-registration guard, output path, episode summaries."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections import Counter

from ..core import metrics as M
from ..core.parallel import default_procs
from ..core.prereg import NotRegistered, guard
from ..core.results import Run, default_out, write

EPISODE_SEEDS = tuple(range(1000, 1200))
HEADLINE_SEEDS = tuple(range(1000, 2000))
DIAG_SEEDS = tuple(range(101, 600, 2))
SCRIPTED_SEEDS = tuple(range(101, 300, 2))
SMOKE_EPISODE_SEEDS = (1000, 1001)
SMOKE_DIAG_SEEDS = (101, 103)


def parse(exp: str, argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=f"Plan V2 {exp}")
    ap.add_argument("--smoke", action="store_true", help="1-2 learners, temporary output")
    ap.add_argument("--procs", type=int, default=default_procs())
    ap.add_argument("--out", default=None)
    ap.add_argument("--prereg", default=None, help=argparse.SUPPRESS)  # tests only
    return ap.parse_args(argv)


def start(exp: str, name: str, args) -> tuple[Run, str]:
    """Guard the run, start provenance, and choose the output path."""
    try:
        info = guard(exp, args.smoke, args.prereg)
    except NotRegistered as e:
        sys.exit(f"refusing to run {exp}: {e}")
    out = args.out or (
        os.path.join(tempfile.mkdtemp(prefix=f"v2_{exp}_"), f"{name}.json")
        if args.smoke
        else default_out(name)
    )
    return Run(name, info, args.procs), out


def finish(run: Run, out: str, **parts) -> dict:
    doc = run.finish(**parts)
    write(doc, out)
    print(f"{run.experiment}: wrote {out} ({doc['wall_s']} s, {run.procs} workers)")
    return doc


# ---------------------------------------------------------------- episode summaries

PER_LEARNER = ("goal_mastered", "all_required", "minutes", "goal_theta", "exec_viol", "idle_days")


def per_learner(rows: list) -> dict:
    out = {k: [float(r[k]) if isinstance(r[k], bool) else r[k] for r in rows] for k in PER_LEARNER}
    out["seed"] = [r["seed"] for r in rows]
    if "first_plan" in rows[0]:
        out["first_status"] = [r["first_plan"]["status"] for r in rows]
        out["plan_level_violations"] = [
            sum(r["plan_checks"][k] for k in ("prereq", "budget", "deadline")) for r in rows
        ]
    if "diag_items" in rows[0]:
        out["diag_items"] = [r["diag_items"] for r in rows]
        out["total_minutes"] = [r["minutes"] + r["diag_minutes"] for r in rows]
    return out


def summarise(rows: list) -> dict:
    """Arm metrics over learners (rows from episode.run_episode)."""
    reach = [r["minutes_to_mastery"] for r in rows]
    hist = M.histogram([p for r in rows for p in r["attempts"]])
    att = M.score_histogram(hist)
    m = {
        "goal_mastery_rate": M.mean([float(r["goal_mastered"]) for r in rows]),
        "mean_goal_theta": M.mean([r["goal_theta"] for r in rows]),
        "all_required_rate": M.mean([float(r["all_required"]) for r in rows]),
        "mean_minutes": M.mean([r["minutes"] for r in rows]),
        "reach_rate": M.mean([float(x is not None) for x in reach]),
        "mean_minutes_to_mastery": M.mean(reach),
        "executed_prereq_violations": sum(r["exec_viol"] for r in rows),
        "learners_with_executed_violations": sum(1 for r in rows if r["exec_viol"]),
        "executed_budget_violations": sum(r["exec_budget_viol"] for r in rows),
        "executed_deadline_violations": sum(r["exec_deadline_viol"] for r in rows),
        "idle_days": sum(r["idle_days"] for r in rows),
        "retention_reviewed": M.mean([r["ret_reviewed"] for r in rows]),
        "retention_not_reviewed": M.mean([r["ret_not_reviewed"] for r in rows]),
        "attempts": {k: att[k] for k in ("n", "brier", "log_loss", "auc", "ece")},
        "attempt_reliability": att["reliability"],
        "attempt_histogram": hist,
    }
    if "plan_checks" in rows[0]:
        m["plan_checks"] = {
            k: sum(r["plan_checks"][k] for r in rows)
            for k in ("plans", "prereq", "budget", "deadline")
        }
        m["plan_level_violations"] = sum(
            m["plan_checks"][k] for k in ("prereq", "budget", "deadline")
        )
        fp = [r["first_plan"] for r in rows]
        m["first_plan_verdicts"] = dict(sorted(Counter(x["verdict"] for x in fp).items()))
        m["first_plan"] = fp[0] if all(x == fp[0] for x in fp) else None
        m["first_plan_feasible_share"] = M.mean([float(x["status"] == "FEASIBLE") for x in fp])
        m["mean_reviews_in_first_plan"] = M.mean([x["reviews"] for x in fp])
    if "diag_items" in rows[0]:
        m["mean_diag_items"] = M.mean([r["diag_items"] for r in rows])
        m["mean_diag_minutes"] = M.mean([r["diag_minutes"] for r in rows])
        m["mean_total_minutes"] = M.mean([r["minutes"] + r["diag_minutes"] for r in rows])
        conf_d = sum(r["confirmed_at_diag"] for r in rows)
        conf_e = sum(r["confirmed_at_end"] for r in rows)
        m["confirmed_at_diag"] = conf_d
        m["false_confirm_rate_at_diag"] = (
            round(sum(r["false_confirm_at_diag"] for r in rows) / conf_d, 4) if conf_d else None
        )
        m["confirmed_at_end"] = conf_e
        m["false_confirm_rate_at_end"] = (  # after forgetting up to the deadline
            round(sum(r["false_confirm_at_end"] for r in rows) / conf_e, 4) if conf_e else None
        )
        n_conf = sum(r["confirmations"] for r in rows)
        m["confirmations"] = n_conf
        m["confirmation_false_pass_rate"] = (  # theta < 0.70 when the confirmation happened (E4 H3)
            round(sum(r["false_confirmations"] for r in rows) / n_conf, 4) if n_conf else None
        )
    return m


def arm_entry(rows: list) -> dict:
    return {"n": len(rows), "metrics": summarise(rows), "per_learner": per_learner(rows)}


def contrast(a: dict, b: dict, keys=("goal_mastered", "all_required", "minutes")) -> dict:
    """Paired a - b on per-learner vectors (same seeds)."""
    if a["per_learner"]["seed"] != b["per_learner"]["seed"]:
        raise ValueError("contrast between arms with different seeds")
    return {k: M.paired(a["per_learner"][k], b["per_learner"][k]) for k in keys}


def slim(rows: list) -> list:
    """Drop the bulky per-step fields once summaries and contrasts are computed."""
    return [{k: v for k, v in r.items() if k not in ("traj", "attempts")} for r in rows]
