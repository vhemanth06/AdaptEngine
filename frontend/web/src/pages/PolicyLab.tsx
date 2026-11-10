import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type PolicyPreview } from "../api/client";
import type { Ctx } from "../ctx";
import { Button, Card, Chip, EmptyState, ErrorBox, Segmented } from "../components/ui";

const POLICIES = ["deterministic", "bandit_frozen", "bandit_updating", "random", "agent", "agent_bad"] as const;
type Pol = (typeof POLICIES)[number];
const LABEL: Record<Pol, string> = {
  deterministic: "Deterministic (engine)",
  bandit_frozen: "Bandit · frozen",
  bandit_updating: "Bandit · updating",
  random: "Random",
  agent: "LLM agent",
  agent_bad: "Agent · forced bad output",
};

type PolicyEval = {
  cells?: Record<string, Record<string, Record<string, unknown>> & { ope_frozen?: Record<string, Record<string, unknown> | number> }>;
};

export default function PolicyLab({ session, sid, go }: Ctx) {
  const [pol, setPol] = useState<Pol>("bandit_frozen");
  const preview = useMutation({ mutationFn: (p: Pol) => api.policyPreview(sid!, p) });
  const evalQ = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation });
  const pe = evalQ.data?.files.find((f) => f.name === "w8_policy_eval.json")?.data as PolicyEval | undefined;

  if (!session?.plan)
    return (
      <EmptyState title="Make a plan first" action={<Button onClick={() => go("setup")}>Go to Setup</Button>}>
        The Policy Lab re-ranks the engine's own eligible candidates for the current learner.
      </EmptyState>
    );
  return (
    <div className="space-y-4">
      <Card
        title="Policy switch"
        actions={
          <Button testId="run-policy" onClick={() => preview.mutate(pol)} disabled={preview.isPending}>
            {preview.isPending ? "Asking…" : "Show today's choices"}
          </Button>
        }
      >
        <div className="flex flex-wrap items-center gap-3">
          <Segmented label="Ranking policy" value={pol} options={POLICIES} onChange={setPol} />
        </div>
        <p className="mt-3 text-sm text-[var(--text-muted)]">
          {LABEL[pol]}: only the bandit learns from feedback (D53); the LLM agent is a non-learning proposer (D55). Every policy sees
          the engine's top-5 eligible new-content candidates; the engine re-checks the answer and falls back on any failure.
        </p>
        <ErrorBox error={preview.error} onRetry={() => preview.mutate(pol)} />
      </Card>
      {preview.data && <Decisions data={preview.data} />}
      <PolicyEvaluation pe={pe} />
    </div>
  );
}

function Decisions({ data }: { data: PolicyPreview }) {
  return (
    <Card title={`Today under ${LABEL[data.policy as Pol]}`} testId="policy-decisions">
      {data.agent_label && <p className="mb-2 text-sm text-[var(--text-muted)]">Agent provider: {data.agent_label}</p>}
      <p className="mb-3">
        Today: {data.today ? data.today.activities.map((a) => <code key={a} className="mr-2">{a}</code>) : "nothing scheduled"}
      </p>
      {data.decisions.length === 0 && <p className="text-[var(--text-muted)]">Deterministic ranking: no policy decisions to log.</p>}
      <ol className="space-y-3">
        {data.decisions.map((d, i) => {
          const cands = (d.candidates as string[]) ?? [];
          const props = (d.propensities as number[] | undefined) ?? [];
          const ok = d.decision === "POLICY_SELECTED";
          return (
            <li key={i} className="rounded-[var(--radius)] border border-[var(--border)] p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="font-medium">Slot {String(d.slot)}</span>
                {ok ? (
                  <Chip tone="mastered">✓ accepted by engine</Chip>
                ) : d.reason === "SINGLE_CANDIDATE" ? (
                  <Chip tone="neutral">only one eligible option: engine order</Chip>
                ) : (
                  <Chip tone="violation" testId="fallback-badge">
                    ✗ {String(d.decision)} → deterministic ({String(d.reason)})
                  </Chip>
                )}
                {ok && d.propensity != null && <Chip tone="neutral">propensity {Number(d.propensity).toFixed(3)}</Chip>}
                <span className="text-sm text-[var(--text-muted)]">engine choice {String(d.deterministic_choice)}</span>
              </div>
              <ul className="space-y-1">
                {cands.map((c, k) => (
                  <li key={c} className="flex items-center gap-3">
                    <code className={`w-28 ${c === d.chosen ? "font-bold text-[var(--accent)]" : ""}`}>{c}</code>
                    {props.length > 0 && (
                      <div className="h-2 flex-1 rounded-full bg-[var(--surface-3)]" title={`P = ${props[k]?.toFixed(3)}`}>
                        <div className="h-2 rounded-full bg-[var(--accent)]" style={{ width: `${(props[k] ?? 0) * 100}%` }} />
                      </div>
                    )}
                    {c === d.chosen && <Chip tone="accent">chosen</Chip>}
                  </li>
                ))}
              </ul>
              {d.rationale != null && <p className="mt-2 italic">“{String(d.rationale)}”</p>}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

function PolicyEvaluation({ pe }: { pe?: PolicyEval }) {
  if (!pe?.cells) return <Card title="Frozen vs updating vs random">No policy evaluation results yet (run experiments/run_policy_eval.py).</Card>;
  const variants = ["deterministic", "bandit_frozen", "bandit_updating", "random"];
  const fmt = (x: unknown, d = 3) => (typeof x === "number" ? x.toFixed(d) : "—");
  return (
    <Card title="Frozen vs updating vs random (held-out seeds) and off-policy estimates" testId="policy-eval">
      <div className="overflow-x-auto">
        <table className="tabular w-full text-left text-sm">
          <thead className="text-[var(--text-muted)]">
            <tr className="border-b border-[var(--border)]">
              <th className="py-1">Cell</th>
              {variants.map((v) => (
                <th key={v}>{v}</th>
              ))}
              <th>OPE of frozen (IPS / SNIPS / DR, from random)</th>
              <th>simulated</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(pe.cells).map(([cell, c]) => {
              const ope = c.ope_frozen as Record<string, Record<string, number> | number> | undefined;
              const fr = (ope?.from_random ?? {}) as Record<string, number>;
              return (
                <tr key={cell} className="border-b border-[var(--border)]">
                  <td className="py-1">{cell}</td>
                  {variants.map((v) => (
                    <td key={v} className="font-mono">
                      {fmt((c[v] as Record<string, unknown>)?.goal_mastery_rate, 2)} · viol {String((c[v] as Record<string, unknown>)?.executed_violations ?? "—")}
                    </td>
                  ))}
                  <td className="font-mono">
                    {fmt(fr.ips)} / {fmt(fr.snips)} / {fmt(fr.dr)}
                  </td>
                  <td className="font-mono">{fmt(ope?.simulated_value)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-sm text-[var(--text-muted)]">Goal mastery rate · executed prerequisite violations per variant; value = mean learning progress per decision.</p>
    </Card>
  );
}
