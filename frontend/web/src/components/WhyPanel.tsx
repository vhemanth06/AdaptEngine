import { useQuery } from "@tanstack/react-query";
import { api, type Session, type TraceRecord } from "../api/client";
import { C } from "./ui";

// Engine reason codes in words (display only, D45)
const REASON: Record<string, string> = {
  RANKED_TOP: "Highest score among new work whose prerequisites are done",
  REVIEW_DUE: "Projected recall fell below the review threshold: spaced review",
  REMEDIATION_INSERTED: "Remediation: repeat lesson after a wrong answer left p below the threshold",
  ORACLE_ASSIGNED: "Placed by the exact packing solver because the greedy schedule overshot the deadline",
  DOES_NOT_FIT_REMAINING_TIME: "Did not fit in the minutes left that day",
  REPLAN_PRESERVED_COMPLETED: "Already done; kept out of the new plan",
  CPSAT_ASSIGNED: "Placed by the CP-SAT scheduler (D62)",
  REVIEW_SCHEDULED: "Spaced review placed by CP-SAT inside its due window (D65)",
  CONFIRMATION_CHECK: "Short check instead of the full workload (D57)",
  CONFIRMED_BY_DIAGNOSTIC: "Left out of the plan: the diagnostic's belief was confirmed by its checks (D57)",
  ALREADY_EVIDENCE_MASTERED: "Left out of the plan: already mastered by evidence",
};

const BECAUSE = (b: string) =>
  b === "PLAN_START"
    ? "the start of the plan"
    : b === "PREVIOUS_ITEM_OF_CONCEPT"
      ? "the previous item of this concept"
      : b.startsWith("PREREQUISITE_")
        ? `prerequisite ${b.slice("PREREQUISITE_".length).replace(/_FINISHES$/, "")} finishes`
        : b;

const COMPONENT_MAX: Record<string, number> = { review: 1, unlock: 7, fit: 1 };

function CpsatPlacement({ r }: { r: TraceRecord }) {
  const full = r.full_days as number[] | undefined;
  return (
    <div className="mt-1 space-y-0.5" data-testid="why-cpsat">
      <div>
        Earliest possible: day {String(r.earliest_possible_day)}, because {BECAUSE(String(r.earliest_because))}.
      </div>
      <div className="text-[var(--text-muted)]">
        {r.placement === "AT_EARLIEST"
          ? "Placed at the earliest day."
          : r.placement === "BUDGET_FULL"
            ? `Days ${full?.[0]}–${full?.[1]} were full.`
            : "Moved by a lower-priority objective (concept finish, reviews or an even load)."}
      </div>
    </div>
  );
}

function TraceItem({ r }: { r: TraceRecord }) {
  const comps = (r.score_components ?? {}) as Record<string, number>;
  const reason = String(r.reason ?? "");
  return (
    <li className={`rounded-[var(--radius)] border p-3 ${r.superseded ? "border-dashed opacity-60" : "border-[var(--border-strong)]"}`}>
      <div className="font-semibold">
        {String(r.decision)} {r.day != null && <>· day {String(r.day)}</>}
        {r.superseded ? " · superseded greedy attempt" : ""}
      </div>
      <div>
        <code>{reason}</code> {REASON[reason] && <span className="text-[var(--text-muted)]">— {REASON[reason]}</span>}
      </div>
      {r.earliest_possible_day != null && <CpsatPlacement r={r} />}
      {reason === "REVIEW_SCHEDULED" && <div className="mt-1">Spaced review #{String(r.review_number)}</div>}
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
            <div className="text-sm text-[var(--text-muted)]">Projected p after this step: {r.projected_p.toFixed(2)}</div>
          )}
        </div>
      )}
    </li>
  );
}

const num = (x: unknown, d = 2) => (typeof x === "number" ? x.toFixed(d) : String(x));

export default function WhyPanel({ session, aid }: { session: Session; aid: string | null }) {
  const c = session.context;
  const q = useQuery({
    queryKey: ["trace", session.session_id, aid, session.events.length, c.goal, c.budget, c.deadline_day],
    queryFn: () => api.trace(session.session_id, aid!),
    enabled: !!aid && !!session.plan,
  });
  const trace = session.plan?.trace ?? [];
  const solve = trace.find((r) => r.decision === "CPSAT_SOLVE");
  const omitted = trace.filter((r) => r.reason === "CONFIRMED_BY_DIAGNOSTIC");
  const footer = (
    <>
      {omitted.length > 0 && (
        <div className="text-sm">
          <h4 className="font-semibold">Confirmed by the diagnostic</h4>
          {omitted.map((r) => (
            <p key={String(r.concept_id)}>
              <code>{String(r.concept_id)}</code>: {REASON.CONFIRMED_BY_DIAGNOSTIC} (p {num(r.p)}).
            </p>
          ))}
        </div>
      )}
      <details data-testid="raw-trace">
        <summary className="cursor-pointer">Raw trace ({trace.length} records)</summary>
        {solve && (
          <p className="mt-2 text-sm" data-testid="cpsat-solve">
            CP-SAT solve: {String(solve.status)} · objectives {JSON.stringify(solve.objectives)} · work units{" "}
            {String(solve.work_units)} · seed {String(solve.seed)}
          </p>
        )}
        <pre className="mt-2 max-h-80 overflow-auto rounded-[var(--radius)] bg-[var(--surface-2)] p-2 text-xs">
          {JSON.stringify(aid && q.data ? q.data.records : trace, null, 1)}
        </pre>
      </details>
    </>
  );
  if (!aid)
    return (
      <div className="space-y-4">
        <p className="text-[var(--text-muted)]">Click an activity card to see why the engine scheduled it.</p>
        {footer}
      </div>
    );
  if (!q.data) return <p>Loading trace…</p>;
  const live = q.data.records.filter((r) => !r.superseded);
  const old = q.data.records.filter((r) => r.superseded);
  const conf = q.data.confirmation;
  return (
    <div className="space-y-4" data-testid="why">
      <h3 className="text-lg font-semibold">
        Why <code>{aid}</code>?
      </h3>
      {conf && (
        <div className="rounded-[var(--radius)] border p-3" style={{ borderColor: "var(--check)", background: "var(--check-soft)" }} data-testid="why-confirmation">
          <div className="font-semibold">⧗ Confirmation check for {String(conf.concept_id)}</div>
          <p>
            Short check instead of the full workload: {String(conf.n_checks)} check(s), {String(conf.minutes_checks)} min vs{" "}
            {String(conf.minutes_full)} min; pass probability {num(conf.p_pass)}.
          </p>
          <p className="text-sm text-[var(--text-muted)]">
            The diagnostic believes {String(conf.concept_id)} is known (p {num(conf.p)}); a wrong answer sends it back to normal study.
          </p>
        </div>
      )}
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
      {footer}
    </div>
  );
}
