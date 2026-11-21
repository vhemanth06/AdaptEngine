"""report/data/*.csv -> report/tables/*.tex (booktabs) and *.md. Reads only report/data/.

Numbers to 3 decimals; confidence intervals as `diff [lo, hi]`; `mean ± sd` for latency.

    python -m experiments.report.render_tables [--data DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import os

V2 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(V2, "report", "data")
OUT = os.path.join(V2, "report", "tables")


def T(header, kind, *cols):
    return (header, kind, cols)


# name -> (source CSV, caption, columns); kinds: text, int, num, ci, pm
TABLES = {
    "T1": ("t1_violations", "Executed prerequisite violations per arm (E1, E4, E5)",
           [T("Experiment", "text", "experiment"), T("Arm", "text", "arm"), T("Cells", "int", "cells"),
            T("Learners", "int", "learners"), T("Violations", "int", "executed_violations"),
            T("Learners with any", "int", "learners_with_violations")]),
    "T1b": ("t1b_plan_validity", "Plan validity: every plan and replan checked (E1, E5)",
            [T("Experiment", "text", "experiment"), T("Arm / planner", "text", "arm"), T("Plans checked", "int", "plans_checked"),
             T("Prerequisite", "int", "prereq"), T("Budget", "int", "budget"), T("Deadline", "int", "deadline"),
             T("Total", "int", "plan_level_violations")]),
    "T2": ("t2_shortfall", "Shortfall advice at too-short deadlines: greedy (bound-based) vs CP-SAT (exact) (E5)",
           [T("Curriculum", "text", "curriculum"), T("Budget", "int", "budget"), T("Needed days", "int", "needed_days"),
            T("Deadline", "int", "deadline"), T("Greedy", "text", "greedy_verdict"), T("Greedy shortfall", "int", "greedy_shortfall"),
            T("Hybrid shortfall", "int", "hybrid_shortfall"), T("CP-SAT", "text", "cpsat_verdict"),
            T("CP-SAT shortfall", "int", "cpsat_shortfall")]),
    "T3": ("t3_diagnostic_matrix", "Diagnostic accuracy per arm and world, mean over curricula (E2)",
           [T("World", "text", "world"), T("Arm", "text", "arm"), T("Brier", "num", "brier"), T("AUC", "num", "auc"),
            T("Questions", "num", "questions"), T("Next-answer Brier", "num", "next_answer_brier"),
            T("Curricula better than prior", "int", "cells_better_than_prior")]),
    "T4": ("t4_scripted", "Scripted learners: sweep vs bisection (E2)",
           [T("Curriculum", "text", "curriculum"), T("Learner", "text", "profile"), T("Sweep Brier", "num", "sweep_brier"),
            T("Bisection Brier", "num", "bisection_brier"), T("Bisection − sweep", "ci", "brier_diff", "brier_diff_lo", "brier_diff_hi"),
            T("Sweep questions", "num", "sweep_questions"), T("Bisection questions", "num", "bisection_questions")]),
    "T5": ("t5_realdata", "Held-out (5-fold by student) prediction on real students (E3 Part A)",
           [T("Dataset", "text", "dataset"), T("Model", "text", "model"), T("Answers", "int", "n"), T("RMSE", "num", "rmse"),
            T("Brier", "num", "brier"), T("Log-loss", "num", "log_loss"), T("AUC", "num", "auc"), T("ECE", "num", "ece"),
            T("Note", "text", "note")]),
    "T6": ("t6_fitted_contrasts", "Simulated learners: fitted − heuristic item model (E3 Part B)",
           [T("World", "text", "world"), T("Curriculum", "text", "curriculum"), T("Profile", "text", "profile"),
            T("Next-answer Brier", "ci", "next_brier_diff", "next_brier_diff_lo", "next_brier_diff_hi"),
            T("Diagnostic Brier", "ci", "diag_brier_diff", "diag_brier_diff_lo", "diag_brier_diff_hi"),
            T("Questions", "ci", "questions_diff", "questions_diff_lo", "questions_diff_hi")]),
    "T6b": ("t6b_attempt_calibration", "Engine P(correct) on executed attempts, adapt arm, pooled per world (E1)",
            [T("World", "text", "world"), T("Attempts", "int", "n"), T("Brier", "num", "brier"), T("Log-loss", "num", "log_loss"),
             T("AUC", "num", "auc"), T("ECE", "num", "ece")]),
    "T7": ("t7_headline", "Headline cells, budget 15, calm, N = 1000 (E1)",
           [T("World", "text", "world"), T("Curriculum", "text", "curriculum"), T("Arm", "text", "arm"),
            T("Goal mastery", "num", "goal_mastery"), T("All required", "num", "all_required"), T("Minutes", "num", "minutes"),
            T("Adapt − arm (goal)", "ci", "adapt_minus_arm_goal", "adapt_minus_arm_goal_lo", "adapt_minus_arm_goal_hi")]),
    "T8": ("t8_adapt_vs_static", "Adapt vs static on goal mastery: cells better / no difference / worse (E1)",
           [T("World", "text", "world"), T("Curriculum", "text", "curriculum"), T("Better", "int", "better"),
            T("No difference", "int", "no_difference"), T("Worse", "int", "worse"), T("Cells", "int", "cells")]),
    "T9": ("t9_bisect_vs_sweep", "Bisection with confirmation − sweep, budget 15, calm (E4)",
           [T("World", "text", "world"), T("Curriculum", "text", "curriculum"),
            T("Goal mastery", "ci", "goal_diff", "goal_diff_lo", "goal_diff_hi"),
            T("All required", "ci", "all_required_diff", "all_required_diff_lo", "all_required_diff_hi"),
            T("Total minutes", "ci", "total_minutes_diff", "total_minutes_diff_lo", "total_minutes_diff_hi")]),
    "T10": ("t10_two_by_two", "The 2×2: diagnostic {sweep, bisect_confirm} × item model {heuristic, fitted_assist09} (E4)",
            [T("World", "text", "world"), T("Curriculum", "text", "curriculum"), T("Metric", "text", "metric"),
             T("Diagnostic effect", "ci", "main_diagnostic", "main_diagnostic_lo", "main_diagnostic_hi"),
             T("Item-model effect", "ci", "main_item_model", "main_item_model_lo", "main_item_model_hi"),
             T("Interaction", "ci", "interaction", "interaction_lo", "interaction_hi")]),
    "T11": ("t11_replanning", "Replanning under disruptions: adapt − no_replan goal mastery (E1)",
            [T("Scenario", "text", "scenario"), T("World", "text", "world"), T("Cells", "int", "cells"),
             T("Mean difference", "num", "mean_diff"), T("Better", "int", "better"), T("No difference", "int", "no_difference"),
             T("Worse", "int", "worse")]),
    "T12": ("t12_planners", "Planner verdicts and shortfall advice (E5)",
            [T("Planner", "text", "planner"), T("Cells", "int", "cells"),
             T("First verdict = greedy", "num", "first_verdict_agreement_with_greedy"), T("UNKNOWN rate", "num", "unknown_rate"),
             T("Probe plans", "int", "probe_plans"), T("Probe not FEASIBLE", "int", "probe_not_feasible"),
             T("Mean shortfall (days)", "num", "probe_mean_shortfall_days"),
             T("Shortfall below greedy", "int", "probe_shortfall_below_greedy")]),
    "T12b": ("t12b_feasibility", "Path feasibility: feasible share of first plans per budget and planner (E1, E5)",
             [T("Planner", "text", "planner"), T("Budget", "int", "budget"), T("Curriculum", "text", "curriculum"),
              T("Cells", "int", "cells"), T("Feasible share", "num", "feasible_share")]),
    "T13": ("t13_cold_latency", "Cold-start planning time (ms), budget 15 (E5, timing)",
            [T("Curriculum", "text", "curriculum"), T("Planner", "text", "planner"), T("Mean ± sd", "pm", "mean_ms", "sd_ms"),
             T("Median", "num", "median_ms"), T("Repetitions", "int", "reps")]),
    "T13b": ("t13b_replan_latency", "Replanning time (ms) from a day-2 state (E5, timing)",
             [T("Curriculum", "text", "curriculum"), T("Planner", "text", "planner"), T("Event", "text", "event"),
              T("Mean ± sd", "pm", "mean_ms", "sd_ms"), T("Median", "num", "median_ms")]),
    "T14": ("t14_realworld", "Exploratory real-data world S4-assist09 (E6)",
            [T("Curriculum", "text", "curriculum"), T("Scenario", "text", "scenario"), T("Arm", "text", "arm"),
             T("Goal mastery", "num", "goal_mastery"), T("All required", "num", "all_required"), T("Minutes", "num", "minutes"),
             T("Adapt − arm (goal)", "ci", "adapt_minus_arm_goal", "adapt_minus_arm_goal_lo", "adapt_minus_arm_goal_hi")]),
    "H": ("hypotheses", "Pre-registered hypotheses: held or failed (E1–E6)",
          [T("Experiment", "text", "experiment"), T("Hypothesis", "text", "hypothesis"), T("Held", "text", "held"),
           T("Evidence", "text", "evidence")]),
}  # fmt: skip


def _num(v: str, digits: int = 3) -> str:
    if v in ("", None):
        return "–"
    x = float(v)
    return f"{x:.{digits}f}"


def cell(row: dict, kind: str, cols) -> str:
    if row["status"] != "ok":
        return "not run" if cols[0] == "experiment" or kind == "text" else "–"
    v = [row.get(c, "") for c in cols]
    if kind == "text":
        return v[0] or "–"
    if kind == "int":
        return str(int(float(v[0]))) if v[0] != "" else "–"
    if kind == "num":
        return _num(v[0])
    if kind == "pm":
        return f"{_num(v[0])} ± {_num(v[1])}" if v[0] != "" else "–"
    if kind == "ci":
        if v[0] == "":
            return "–"
        return f"{float(v[0]):+.3f} [{float(v[1]):+.3f}, {float(v[2]):+.3f}]"
    raise ValueError(kind)


def _tex(s: str) -> str:
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#"),
                 ("±", r"$\pm$"), ("−", "$-$"), ("×", r"$\times$"), ("θ", r"$\theta$"), ("≥", r"$\geq$"), ("–", "--")):  # fmt: skip
        s = s.replace(a, b)
    return s


def render(name: str, data_dir: str) -> tuple[str, str]:
    src, caption, cols = TABLES[name]
    with open(os.path.join(data_dir, f"{src}.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    head = [c[0] for c in cols]
    body = [[cell(r, kind, cs) for _, kind, cs in cols] for r in rows]
    sources = sorted({f"{r['source_file']} (code {r['code_hash'][:12] or 'n/a'})" for r in rows})
    md = [f"**{name}.** {caption}", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    md += ["| " + " | ".join(x.replace("|", "\\|") for x in b) + " |" for b in body]
    md += ["", "Source: " + "; ".join(sources), ""]
    align = "".join("l" if k == "text" else "r" for _, k, _ in cols)
    tex = [
        "% generated by experiments/report/render_tables.py from report/data/" + src + ".csv",
        r"\begin{table}[htbp]",
        r"\centering\small",
        rf"\caption{{{_tex(caption)}}}",
        rf"\label{{tab:{name.lower()}}}",
        rf"\begin{{tabular}}{{{align}}}",
        r"\toprule",
        " & ".join(_tex(h) for h in head) + r" \\",
        r"\midrule",
    ]
    tex += [" & ".join(_tex(x) for x in b) + r" \\" for b in body]
    tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(md), "\n".join(tex)


def main(data_dir: str = DATA, out_dir: str = OUT) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for name in TABLES:
        md, tex = render(name, data_dir)
        for ext, text in (("md", md), ("tex", tex)):
            p = os.path.join(out_dir, f"{name}.{ext}")
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            out.append(p)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    print(f"{len(main(a.data, a.out))} table files written")
