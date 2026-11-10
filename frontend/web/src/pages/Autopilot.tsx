import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type SimulateOut, type SimulateRequest } from "../api/client";
import type { Ctx } from "../ctx";
import { ARM_COLOR, Button, Card, Chip, ErrorBox, Segmented, fieldCls } from "../components/ui";

const ARMS = ["adapt_final", "adapt", "static_loop", "static", "random_eligible"] as const;
type Arm = (typeof ARMS)[number];
const ARM_LABEL: Record<Arm, string> = {
  adapt_final: "adapt (final)",
  adapt: "adapt (W7)",
  static_loop: "static_loop",
  static: "static (one pass)",
  random_eligible: "random_eligible",
};
const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
const AXIS = { fontSize: 12, stroke: "var(--text-faint)" };

export default function Autopilot({ session }: Ctx) {
  const [f, setF] = useState({
    curriculum: session?.curriculum ?? "4node",
    goal: session?.context.goal ?? "C4",
    budget: 15,
    scenario: "calm" as SimulateRequest["scenario"],
    profile: "nominal" as SimulateRequest["profile"],
    world: "S1" as NonNullable<SimulateRequest["world"]>,
    horizon: 14 as number | "w7",
    n_seeds: 20,
  });
  const [arms, setArms] = useState<Arm[]>(["adapt_final", "adapt", "static_loop"]);
  const [beliefArm, setBeliefArm] = useState<Arm>("adapt");
  const cur = useQuery({ queryKey: ["curriculum", f.curriculum], queryFn: () => api.curriculum(f.curriculum) });
  const run = useMutation({
    mutationFn: async () => {
      const { horizon, ...rest } = f;
      const outs = await Promise.all(
        arms.map((arm) => api.simulate({ ...rest, arm, seed: 2001, horizon: horizon === "w7" ? null : horizon })),
      );
      return arms.map((arm, i) => [arm, outs[i]] as [Arm, SimulateOut]);
    },
  });

  const rows = (run.data ?? []).map(([arm, out]) => {
    const e = out.episodes;
    const believed = e.reduce((a, x) => a + x.believed_mastered, 0);
    return {
      arm,
      label: ARM_LABEL[arm],
      n: e.length,
      mastered: +mean(e.map((x) => (x.goal_mastered ? 1 : 0))).toFixed(3),
      theta: +mean(e.map((x) => x.goal_true_mastery)).toFixed(3),
      util: +mean(e.map((x) => x.minute_utilisation)).toFixed(3),
      execViol: e.reduce((a, x) => a + x.executed_prereq_violations, 0),
      falseMastery: believed ? +(e.reduce((a, x) => a + x.false_mastered, 0) / believed).toFixed(3) : 0,
      fm: e.reduce((a, x) => a + x.false_mastered, 0),
    };
  });
  // Mean goal-θ curve over minutes (each learner's trajectory is a step function)
  const curves = (() => {
    if (!run.data) return [];
    const maxM = Math.max(...run.data.flatMap(([, o]) => o.episodes.map((e) => e.minutes_used)), 0);
    const step = Math.max(5, Math.round(maxM / 40));
    const pts = [];
    for (let m = 0; m <= maxM; m += step) {
      const row: Record<string, number> = { m };
      for (const [arm, o] of run.data) {
        row[arm] = +mean(
          o.episodes.map((e) => {
            let v = e.goal_theta_by_minutes[0]?.[1] ?? 0;
            for (const [mm, th] of e.goal_theta_by_minutes) if (mm <= m) v = th;
            return v;
          }),
        ).toFixed(3);
      }
      pts.push(row);
    }
    return pts;
  })();
  const belief = (() => {
    const o = run.data?.find(([a]) => a === beliefArm)?.[1];
    if (!o?.episodes.length) return [];
    return Object.keys(o.episodes[0].final_p).map((c) => ({
      c,
      p: +mean(o.episodes.map((e) => e.final_p[c])).toFixed(3),
      theta: +mean(o.episodes.map((e) => e.final_theta[c])).toFixed(3),
    }));
  })();
  const sc = run.data?.[0]?.[1].scenario;
  return (
    <div className="space-y-4">
      <Card title="Simulated learners (held-out seeds 2001…)" testId="autopilot-controls">
        <div className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm">
            Curriculum
            <select className={fieldCls} value={f.curriculum} onChange={(e) => setF({ ...f, curriculum: e.target.value, goal: e.target.value === "8node" ? "C8" : "C4" })}>
              <option value="4node">4node</option>
              <option value="8node">8node</option>
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            Goal
            <select className={fieldCls} value={f.goal} onChange={(e) => setF({ ...f, goal: e.target.value })}>
              {cur.data?.concepts.map((c) => (
                <option key={c.concept_id}>{c.concept_id}</option>
              ))}
            </select>
          </label>
          <div className="grid gap-1 text-sm">
            World
            <Segmented label="World" value={f.world} options={["S0", "S1", "S2", "S3", "S4"] as const} onChange={(w) => setF({ ...f, world: w })} />
          </div>
          <div className="grid gap-1 text-sm">
            Horizon (days)
            <Segmented label="Horizon" value={f.horizon} options={["w7", 7, 14, 21] as const} onChange={(h) => setF({ ...f, horizon: h })} />
          </div>
          <label className="grid gap-1 text-sm">
            Scenario
            <select className={fieldCls} value={f.scenario} onChange={(e) => setF({ ...f, scenario: e.target.value as typeof f.scenario })}>
              {["calm", "missed_day", "missed_2days", "forgetting_21"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <div className="grid gap-1 text-sm">
            Learners
            <Segmented label="Learners" value={f.n_seeds} options={[1, 20, 100] as const} onChange={(n) => setF({ ...f, n_seeds: n })} />
          </div>
          <Button testId="run-autopilot" disabled={run.isPending || !arms.length} onClick={() => run.mutate()}>
            {run.isPending ? "Running…" : "Run"}
          </Button>
        </div>
        <fieldset className="mt-3 flex flex-wrap gap-3 text-sm">
          <legend className="sr-only">Arms</legend>
          {ARMS.map((a) => (
            <label key={a} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={arms.includes(a)}
                onChange={(e) => setArms(e.target.checked ? [...arms, a] : arms.filter((x) => x !== a))}
              />
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: ARM_COLOR[a] }} />
              {ARM_LABEL[a]}
            </label>
          ))}
        </fieldset>
        <ErrorBox error={run.error} onRetry={() => run.mutate()} />
        {sc && (
          <p className="mt-3 text-sm text-[var(--text-muted)]">
            Scenario {String(sc.name)}: goal {String(sc.goal)}, {String(sc.budget)} min/day, deadline day {String(sc.deadline)}. True mastery θ is
            hidden from the engine; world {f.world}.
          </p>
        )}
      </Card>

      {rows.length > 0 && rows[0].n > 0 && (
        <div className="grid gap-4 xl:grid-cols-2" data-testid="autopilot-results">
          <Card title="Goal θ over minutes (mean over learners)">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={curves}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="m" {...AXIS} label={{ value: "minutes", position: "insideBottom", offset: -2, fill: "var(--text-faint)" }} />
                <YAxis domain={[0, 1]} {...AXIS} />
                <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)" }} />
                <Legend />
                {arms.map((a) => (
                  <Line key={a} type="stepAfter" dataKey={a} name={ARM_LABEL[a]} stroke={ARM_COLOR[a]} dot={false} strokeWidth={2} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </Card>
          <Card
            title="Belief vs reality"
            testId="belief-vs-reality"
            actions={<Segmented label="Arm for belief panel" value={beliefArm} options={arms} onChange={setBeliefArm} />}
          >
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={belief}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="c" {...AXIS} />
                <YAxis domain={[0, 1]} {...AXIS} />
                <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)" }} />
                <Legend />
                <Bar dataKey="p" name="engine belief p" fill="var(--progress)" />
                <Bar dataKey="theta" name="simulated true θ" fill="var(--mastered)" />
              </BarChart>
            </ResponsiveContainer>
            <p className="mt-2 flex flex-wrap gap-2">
              {rows.map((r) => (
                <Chip key={r.arm} tone={r.falseMastery > 0.2 ? "violation" : "neutral"}>
                  {r.label}: false mastery {(r.falseMastery * 100).toFixed(0)}% ({r.fm})
                </Chip>
              ))}
            </p>
          </Card>
          <Card title="Per arm" className="xl:col-span-2">
            <table className="tabular w-full text-left text-sm">
              <thead className="text-[var(--text-muted)]">
                <tr className="border-b border-[var(--border)]">
                  <th className="py-1">Arm</th>
                  <th>Learners</th>
                  <th>Goal mastered</th>
                  <th>Mean goal θ</th>
                  <th>Minute utilisation</th>
                  <th>False mastery</th>
                  <th>Executed violations</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.arm} className="border-b border-[var(--border)]">
                    <td className="py-1">
                      <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ background: ARM_COLOR[r.arm] }} />
                      {r.label}
                    </td>
                    <td>{r.n}</td>
                    <td className="font-mono">{r.mastered}</td>
                    <td className="font-mono">{r.theta}</td>
                    <td className="font-mono">{r.util}</td>
                    <td className="font-mono">{r.falseMastery}</td>
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
