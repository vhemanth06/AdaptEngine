import type { ReactNode } from "react";
import type { ConceptState, Curriculum, Plan, Session } from "../api/client";

// Okabe-Ito colour-blind-safe palette; every colour is paired with a text label.
export const C = {
  blue: "#0072B2",
  sky: "#56B4E9",
  green: "#009E73",
  orange: "#E69F00",
  vermillion: "#D55E00",
  purple: "#CC79A7",
  grey: "#8C8C8C",
};
export const ARM_COLOR: Record<string, string> = {
  adapt: C.blue,
  no_review: C.sky,
  no_replan: C.orange,
  static: C.purple,
};

export function Card({ title, children, testId }: { title?: ReactNode; children: ReactNode; testId?: string }) {
  return (
    <section className="rounded-xl border border-slate-300 bg-white p-5 shadow-sm" data-testid={testId}>
      {title && <h2 className="mb-3 text-xl font-semibold">{title}</h2>}
      {children}
    </section>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  kind = "primary",
  testId,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  kind?: "primary" | "secondary" | "danger";
  testId?: string;
}) {
  const style = {
    primary: "bg-[#0072B2] text-white hover:bg-[#005a8c]",
    secondary: "bg-white border border-slate-400 hover:bg-slate-100",
    danger: "bg-[#D55E00] text-white hover:bg-[#b34f00]",
  }[kind];
  return (
    <button
      type="button"
      data-testid={testId}
      className={`rounded-lg px-4 py-2 font-medium disabled:opacity-40 ${style}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="mt-3 rounded-lg border-2 border-[#D55E00] bg-orange-50 p-3">
      Error: {error instanceof Error ? error.message : String(error)}
    </p>
  );
}

export function StatusBadge({ plan, testId }: { plan?: Plan | null; testId?: string }) {
  if (!plan) return <span className="text-slate-500">no plan yet</span>;
  const color = plan.status === "FEASIBLE" ? C.green : plan.status === "INFEASIBLE" ? C.vermillion : C.orange;
  const icon = plan.status === "FEASIBLE" ? "✓" : "✗";
  return (
    <span
      data-testid={testId}
      className="inline-block rounded-full px-3 py-1 font-bold text-white"
      style={{ background: color }}
    >
      {icon} {plan.status}
      {plan.reason && <span className="ml-2 font-normal">({plan.reason})</span>}
    </span>
  );
}

export function PBar({ p, label, theta = 0.85 }: { p: number; label?: ReactNode; theta?: number }) {
  return (
    <div className="flex items-center gap-3">
      {label && <span className="w-56 shrink-0 truncate">{label}</span>}
      <div
        className="relative h-5 flex-1 rounded bg-slate-200"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={p}
      >
        <div
          className="h-5 rounded transition-all duration-500"
          style={{ width: `${p * 100}%`, background: p >= theta ? C.green : C.blue }}
        />
        <div className="absolute top-0 h-5 border-l-2 border-dashed border-slate-700" style={{ left: `${theta * 100}%` }} />
      </div>
      <span className="w-14 text-right font-mono">{p.toFixed(2)}</span>
    </div>
  );
}

export function conceptName(cur: Curriculum | undefined, id: string) {
  const d = cur?.concepts.find((c) => c.concept_id === id)?.description;
  return d ? `${id} ${d}` : id;
}

export const planDays = (plan?: Plan | null) =>
  !plan ? [] : plan.status === "FEASIBLE" ? plan.days : plan.best_effort_days;

// Display mapping of engine outputs only (D45): evidence-mastered and remediation flags come from
// the learner state; "unlocked" = the engine scheduled the concept today, "locked" = later.
export type MapStatus = { key: string; label: string; color: string };
export function conceptStatus(c: ConceptState, s: Session, cur?: Curriculum): MapStatus {
  const conceptOf = (aid: string) => cur?.activities.find((a) => a.activity_id === aid)?.target_concept;
  if (c.evidence_mastered) return { key: "mastered", label: "Mastered (evidence)", color: C.green };
  if (c.needs_remediation) return { key: "remediation", label: "Remediation", color: C.vermillion };
  if (s.today?.activities.some((a) => conceptOf(a) === c.concept_id))
    return { key: "unlocked", label: "Unlocked (today)", color: C.blue };
  if (planDays(s.plan).some((d) => d.activities.some((a) => conceptOf(a) === c.concept_id)))
    return { key: "locked", label: "Locked (later)", color: C.grey };
  return { key: "none", label: "Not in plan", color: "#ffffff" };
}

// Minimal Markdown: fenced code blocks, paragraphs, bullet lines, `code` and **bold**.
export function Markdown({ text }: { text: string }) {
  const parts = text.split(/```[a-z]*\n?/);
  return (
    <div className="space-y-3 leading-relaxed">
      {parts.map((part, i) =>
        i % 2 ? (
          <pre key={i} className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-base text-slate-50">
            {part.replace(/\n$/, "")}
          </pre>
        ) : (
          part
            .split(/\n\n+/)
            .filter((p) => p.trim())
            .map((p, j) => (
              <p key={`${i}-${j}`} className="whitespace-pre-wrap">
                {inline(p)}
              </p>
            ))
        ),
      )}
    </div>
  );
}

export function inline(s: string) {
  return s.split(/(`[^`]+`|\*\*[^*]+\*\*)/).map((t, i) =>
    t.startsWith("`") ? (
      <code key={i} className="rounded bg-slate-200 px-1 font-mono">
        {t.slice(1, -1)}
      </code>
    ) : t.startsWith("**") ? (
      <strong key={i}>{t.slice(2, -2)}</strong>
    ) : (
      t
    ),
  );
}
