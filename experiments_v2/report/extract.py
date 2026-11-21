"""Results JSON -> report/data/*.csv: one small CSV per table or figure (D100).

Reads only experiments_v2/results/*.json. Every row carries `experiment`, `source_file`,
`code_hash` and `status`. A missing results file gives the expected rows with status `not_run`
and empty values, never a made-up number.

    python -m experiments_v2.report.extract [--results DIR] [--data DIR]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict

V2 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS = os.path.join(V2, "results")
DATA = os.path.join(V2, "report", "data")
FILES = {
    "E1": "E1_safety_outcomes.json",
    "E2": "E2_diagnostic.json",
    "E3": "E3_calibration.json",
    "E4": "E4_features.json",
    "E5": "E5_planners.json",
    "E5L": "E5_latency.json",
    "E6": "E6_sensitivity.json",
}
PROV = ["experiment", "source_file", "code_hash", "status"]
DISRUPTIONS = (
    "missed_day",
    "missed_2days",
    "budget_drop",
    "budget_crash",
    "deadline_cut",
    "deadline_halved",
)


def _ci(prefix: str, c: dict) -> dict:
    return {prefix: c["diff"], f"{prefix}_lo": c["ci95"][0], f"{prefix}_hi": c["ci95"][1]}


def _ci_cols(prefix: str) -> list:
    return [prefix, f"{prefix}_lo", f"{prefix}_hi"]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def _dir(c) -> str:
    lo, hi = c["ci95"]
    return "better" if lo > 0 else "worse" if hi < 0 else "no_difference"


# ---------------------------------------------------------------- 5.1


def t1_violations(d):
    rows = []
    for exp in ("E1", "E4", "E5"):
        if exp not in d:
            continue
        acc = defaultdict(lambda: [0, 0, 0, 0])
        for c in d[exp]["cells"]:
            for arm, a in c["arms"].items():
                x = acc[arm + ("_confirm" if c["key"].get("confirmation") else "")]
                x[0] += 1
                x[1] += a["n"]
                x[2] += a["metrics"]["executed_prereq_violations"]
                x[3] += a["metrics"]["learners_with_executed_violations"]
        for arm, (cells, n, v, lv) in sorted(acc.items()):
            rows.append(
                {
                    "_exp": exp,
                    "arm": arm,
                    "cells": cells,
                    "learners": n,
                    "executed_violations": v,
                    "learners_with_violations": lv,
                }
            )
    return rows


def t1b_plan_validity(d):
    rows = []
    for exp in ("E1", "E5"):
        if exp not in d:
            continue
        acc = defaultdict(lambda: [0, 0, 0, 0, 0])
        for c in d[exp]["cells"]:
            for arm, a in c["arms"].items():
                pc = a["metrics"].get("plan_checks")
                if pc is None:
                    continue
                name = arm + ("_confirm" if c["key"].get("confirmation") else "")
                x = acc[name]
                x[0] += 1
                for i, k in enumerate(("plans", "prereq", "budget", "deadline"), start=1):
                    x[i] += pc[k]
        for arm, (cells, plans, pr, bu, de) in sorted(acc.items()):
            rows.append(
                {
                    "_exp": exp,
                    "arm": arm,
                    "cells": cells,
                    "plans_checked": plans,
                    "prereq": pr,
                    "budget": bu,
                    "deadline": de,
                    "plan_level_violations": pr + bu + de,
                }
            )
    return rows


def t2_shortfall(d):
    rows = []
    for r in d["E5"].get("shortfall_probe", []):
        row = {
            "_exp": "E5",
            **{k: r[k] for k in ("curriculum", "budget", "needed_days", "deadline")},
        }
        for p in ("greedy", "hybrid", "cpsat"):
            row[f"{p}_verdict"] = r[p]["verdict"]
            row[f"{p}_shortfall"] = r[p]["shortfall_days"]
            row[f"{p}_reason"] = r[p]["reason"]
        rows.append(row)
    return rows


def f1_violations(d):
    return [
        {
            "_exp": "E1",
            "arm": r["arm"],
            "executed_violations": r["executed_violations"],
            "learners": r["learners"],
        }
        for r in t1_violations({"E1": d["E1"]})
    ]


# ---------------------------------------------------------------- 5.2


def e2_detail(d):
    rows = []
    for c in d["E2"]["cells"]:
        if c["key"]["part"] != "simulated":
            continue
        for arm, a in c["arms"].items():
            m = a["metrics"]
            rows.append(
                {
                    "_exp": "E2",
                    "world": c["key"]["world"],
                    "curriculum": c["key"]["curriculum"],
                    "arm": arm,
                    "brier": m["brier"],
                    "log_loss": m["log_loss"],
                    "auc": m["auc"],
                    "questions": m["questions"],
                    "next_answer_brier": m["next_answer_brier"],
                    **(
                        _ci("brier_vs_prior", c["contrasts"][f"{arm}_minus_prior_only"]["brier"])
                        if arm != "prior_only"
                        else {
                            "brier_vs_prior": 0.0,
                            "brier_vs_prior_lo": 0.0,
                            "brier_vs_prior_hi": 0.0,
                        }
                    ),
                }
            )
    return rows


def t3_diagnostic_matrix(d):
    by = defaultdict(list)
    for r in e2_detail(d):
        by[(r["world"], r["arm"])].append(r)
    order = (
        "prior_only",
        "sweep",
        "bisection",
        "fixed@n",
        "irt_cat_global@n",
        "irt_cat_per_concept@n",
    )
    rows = []
    for (w, arm), rs in sorted(by.items(), key=lambda kv: (kv[0][0], order.index(kv[0][1]))):
        rows.append(
            {
                "_exp": "E2",
                "world": w,
                "arm": arm,
                "curricula": len(rs),
                "brier": _mean([r["brier"] for r in rs]),
                "auc": _mean([r["auc"] for r in rs]),
                "questions": _mean([r["questions"] for r in rs]),
                "next_answer_brier": _mean([r["next_answer_brier"] for r in rs]),
                "cells_better_than_prior": sum(r["brier_vs_prior_hi"] < 0 for r in rs)
                if arm != "prior_only"
                else None,
            }
        )
    return rows


def t4_scripted(d):
    rows = []
    for c in d["E2"]["cells"]:
        if c["key"]["part"] != "scripted":
            continue
        s, b = c["arms"]["sweep"]["metrics"], c["arms"]["bisection"]["metrics"]
        rows.append(
            {
                "_exp": "E2",
                "curriculum": c["key"]["curriculum"],
                "profile": c["key"]["profile"],
                "sweep_brier": s["brier"],
                "bisection_brier": b["brier"],
                **_ci("brier_diff", c["contrasts"]["bisection_minus_sweep"]["brier"]),
                "sweep_questions": s["questions"],
                "bisection_questions": b["questions"],
                "bisection_false_confirm_rate": b["false_confirm_rate"],
            }
        )
    return rows


# ---------------------------------------------------------------- 5.3


def t5_realdata(d):
    rows = []
    for name, v in d["E3"].get("realdata", {}).items():
        if v["status"] != "run":
            rows.append({"_exp": "E3", "dataset": name, "model": "", "note": v["status"]})
            continue
        for m, x in v["heldout"]["pooled_oof"].items():
            rows.append(
                {
                    "_exp": "E3",
                    "dataset": name,
                    "model": m,
                    "n": x["n"],
                    "rmse": x["rmse"],
                    "brier": x["brier"],
                    "log_loss": x["log_loss"],
                    "auc": x["auc"],
                    "ece": x["ece"],
                    "note": "",
                }
            )
    return rows


def f3_reliability(d):
    rows = []
    for name, v in d["E3"].get("realdata", {}).items():
        if v["status"] != "run":
            continue
        for m, x in v["heldout"]["pooled_oof"].items():
            for b in x["reliability"]:
                rows.append(
                    {
                        "_exp": "E3",
                        "dataset": name,
                        "model": m,
                        "lo": b["lo"],
                        "hi": b["hi"],
                        "n": b["n"],
                        "mean_p": b["mean_p"],
                        "freq": b["freq"],
                    }
                )
    return rows


def t6_fitted_contrasts(d):
    rows = []
    for c in d["E3"]["cells"]:
        for f in ("fitted_assist09", "fitted_ct"):
            con = c["contrasts"][f"{f}_minus_heuristic"]
            rows.append(
                {
                    "_exp": "E3",
                    "world": c["key"]["world"],
                    "curriculum": c["key"]["curriculum"],
                    "profile": f,
                    **_ci("next_brier_diff", con["next_brier"]),
                    **_ci("diag_brier_diff", con["diag_brier"]),
                    **_ci("questions_diff", con["questions"]),
                }
            )
    return rows


def t6b_attempt_calibration(d):
    return [
        {
            "_exp": "E1",
            "world": w,
            "n": x["n"],
            "brier": x["brier"],
            "log_loss": x["log_loss"],
            "auc": x["auc"],
            "ece": x["ece"],
        }
        for w, x in sorted(d["E1"].get("attempt_calibration_by_world", {}).items())
    ]


def f3b_attempt_reliability(d):
    return [
        {
            "_exp": "E1",
            "world": w,
            "lo": b["lo"],
            "hi": b["hi"],
            "n": b["n"],
            "mean_p": b["mean_p"],
            "freq": b["freq"],
        }
        for w, x in sorted(d["E1"].get("attempt_calibration_by_world", {}).items())
        for b in x["reliability"]
    ]


# ---------------------------------------------------------------- 5.4


def t7_headline(d):
    rows = []
    for c in d["E1"]["cells"]:
        k = c["key"]
        if not k.get("headline"):
            continue
        for arm, a in c["arms"].items():
            m = a["metrics"]
            row = {
                "_exp": "E1",
                "world": k["world"],
                "curriculum": k["curriculum"],
                "arm": arm,
                "n": a["n"],
                "goal_mastery": m["goal_mastery_rate"],
                "all_required": m["all_required_rate"],
                "minutes": m["mean_minutes"],
                "goal_theta": m["mean_goal_theta"],
            }
            con = c["contrasts"].get(f"adapt_minus_{arm}") if arm != "adapt" else None
            row.update(
                _ci("adapt_minus_arm_goal", con["goal_mastered"])
                if con
                else {
                    "adapt_minus_arm_goal": None,
                    "adapt_minus_arm_goal_lo": None,
                    "adapt_minus_arm_goal_hi": None,
                }
            )
            rows.append(row)
    return rows


def t8_adapt_vs_static(d):
    acc = defaultdict(lambda: {"better": 0, "no_difference": 0, "worse": 0})
    for c in d["E1"]["cells"]:
        k = c["key"]
        acc[(k["world"], k["curriculum"])][
            _dir(c["contrasts"]["adapt_minus_static"]["goal_mastered"])
        ] += 1
    return [
        {"_exp": "E1", "world": w, "curriculum": cur, **v, "cells": sum(v.values())}
        for (w, cur), v in sorted(acc.items())
    ]


def t9_bisect_vs_sweep(d):
    rows = []
    for c in d["E4"]["cells"]:
        con = c["contrasts"]["bisect_confirm_minus_sweep"]
        m = c["arms"]
        rows.append(
            {
                "_exp": "E4",
                "world": c["key"]["world"],
                "curriculum": c["key"]["curriculum"],
                "sweep_goal": m["sweep"]["metrics"]["goal_mastery_rate"],
                "bisect_confirm_goal": m["bisect_confirm"]["metrics"]["goal_mastery_rate"],
                "sweep_total_minutes": m["sweep"]["metrics"]["mean_total_minutes"],
                "bisect_confirm_total_minutes": m["bisect_confirm"]["metrics"][
                    "mean_total_minutes"
                ],
                **_ci("goal_diff", con["goal_mastered"]),
                **_ci("all_required_diff", con["all_required"]),
                **_ci("total_minutes_diff", con["total_minutes"]),
            }
        )
    return rows


def t10_two_by_two(d):
    rows = []
    for c in d["E4"]["cells"]:
        for metric, x in c["contrasts"]["two_by_two"].items():
            rows.append(
                {
                    "_exp": "E4",
                    "world": c["key"]["world"],
                    "curriculum": c["key"]["curriculum"],
                    "metric": metric,
                    **_ci("main_diagnostic", x["main_diagnostic"]),
                    **_ci("main_item_model", x["main_item_model"]),
                    **_ci("interaction", x["interaction"]),
                }
            )
    return rows


def f4_goal_vs_minutes(d):
    acc = defaultdict(lambda: [[], []])
    for c in d["E4"]["cells"]:
        for arm, a in c["arms"].items():
            acc[(c["key"]["world"], arm)][0].append(a["metrics"]["goal_mastery_rate"])
            acc[(c["key"]["world"], arm)][1].append(a["metrics"]["mean_total_minutes"])
    return [
        {"_exp": "E4", "world": w, "arm": arm, "goal_mastery": _mean(g), "total_minutes": _mean(t)}
        for (w, arm), (g, t) in sorted(acc.items())
    ]


def t11_replanning(d):
    acc = defaultdict(lambda: {"better": 0, "no_difference": 0, "worse": 0, "diffs": []})
    for c in d["E1"]["cells"]:
        k = c["key"]
        if k["scenario"] in DISRUPTIONS:
            con = c["contrasts"]["adapt_minus_no_replan"]["goal_mastered"]
            x = acc[(k["scenario"], k["world"])]
            x[_dir(con)] += 1
            x["diffs"].append(con["diff"])
    return [
        {
            "_exp": "E1",
            "scenario": s,
            "world": w,
            "cells": len(v["diffs"]),
            "mean_diff": _mean(v["diffs"]),
            "better": v["better"],
            "no_difference": v["no_difference"],
            "worse": v["worse"],
        }
        for (s, w), v in sorted(acc.items(), key=lambda kv: (DISRUPTIONS.index(kv[0][0]), kv[0][1]))
    ]


def f5_retention(d):
    acc = defaultdict(lambda: [[], []])
    for c in d["E1"]["cells"]:
        if c["key"]["scenario"] != "forgetting_21":
            continue
        for arm in ("adapt", "no_review", "adapt_h7", "no_review_h7"):
            m = c["arms"][arm]["metrics"]
            acc[arm][0].append(m["retention_reviewed"])
            acc[arm][1].append(m["retention_not_reviewed"])
    return [
        {
            "_exp": "E1",
            "arm": arm,
            "retention_reviewed": _mean(r),
            "retention_not_reviewed": _mean(nr),
            "cells": len(r),
        }
        for arm, (r, nr) in acc.items()
    ]


# ---------------------------------------------------------------- 5.5


def t12_planners(d):
    acc = defaultdict(lambda: {"cells": 0, "agree": [], "unknown": []})
    for c in d["E5"]["cells"]:
        ag = c["contrasts"]["first_plan_agreement"]
        for p, u in ag["unknown_rate"].items():
            x = acc[p]
            x["cells"] += 1
            x["unknown"].append(u)
            x["agree"].append(ag.get(f"{p}_vs_greedy", 1.0))
    probe = d["E5"].get("shortfall_probe", [])
    rows = []
    for p in ("greedy", "hybrid", "cpsat"):
        if p not in acc:
            continue
        sh = [
            r for r in probe if r["greedy"]["status"] != "FEASIBLE" and r[p]["status"] != "FEASIBLE"
        ]
        rows.append(
            {
                "_exp": "E5",
                "planner": p,
                "cells": acc[p]["cells"],
                "first_verdict_agreement_with_greedy": _mean(acc[p]["agree"]),
                "unknown_rate": _mean(acc[p]["unknown"]),
                "probe_plans": len(probe),
                "probe_not_feasible": sum(r[p]["status"] != "FEASIBLE" for r in probe),
                "probe_mean_shortfall_days": _mean([r[p]["shortfall_days"] for r in sh]),
                "probe_shortfall_below_greedy": sum(
                    r[p]["shortfall_days"] < r["greedy"]["shortfall_days"] for r in sh
                ),
            }
        )
    return rows


def t12b_feasibility(d):
    acc = defaultdict(list)
    for c in d["E5"]["cells"]:
        if c["key"]["confirmation"]:
            continue
        for p, a in c["arms"].items():
            acc[(p, c["key"]["budget"], c["key"]["curriculum"])].append(
                a["metrics"]["first_plan_feasible_share"]
            )
    return [
        {
            "_exp": "E5",
            "planner": p,
            "budget": b,
            "curriculum": cur,
            "cells": len(v),
            "feasible_share": _mean(v),
        }
        for (p, b, cur), v in sorted(acc.items())
    ]


def _lat(d, kind):
    rows = []
    for c in d["E5L"]["cells"]:
        k = c["key"]
        if k["kind"] != kind:
            continue
        m = c["arms"][k["planner"]]["metrics"]
        rows.append(
            {
                "_exp": "E5",
                "curriculum": k["curriculum"],
                "planner": k["planner"],
                "event": k.get("event", ""),
                "reps": c["arms"][k["planner"]]["n"],
                "mean_ms": round(m["mean_s"] * 1000, 3),
                "sd_ms": round(m["sd_s"] * 1000, 3),
                "median_ms": round(m["median_s"] * 1000, 3),
            }
        )
    return rows


def t13_cold_latency(d):
    return _lat(d, "cold_start")


def t13b_replan_latency(d):
    return _lat(d, "replan")


# ---------------------------------------------------------------- 5.6


def t14_realworld(d):
    rows = []
    for c in d["E6"]["cells"]:
        k = c["key"]
        if k["part"] != "real":
            continue
        for arm, a in c["arms"].items():
            m = a["metrics"]
            con = c["contrasts"].get(f"adapt_minus_{arm}")
            rows.append(
                {
                    "_exp": "E6",
                    "world": k["world"],
                    "curriculum": k["curriculum"],
                    "scenario": k["scenario"],
                    "arm": arm,
                    "goal_mastery": m["goal_mastery_rate"],
                    "all_required": m["all_required_rate"],
                    "minutes": m["mean_minutes"],
                    **(
                        _ci("adapt_minus_arm_goal", con["goal_mastered"])
                        if con
                        else {
                            "adapt_minus_arm_goal": None,
                            "adapt_minus_arm_goal_lo": None,
                            "adapt_minus_arm_goal_hi": None,
                        }
                    ),
                }
            )
    return rows


def f7_heatmap(d):
    acc = defaultdict(list)
    for c in d["E1"]["cells"]:
        acc[(c["key"]["world"], c["key"]["scenario"])].append(
            c["contrasts"]["adapt_minus_static"]["goal_mastered"]["diff"]
        )
    return [
        {"_exp": "E1", "world": w, "scenario": s, "cells": len(v), "mean_diff": _mean(v)}
        for (w, s), v in sorted(acc.items())
    ]


def _scan_rows(d):
    for c in d["E6"]["cells"]:
        if c["key"]["part"] == "scan":
            yield c


def f8_theta_k(d):
    acc = defaultdict(lambda: [[], []])
    for c in _scan_rows(d):
        for lab, a in c["arms"].items():
            if lab.startswith("theta=") and "|k=" in lab:
                t, k = lab[6:].split("|k=")
                acc[(float(t), int(k))][0].append(a["metrics"]["goal_mastery_rate"])
                acc[(float(t), int(k))][1].append(
                    c["contrasts"][f"{lab}_minus_static"]["goal_mastered"]["diff"]
                )
    return [
        {
            "_exp": "E6",
            "theta": t,
            "k": k,
            "cells": len(g),
            "goal_mastery": _mean(g),
            "minus_static": _mean(s),
        }
        for (t, k), (g, s) in sorted(acc.items())
    ]


def f9_scans(d):
    rows = []
    for c in _scan_rows(d):
        for lab, a in c["arms"].items():
            if lab in ("static",) or "|k=" in lab or lab.startswith("criterion="):
                continue
            param, val = ("baseline", "") if lab == "baseline" else lab.split("=")
            rows.append(
                {
                    "_exp": "E6",
                    "world": c["key"]["world"],
                    "curriculum": c["key"]["curriculum"],
                    "parameter": param,
                    "value": val,
                    "goal_mastery": a["metrics"]["goal_mastery_rate"],
                    "all_required": a["metrics"]["all_required_rate"],
                    "minutes": a["metrics"]["mean_minutes"],
                }
            )
        for lab, a in c["arms"].items():
            if lab.startswith("criterion="):
                rows.append(
                    {
                        "_exp": "E6",
                        "world": c["key"]["world"],
                        "curriculum": c["key"]["curriculum"],
                        "parameter": "criterion",
                        "value": lab.split("=")[1],
                        "goal_mastery": a["metrics"]["goal_mastery_rate"],
                        "all_required": a["metrics"]["all_required_rate"],
                        "minutes": a["metrics"]["mean_minutes"],
                    }
                )
    return rows


def hypotheses(d):
    rows = []
    for exp in ("E1", "E2", "E3", "E4", "E5", "E6"):
        if exp not in d:
            continue
        for h, v in d[exp]["hypotheses"].items():
            rows.append(
                {
                    "_exp": exp,
                    "hypothesis": h,
                    "held": "" if v["held"] is None else ("yes" if v["held"] else "no"),
                    "evidence": v["evidence"],
                }
            )
    return rows


# name -> (experiments needed, value columns, extractor)
TABLES = {
    "t1_violations": (
        ("E1", "E4", "E5"),
        ["arm", "cells", "learners", "executed_violations", "learners_with_violations"],
        t1_violations,
    ),
    "t1b_plan_validity": (
        ("E1", "E5"),
        ["arm", "cells", "plans_checked", "prereq", "budget", "deadline", "plan_level_violations"],
        t1b_plan_validity,
    ),
    "t2_shortfall": (
        ("E5",),
        ["curriculum", "budget", "needed_days", "deadline"]
        + [
            f"{p}_{x}"
            for p in ("greedy", "hybrid", "cpsat")
            for x in ("verdict", "shortfall", "reason")
        ],
        t2_shortfall,
    ),
    "f1_violations": (("E1",), ["arm", "executed_violations", "learners"], f1_violations),
    "t3_diagnostic_matrix": (
        ("E2",),
        [
            "world",
            "arm",
            "curricula",
            "brier",
            "auc",
            "questions",
            "next_answer_brier",
            "cells_better_than_prior",
        ],
        t3_diagnostic_matrix,
    ),
    "f2_diagnostic_detail": (
        ("E2",),
        ["world", "curriculum", "arm", "brier", "log_loss", "auc", "questions", "next_answer_brier"]
        + _ci_cols("brier_vs_prior"),
        e2_detail,
    ),
    "t4_scripted": (
        ("E2",),
        ["curriculum", "profile", "sweep_brier", "bisection_brier"]
        + _ci_cols("brier_diff")
        + ["sweep_questions", "bisection_questions", "bisection_false_confirm_rate"],
        t4_scripted,
    ),
    "t5_realdata": (
        ("E3",),
        ["dataset", "model", "n", "rmse", "brier", "log_loss", "auc", "ece", "note"],
        t5_realdata,
    ),
    "f3_reliability_realdata": (
        ("E3",),
        ["dataset", "model", "lo", "hi", "n", "mean_p", "freq"],
        f3_reliability,
    ),
    "t6_fitted_contrasts": (
        ("E3",),
        ["world", "curriculum", "profile"]
        + _ci_cols("next_brier_diff")
        + _ci_cols("diag_brier_diff")
        + _ci_cols("questions_diff"),
        t6_fitted_contrasts,
    ),
    "t6b_attempt_calibration": (
        ("E1",),
        ["world", "n", "brier", "log_loss", "auc", "ece"],
        t6b_attempt_calibration,
    ),
    "f3b_attempt_reliability": (
        ("E1",),
        ["world", "lo", "hi", "n", "mean_p", "freq"],
        f3b_attempt_reliability,
    ),
    "t7_headline": (
        ("E1",),
        ["world", "curriculum", "arm", "n", "goal_mastery", "all_required", "minutes", "goal_theta"]
        + _ci_cols("adapt_minus_arm_goal"),
        t7_headline,
    ),
    "t8_adapt_vs_static": (
        ("E1",),
        ["world", "curriculum", "better", "no_difference", "worse", "cells"],
        t8_adapt_vs_static,
    ),
    "t9_bisect_vs_sweep": (
        ("E4",),
        [
            "world",
            "curriculum",
            "sweep_goal",
            "bisect_confirm_goal",
            "sweep_total_minutes",
            "bisect_confirm_total_minutes",
        ]
        + _ci_cols("goal_diff")
        + _ci_cols("all_required_diff")
        + _ci_cols("total_minutes_diff"),
        t9_bisect_vs_sweep,
    ),
    "t10_two_by_two": (
        ("E4",),
        ["world", "curriculum", "metric"]
        + _ci_cols("main_diagnostic")
        + _ci_cols("main_item_model")
        + _ci_cols("interaction"),
        t10_two_by_two,
    ),
    "f4_goal_vs_minutes": (
        ("E4",),
        ["world", "arm", "goal_mastery", "total_minutes"],
        f4_goal_vs_minutes,
    ),
    "t11_replanning": (
        ("E1",),
        ["scenario", "world", "cells", "mean_diff", "better", "no_difference", "worse"],
        t11_replanning,
    ),
    "f5_retention": (
        ("E1",),
        ["arm", "retention_reviewed", "retention_not_reviewed", "cells"],
        f5_retention,
    ),
    "t12_planners": (
        ("E5",),
        [
            "planner",
            "cells",
            "first_verdict_agreement_with_greedy",
            "unknown_rate",
            "probe_plans",
            "probe_not_feasible",
            "probe_mean_shortfall_days",
            "probe_shortfall_below_greedy",
        ],
        t12_planners,
    ),
    "t12b_feasibility": (
        ("E5",),
        ["planner", "budget", "curriculum", "cells", "feasible_share"],
        t12b_feasibility,
    ),
    "t13_cold_latency": (
        ("E5L",),
        ["curriculum", "planner", "event", "reps", "mean_ms", "sd_ms", "median_ms"],
        t13_cold_latency,
    ),
    "t13b_replan_latency": (
        ("E5L",),
        ["curriculum", "planner", "event", "reps", "mean_ms", "sd_ms", "median_ms"],
        t13b_replan_latency,
    ),
    "t14_realworld": (
        ("E6",),
        ["world", "curriculum", "scenario", "arm", "goal_mastery", "all_required", "minutes"]
        + _ci_cols("adapt_minus_arm_goal"),
        t14_realworld,
    ),
    "f7_adapt_static_heatmap": (("E1",), ["world", "scenario", "cells", "mean_diff"], f7_heatmap),
    "f8_theta_k": (("E6",), ["theta", "k", "cells", "goal_mastery", "minus_static"], f8_theta_k),
    "f9_scans": (
        ("E6",),
        ["world", "curriculum", "parameter", "value", "goal_mastery", "all_required", "minutes"],
        f9_scans,
    ),
    "hypotheses": (
        ("E1", "E2", "E3", "E4", "E5", "E6"),
        ["hypothesis", "held", "evidence"],
        hypotheses,
    ),
}


def load_results(results_dir: str) -> dict:
    out = {}
    for k, f in FILES.items():
        p = os.path.join(results_dir, f)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                out[k] = json.load(fh)
            out[k]["_source"] = f"experiments_v2/results/{f}"
    return out


def main(results_dir: str = RESULTS, data_dir: str = DATA) -> dict:
    docs = load_results(results_dir)
    os.makedirs(data_dir, exist_ok=True)
    written = {}
    for name, (needed, cols, fn) in TABLES.items():
        have = {k: docs[k] for k in needed if k in docs}
        rows = []
        if have:
            for r in fn(have):
                exp = r.pop("_exp")
                src = docs["E5L" if name.startswith("t13") else exp]
                rows.append(
                    {
                        "experiment": src["experiment"],
                        "source_file": src["_source"],
                        "code_hash": src["code_hash"],
                        "status": "ok",
                        **r,
                    }
                )
        for k in needed:  # every missing results file gives an explicit not_run row
            if k not in docs:
                rows.append(
                    {
                        "experiment": FILES[k][:-5],
                        "source_file": f"experiments_v2/results/{FILES[k]}",
                        "code_hash": "",
                        "status": "not_run",
                    }
                )
        path = os.path.join(data_dir, f"{name}.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=PROV + cols, lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow({k: ("" if r.get(k) is None else r.get(k, "")) for k in PROV + cols})
        written[name] = len(rows)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=RESULTS)
    ap.add_argument("--data", default=DATA)
    a = ap.parse_args()
    for k, v in main(a.results, a.data).items():
        print(f"{k}: {v} rows")
