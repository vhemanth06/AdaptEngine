import type { ReactNode } from "react";
import type { Ctx } from "../ctx";
import { Button, Card, Chip, EmptyState, StatusBadge, cx } from "../components/ui";

function Kpi({ label, value, sub, testId }: { label: string; value: ReactNode; sub?: ReactNode; testId?: string }) {
  return (
    <Card testId={testId}>
      <div className="text-sm text-[var(--text-muted)]">{label}</div>
      <div className="tabular mt-1 text-3xl font-semibold tracking-tight">{value}</div>
      {sub && <div className="mt-1 text-sm text-[var(--text-faint)]">{sub}</div>}
    </Card>
  );
}

export default function Overview({ session, cur, go }: Ctx) {
  if (!session)
    return (
      <EmptyState title="No learner yet" action={<Button onClick={() => go("setup")}>Set a goal</Button>}>
        Choose a goal, a deadline and daily minutes; the engine answers with a plan or an honest "not feasible".
      </EmptyState>
    );
  const eff = session.effective;
  const goal = session.context.goal;
  const path = new Set([goal]);
  const pre = new Map(cur?.concepts.map((c) => [c.concept_id, c.prerequisites]) ?? []);
  const stack = [goal];
  while (stack.length) for (const p of pre.get(stack.pop()!) ?? []) if (!path.has(p)) (path.add(p), stack.push(p));
  const onPath = session.concepts.filter((c) => path.has(c.concept_id));
  const mastered = onPath.filter((c) => c.evidence_mastered).length;
  const used = session.events.reduce((a, e) => a + (e.minutes_elapsed ?? 0), 0);
  const available = session.context.deadline_day * session.context.budget;
  const daysLeft = eff ? eff.deadline_day - eff.current_day + 1 : 0;
  const steps: [string, boolean, Parameters<typeof go>[0]][] = [
    ["Diagnose", session.diagnostic.done, "diagnostic"],
    ["Plan", !!session.plan, "plan"],
    ["Study", session.events.some((e) => e.kind === "COMPLETED"), "study"],
    ["Adapt", session.events.some((e) => e.kind !== "COMPLETED"), "disruptions"],
  ];
  const next = steps.find((s) => !s[1]);
  return (
    <div className="space-y-4" data-testid="overview">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Kpi testId="kpi-mastered" label="Goal-path concepts mastered (evidence)" value={`${mastered} / ${onPath.length}`} sub={`goal ${goal}`} />
        <Kpi label="Minutes used / available" value={`${used} / ${available}`} sub={`${session.context.budget} min/day`} />
        <Kpi label="Days left" value={eff ? daysLeft : "—"} sub={eff ? `today is day ${eff.current_day}` : "past the deadline"} />
        <Kpi label="Plan status" value={<StatusBadge plan={session.plan} />} sub={session.replan_ms != null ? `last replan ${session.replan_ms} ms` : undefined} />
      </div>
      <Card title="Learning journey">
        <ol className="flex flex-wrap items-center gap-3" aria-label="Journey">
          {steps.map(([label, done, tab], i) => (
            <li key={label} className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => go(tab)}
                className={cx(
                  "flex items-center gap-2 rounded-full border px-4 py-2",
                  done ? "border-[var(--mastered)] text-[var(--mastered)]" : next?.[0] === label ? "border-[var(--accent)] text-[var(--accent)]" : "border-[var(--border-strong)] text-[var(--text-muted)]",
                )}
              >
                <span aria-hidden>{done ? "✓" : i + 1}</span> {label}
                <span className="sr-only">{done ? "(done)" : "(to do)"}</span>
              </button>
              {i < steps.length - 1 && <span aria-hidden className="text-[var(--text-faint)]">→</span>}
            </li>
          ))}
        </ol>
        {next && (
          <p className="mt-3 text-[var(--text-muted)]">
            Next: <b>{next[0]}</b>.{" "}
            <Button size="sm" onClick={() => go(next[2])}>
              Continue
            </Button>
          </p>
        )}
        {session.feasibility_warning && (
          <p className="mt-3">
            <Chip tone="remediation">⚠ {session.feasibility_warning}</Chip>
          </p>
        )}
      </Card>
      <Card title="Recent activity">
        {session.events.length === 0 ? (
          <p className="text-[var(--text-muted)]">No study events yet.</p>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {session.events
              .slice(-8)
              .reverse()
              .map((e, i) => (
                <li key={i} className="flex items-center gap-3 py-2">
                  <Chip tone="neutral">day {e.day}</Chip>
                  <span className="font-medium">{e.kind}</span>
                  {e.activity_id && <code>{e.activity_id}</code>}
                  {e.correct != null && <Chip tone={e.correct ? "mastered" : "remediation"}>{e.correct ? "✓ right" : "✗ wrong"}</Chip>}
                  {e.value != null && <span className="text-[var(--text-muted)]">→ {e.value}</span>}
                </li>
              ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
