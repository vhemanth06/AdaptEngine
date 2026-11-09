import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type SimulateOut, type SimulateRequest } from "../api/client";
import type { Ctx } from "../ctx";
import { ARM_COLOR, Button, C, Card, ErrorBox } from "../components/ui";

const ARMS = ["adapt", "no_review", "no_replan", "static"] as const;
const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

export default function Autopilot({ session }: Ctx) {
  const [f, setF] = useState({
    curriculum: session?.curriculum ?? "8node",
    goal: session?.context.goal ?? "C8",
    budget: 15,
    scenario: "missed_day" as SimulateRequest["scenario"],
    profile: "nominal" as SimulateRequest["profile"],
    n_seeds: 20,
  });
  const cur = useQuery({ queryKey: ["curriculum", f.curriculum], queryFn: () => api.curriculum(f.curriculum) });
  const run = useMutation({
    mutationFn: () => Promise.all(ARMS.map((arm) => api.simulate({ ...f, arm, seed: 100 }))),
  });

  const rows = (run.data ?? []).map((out: SimulateOut, i) => {
    const e = out.episodes;
    return {
      arm: ARMS[i],
      n: e.length,
      mastery: +mean(e.map((x) => x.goal_true_mastery)).toFixed(3),
      mastered: +mean(e.map((x) => (x.goal_mastered ? 1 : 0))).toFixed(3),
      days: +mean(e.map((x) => x.days_used)).toFixed(2),
      execViol: e.reduce((a, x) => a + x.executed_prereq_violations, 0),
      budgetViol: e.reduce((a, x) => a + x.budget_violations, 0),
      idle: +mean(e.map((x) => x.idle_days)).toFixed(2),
    };
  });
  const sc = run.data?.[0]?.scenario;
  const note = run.data?.find((o) => o.note)?.note;
  const field = "rounded-lg border border-slate-400 bg-white px-3 py-2";
  return (
    <div className="space-y-4">
      <Card title="Autopilot: simulated learners (fixed seeds 100…)">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col">
            Curriculum
            <select className={field} value={f.curriculum} onChange={(e) => setF({ ...f, curriculum: e.target.value, goal: "" })}>
              <option value="8node">8node</option>
              <option value="4node">4node</option>
            </select>
          </label>
          <label className="flex flex-col">
            Goal
            <select className={field} value={f.goal} onChange={(e) => setF({ ...f, goal: e.target.value })}>
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
          <label className="flex flex-col">
            Budget
            <select className={field} value={f.budget} onChange={(e) => setF({ ...f, budget: Number(e.target.value) })}>
              {(cur.data?.allowed_budgets ?? [5, 10, 15, 30]).map((b) => (
                <option key={b}>{b}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col">
            Scenario
            <select className={field} value={f.scenario} onChange={(e) => setF({ ...f, scenario: e.target.value as typeof f.scenario })}>
              {["calm", "missed_day", "budget_drop", "deadline_cut"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col">
            Learner profile
            <select className={field} value={f.profile} onChange={(e) => setF({ ...f, profile: e.target.value as typeof f.profile })}>
              {["nominal", "high_slip", "fast_forgetter", "rapid_learner"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col">
            Learners
            <input
              type="number"
              min={1}
              max={100}
              className={`${field} w-24`}
              value={f.n_seeds}
              onChange={(e) => setF({ ...f, n_seeds: Number(e.target.value) })}
            />
          </label>
          <Button testId="run-autopilot" disabled={run.isPending || !f.goal} onClick={() => run.mutate()}>
            {run.isPending ? "Running…" : "Run all four arms"}
          </Button>
        </div>
        <ErrorBox error={run.error} />
        {note && <p className="mt-3">{note}</p>}
        {sc && (
          <p className="mt-3 text-base text-slate-600">
            Scenario {sc.name as string}: goal {sc.goal as string}, {sc.budget as number} min/day, deadline day{" "}
            {sc.deadline as number}, events {JSON.stringify(sc.events)}. True mastery is hidden from the engine.
          </p>
        )}
      </Card>

      {rows.length > 0 && rows[0].n > 0 && (
        <div className="grid gap-4 lg:grid-cols-2" data-testid="autopilot-results">
          <Card title="Goal: true mastery (mean) and share mastered">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="arm" fontSize={16} />
                <YAxis domain={[0, 1]} fontSize={16} />
                <Tooltip />
                <Legend />
                <Bar dataKey="mastery" name="mean true mastery" fill={C.blue} />
                <Bar dataKey="mastered" name="share mastered" fill={C.orange} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Safety: executed prerequisite violations (total)">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="arm" fontSize={16} />
                <YAxis allowDecimals={false} fontSize={16} />
                <Tooltip />
                <Legend />
                <Bar dataKey="execViol" name="executed prereq violations" fill={C.vermillion} />
                <Bar dataKey="budgetViol" name="budget violations" fill={C.purple} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Per arm">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b">
                  <th>Arm</th>
                  <th>Learners</th>
                  <th>Mean mastery</th>
                  <th>Days used</th>
                  <th>Idle days</th>
                  <th>Exec. violations</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.arm} className="border-b border-slate-200">
                    <td>
                      <span className="mr-2 inline-block h-3 w-3 rounded-full" style={{ background: ARM_COLOR[r.arm] }} />
                      {r.arm}
                    </td>
                    <td>{r.n}</td>
                    <td className="font-mono">{r.mastery}</td>
                    <td className="font-mono">{r.days}</td>
                    <td className="font-mono">{r.idle}</td>
                    <td className="font-mono">{r.execViol}</td>
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
