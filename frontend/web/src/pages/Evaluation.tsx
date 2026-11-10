import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ARM_COLOR, Button, Card, Chip, EmptyState, ErrorBox, LoadingCard, Segmented } from "../components/ui";

type ArmSum = {
  n: number;
  goal_mastery_rate: number;
  all_required_rate: number;
  executed_prereq_violations: number;
  false_mastery_rate: number | null;
  minute_utilisation: number;
  km_median_minutes_to_mastery: number | null;
  km_rmst_minutes_to_mastery: number;
  brier: number | null;
  auc: number | null;
  calibration_bins?: { pos: number[]; neg: number[]; sum_p: number[]; sum_y: number[] };
};
type Pair = { goal_mastery: { diff: number; ci95: [number, number] }; all_required: { diff: number; ci95: [number, number] } };
type Cell = { deadline: number; arms: Record<string, ArmSum>; paired_vs_static_loop: Record<string, Pair>; paired: Record<string, Pair> };
type Grid = { metadata: Record<string, unknown>; cells: Record<string, Cell> };

const ARMS = ["adapt_final", "adapt_final_dx", "adapt_cal", "adapt_w7", "static_loop", "static", "random_eligible", "no_replan"];
const fmt = (x: unknown, d = 3) => (typeof x === "number" ? x.toFixed(d) : "—");

export default function Evaluation() {
  const q = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation });
  const [horizon, setHorizon] = useState<"h7" | "h14" | "h21" | "hw7">("h14");
  const [budget, setBudget] = useState<"B10" | "B15">("B15");
  const grid = q.data?.files.find((f) => f.name === "final_grid.json")?.data as Grid | undefined;
  const cells = useMemo(() => Object.entries(grid?.cells ?? {}), [grid]);
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <LoadingCard label="Loading results" />;
  if (!grid)
    return (
      <EmptyState title="Final grid not found">
        Run <code>python experiments/run_final_grid.py</code> to produce experiments/results/final_grid.json.
      </EmptyState>
    );

  const shown = cells.filter(([k]) => k.includes(`|${budget}|`) && k.endsWith(`|${horizon}`));
  const forest = shown.map(([k, c]) => ({ k: k.split("|").filter((x) => !x.startsWith("B") && !x.startsWith("h")).join(" · "), p: c.paired_vs_static_loop.adapt_final?.goal_mastery }));
  const violations = ARMS.map((a) => ({ a, v: cells.reduce((s, [, c]) => s + (c.arms[a]?.executed_prereq_violations ?? 0), 0) }));
  const md = grid.metadata;

  const exportCsv = () => {
    const head = ["cell", "arm", "n", "goal_mastery", "all_required", "exec_violations", "false_mastery", "utilisation", "km_median", "km_rmst", "brier", "auc", "diff_vs_static_loop", "ci_lo", "ci_hi"];
    const lines = [head.join(",")];
    for (const [k, c] of cells)
      for (const a of ARMS) {
        const s = c.arms[a];
        if (!s) continue;
        const p = c.paired_vs_static_loop[a]?.goal_mastery;
        lines.push([k, a, s.n, s.goal_mastery_rate, s.all_required_rate, s.executed_prereq_violations, s.false_mastery_rate, s.minute_utilisation, s.km_median_minutes_to_mastery, s.km_rmst_minutes_to_mastery, s.brier, s.auc, p?.diff, p?.ci95[0], p?.ci95[1]].map((x) => x ?? "").join(","));
      }
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "final_grid.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4" data-testid="evaluation">
      <Card
        title="Final grid (pre-registered, held-out odd seeds)"
        actions={
          <Button size="sm" kind="secondary" onClick={exportCsv} testId="export-csv">
            Export CSV
          </Button>
        }
      >
        <p className="flex flex-wrap gap-2 text-sm">
          <Chip tone="neutral">{cells.length} cells</Chip>
          <Chip tone="neutral">N = {String(md.n_per_cell)} per cell, {String(md.n_headline)} headline</Chip>
          <Chip tone="neutral">calibration winner {String(md.calibration_winner)}</Chip>
          <Chip tone="neutral" title={String(md.code_hash)}>code {String(md.code_hash).slice(0, 8)}</Chip>
          <Chip tone="remediation">Simulated learners (worlds S0, S1, S4, S4-fitted); results are synthetic</Chip>
        </p>
      </Card>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card
          title="Goal mastery: adapt (final) − static_loop, 95% CI"
          actions={
            <span className="flex gap-2">
              <Segmented label="Budget" value={budget} options={["B10", "B15"] as const} onChange={setBudget} />
              <Segmented label="Horizon" value={horizon} options={["hw7", "h7", "h14", "h21"] as const} onChange={setHorizon} />
            </span>
          }
        >
          <Forest rows={forest} />
        </Card>
        <Card title="Executed prerequisite violations, all cells (log scale)">
          <LogBars rows={violations} />
        </Card>
        <Card title="In-loop reliability (all cells, per world)">
          <Reliability cells={cells} />
        </Card>
        <Card title="Headline cell">
          <Headline cell={grid.cells[`${String(md.headline_cell).split("|").slice(0, 2).join("|")}|B15|calm|h14`]} />
        </Card>
      </div>
    </div>
  );
}

