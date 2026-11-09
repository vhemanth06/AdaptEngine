import { useState } from "react";
import type { Ctx } from "../ctx";
import { Button, Card, ErrorBox, StatusBadge } from "../components/ui";
import PlanTimeline from "../components/PlanTimeline";
import NoSession from "./NoSession";

export default function Disruptions({ session, cur, sendEvent, lastEvent, go }: Ctx) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [budget, setBudget] = useState(5);
  if (!session) return <NoSession go={go} />;
  const eff = session.effective;

  const fire = async (body: Parameters<Ctx["sendEvent"]>[0], label: string) => {
    setBusy(true);
    setError(null);
    try {
      await sendEvent(body, label);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const ev = lastEvent && lastEvent.label !== "study" ? lastEvent : null;
  const moved = new Set(ev?.result.changes.map((c) => c.activity_id));
  const budgetNow = eff?.budget ?? session.context.budget;
  return (
    <div className="space-y-4">
      <Card title="Disrupt the plan">
        {!eff ? (
          <p>The session is past its deadline.</p>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <Button testId="missed-day" disabled={busy} onClick={() => fire({ kind: "MISSED" }, `Missed day ${eff.current_day}`)}>
              Missed day {eff.current_day}
            </Button>
            <span className="flex items-center gap-2">
              <select
                aria-label="New daily budget"
                className="rounded-lg border border-slate-400 bg-white px-3 py-2"
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
              >
                {(cur?.allowed_budgets ?? [5, 10, 15, 30]).map((b) => (
                  <option key={b} value={b}>
                    {b} min
                  </option>
                ))}
              </select>
              <Button
                testId="budget-change"
                disabled={busy}
                onClick={() => fire({ kind: "BUDGET_CHANGED", value: budget }, `Budget ${budgetNow} → ${budget} min`)}
              >
                Change daily budget
              </Button>
            </span>
            <Button
              testId="deadline-cut"
              disabled={busy || eff.deadline_day - 2 < eff.current_day}
              onClick={() =>
                fire({ kind: "DEADLINE_CHANGED", value: eff.deadline_day - 2 }, `Deadline ${eff.deadline_day} → ${eff.deadline_day - 2}`)
              }
            >
              Deadline −2 days
            </Button>
          </div>
        )}
        <ErrorBox error={error} />
      </Card>

      {ev && (
        <Card
          testId="diff"
          title={
            <span>
              {ev.label}: replanned in <span data-testid="latency">{ev.result.session.replan_ms} ms</span> (server-side)
            </span>
          }
        >
          <p className="mb-3">
            {ev.result.changes.length} activity move(s). Highlighted cards moved.
          </p>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div>
              <h3 className="mb-2 flex items-center gap-2 font-semibold">
                Before <StatusBadge plan={ev.oldPlan} />
              </h3>
              {ev.oldPlan && <PlanTimeline plan={ev.oldPlan} cur={cur} budget={budgetNow} highlight={moved} testId="old-plan" />}
            </div>
            <div>
              <h3 className="mb-2 flex items-center gap-2 font-semibold">
                After <StatusBadge plan={ev.result.session.plan} />
              </h3>
              {ev.result.session.plan && (
                <PlanTimeline plan={ev.result.session.plan} cur={cur} budget={budgetNow} highlight={moved} testId="new-plan" />
              )}
            </div>
          </div>
          <table className="mt-3 text-left">
            <thead>
              <tr className="border-b">
                <th className="pr-6">Activity</th>
                <th className="pr-6">Old day</th>
                <th>New day</th>
              </tr>
            </thead>
            <tbody>
              {ev.result.changes.map((c) => (
                <tr key={c.activity_id} className="border-b border-slate-200">
                  <td className="pr-6">
                    <code>{c.activity_id}</code>
                  </td>
                  <td>{c.old_day ?? "—"}</td>
                  <td>{c.new_day ?? "dropped"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
