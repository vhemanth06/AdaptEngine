import type { Curriculum, Plan } from "../api/client";
import { C, planDays } from "./ui";

const TAG: Record<string, [string, string]> = {
  REMEDIATION_INSERTED: ["Remediation", C.vermillion],
  REVIEW_DUE: ["Review", C.purple],
  ORACLE_ASSIGNED: ["Solver", C.orange],
};

export default function PlanTimeline({
  plan,
  cur,
  budget,
  selected,
  onSelect,
  highlight,
  testId = "timeline",
}: {
  plan: Plan;
  cur?: Curriculum;
  budget: number;
  selected?: string | null;
  onSelect?: (aid: string) => void;
  highlight?: Set<string>;
  testId?: string;
}) {
  const days = planDays(plan);
  const reasonAt = new Map<string, string>();
  for (const r of plan.trace) {
    if (r.decision === "SELECTED") reasonAt.set(`${r.day}|${r.activity_id}`, String(r.reason));
  }
  if (!days.length) return <p className="text-slate-600">No days scheduled.</p>;
  return (
    <div data-testid={testId}>
      {plan.status !== "FEASIBLE" && (
        <p className="mb-2 font-semibold" style={{ color: C.vermillion }}>
          Best-effort schedule (the goal itself does not fit)
        </p>
      )}
      <div className="flex gap-3 overflow-x-auto pb-2">
        {days.map((d) => (
          <div key={d.day} className="w-52 shrink-0 rounded-lg border border-slate-300 bg-slate-50 p-2">
            <div className="flex justify-between font-semibold">
              <span>Day {d.day}</span>
              <span className="font-mono">
                {d.duration}/{budget} min
              </span>
            </div>
            <div className="my-1 h-3 rounded bg-slate-200" title={`${d.duration} of ${budget} minutes`}>
              <div
                className="h-3 rounded"
                style={{ width: `${Math.min(100, (d.duration / budget) * 100)}%`, background: d.duration > budget ? C.vermillion : C.blue }}
              />
            </div>
            <ul className="space-y-1">
              {d.activities.map((aid, i) => {
                const a = cur?.activities.find((x) => x.activity_id === aid);
                const tag = TAG[reasonAt.get(`${d.day}|${aid}`) ?? ""];
                const sel = selected === aid;
                return (
                  <li key={`${aid}-${i}`}>
                    <button
                      type="button"
                      data-testid={`card-${aid}`}
                      onClick={() => onSelect?.(aid)}
                      className={`w-full rounded-md border bg-white px-2 py-1 text-left text-base ${
                        sel ? "border-4 border-slate-900" : "border-slate-300"
                      } ${highlight?.has(aid) ? "ring-4 ring-[#E69F00]" : ""}`}
                    >
                      <div className="flex justify-between">
                        <code>{aid}</code>
                        <span className="font-mono">{a?.duration}′</span>
                      </div>
                      <div className="text-sm text-slate-600">
                        {a?.type === "LESSON" ? "Lesson" : `Exercise d=${a?.difficulty}`}
                        {tag && (
                          <span className="ml-2 rounded px-1 font-semibold text-white" style={{ background: tag[1] }}>
                            {tag[0]}
                          </span>
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
