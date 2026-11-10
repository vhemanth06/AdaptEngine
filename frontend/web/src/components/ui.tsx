import { Component, createContext, useCallback, useContext, useState, type ErrorInfo, type ReactNode } from "react";
import type { ConceptState, Curriculum, Plan, Session } from "../api/client";

// Chart palette: Okabe-Ito (colour-blind safe); every colour is paired with a text label.
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
  adapt_w7: C.sky,
  adapt_final: C.blue,
  adapt_final_dx: "#3949ab",
  adapt_cal: "#7e57c2",
  no_review: C.sky,
  no_replan: C.orange,
  static: C.purple,
  static_loop: C.vermillion,
  random_eligible: C.grey,
};
// Engine-state colours come from the design tokens (light/dark aware).
export const STATE = {
  mastered: { color: "var(--mastered)", soft: "var(--mastered-soft)", icon: "✓", label: "Mastered" },
  progress: { color: "var(--progress)", soft: "var(--progress-soft)", icon: "▶", label: "In progress" },
  remediation: { color: "var(--remediation)", soft: "var(--remediation-soft)", icon: "↻", label: "Remediation" },
  locked: { color: "var(--locked)", soft: "var(--locked-soft)", icon: "🔒", label: "Locked" },
  violation: { color: "var(--violation)", soft: "var(--violation-soft)", icon: "!", label: "Violation" },
};

export const cx = (...xs: (string | false | null | undefined)[]) => xs.filter(Boolean).join(" ");

