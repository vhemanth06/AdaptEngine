import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type SimEpisode, type SimulateRequest } from "../api/client";
import { MODELS, MODEL_LABEL, PLANNERS, PLANNER_LABEL, useDemoPreset, useHealth, type Ctx } from "../ctx";
import { ARM_COLOR, Button, Card, ErrorBox, Segmented, fieldCls } from "../components/ui";

const ARMS = ["adapt", "no_review", "no_replan", "static"] as const;
const COMPARE = ["arms", "diagnostics"] as const;
const COMPARE_LABEL = { arms: "Arms (default engine)", diagnostics: "Diagnostics: sweep vs bisection" };
// Recharts animates in JS, so the CSS reduced-motion rule does not reach it
const animate = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
const AXIS = { fontSize: 12, stroke: "var(--text-faint)" };
const TIP = { contentStyle: { background: "var(--surface)", border: "1px solid var(--border)" } };

type Row = {
  key: string;
  n: number;
  mastered: number;
  mastery: number;
  minutes: number;
  execViol: number;
  diagItems: number | null;
  falseDiag: number | null;
  falseEnd: number | null;
};

function summarise(key: string, e: SimEpisode[]): Row {
  const diag = e.every((x) => x.diag_items != null);
  return {
    key,
    n: e.length,
    mastered: +mean(e.map((x) => (x.goal_mastered ? 1 : 0))).toFixed(3),
    mastery: +mean(e.map((x) => x.goal_true_mastery)).toFixed(3),
    minutes: +mean(e.map((x) => x.minutes_used)).toFixed(1),
    execViol: e.reduce((a, x) => a + x.executed_prereq_violations, 0),
    diagItems: diag ? +mean(e.map((x) => x.diag_items ?? 0)).toFixed(2) : null,
    falseDiag: diag ? e.reduce((a, x) => a + (x.false_confirm_at_diag ?? 0), 0) : null,
    falseEnd: diag ? e.reduce((a, x) => a + (x.false_confirm_at_end ?? 0), 0) : null,
  };
}

