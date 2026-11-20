import { useState } from "react";
import type { Ctx } from "../ctx";
import { Card, Chip, StatusBadge } from "../components/ui";
import PlanTimeline from "../components/PlanTimeline";
import WhyPanel from "../components/WhyPanel";
import NoSession from "./NoSession";

export default function PlanPage({ session, cur, go }: Ctx) {
  const [aid, setAid] = useState<string | null>(null);
  if (!session?.plan) return <NoSession go={go} />;
  const plan = session.plan;
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_460px]">
      <Card
        title={
          <span className="flex items-center gap-3">
            Plan <StatusBadge plan={plan} />
            {session.replan_ms != null && <span className="text-sm font-normal text-[var(--text-muted)]">({session.replan_ms} ms)</span>}
          </span>
        }
      >
        {plan.status !== "FEASIBLE" && (
          <div className="mb-3 space-y-1" data-testid="plan-verdict">
            <p>
              Short by <b>{plan.shortfall_days} day(s)</b>.
              {plan.reason === "CPSAT_INFEASIBLE" && (
                <>
                  {" "}
                  <Chip tone="accent">exact (CP-SAT proved it)</Chip>
                </>
              )}
            </p>
            {plan.options.length > 0 && (
              <ul className="list-disc pl-6">
                {plan.options.map((o) => (
                  <li key={o}>{o}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        <PlanTimeline
          plan={plan}
          cur={cur}
          budget={session.effective?.budget ?? session.context.budget}
          selected={aid}
          onSelect={setAid}
        />
      </Card>
      <Card title="Why? (from the engine trace)">
        <WhyPanel session={session} aid={aid} />
      </Card>
    </div>
  );
}
