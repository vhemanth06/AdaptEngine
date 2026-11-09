import { useState } from "react";
import type { Ctx } from "../ctx";
import { Card, StatusBadge } from "../components/ui";
import PlanTimeline from "../components/PlanTimeline";
import WhyPanel from "../components/WhyPanel";
import NoSession from "./NoSession";

export default function PlanPage({ session, cur, go }: Ctx) {
  const [aid, setAid] = useState<string | null>(null);
  if (!session?.plan) return <NoSession go={go} />;
  const plan = session.plan;
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_480px]">
      <Card
        title={
          <span className="flex items-center gap-3">
            Plan <StatusBadge plan={plan} />
            {session.replan_ms != null && <span className="text-base font-normal">({session.replan_ms} ms)</span>}
          </span>
        }
      >
        {plan.status !== "FEASIBLE" && (
          <p className="mb-2">
            Short by {plan.shortfall_days} day(s). {plan.options.join(" · ")}
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
      <Card title="Why? (from the engine trace)">
        <WhyPanel session={session} aid={aid} />
      </Card>
    </div>
  );
}