export default function Autopilot({ session }: Ctx) {
  const preset = useDemoPreset();
  const health = useHealth();
  const curricula = useQuery({ queryKey: ["curricula"], queryFn: api.curricula });
  const [f, setF] = useState(() => ({
    curriculum: session?.curriculum ?? preset.data?.curriculum ?? "8node",
    goal: session?.context.goal ?? preset.data?.goal ?? "C8",
    budget: 15,
    scenario: "calm" as SimulateRequest["scenario"],
    profile: "nominal" as SimulateRequest["profile"],
    arm: "adapt" as SimulateRequest["arm"],
    n_seeds: 20,
    model_profile: (session?.model_profile ?? preset.data?.model_profile ?? "heuristic") as (typeof MODELS)[number],
    planner_method: (session?.planner_method ?? "greedy") as (typeof PLANNERS)[number],
  }));
  const [compare, setCompare] = useState<(typeof COMPARE)[number]>("arms");
  const cur = useQuery({ queryKey: ["curriculum", f.curriculum], queryFn: () => api.curriculum(f.curriculum) });
  const base = { curriculum: f.curriculum, goal: f.goal, budget: f.budget, scenario: f.scenario, profile: f.profile, n_seeds: f.n_seeds, seed: 100 };
  const run = useMutation({
    mutationFn: async () => {
      if (compare === "arms") {
        const outs = await Promise.all(ARMS.map((arm) => api.simulate({ ...base, arm })));
        return outs.map((o, i) => ({ key: ARMS[i] as string, out: o }));
      }
      const methods = ["sweep", "bisection"] as const;
      const outs = await Promise.all(
        methods.map((m) =>
          api.simulate({ ...base, arm: f.arm, diagnostic_method: m, model_profile: f.model_profile, planner_method: f.planner_method }),
        ),
      );
      return outs.map((o, i) => ({ key: methods[i] as string, out: o }));
    },
  });

  const rows = (run.data ?? []).map(({ key, out }) => summarise(key, out.episodes));
  const note = run.data?.find((r) => r.out.note)?.out.note;
  const sc = run.data?.[0]?.out.scenario;
  const diag = rows.length > 0 && rows.every((r) => r.diagItems != null);
  const slow = compare === "diagnostics" && f.planner_method !== "greedy";
  const noOrtools = health.data && !health.data.ortools_available ? "needs the [cpsat] extra" : undefined;
  return (
    <div className="space-y-4">
      <Card title="Simulated learners (fixed seeds 100…)" testId="autopilot-controls">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <span className="text-sm">Compare</span>
          <Segmented label="Compare" testId="compare-mode" value={compare} options={COMPARE} labels={COMPARE_LABEL} onChange={setCompare} />
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm">
            Curriculum
            <select className={fieldCls} value={f.curriculum} onChange={(e) => setF({ ...f, curriculum: e.target.value, goal: "" })}>
              {curricula.data
                ?.filter((c) => c.reviewed)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.id}
                  </option>
                ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            Goal
            <select className={fieldCls} value={f.goal} onChange={(e) => setF({ ...f, goal: e.target.value })}>
              <option value="" disabled>
                pick
              </option>
              {cur.data?.concepts.map((c) => (
                <option key={c.concept_id} value={c.concept_id}>
                  {c.concept_id}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            Budget
            <select className={fieldCls} value={f.budget} onChange={(e) => setF({ ...f, budget: Number(e.target.value) })}>
              {(cur.data?.allowed_budgets ?? [5, 10, 15, 30]).map((b) => (
                <option key={b} value={b}>
                  {b} min
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            Scenario
            <select className={fieldCls} value={f.scenario} onChange={(e) => setF({ ...f, scenario: e.target.value as typeof f.scenario })}>
              {["calm", "missed_day", "budget_drop", "deadline_cut"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            Learner profile
            <select className={fieldCls} value={f.profile} onChange={(e) => setF({ ...f, profile: e.target.value as typeof f.profile })}>
              {["nominal", "high_slip", "fast_forgetter", "rapid_learner"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            Learners
            <input
              type="number"
              min={1}
              max={100}
              className={`${fieldCls} w-24`}
              value={f.n_seeds}
              onChange={(e) => setF({ ...f, n_seeds: Math.max(1, Math.min(100, Number(e.target.value))) })}
            />
          </label>
          {compare === "diagnostics" && (
            <>
              <label className="grid gap-1 text-sm">
                Arm
                <select className={fieldCls} value={f.arm} onChange={(e) => setF({ ...f, arm: e.target.value as typeof f.arm })}>
                  {ARMS.map((a) => (
                    <option key={a}>{a}</option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-sm">
                Item model
                <select
                  className={fieldCls}
                  value={f.model_profile}
                  onChange={(e) => setF({ ...f, model_profile: e.target.value as typeof f.model_profile })}
                >
                  {MODELS.map((m) => (
                    <option key={m} value={m}>
                      {MODEL_LABEL[m]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-sm">
                Planner
                <select
                  className={fieldCls}
                  value={f.planner_method}
                  onChange={(e) => setF({ ...f, planner_method: e.target.value as typeof f.planner_method })}
                >
                  {PLANNERS.map((p) => (
                    <option key={p} value={p} disabled={p !== "greedy" && !!noOrtools}>
                      {PLANNER_LABEL[p]}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          <Button testId="run-autopilot" disabled={run.isPending || !f.goal} onClick={() => run.mutate()}>
            {run.isPending ? "Running…" : compare === "arms" ? "Run all four arms" : "Run sweep and bisection"}
          </Button>
        </div>
        {slow && (
          <p className="mt-3 text-sm" style={{ color: "var(--remediation)" }} data-testid="cpsat-warning">
            ⚠ With {PLANNER_LABEL[f.planner_method]} every replan is a solver call: 100 learners can take minutes.
          </p>
        )}
        <ErrorBox error={run.error} onRetry={() => run.mutate()} />
        {note && <p className="mt-3">{note}</p>}
        {sc && (
          <p className="mt-3 text-sm text-[var(--text-muted)]">
            Scenario {String(sc.name)}: goal {String(sc.goal)}, {String(sc.budget)} min/day, deadline day {String(sc.deadline)}. True mastery
            is hidden from the engine.
          </p>
        )}
      </Card>

      {rows.length > 0 && rows[0].n > 0 && (
        <div className="grid gap-4 xl:grid-cols-2" data-testid="autopilot-results">
          <Card title="Goal: share mastered and mean true mastery">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="key" {...AXIS} />
                <YAxis domain={[0, 1]} {...AXIS} />
                <Tooltip {...TIP} />
                <Legend />
                <Bar isAnimationActive={animate} dataKey="mastered" name="goal mastered (share)" fill="var(--mastered)" />
                <Bar isAnimationActive={animate} dataKey="mastery" name="mean true mastery" fill="var(--progress)" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title={diag ? "Questions asked and minutes used (mean per learner)" : "Minutes used (mean per learner)"}>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="key" {...AXIS} />
                <YAxis {...AXIS} />
                <Tooltip {...TIP} />
                <Legend />
                {diag && <Bar isAnimationActive={animate} dataKey="diagItems" name="diagnostic questions" fill={ARM_COLOR.bisection} />}
                <Bar isAnimationActive={animate} dataKey="minutes" name="minutes used" fill={ARM_COLOR.adapt} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Per run" className="xl:col-span-2">
            <table className="tabular w-full text-left text-sm" data-testid="autopilot-table">
              <thead className="text-[var(--text-muted)]">
                <tr className="border-b border-[var(--border)]">
                  <th className="py-1">{diag ? "Diagnostic" : "Arm"}</th>
                  <th>Learners</th>
                  <th>Goal mastered</th>
                  <th>Mean true mastery</th>
                  <th>Minutes used</th>
                  {diag && <th>Questions asked</th>}
                  {diag && <th>False confirmations (diagnostic / end)</th>}
                  <th>Executed prerequisite violations</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.key} className="border-b border-[var(--border)]">
                    <td className="py-1">
                      <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ background: ARM_COLOR[r.key] }} />
                      {r.key}
                    </td>
                    <td>{r.n}</td>
                    <td className="font-mono">{r.mastered}</td>
                    <td className="font-mono">{r.mastery}</td>
                    <td className="font-mono">{r.minutes}</td>
                    {diag && <td className="font-mono" data-testid={`diag-items-${r.key}`}>{r.diagItems}</td>}
                    {diag && (
                      <td className="font-mono">
                        {r.falseDiag} / {r.falseEnd}
                      </td>
                    )}
                    <td className="font-mono" style={{ color: r.execViol ? "var(--violation)" : undefined }}>
                      {r.execViol}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}
    </div>
  );
}