function Forest({ rows }: { rows: { k: string; p?: { diff: number; ci95: [number, number] } }[] }) {
  const W = 620,
    rowH = 22,
    left = 230,
    H = rows.length * rowH + 30;
  const x = (v: number) => left + ((v + 1) / 2) * (W - left - 10);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Forest plot of goal-mastery differences vs static_loop">
      <line x1={x(0)} x2={x(0)} y1={0} y2={H - 20} stroke="var(--text-faint)" strokeDasharray="4 3" />
      {[-1, -0.5, 0, 0.5, 1].map((t) => (
        <text key={t} x={x(t)} y={H - 4} textAnchor="middle" fontSize={11} fill="var(--text-faint)">
          {t > 0 ? `+${t}` : t}
        </text>
      ))}
      {rows.map((r, i) => {
        const y = i * rowH + 12;
        if (!r.p) return null;
        const sig = r.p.ci95[0] > 0 ? "var(--mastered)" : r.p.ci95[1] < 0 ? "var(--violation)" : "var(--text-muted)";
        return (
          <g key={r.k}>
            <text x={4} y={y + 4} fontSize={12} fill="var(--text)">
              {r.k}
            </text>
            <line x1={x(r.p.ci95[0])} x2={x(r.p.ci95[1])} y1={y} y2={y} stroke={sig} strokeWidth={2} />
            <circle cx={x(r.p.diff)} cy={y} r={4} fill={sig} />
            <text x={W - 4} y={y + 4} fontSize={11} textAnchor="end" fill="var(--text-faint)">
              {r.p.diff >= 0 ? "+" : ""}
              {r.p.diff.toFixed(3)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function LogBars({ rows }: { rows: { a: string; v: number }[] }) {
  const max = Math.max(10, ...rows.map((r) => r.v));
  const scale = (v: number) => (v <= 0 ? 0 : Math.log10(v + 1) / Math.log10(max + 1));
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.a} className="flex items-center gap-3 text-sm">
          <span className="w-36">{r.a}</span>
          <div className="h-3 flex-1 rounded-full bg-[var(--surface-3)]">
            <div className="h-3 rounded-full" style={{ width: `${scale(r.v) * 100}%`, background: r.v ? "var(--violation)" : "var(--mastered)" }} />
          </div>
          <span className="tabular w-20 text-right font-mono" style={{ color: r.v ? "var(--violation)" : "var(--mastered)" }}>
            {r.v === 0 ? "✓ 0" : r.v.toLocaleString()}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Reliability({ cells }: { cells: [string, Cell][] }) {
  const worlds = ["S0", "S1", "S4", "S4F"];
  const pool = (w: string, arm: string) => {
    const n = 20;
    const acc = { cnt: Array(n).fill(0), sp: Array(n).fill(0), sy: Array(n).fill(0) };
    for (const [k, c] of cells) {
      if (!k.startsWith(`${w}|`)) continue;
      const b = c.arms[arm]?.calibration_bins;
      if (!b) continue;
      for (let i = 0; i < n; i++) {
        acc.cnt[i] += b.pos[i] + b.neg[i];
        acc.sp[i] += b.sum_p[i];
        acc.sy[i] += b.sum_y[i];
      }
    }
    return acc.cnt.map((c, i) => (c ? { x: acc.sp[i] / c, y: acc.sy[i] / c } : null)).filter(Boolean) as { x: number; y: number }[];
  };
  const S = 140;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {worlds.map((w) => (
        <figure key={w}>
          <svg viewBox={`0 0 ${S} ${S}`} className="w-full rounded border border-[var(--border)]" role="img" aria-label={`Reliability diagram ${w}`}>
            <line x1={0} y1={S} x2={S} y2={0} stroke="var(--text-faint)" strokeDasharray="3 3" />
            {(["adapt_w7", "adapt_final"] as const).map((arm) =>
              pool(w, arm).map((p, i) => <circle key={`${arm}${i}`} cx={p.x * S} cy={S - p.y * S} r={3} fill={ARM_COLOR[arm]} />),
            )}
          </svg>
          <figcaption className="mt-1 text-center text-xs text-[var(--text-muted)]">{w}</figcaption>
        </figure>
      ))}
      <p className="col-span-full text-xs text-[var(--text-muted)]">
        <span style={{ color: ARM_COLOR.adapt_w7 }}>●</span> adapt (W7) <span style={{ color: ARM_COLOR.adapt_final }}>●</span> adapt (final); x = predicted P(correct), y =
        observed rate; the diagonal is perfect calibration.
      </p>
    </div>
  );
}

function Headline({ cell }: { cell?: Cell }) {
  if (!cell) return <p className="text-[var(--text-muted)]">Headline cell not in the results.</p>;
  return (
    <table className="tabular w-full text-left text-sm">
      <thead className="text-[var(--text-muted)]">
        <tr className="border-b border-[var(--border)]">
          <th className="py-1">Arm</th>
          <th>Goal</th>
          <th>All req.</th>
          <th>False m.</th>
          <th>Util.</th>
          <th>KM median</th>
          <th>Brier</th>
          <th>Δ vs static_loop</th>
        </tr>
      </thead>
      <tbody>
        {ARMS.filter((a) => cell.arms[a]).map((a) => {
          const s = cell.arms[a];
          const p = cell.paired_vs_static_loop[a]?.goal_mastery;
          return (
            <tr key={a} className="border-b border-[var(--border)]">
              <td className="py-1">{a}</td>
              <td className="font-mono">{fmt(s.goal_mastery_rate, 3)}</td>
              <td className="font-mono">{fmt(s.all_required_rate, 3)}</td>
              <td className="font-mono">{fmt(s.false_mastery_rate, 3)}</td>
              <td className="font-mono">{fmt(s.minute_utilisation, 2)}</td>
              <td className="font-mono">{s.km_median_minutes_to_mastery ?? "censored"}</td>
              <td className="font-mono">{fmt(s.brier, 3)}</td>
              <td className="font-mono">{p ? `${p.diff >= 0 ? "+" : ""}${p.diff.toFixed(3)} [${p.ci95[0].toFixed(3)}, ${p.ci95[1].toFixed(3)}]` : "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
