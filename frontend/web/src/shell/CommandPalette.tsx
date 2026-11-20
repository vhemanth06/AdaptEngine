import { useEffect, useMemo, useRef, useState } from "react";
import { cx } from "../components/ui";

export type Command = { id: string; label: string; group: string; run: () => void; hint?: string };

// ⌘K / Ctrl+K command palette: jump to a screen or run a demo action (keyboard only on stage).
export default function CommandPalette({ commands }: { commands: Command[] }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") setOpen(false);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("ae:palette", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("ae:palette", onOpen);
    };
  }, []);
  useEffect(() => {
    if (open) {
      setQ("");
      setI(0);
      setTimeout(() => input.current?.focus(), 0);
    }
  }, [open]);

  const hits = useMemo(
    () => commands.filter((c) => `${c.group} ${c.label}`.toLowerCase().includes(q.toLowerCase())),
    [commands, q],
  );
  if (!open) return null;
  const run = (c?: Command) => {
    if (!c) return;
    setOpen(false);
    c.run();
  };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-[12vh]" onClick={() => setOpen(false)}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        data-testid="palette"
        className="ae-in w-[560px] max-w-[92vw] overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-overlay)]"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={input}
          value={q}
          aria-label="Search commands"
          placeholder="Jump to a screen or run an action…"
          className="w-full border-b border-[var(--border)] bg-transparent px-4 py-3 outline-none"
          onChange={(e) => {
            setQ(e.target.value);
            setI(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setI((x) => Math.min(hits.length - 1, x + 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setI((x) => Math.max(0, x - 1));
            } else if (e.key === "Enter") run(hits[i]);
          }}
        />
        <ul className="max-h-80 overflow-y-auto py-1" role="listbox">
          {hits.map((c, k) => (
            <li key={c.id} role="option" aria-selected={k === i}>
              <button
                type="button"
                onMouseEnter={() => setI(k)}
                onClick={() => run(c)}
                className={cx("flex w-full items-center gap-3 px-4 py-2 text-left", k === i && "bg-[var(--accent-soft)]")}
              >
                <span className="w-24 text-sm text-[var(--text-faint)]">{c.group}</span>
                <span className="flex-1">{c.label}</span>
                {c.hint && <span className="text-sm text-[var(--text-faint)]">{c.hint}</span>}
              </button>
            </li>
          ))}
          {!hits.length && <li className="px-4 py-3 text-[var(--text-muted)]">No matching command.</li>}
        </ul>
      </div>
    </div>
  );
}
