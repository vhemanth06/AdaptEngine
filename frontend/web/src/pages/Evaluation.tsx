import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ErrorBar, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { ARM_COLOR, Card, ErrorBox } from "../components/ui";

type Row = Record<string, unknown> & { paired_diff_vs_adapt?: Record<string, unknown> };
type Table = Record<string, Record<string, Row>>;
const ARMS = ["adapt", "no_review", "no_replan", "static"];
const num = (x: unknown) => (typeof x === "number" ? x : undefined);
const fmt = (x: unknown, d = 3) => (typeof x === "number" ? x.toFixed(d) : "—");
const ci = (x: unknown) => (Array.isArray(x) ? `[${fmt(x[0])}, ${fmt(x[1])}]` : "");
// Older results files call executed violations "prerequisite_violations".
const execViol = (r: Row) => num(r.executed_prereq_violations) ?? num(r.prerequisite_violations);

export default function Evaluation() {
  const q = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation });
  if (q.error) return <ErrorBox error={q.error} />;
  if (!q.data) return <p>Loading…</p>;
  const files = q.data.files;
  const main = files.find((f) => f.name === "evaluation_results.json")?.data as
    | { metadata?: Record<string, unknown>; planner?: { main_table?: Table } }
    | undefined;
  const table = main?.planner?.main_table;
  const latency = files.find((f) => f.name === "replan_latency.json")?.data as
    | { curricula?: Record<string, Record<string, unknown>[]> }
    | undefined;
  const others = files.filter((f) => !["evaluation_results.json", "replan_latency.json"].includes(f.name));

  const scen = table ? Object.keys(table) : [];
  const masteryData = scen.map((s) => ({ scenario: s, ...Object.fromEntries(ARMS.map((a) => [a, num(table![s][a]?.mean_true_goal_mastery)])) }));
  const violData = scen.map((s) => ({ scenario: s, ...Object.fromEntries(ARMS.map((a) => [a, table![s][a] ? execViol(table![s][a]) : undefined])) }));
  const diffData = scen.map((s) => {
    const row: Record<string, unknown> = { scenario: s };
    for (const a of ARMS.slice(1)) {
      const p = table![s][a]?.paired_diff_vs_adapt;
      const d = num(p?.goal_true_mastery_diff);
      const c = p?.goal_true_mastery_diff_95ci as number[] | undefined;
      row[a] = d;
      if (d !== undefined && c) row[`${a}_err`] = [d - c[0], c[1] - d];
    }
    return row;
  });

  return (
    <div className="space-y-4" data-testid="evaluation">
      {!files.length && <Card>No results files found in experiments/results/.</Card>}
      {main?.metadata && (
        <Card title="Closed-loop evaluation (simulated learners)">
          <p>
            {String(main.metadata.num_seeds)} seeds per cell · profiles {JSON.stringify(main.metadata.profiles)} · git{" "}
            <code>{String(main.metadata.git_sha).slice(0, 8)}</code>
          </p>
          {main.metadata.limitation != null && <p className="mt-2 text-slate-600">Limitation: {String(main.metadata.limitation)}</p>}
        </Card>
      )}
      {table && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card title="Mean true goal mastery by scenario">
            <Chart data={masteryData} />
          </Card>
          <Card title="Executed prerequisite violations (total)">
            <Chart data={violData} />
          </Card>
          <Card title="Paired difference vs adapt: goal true mastery, 95% CI">
            <Chart data={diffData} arms={ARMS.slice(1)} errors />
          </Card>
        </div>
      )}
      {table && (
          <Card title="Table">
            <div className="overflow-x-auto">
              <table className="w-full whitespace-nowrap text-left text-base" data-testid="eval-table">
                <thead>
                  <tr className="border-b">
                    <th>Scenario</th>
                    <th>Arm</th>
                    <th>Mastered</th>
                    <th>Mean θ</th>
                    <th>Δ vs adapt [95% CI]</th>
                    <th>Exec. viol.</th>
                    <th>Budget viol.</th>
                    <th>Days</th>
                  </tr>
                </thead>
                <tbody>
                  {scen.flatMap((s) =>
                    ARMS.filter((a) => table[s][a]).map((a) => {
                      const r = table[s][a];
                      const p = r.paired_diff_vs_adapt ?? {};
                      return (
                        <tr key={`${s}-${a}`} className="border-b border-slate-200">
                          <td>{s}</td>
                          <td>{a}</td>
                          <td className="font-mono">{fmt(r.goal_mastery_rate, 2)}</td>
                          <td className="font-mono">{fmt(r.mean_true_goal_mastery)}</td>
                          <td className="font-mono">
                            {a === "adapt" ? "—" : `${fmt(p.goal_true_mastery_diff)} ${ci(p.goal_true_mastery_diff_95ci)}`}
                          </td>
                          <td className="font-mono">{execViol(r) ?? "—"}</td>
                          <td className="font-mono">{String(r.budget_violations ?? "—")}</td>
                          <td className="font-mono">{fmt(r.mean_days_used, 1)}</td>
                        </tr>
                      );
                    }),
                  )}
                </tbody>
              </table>
            </div>
          </Card>
      )}
      {latency?.curricula && (
        <Card title="Replan latency (ms)">
          <table className="w-full text-left text-base">
            <thead>
              <tr className="border-b">
                <th>Curriculum</th>
                <th>Event</th>
                <th>Median full</th>
                <th>p95 full</th>
                <th>Median frontier</th>
                <th>Speed-up</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(latency.curricula).flatMap(([c, rows]) =>
                rows.map((r, i) => (
                  <tr key={`${c}-${i}`} className="border-b border-slate-200">
                    <td>{c}</td>
                    <td>{String(r.event_kind)}</td>
                    <td className="font-mono">{fmt(r.median_full_ms, 2)}</td>
                    <td className="font-mono">{fmt(r.p95_full_ms, 2)}</td>
                    <td className="font-mono">{fmt(r.median_frontier_ms, 2)}</td>
                    <td className="font-mono">{fmt(r.speedup, 2)}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </Card>
      )}
      {others.map((f) => (
        <Card key={f.name} title={f.name}>
          <details>
            <summary>Show JSON summary</summary>
            <pre className="max-h-96 overflow-auto text-sm">{JSON.stringify(f.data, null, 1).slice(0, 20000)}</pre>
          </details>
        </Card>
      ))}
    </div>
  );
}

function Chart({ data, arms = ARMS, errors }: { data: Record<string, unknown>[]; arms?: string[]; errors?: boolean }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="scenario" fontSize={15} />
        <YAxis fontSize={15} />
        <Tooltip />
        <Legend />
        {arms.map((a) => (
          <Bar key={a} dataKey={a} fill={ARM_COLOR[a]} isAnimationActive={false}>
            {errors && <ErrorBar dataKey={`${a}_err`} width={6} strokeWidth={2} stroke="#111" />}
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
