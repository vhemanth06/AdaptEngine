#!/usr/bin/env python3
"""Turn the E1-E6 result JSON files into docs/RESULTS.md and docs/figures/results_*.png.

  python experiments/make_results.py [--smoke] [--out-dir DIR]
--out-dir holds the result files (default experiments/results). Without --smoke it reads
<name>.json and writes docs/RESULTS.md + docs/figures/; with --smoke it reads <name>_smoke.json
and writes RESULTS_smoke.md + figures/ inside --out-dir. Reads files only; never re-runs episodes.
Every table and figure is followed by a `Source:` line with the source file and its code hash.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from experiments.provenance import prereg_hashes  # noqa: E402

PREREG = os.path.join(ROOT, "docs", "preregistration", "PRODUCT_RERUN_2026-11-15.md")
OLD_RESULTS = os.path.join(ROOT, "docs", "FINAL_RESULTS.md")
NAMES = (
    "grid",
    "diag_matrix",
    "sensitivity",
    "policy_train",
    "policy_eval",
    "extensions",
    "hlr_fit",
    "planner_cost",
)
NOT_ADAPTIVE = {"static", "static_loop", "random_eligible", "product_noreplan"}
MISSING = "not run (file missing)"
METRICS = (
    ("goal_mastery_rate", "goal"),
    ("all_required_rate", "all-req"),
    ("false_mastery_rate", "false mast."),
    ("minute_utilisation", "util."),
)


# ---------------------------------------------------------------- formatting helpers
def f3(x):
    return "—" if x is None else f"{x:.3f}"


def fd(d):
    """Paired-difference dict {'diff', 'ci95'} -> '+0.100 [-0.150, +0.350]'."""
    if not d:
        return "—"
    lo, hi = d["ci95"]
    return f"{d['diff']:+.3f} [{lo:+.3f}, {hi:+.3f}]"


def fx(x, nd=1):
    return "—" if x is None else f"{x:.{nd}f}"


def table(headers, rows, source):
    if not rows:
        rows = [["(no rows)"] + [""] * (len(headers) - 1)]
    esc = lambda c: str(c).replace("|", "\\|")  # noqa: E731  cell ids contain "|"
    out = ["| " + " | ".join(esc(h) for h in headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return out + ["", source, ""]


class Results:
    def __init__(self, out_dir, smoke):
        self.smoke = smoke
        self.data, self.files = {}, {}
        for n in NAMES:
            fn = f"{n}_smoke.json" if smoke else f"{n}.json"
            self.files[n] = fn
            p = os.path.join(out_dir, fn)
            if os.path.isfile(p):
                with open(p) as f:
                    self.data[n] = json.load(f)
            else:
                self.data[n] = None

    def provenance_problems(self, registered):
        """Inputs whose stamps differ from the registered hashes (top-level meta and the per-key
        meta of read-modify-write files), or that are missing."""
        bad = []
        for n in NAMES:
            d = self.data[n]
            if d is None:
                bad.append(f"`{self.files[n]}` missing")
                continue
            metas = [("", d.get("meta") or {})] + [
                (f"[{k}]", v["meta"])
                for k, v in d.items()
                if k != "meta" and isinstance(v, dict) and isinstance(v.get("meta"), dict)
                and "code_hash" in v["meta"]
            ]  # fmt: skip
            for where, m in metas:
                for k, want in registered.items():
                    got = m.get(k)
                    if want is None or got != want:
                        bad.append(f"`{self.files[n]}`{where} {k} {(got or 'absent')[:12]} != "
                                   f"registered {(want or 'absent')[:12]}")  # fmt: skip
        return bad

    def src(self, name, extra=""):
        d = self.data[name]
        h = (d.get("meta") or {}).get("code_hash", "unknown")[:12]
        return f"Source: `{self.files[name]}` (code hash `{h}`){extra}"

    def get(self, name):
        return self.data[name]


def cells_of(grid, kind):
    return {k: v for k, v in sorted(grid["cells"].items()) if v.get("grid") == kind}


def arm_order(cell, meta_arms=None):
    arms = list(cell["arms"])
    pref = meta_arms or []
    return [a for a in pref if a in arms] + sorted(a for a in arms if a not in pref)


# ---------------------------------------------------------------- figures
def fig_save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def fig_km(grid, cid, path):
    cell = grid["cells"][cid]
    arms = [a for a in arm_order(cell, grid["meta"].get("arms")) if "km_curve" in cell["arms"][a]]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for a in arms:
        c = cell["arms"][a]["km_curve"]
        tau = cell["arms"][a]["km_tau"]
        xs, ys = [t for t, _ in c] + [tau], [v for _, v in c] + [c[-1][1]]
        ax.step(xs, ys, where="post", label=a, lw=1.4)
    ax.axhline(0.5, color="grey", lw=0.6, ls=":")
    ax.set_xlabel("minutes to goal mastery")
    ax.set_ylabel("S(t): fraction not yet mastered")
    ax.set_title(f"Kaplan-Meier, headline cell {cid}", fontsize=9)
    ax.legend(fontsize=7)
    fig_save(fig, path)


def fig_forest(grid, path):
    rows = []
    for cid, c in cells_of(grid, "primary").items():
        p = c["paired_vs_static_loop"].get("product")
        if p:
            rows.append((cid, p["goal_mastery"]))
    fig, ax = plt.subplots(figsize=(7, min(40, max(3, 0.12 * len(rows) + 1.5))))
    for i, (_, d) in enumerate(rows):
        ax.plot(d["ci95"], [i, i], color="#4c78a8", lw=0.8)
        ax.plot(d["diff"], i, "o", color="#1f4e79", ms=2.5)
    ax.axvline(0, color="grey", lw=0.8)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=4)
    ax.invert_yaxis()
    ax.set_xlabel("goal mastery: product minus static_loop (paired 95% CI)")
    fig_save(fig, path)


def fig_reliability(grid, cid, path):
    cell = grid["cells"][cid]
    arms = [
        a for a in arm_order(cell, grid["meta"].get("arms")) if "reliability" in cell["arms"][a]
    ]
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.plot([0, 1], [0, 1], color="grey", lw=0.8, ls=":")
    for a in arms:
        b = [x for x in cell["arms"][a]["reliability"] if x["n"]]
        ax.plot([x["mean_p"] for x in b], [x["freq"] for x in b], "o-", ms=3, lw=1, label=a)
    ax.set_xlabel("mean predicted P(correct)")
    ax.set_ylabel("observed correct rate")
    ax.set_title(f"In-loop reliability, {cid}", fontsize=9)
    ax.legend(fontsize=7)
    fig_save(fig, path)


def fig_fm_util(grid, path):
    fig, ax = plt.subplots(figsize=(7, 5))
    cs = list(cells_of(grid, "primary").values())
    for arm in sorted({a for c in cs for a in c["arms"]}):
        pts = [
            (c["arms"][arm]["minute_utilisation"], c["arms"][arm]["false_mastery_rate"])
            for c in cs
            if arm in c["arms"] and c["arms"][arm].get("false_mastery_rate") is not None
        ]
        ax.scatter(*zip(*pts) if pts else ([], []), s=8, alpha=0.6, label=arm)
    ax.set_xlabel("minute utilisation")
    ax.set_ylabel("false mastery rate")
    ax.legend(fontsize=7)
    fig_save(fig, path)


# ---------------------------------------------------------------- sections
def sec_violations(R):
    lines, bad = [], []

    def add(label, rows, name, nonadaptive=()):
        """rows: (arm, cells, executed, plan, budget); adaptive arms with executed>0 go to bad."""
        out = []
        for arm, n, ex, pl, bu in rows:
            ad = arm not in nonadaptive
            if ad and ex:
                bad.append(f"{label}/{arm}={ex}")
            out.append([arm, "yes" if ad else "no", n, ex, pl, bu])
        lines.append(f"**{label}**\n")
        lines.extend(
            table(
                ["arm", "adaptive", "cells", "executed prereq", "plan prereq", "budget"],
                out,
                R.src(name),
            )
        )

    g = R.get("grid")
    if g:
        acc = {}
        for c in g["cells"].values():
            for a, s in c["arms"].items():
                r = acc.setdefault(a, [0, 0, 0, 0])
                r[0] += 1
                r[1] += s["executed_prereq_violations"]
                r[2] += s["plan_prereq_violations"]
                r[3] += s["budget_violations"]
        add("E1 grid (summed over cells)", [(a, *v) for a, v in sorted(acc.items())], "grid",
            NOT_ADAPTIVE)  # fmt: skip
    s = R.get("sensitivity")
    if s:
        acc = {}
        for c in s["cells"].values():
            for k, v in c["configs"].items():
                r = acc.setdefault(k, [0, 0, 0, 0])
                r[0] += 1
                r[1] += v["executed_prereq_violations"]
                r[2] += v["plan_prereq_violations"]
                r[3] += v["budget_violations"]
        add("E3 sensitivity (adapt_dx configs, summed over cells)",
            [(a, *v) for a, v in sorted(acc.items())], "sensitivity", {"static_loop"})  # fmt: skip
    pe = R.get("policy_eval")
    if pe:
        acc = {}
        for c in pe["cells"].values():
            for k, v in c.items():
                if isinstance(v, dict) and "executed_violations" in v:
                    r = acc.setdefault(k, [0, 0, "n/a", 0])
                    r[0] += 1
                    r[1] += v["executed_violations"]
                    r[3] += v["budget_violations"]
        add("E4 policy eval (summed over cells; n/a = not recorded)",
            [(a, *v) for a, v in sorted(acc.items())], "policy_eval")  # fmt: skip
    pt = R.get("policy_train")
    if pt:
        tv = sum(c["violations"] for c in pt["curve"])
        lines += ["**E4 policy train (executed violations over the training curve)**\n"]
        if tv:
            bad.append(f"E4 train={tv}")
        lines += table(
            ["episodes", "executed prereq"], [[len(pt["curve"]), tv]], R.src("policy_train")
        )
    e = R.get("extensions")
    if e:
        rows = []
        for key in sorted(e):
            if key == "meta":
                continue
            acc = {}
            for c in e[key]["cells"].values():
                for a, v in c["arms"].items():
                    r = acc.setdefault(a, [0, 0, 0, 0])
                    r[0] += 1
                    r[1] += v["executed_prereq_violations"]
                    r[2] += v["plan_prereq_violations"]
                    r[3] += v["budget_violations"]
            rows += [(f"{key}:{a}", *v) for a, v in sorted(acc.items())]
        add("E5 extensions (summed over cells)", rows, "extensions")
    if not lines:
        lines = [f"{MISSING}: no input with violation counts.", ""]
    return lines, bad


def sec_headline(R, figdir):
    g = R.get("grid")
    if not g:
        return [MISSING, ""]
    cid = g["meta"]["headline_cell"]
    cell = g["cells"].get(cid)
    if not cell:
        return [f"headline cell `{cid}` absent from grid file.", ""]
    rows = []
    for a in arm_order(cell, g["meta"].get("arms")):
        s = cell["arms"][a]
        rows.append([a, s["n"], *[f3(s[k]) for k, _ in METRICS],
                     fx(s.get("km_median_minutes")), fx(s.get("km_rmst_minutes")),
                     fx(s.get("mean_dx_minutes")), fx(s.get("mean_dx_items")),
                     fx(s.get("items_per_mastered_concept")),
                     f3(s.get("reach_rate")), f3(s.get("brier")), f3(s.get("auc")),
                     fd(cell["paired_vs_static_loop"].get(a, {}).get("goal_mastery"))])  # fmt: skip
    out = [f"Cell `{cid}`. KM median shows — when censored (median not reached).\n"]
    if not any("km_curve" in v for v in cell["arms"].values()):
        out += ["The grid file has no km_curve / reliability fields (older format).\n"]
    out += table(
        ["arm", "n", *[h for _, h in METRICS], "KM median min", "KM RMST min", "diagnostic min",
         "diagnostic items", "items per mastered concept", "reach rate", "Brier", "AUC",
         "Δ goal vs static_loop [95% CI]"],
        rows, R.src("grid"))  # fmt: skip
    fig_km(g, cid, os.path.join(figdir, "results_km_headline.png"))
    out += [
        "![KM headline](figures/results_km_headline.png)",
        "",
        R.src("grid", f", cell `{cid}`: Kaplan-Meier curves of minutes to goal mastery "
              "(episodes without mastery censored at minutes used)"),
        "",
    ]  # fmt: skip
    fig_reliability(g, cid, os.path.join(figdir, "results_reliability.png"))
    out += [
        "![Reliability](figures/results_reliability.png)",
        "",
        R.src("grid", f", cell `{cid}`: 10 equal-width bins of in-loop predicted P(correct), "
              "merged from the 100-bin histogram; dotted line is perfect calibration"),
        "",
    ]  # fmt: skip
    return out


def sec_vs_static(R, figdir):
    g = R.get("grid")
    if not g:
        return [MISSING, ""]
    cs = cells_of(g, "primary")
    groups, rows = {}, []
    for cid, c in cs.items():
        w, cur, _b, _sc, h = cid.split("|")
        p = c["paired_vs_static_loop"].get("product")
        if not p:
            continue
        groups.setdefault((w, cur, h), []).append(p["goal_mastery"]["diff"])
        rows.append([cid, f3(c["arms"]["product"]["goal_mastery_rate"]),
                     f3(c["arms"]["static_loop"]["goal_mastery_rate"]),
                     fd(p["goal_mastery"]), fd(p["all_required"])])  # fmt: skip
    out = ["Arm `product` vs `static_loop`, paired by seed. First table: unweighted mean of the "
           "per-cell paired differences by world, curriculum and horizon (no pooled CI). "
           "Second table: every primary cell.\n"]  # fmt: skip
    gr = [[w, cur, h, len(v), f"{sum(v) / len(v):+.3f}", f"{min(v):+.3f}", f"{max(v):+.3f}"]
          for (w, cur, h), v in sorted(groups.items())]  # fmt: skip
    out += table(
        ["world", "curriculum", "horizon", "cells", "mean Δ goal", "min", "max"], gr, R.src("grid")
    )
    out += table(["cell", "product goal", "static_loop goal", "Δ goal [95% CI]", "Δ all-req [95% CI]"],
                 rows, R.src("grid"))  # fmt: skip
    comp = [
        [cid, arm, fx(s.get("mean_dx_minutes")), fx(s.get("mean_dx_items")),
         fx(s.get("items_per_mastered_concept")), f3(s.get("reach_rate"))]
        for cid, c in cs.items()
        for arm, s in ((a, c["arms"][a]) for a in arm_order(c, g["meta"].get("arms")))
    ]  # fmt: skip
    out += ["Registered E1 secondary metrics for every primary cell and arm.\n"]
    out += table(["cell", "arm", "diagnostic min", "diagnostic items", "items per mastered concept",
                  "reach rate"],
                 comp, R.src("grid"))  # fmt: skip
    fig_forest(g, os.path.join(figdir, "results_forest_vs_static_loop.png"))
    out += ["![Forest](figures/results_forest_vs_static_loop.png)", "",
            R.src("grid", ", every primary cell, goal mastery of product minus static_loop"), ""]  # fmt: skip
    fig_fm_util(g, os.path.join(figdir, "results_false_mastery_utilisation.png"))
    out += ["![False mastery vs utilisation](figures/results_false_mastery_utilisation.png)", "",
            R.src("grid", ", one point per primary cell and arm"), ""]  # fmt: skip
    return out


def neg(d):
    return {**d, "diff": 0.0 - d["diff"], "ci95": [0.0 - d["ci95"][1], 0.0 - d["ci95"][0]]}


def sec_ablations(R):
    g = R.get("grid")
    if not g:
        return [MISSING, ""]
    # (label, ablation arm, sign): paired_vs_product stores arm - product
    defs = (
        ("diagnostic: product − product_nodx", "product_nodx", -1),
        ("consolidation: product_consol − product", "product_consol", 1),
        ("review: product − product_norev", "product_norev", -1),
        ("replanning: product − product_noreplan", "product_noreplan", -1),
    )
    out = ["Paired by seed, 95% bootstrap CI. Mean row: unweighted mean of per-cell differences "
           "(no CI).\n"]  # fmt: skip
    for key, title in (("goal_mastery", "goal mastery"), ("all_required", "all-required mastery")):
        rows, tot = [], [[] for _ in defs]
        for cid, c in cells_of(g, "primary").items():
            row = [cid]
            for i, (_, arm, sg) in enumerate(defs):
                d = c.get("paired_vs_product", {}).get(arm, {}).get(key)
                if d:
                    d = neg(d) if sg < 0 else d
                    tot[i].append(d["diff"])
                    row.append(fd(d))
                else:
                    row.append("—")
            rows.append(row)
        rows.append(["**mean over cells**"] + [
            f"{sum(t) / len(t):+.3f}" if t else "—" for t in tot])  # fmt: skip
        out += [f"**{title}**\n"] + table(["cell", *[d[0] for d in defs]], rows, R.src("grid"))
    return out


def old_headline():
    """Parse the historical W8 headline rows (adapt_final, static_loop) from docs/FINAL_RESULTS.md."""
    if not os.path.isfile(OLD_RESULTS):
        return None
    txt = open(OLD_RESULTS).read()
    m = re.search(r"### 1\.4 Headline cell.*?\n(.*?)\n\n", txt, re.S)
    h = re.search(r"code hash `([0-9a-f]+)", txt)
    rows = {}
    for ln in m.group(1).splitlines() if m else []:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if cells and cells[0] in ("adapt_final", "static_loop"):
            rows[cells[0]] = cells
    return rows, (h.group(1)[:12] if h else "unknown")


def sec_w8(R):
    g = R.get("grid")
    if not g:
        return [MISSING, ""]
    cid = g["meta"]["headline_cell"]
    cell = g["cells"][cid]
    out = ["Old numbers are the historical W8 headline (S1 | 4-node | B=15 | calm | 14 d, N = 1000, "
           "adapt_final on the old 4-exercise curriculum) parsed from `docs/FINAL_RESULTS.md` §1.4; "
           "new numbers are `product` and `w8_final` on the x10 curricula in this run. The "
           "curricula differ, so the old row is context and not a paired comparison.\n"]  # fmt: skip
    rows = []
    old = old_headline()
    if old and "adapt_final" in old[0]:
        c = old[0]["adapt_final"]
        rows.append(["old W8 adapt_final (FINAL_RESULTS.md)", c[1], c[2], c[3], c[4], c[5], c[6]])
    for a in ("product", "w8_final"):
        if a in cell["arms"]:
            s = cell["arms"][a]
            rows.append([f"new {a}", f3(s["goal_mastery_rate"]), f3(s["all_required_rate"]),
                         f3(s["false_mastery_rate"]), f3(s["minute_utilisation"]),
                         fx(s.get("km_median_minutes")), fx(s.get("km_rmst_minutes"))])  # fmt: skip
    out += table(["row", "goal", "all-req", "false mast.", "util.", "KM median", "KM RMST"], rows,
                 R.src("grid", f"; old row: `docs/FINAL_RESULTS.md` (code hash `{old[1]}`)" if old else ""))  # fmt: skip
    rows = []
    for cid2, c in cells_of(g, "primary").items():
        pw = c.get("paired_vs_product", {}).get("w8_final")
        if pw and "product" in c["arms"] and "w8_final" in c["arms"]:
            p, w = c["arms"]["product"], c["arms"]["w8_final"]
            rows.append([cid2, f3(p["goal_mastery_rate"]), f3(w["goal_mastery_rate"]),
                         fd(neg(pw["goal_mastery"])), fd(neg(pw["all_required"])),
                         f3(p["false_mastery_rate"]), f3(w["false_mastery_rate"]),
                         f3(p["minute_utilisation"]), f3(w["minute_utilisation"])])  # fmt: skip
    return out + table(
        ["cell", "product goal", "w8_final goal", "Δ goal product − w8_final [95% CI]",
         "Δ all-req product − w8_final [95% CI]", "product false mast.",
         "w8_final false mast.", "product util.", "w8_final util."],
        rows, R.src("grid"))  # fmt: skip


def sec_stress(R):
    g = R.get("grid")
    if not g:
        return [MISSING, ""]
    cs = cells_of(g, "stress")
    if not cs:
        return ["No stress cells in this grid file (grid mode primary).", ""]
    rows = []
    for cid, c in cs.items():
        r = [cid]
        for a in ("product", "product_noreplan", "static_loop"):
            s = c["arms"].get(a)
            r += [f3(s["goal_mastery_rate"]), f3(s["all_required_rate"])] if s else ["—", "—"]
        r.append(fd(c["paired_vs_static_loop"].get("product", {}).get("goal_mastery")))
        rows.append(r)
    return table(["cell", "product goal", "product all-req", "noreplan goal", "noreplan all-req",
                  "static_loop goal", "static_loop all-req", "product Δ goal vs static_loop"],
                 rows, R.src("grid"))  # fmt: skip


def sec_diag(R):
    d = R.get("diag_matrix")
    if not d:
        return [MISSING, ""]
    rows = []
    for cid, c in sorted(d["cells"].items()):
        for a in d["meta"]["arms"]:
            s = c["arms"].get(a)
            if s:
                rows.append([cid, a, s["n_learners"], f3(s["auc"]), f3(s["brier"]), f3(s["mae"]),
                             f3(s["known_accuracy"]), f3(s["unknown_accuracy"]),
                             f3(s.get("inferred_precision")), s.get("n_inferred", "—"),
                             fx(s["items_mean"]), s["items_p90"],
                             ", ".join(f"{k} {v}" for k, v in (s.get("stop_reasons") or {}).items())
                             or "—"])  # fmt: skip
    note = ("Truth: 1[θ ≥ 0.70] at day 0. irt_cat@n uses the simulator's true discrimination a = 3 "
            "(advantage in 2PL worlds); fixed@n, random@n, irt_cat@n use the product item count of "
            "the same learner. state_space runs only for curricula with ≤ 12 concepts and is not "
            "budget-matched. INFERRED precision: share of concepts the diagnostic stopped on as "
            "INFERRED that are truly mastered (n inferred = how many). Stop reasons: histogram "
            "over all scored concepts. No minutes are reported.\n")  # fmt: skip
    return [note] + table(
        ["cell", "arm", "learners", "AUC", "Brier", "MAE", "known acc.", "unknown acc.",
         "INFERRED precision", "n inferred", "items mean", "items p90", "stop reasons"],
        rows, R.src("diag_matrix"))  # fmt: skip


def sec_sens(R):
    s = R.get("sensitivity")
    if not s:
        return [MISSING, ""]
    rows = []
    for cid, c in sorted(s["cells"].items()):
        for k, v in c["configs"].items():
            rows.append([cid, k, v["n"], *[f3(v[m]) for m, _ in METRICS],
                         fd(c["paired_vs_product"].get(k, {}).get("goal_mastery")),
                         fd(c["paired_vs_static_loop"].get(k, {}).get("goal_mastery"))])  # fmt: skip
    skipped = s["meta"].get("skipped")
    out = [
        "Arm adapt_dx, one-at-a-time scans around the product config; a measurement, not a selection.\n"
    ]
    out += table(["cell", "config", "n", *[h for _, h in METRICS], "Δ goal vs product [95% CI]",
                  "Δ goal vs static_loop [95% CI]"], rows, R.src("sensitivity"))  # fmt: skip
    if skipped:
        out += ["Skipped combinations (config validation): " + json.dumps(skipped), ""]
    return out


def sec_policy(R):
    pt, pe = R.get("policy_train"), R.get("policy_eval")
    if not pt and not pe:
        return [MISSING, ""]
    out = []
    if pt:
        cv = pt["curve"]
        half = max(1, len(cv) // 2)
        mr = [c["mean_reward"] for c in cv]
        out += table(["updates", "episodes", "mean reward (first half)", "mean reward (second half)", "weights"],
                     [[pt["n_updates"], len(cv), f"{sum(mr[:half]) / half:+.4f}",
                       f"{sum(mr[half:]) / max(1, len(mr) - half):+.4f}" if mr[half:] else "—",
                       json.dumps({k: round(v, 3) for k, v in pt["weights"].items()})]],
                     R.src("policy_train"))  # fmt: skip
    else:
        out += [f"policy_train: {MISSING}", ""]
    if not pe:
        return out + [f"policy_eval: {MISSING}", ""]
    rows, ope = [], []
    for cid, c in sorted(pe["cells"].items()):
        for v in ("deterministic", "frozen", "updating", "random"):
            s = c.get(v)
            if s:
                rows.append([cid, v, s["n"], f3(s["goal_mastery_rate"]), f3(s["all_required_rate"]),
                             fx(s["km_median_minutes_to_mastery"]), fx(s["km_rmst_minutes_to_mastery"]),
                             s["decisions"],
                             f3(s["agreement_with_deterministic"]) if s["decisions"] else "—",
                             fd(s.get("vs_deterministic", {}).get("goal_mastery"))])  # fmt: skip
        o = c.get("ope_frozen")
        for log in ("from_random", "from_updating"):
            if o and log in o:
                e = o[log]
                ope.append([cid, log, e["n"], f3(o["simulated_value"]), f3(e["ips"]), f3(e["snips"]),
                            f3(e["dr"]), f3(e["abs_error"]["ips"]), f3(e["abs_error"]["snips"]),
                            f3(e["abs_error"]["dr"]), f3(e["max_weight"])])  # fmt: skip
    out += table(["cell", "variant", "n", "goal", "all-req", "KM median min", "KM RMST min",
                  "decisions", "agreement w/ deterministic", "Δ goal vs deterministic [95% CI]"],
                 rows, R.src("policy_eval"))  # fmt: skip
    out += [
        "Off-policy evaluation of the frozen policy: estimates from each log vs the simulated value.\n"
    ]
    out += table(["cell", "log", "n", "simulated value", "IPS", "SNIPS", "DR", "|err| IPS",
                  "|err| SNIPS", "|err| DR", "max weight"], ope, R.src("policy_eval"))  # fmt: skip
    return out


def sec_ext(R):
    e = R.get("extensions")
    if not e:
        return [MISSING, ""]
    out = ["review_cap pass rule (applied to goal mastery): capped − product_norev paired 95% CI "
           "includes or exceeds 0, i.e. it fails only if the upper bound is below 0 (lenient).\n"]  # fmt: skip
    for key in sorted(k for k in e if k != "meta"):
        sec = e[key]
        rows = []
        for cid, c in sorted(sec["cells"].items()):
            pk = next((k for k in c if k.startswith("paired_vs_")), None)
            for a, v in c["arms"].items():
                p = c[pk].get(a) if pk else None
                row = [cid, a, v["n"], *[f3(v[m]) for m, _ in METRICS],
                       fx(v.get("mean_dx_minutes")), fx(v.get("mean_dx_items")),
                       fd(p["goal_mastery"]) if p else "—",
                       fd(p["all_required"]) if p else "—"]  # fmt: skip
                if key == "review_cap":
                    row.append(c.get("pass") if a == "capped" else "")
                rows.append(row)
        hdr = ["cell", "arm", "n", *[h for _, h in METRICS], "dx min", "dx items", "Δ goal vs ref [95% CI]",
               "Δ all-req vs ref [95% CI]"] + (["pass"] if key == "review_cap" else [])  # fmt: skip
        out += [f"**{key}**\n"] + table(hdr, rows, R.src("extensions"))
    h = R.get("hlr_fit")
    if h:
        out += ["**hlr_fit**\n"] + table(
            ["weights", "Brier (fit)", "baseline Brier", "observations", "seeds", "episodes"],
            [[json.dumps(h["weights"]), f3(h["brier"]), f3(h["baseline_brier_mean"]),
              h["n_observations"], h["n_seeds"], h["episodes"]]], R.src("hlr_fit"))  # fmt: skip
    else:
        out += [f"hlr_fit: {MISSING}", ""]
    return out


def sec_planner(R):
    p = R.get("planner_cost")
    if not p:
        return [MISSING, ""]
    src = R.src("planner_cost")
    out = ["Latency is a median over repeated timings. Greedy plans can contain in-plan reviews, so "
           "greedy duplicate occurrences can be non-zero; CP-SAT duplicates are asserted 0 in tests. "
           "The E6 CP-SAT deadlines and replan deadlines are implementer-chosen.\n"]  # fmt: skip
    if "cpsat" in p:
        rows = []
        for cid, c in sorted(p["cpsat"]["cells"].items()):
            for pl in ("greedy_or_oracle", "cpsat"):
                v = c.get(pl)
                if v:
                    rows.append([cid, pl, v["status"], v["reason"], v["last_day"], v["n_activities"],
                                 v["minutes"], v["prereq_violations"], v["budget_violations"],
                                 v["duplicate_occurrences"], fx(v["median_ms"], 2)])  # fmt: skip
        out += ["**cpsat**\n"] + table(["cell", "planner", "status", "reason", "last day", "activities",
                                        "minutes", "prereq viol.", "budget viol.", "duplicates", "median ms"],
                                       rows, src)  # fmt: skip
    if "replan" in p:
        rows = [[cur, r["event_kind"], fx(r["median_full_ms"], 2), fx(r["median_frontier_ms"], 2),
                 fx(r["speedup"], 2), r["plans_equal"]]
                for cur, c in sorted(p["replan"]["curricula"].items()) for r in c["rows"]]  # fmt: skip
        out += ["**replan**\n"] + table(["curriculum", "event", "full ms", "frontier ms", "speedup",
                                         "plans equal"], rows, src)  # fmt: skip
    if "plan" in p:
        rows = [
            [k, fx(v["median_ms"], 2), v["status"]] for k, v in sorted(p["plan"]["cells"].items())
        ]
        out += ["**initial plan**\n"] + table(["cell", "median ms", "status"], rows, src)
    if "diag" in p:
        rows = [[k, v["n_learners"], fx(v["median_ms"], 2)]
                for k, v in sorted(p["diag"]["curricula"].items())]  # fmt: skip
        out += ["**diagnostic**\n"] + table(["curriculum", "learners", "median ms"], rows, src)
    return out


APPROX = (
    "- AUC in the E1 grid is computed from per-seed 100-bin histograms of bin-mean predictions "
    "(approximate); Brier is exact.\n"
    "- `irt_cat@n` in E2 uses the simulator's true discrimination (a = 3), an advantage in 2PL worlds.\n"
    "- `product_noreplan` plans once, open loop (non-adaptive); it is excluded from the "
    "zero-violation gate with the static baselines.\n"
    "- The E5 review_cap pass rule is lenient: it fails only if the upper CI bound is below 0.\n"
    "- Greedy plans can contain duplicate in-plan reviews even with maintenance reviews off; the "
    "duplicate audit is asserted 0 for CP-SAT only.\n"
    "- The E6 CP-SAT deadlines and replan deadlines are implementer-chosen.\n"
    "- The by-group means in section 3 are unweighted means of per-cell paired differences "
    "(no pooled CI); the policy_eval file does not record plan prerequisite violations (n/a).\n"
    "- Kaplan-Meier: episodes without goal mastery are censored at minutes used, which is "
    "informative censoring (FINAL_A5 convention); RMST is restricted to the max minutes available.\n"
    "- Items per mastered concept counts required concepts already mastered at day 0 in the "
    "denominator (true θ ≥ 0.70 at episode end); diagnostic items are excluded from the numerator.\n"
    "- OPE: per-decision IPS / SNIPS / DR reweight the action only and do not correct for the "
    "shift in the state distribution that the target policy would induce.\n"
    "- Paired bootstrap 95% CIs, no multiplicity correction; every cell is reported, nothing is "
    "selected from report seeds (measurement only)."
)


def main(argv=None) -> str:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "experiments", "results"))
    a = ap.parse_args(argv)
    R = Results(a.out_dir, a.smoke)
    if a.smoke:
        md_path = os.path.join(a.out_dir, "RESULTS_smoke.md")
        figdir = os.path.join(a.out_dir, "figures")
    else:
        md_path = os.path.join(ROOT, "docs", "RESULTS.md")
        figdir = os.path.join(ROOT, "docs", "figures")
    os.makedirs(figdir, exist_ok=True)

    viol, bad = sec_violations(R)
    secs = (
        ("Violations", viol),
        ("Headline cell", sec_headline(R, figdir)),
        ("Goal mastery vs static_loop by world, curriculum and horizon", sec_vs_static(R, figdir)),
        ("Ablations", sec_ablations(R)),
        ("What changed since W8: product vs w8_final", sec_w8(R)),
        ("Stress grid", sec_stress(R)),
        ("Diagnostic matrix", sec_diag(R)),
        ("Sensitivity", sec_sens(R)),
        ("Policy and OPE", sec_policy(R)),
        ("Extensions", sec_ext(R)),
        ("CP-SAT and latency", sec_planner(R)),
    )
    reg = prereg_hashes(PREREG)
    prov_bad = R.provenance_problems(reg)
    L = ["# Results: product-engine rerun (E1–E6)", ""]
    if a.smoke:
        L += ["**SMOKE RUN: truncated seeds, not results.**", ""]
    L += [f"Generated (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}", ""]
    if bad:
        L += ["**WARNING: NON-ZERO EXECUTED PREREQUISITE VIOLATIONS IN ADAPTIVE ARMS: "
              + "; ".join(bad) + ". See section 1.**", ""]  # fmt: skip
    else:
        L += ["Executed prerequisite violations in adaptive arms: none found in the loaded files "
              "(section 1).", ""]  # fmt: skip
    if prov_bad:
        L += ["**WARNING: INPUTS DO NOT MATCH THE PRE-REGISTERED HASHES (or are missing): "
              + "; ".join(prov_bad) + ".**", ""]  # fmt: skip
    else:
        L += ["Provenance: every input carries the pre-registered code and experiment hashes.", ""]
    L += ["Pre-registration: `docs/preregistration/PRODUCT_RERUN_2026-11-15.md`. "
          "Every table and figure is followed by a `Source:` line.", "", "## Approximations", "",
          APPROX, "",
          f"Source: `docs/preregistration/PRODUCT_RERUN_2026-11-15.md` (registered code hash "
          f"`{(reg['code_hash'] or 'unknown')[:12]}`, experiment hash "
          f"`{(reg['experiment_hash'] or 'unknown')[:12]}`)", ""]  # fmt: skip
    for i, (title, body) in enumerate(secs, 1):
        L += [f"## {i}. {title}", ""] + body
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    with open(md_path, "w") as f:
        f.write("\n".join(L).rstrip() + "\n")
    print(f"wrote {md_path}")
    return md_path


if __name__ == "__main__":
    main()
