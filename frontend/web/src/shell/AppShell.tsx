import { useState, type ReactNode } from "react";
import type { Health, Session } from "../api/client";
import { GROUPS, TABS, type Tab } from "../ctx";
import { Button, Chip, StatusBadge, cx } from "../components/ui";

const ICON: Record<Tab, string> = {
  overview: "◎",
  setup: "⚙",
  diagnostic: "?",
  map: "⌘",
  plan: "▤",
  study: "✎",
  disruptions: "⚡",
  policy: "⚖",
  authoring: "✍",
  autopilot: "▶",
  evaluation: "▦",
};

export function Sidebar({ tab, go }: { tab: Tab; go: (t: Tab) => void }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <nav
      aria-label="Screens"
      className={cx(
        "sticky top-0 flex h-screen shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] transition-[width] duration-150",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className="flex items-center gap-2 px-4 py-4">
        <span
          aria-hidden
          className="grid h-8 w-8 place-items-center rounded-[var(--radius)] bg-[var(--accent)] font-bold text-[var(--on-accent)]"
        >
          A
        </span>
        {!collapsed && <span className="font-semibold tracking-tight">AdaptEngine</span>}
      </div>
      <div className="flex-1 overflow-y-auto px-2">
        {GROUPS.map((g) => (
          <div key={g} className="mb-3">
            {!collapsed && <div className="px-2 pb-1 text-xs font-semibold tracking-wide text-[var(--text-faint)] uppercase">{g}</div>}
            {TABS.filter((t) => t[2] === g).map(([key, label]) => (
              <button
                key={key}
                type="button"
                data-testid={`tab-${key}`}
                aria-current={tab === key ? "page" : undefined}
                title={label}
                onClick={() => go(key)}
                className={cx(
                  "flex w-full items-center gap-3 rounded-[var(--radius)] px-2 py-1.5 text-left transition-colors",
                  tab === key
                    ? "bg-[var(--accent-soft)] font-medium text-[var(--accent)]"
                    : "text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
                )}
              >
                <span aria-hidden className="w-5 text-center">
                  {ICON[key]}
                </span>
                {!collapsed && label}
              </button>
            ))}
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="m-2 rounded-[var(--radius)] px-2 py-1.5 text-left text-sm text-[var(--text-faint)] hover:bg-[var(--surface-2)]"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? "»" : "« Collapse"}
      </button>
    </nav>
  );
}

export function TopBar({
  session,
  demo,
  setDemo,
  theme,
  toggleTheme,
  reset,
}: {
  session?: Session;
  demo: boolean;
  setDemo: (b: boolean) => void;
  theme: string;
  toggleTheme: () => void;
  reset: () => void;
}) {
  const eff = session?.effective;
  return (
    <header className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_85%,transparent)] px-5 py-3 backdrop-blur">
      {session ? (
        <Chip tone="neutral" title={`session ${session.session_id}`}>
          <span className="font-mono">{session.session_id.slice(0, 6)}</span> · {session.curriculum} · {session.profile}
        </Chip>
      ) : (
        <Chip tone="neutral">no session</Chip>
      )}
      <StatusBadge plan={session?.plan} testId="plan-status" />
      {eff && (
        <span data-testid="effective" className="flex flex-wrap gap-2">
          <Chip tone="accent">Day {eff.current_day}</Chip>
          <Chip tone="neutral">deadline {eff.deadline_day}</Chip>
          <Chip tone="neutral">{eff.budget} min/day</Chip>
        </span>
      )}
      <span className="flex-1" />
      <Button kind="ghost" size="sm" onClick={() => window.dispatchEvent(new Event("ae:palette"))} title="Command palette">
        ⌘K
      </Button>
      <label className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
        <input
          type="checkbox"
          role="switch"
          checked={demo}
          onChange={(e) => setDemo(e.target.checked)}
          className="h-4 w-4 accent-[var(--accent)]"
        />
        Demo mode
      </label>
      <Button kind="ghost" size="sm" onClick={toggleTheme} title="Toggle theme" testId="theme-toggle">
        {theme === "dark" ? "☀ Light" : "☾ Dark"}
      </Button>
      <Button kind="secondary" size="sm" testId="reset" onClick={reset}>
        Reset demo
      </Button>
    </header>
  );
}

export function Footer({ health }: { health?: Health }) {
  const reviewer = health?.content_reviewer;
  const reviewed = reviewer && !reviewer.startsWith("PENDING");
  return (
    <footer className="flex flex-wrap items-center gap-3 border-t border-[var(--border)] px-5 py-2 text-xs text-[var(--text-faint)]">
      <span data-testid="honesty-badge">
        Simulated learners · demo content AI-drafted, {reviewed ? `reviewed by ${reviewer}` : "human review pending"}
      </span>
      <span className="flex-1" />
      {health && (
        <span className="font-mono" data-testid="code-hash" title={health.code_hash}>
          engine {health.engine_version} · code {health.code_hash.slice(0, 8)}
          {health.web_build === "stale" && " · web build is stale (make demo rebuilds it)"}
        </span>
      )}
    </footer>
  );
}

export function Page({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[1500px] px-6 py-6">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-[var(--text-muted)]">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
