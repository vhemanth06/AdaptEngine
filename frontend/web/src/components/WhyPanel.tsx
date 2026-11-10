import { useQuery } from "@tanstack/react-query";
import { api, type Session, type TraceRecord } from "../api/client";
import { C } from "./ui";

const REASON: Record<string, string> = {
  RANKED_TOP: "Highest score among new work whose prerequisites are done",
  REVIEW_DUE: "Projected recall fell below the review threshold: spaced review",
  REMEDIATION_INSERTED: "Remediation: repeat lesson after a wrong answer left p below the threshold",
  ORACLE_ASSIGNED: "Placed by the exact packing solver because the greedy schedule overshot the deadline",
  DOES_NOT_FIT_REMAINING_TIME: "Did not fit in the minutes left that day",
  REPLAN_PRESERVED_COMPLETED: "Already done; kept out of the new plan",
  CONSOLIDATION: "Verification practice: every required concept is believed mastered and time remains (D49)",
  VERIFICATION_PROBE: "One hard item before unlocking dependents: the evidence came mostly from easy items (D50)",
  HORIZON_AWARE_STRICT: "Plenty of slack before the deadline, so mastery needs more certainty (D51)",
  REVIEW_CAP: "Review deferred: today's review share is used up while new content is pending",
  CPSAT_ASSIGNED: "Placed by the CP-SAT exact scheduler (D60)",
  AGENT_PROPOSED: "Placed by an agent-proposed plan that passed every engine check (D57)",
};

const COMPONENT_MAX: Record<string, number> = { review: 1, unlock: 7, fit: 1 };

function TraceItem({ r }: { r: TraceRecord }) {
  const comps = (r.score_components ?? {}) as Record<string, number>;
  const reason = String(r.reason ?? "");
  return (
    <li className={`rounded-lg border p-3 ${r.superseded ? "border-dashed opacity-60" : "border-slate-300"}`}>
      <div className="font-semibold">
        {String(r.decision)} {r.day != null && <>· day {String(r.day)}</>}
        {r.superseded ? " · superseded greedy attempt" : ""}
      </div>
      <div>
        <code>{reason}</code> {REASON[reason] && <span className="text-slate-700">— {REASON[reason]}</span>}
      </div>
      {typeof r.score === "number" && (
        <div className="mt-2 space-y-1">
          <div>
            Score <b className="font-mono">{r.score.toFixed(3)}</b> = review + unlock + fit
          </div>
          {Object.entries(comps).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2">
              <span className="w-16">{k}</span>
              <div className="h-4 flex-1 rounded bg-slate-200">
                <div
                  className="h-4 rounded"
                  style={{ width: `${Math.min(100, (v / (COMPONENT_MAX[k] ?? 1)) * 100)}%`, background: C.blue }}
                />
              </div>
              <span className="w-16 text-right font-mono">{v.toFixed(2)}</span>
            </div>
          ))}
          {typeof r.projected_p === "number" && (
            <div className="text-base text-slate-600">Projected p after this step: {r.projected_p.toFixed(2)}</div>
          )}
        </div>
      )}
    </li>
  );
}

export default function WhyPanel({ session, aid }: { session: Session; aid: string | null }) {
  const c = session.context;
  const q = useQuery({
    queryKey: ["trace", session.session_id, aid, session.events.length, c.goal, c.budget, c.deadline_day],
    queryFn: () => api.trace(session.session_id, aid!),
    enabled: !!aid && !!session.plan,
  });
  if (!aid) return <p className="text-slate-600">Click an activity card to see why the engine scheduled it.</p>;
  if (!q.data) return <p>Loading trace…</p>;
  const live = q.data.records.filter((r) => !r.superseded);
  const old = q.data.records.filter((r) => r.superseded);
  return (
    <div className="space-y-4" data-testid="why">
      <h3 className="text-lg font-semibold">
        Why <code>{aid}</code>?
      </h3>
      <ul className="space-y-2">
        {live.map((r, i) => (
          <TraceItem key={i} r={r} />
        ))}
      </ul>
      {q.data.deferred_same_day.length > 0 && (
        <div>
          <h4 className="font-semibold">Deferred alternatives on the same day</h4>
          <ul className="space-y-1">
            {q.data.deferred_same_day.map((r, i) => (
              <li key={i}>
                <code>{String(r.activity_id)}</code> ({String(r.duration)} min, {String(r.remaining_budget)} left):{" "}
                {REASON[String(r.reason)] ?? String(r.reason)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {old.length > 0 && (
        <details>
          <summary>{old.length} superseded greedy record(s)</summary>
          <ul className="mt-2 space-y-2">
            {old.map((r, i) => (
              <TraceItem key={i} r={r} />
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
