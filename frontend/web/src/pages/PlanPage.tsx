import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Ctx } from "../ctx";
import { Button, Card, Chip, ErrorBox, StatusBadge } from "../components/ui";
import PlanTimeline from "../components/PlanTimeline";
import WhyPanel from "../components/WhyPanel";
import NoSession from "./NoSession";

export default function PlanPage({ session, cur, go }: Ctx) {
  const [aid, setAid] = useState<string | null>(null);
  if (!session?.plan) return <NoSession go={go} />;
  const plan = session.plan;
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_460px]">
      <div className="space-y-4">
        <Card
          title={
            <span className="flex items-center gap-3">
              Plan <StatusBadge plan={plan} />
              {session.replan_ms != null && <span className="text-sm font-normal text-[var(--text-muted)]">({session.replan_ms} ms)</span>}
            </span>
          }
        >
          {plan.status !== "FEASIBLE" && (
            <p className="mb-2">
              Short by {plan.shortfall_days} day(s). {plan.options.join(" · ")}
            </p>
          )}
          {session.feasibility_warning && (
            <p className="mb-2">
              <Chip tone="remediation">⚠ {session.feasibility_warning}</Chip>
            </p>
          )}
          <PlanTimeline
            plan={plan}
            cur={cur}
            budget={session.effective?.budget ?? session.context.budget}
            selected={aid}
            onSelect={setAid}
          />
        </Card>
        <AgentProposal sid={session.session_id} />
      </div>
      <Card title="Why? (from the engine trace)">
        <WhyPanel session={session} aid={aid} />
      </Card>
    </div>
  );
}

// M.3: an agent proposes a whole plan; the engine validates it (D57). Display only.
function AgentProposal({ sid }: { sid: string }) {
  const m = useMutation({ mutationFn: (mode: "agent" | "agent_bad") => api.propose(sid, mode) });
  const r = m.data;
  return (
    <Card
      title="Ask the agent for a plan"
      testId="agent-proposal"
      actions={
        <span className="flex gap-2">
          <Button size="sm" kind="secondary" testId="propose" onClick={() => m.mutate("agent")} disabled={m.isPending}>
            Ask the agent
          </Button>
          <Button size="sm" kind="ghost" testId="propose-bad" onClick={() => m.mutate("agent_bad")} disabled={m.isPending}>
            Force a bad proposal
          </Button>
        </span>
      }
    >
      <ErrorBox error={m.error} />
      {!r ? (
        <p className="text-[var(--text-muted)]">
          The agent proposes; the engine checks ids, budget, deadline, prerequisite order and the goal; on any failure the
          deterministic plan stays.
        </p>
      ) : (
        <div className="space-y-2" data-testid="proposal-result">
          <p className="flex flex-wrap items-center gap-2">
            {r.accepted ? <Chip tone="mastered">✓ accepted by engine</Chip> : <Chip tone="violation">✗ rejected → deterministic plan kept</Chip>}
            <span className="text-sm text-[var(--text-muted)]">provider: {r.agent_label}</span>
          </p>
          {r.rationale && <p className="italic">“{r.rationale}”</p>}
          {r.violations.length > 0 && (
            <ul className="list-disc pl-6">
              {r.violations.map((v, i) => (
                <li key={i}>
                  <code>{String(v.rule)}</code>
                  {v.day != null && <> on day {String(v.day)}</>}
                  {v.activity_id != null && <> · {String(v.activity_id)}</>}
                  {Array.isArray(v.missing_prerequisites) && <> · missing {(v.missing_prerequisites as string[]).join(", ")}</>}
                </li>
              ))}
            </ul>
          )}
          <p className="text-sm text-[var(--text-muted)]">
            Proposed {r.proposed_days.length} days vs engine {r.reference_days.length} days.
          </p>
        </div>
      )}
    </Card>
  );
}