export function Card({
  title,
  children,
  testId,
  actions,
  className,
}: {
  title?: ReactNode;
  children: ReactNode;
  testId?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cx("ae-in rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-5", className)}
      data-testid={testId}
    >
      {(title || actions) && (
        <div className="mb-3 flex items-center gap-3">
          {title && <h2 className="text-[1.05rem] font-semibold tracking-tight">{title}</h2>}
          <span className="flex-1" />
          {actions}
        </div>
      )}
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
  title,
  size = "md",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  kind?: "primary" | "secondary" | "danger" | "ghost";
  testId?: string;
  title?: string;
  size?: "sm" | "md";
}) {
  const style = {
    primary: "bg-[var(--accent)] text-[var(--on-accent)] hover:bg-[var(--accent-hover)] border border-transparent",
    secondary: "bg-[var(--surface)] text-[var(--text)] border border-[var(--border-strong)] hover:bg-[var(--surface-2)]",
    danger: "bg-[var(--violation)] text-[var(--on-accent)] border border-transparent hover:opacity-90",
    ghost: "bg-transparent text-[var(--text-muted)] border border-transparent hover:bg-[var(--surface-2)]",
  }[kind];
  return (
    <button
      type="button"
      data-testid={testId}
      title={title}
      className={cx(
        "inline-flex items-center gap-2 rounded-[var(--radius)] font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40",
        size === "sm" ? "px-2.5 py-1 text-sm" : "px-3.5 py-2",
        style,
      )}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export function Chip({ children, tone = "neutral", testId, title }: { children: ReactNode; tone?: keyof typeof STATE | "neutral" | "accent"; testId?: string; title?: string }) {
  const s =
    tone === "neutral"
      ? { color: "var(--text-muted)", soft: "var(--surface-2)" }
      : tone === "accent"
        ? { color: "var(--accent)", soft: "var(--accent-soft)" }
        : STATE[tone];
  return (
    <span
      data-testid={testId}
      title={title}
      className="tabular inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-sm font-medium whitespace-nowrap"
      style={{ color: s.color, background: s.soft, borderColor: "color-mix(in srgb, currentColor 25%, transparent)" }}
    >
      {children}
    </span>
  );
}

export function StateBadge({ state }: { state: keyof typeof STATE }) {
  const s = STATE[state];
  return (
    <Chip tone={state}>
      <span aria-hidden>{s.icon}</span> {s.label}
    </Chip>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div
      role="alert"
      className="mt-3 flex flex-wrap items-center gap-3 rounded-[var(--radius)] border border-[var(--violation)] bg-[var(--violation-soft)] p-3 text-[var(--text)]"
    >
      <span className="font-semibold" style={{ color: "var(--violation)" }}>
        ! Error
      </span>
      <span className="flex-1">{msg}</span>
      {onRetry && (
        <Button size="sm" kind="secondary" onClick={onRetry}>
          Retry
        </Button>
      )}
      <Button size="sm" kind="ghost" onClick={() => copyDebug(msg)}>
        Copy debug info
      </Button>
    </div>
  );
}

export function copyDebug(msg: string) {
  const info = {
    error: msg,
    session: (() => {
      try {
        return localStorage.getItem("ae.sid");
      } catch {
        return null;
      }
    })(),
    url: location.href,
    time: new Date().toISOString(),
  };
  navigator.clipboard?.writeText(JSON.stringify(info, null, 1)).catch(() => undefined);
}

export function Skeleton({ h = 16, w = "100%", className }: { h?: number; w?: number | string; className?: string }) {
  return <div className={cx("ae-skeleton", className)} style={{ height: h, width: w }} aria-hidden />;
}

export function LoadingCard({ lines = 4, label = "Loading" }: { lines?: number; label?: string }) {
  return (
    <Card>
      <div className="space-y-3" role="status" aria-label={label}>
        {Array.from({ length: lines }, (_, i) => (
          <Skeleton key={i} h={14} w={`${90 - i * 12}%`} />
        ))}
      </div>
    </Card>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-[var(--radius-lg)] border border-dashed border-[var(--border-strong)] bg-[var(--surface)] p-8">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children && <div className="text-[var(--text-muted)]">{children}</div>}
      {action}
    </div>
  );
}

export class ErrorBoundary extends Component<{ children: ReactNode; name: string }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.name}]`, error, info.componentStack);
  }
  render() {
    if (this.state.error)
      return (
        <Card title={`The ${this.props.name} screen failed to render`}>
          <ErrorBox error={this.state.error} onRetry={() => this.setState({ error: null })} />
        </Card>
      );
    return this.props.children;
  }
}

// ------------------------------------------------------------------------------- toasts
type Toast = { id: number; text: string; tone: "neutral" | "mastered" | "remediation" | "violation" };
const ToastCtx = createContext<(text: string, tone?: Toast["tone"]) => void>(() => undefined);
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Toast["tone"] = "neutral") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-3), { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed right-4 bottom-12 z-50 flex flex-col gap-2" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            data-testid="toast"
            className="ae-in rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3 shadow-[var(--shadow-overlay)]"
            style={t.tone !== "neutral" ? { borderLeft: `4px solid ${STATE[t.tone].color}` } : undefined}
          >
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: readonly T[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-[var(--radius)] border border-[var(--border-strong)] bg-[var(--surface-2)] p-0.5">
      {options.map((o) => (
        <button
          key={String(o)}
          type="button"
          role="radio"
          aria-checked={o === value}
          onClick={() => onChange(o)}
          className={cx(
            "tabular rounded-[6px] px-3 py-1 text-sm font-medium transition-colors",
            o === value ? "bg-[var(--surface)] text-[var(--text)] shadow-sm" : "text-[var(--text-muted)] hover:text-[var(--text)]",
          )}
        >
          {String(o)}
        </button>
      ))}
    </div>
  );
}

export const fieldCls =
  "rounded-[var(--radius)] border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-[var(--text)]";

export function StatusBadge({ plan, testId }: { plan?: Plan | null; testId?: string }) {
  if (!plan)
    return (
      <Chip tone="neutral" testId={testId}>
        no plan yet
      </Chip>
    );
  const tone = plan.status === "FEASIBLE" ? "mastered" : plan.status === "INFEASIBLE" ? "violation" : "remediation";
  const icon = plan.status === "FEASIBLE" ? "✓" : "✗";
  return (
    <Chip tone={tone} testId={testId} title={plan.reason ?? undefined}>
      {icon} {plan.status}
      {plan.reason && <span className="font-normal opacity-80">({plan.reason})</span>}
    </Chip>
  );
}

export function PBar({ p, label, theta = 0.85 }: { p: number; label?: ReactNode; theta?: number }) {
  return (
    <div className="flex items-center gap-3">
      {label && <span className="w-56 shrink-0 truncate">{label}</span>}
      <div
        className="relative h-2.5 flex-1 rounded-full bg-[var(--surface-3)]"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={p}
      >
        <div
          className="h-2.5 rounded-full transition-all duration-500"
          style={{ width: `${p * 100}%`, background: p >= theta ? "var(--mastered)" : "var(--progress)" }}
        />
        <div
          className="absolute -top-1 h-4.5 border-l-2 border-dashed border-[var(--text-muted)]"
          style={{ left: `${theta * 100}%` }}
          title={`θ = ${theta}`}
        />
      </div>
      <span className="tabular w-12 text-right font-mono text-sm">{p.toFixed(2)}</span>
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
  if (c.evidence_mastered) return { key: "mastered", label: "✓ Mastered (evidence)", color: "var(--mastered)" };
  if (c.needs_remediation) return { key: "remediation", label: "↻ Remediation", color: "var(--remediation)" };
  if (s.today?.activities.some((a) => conceptOf(a) === c.concept_id))
    return { key: "unlocked", label: "▶ Unlocked (today)", color: "var(--progress)" };
  if (planDays(s.plan).some((d) => d.activities.some((a) => conceptOf(a) === c.concept_id)))
    return { key: "locked", label: "🔒 Locked (later)", color: "var(--locked)" };
  return { key: "none", label: "Not in plan", color: "var(--surface)" };
}

// Minimal Markdown: fenced code blocks, paragraphs, bullet lines, `code` and **bold**.
export function Markdown({ text }: { text: string }) {
  const parts = text.split(/```[a-z]*\n?/);
  return (
    <div className="space-y-3 leading-relaxed">
      {parts.map((part, i) =>
        i % 2 ? (
          <pre key={i} className="overflow-x-auto rounded-[var(--radius)] bg-[#18181b] p-3 text-sm text-[#f4f4f5]">
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
      <code key={i} className="rounded bg-[var(--surface-3)] px-1 text-[0.92em]">
        {t.slice(1, -1)}
      </code>
    ) : t.startsWith("**") ? (
      <strong key={i}>{t.slice(2, -2)}</strong>
    ) : (
      t
    ),
  );
}
