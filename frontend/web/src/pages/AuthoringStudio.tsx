import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, type DraftOut } from "../api/client";
import { Button, Card, Chip, ErrorBox, fieldCls } from "../components/ui";

type Entry = { type: string; target_concept: string; title?: string; markdown?: string; prompt?: string; options?: string[]; correct?: number; explanation?: string };
type Issue = { check: string; severity: string; message: string; hint?: string; where?: string | null };

export default function AuthoringStudio() {
  const [form, setForm] = useState({ name: "py_dicts", topic: "Python dictionaries", n_concepts: 3, provider: "stub" as const });
  const [draft, setDraft] = useState<DraftOut | null>(null);
  const [reviewer, setReviewer] = useState("");
  const gen = useMutation({ mutationFn: () => api.draft(form), onSuccess: setDraft });
  const edit = useMutation({
    mutationFn: (c: Record<string, Record<string, unknown>>) => api.editDraft(draft!.name, c),
    onSuccess: setDraft,
  });
  const approve = useMutation({ mutationFn: () => api.approve(draft!.name, reviewer) });

  const report = draft?.report as { ok: boolean; errors: number; warnings: number; issues: Issue[] } | undefined;
  const concepts = (draft?.curriculum.concepts ?? []) as { concept_id: string; description: string; prerequisites: string[] }[];
  const content = (draft?.content.activities ?? {}) as Record<string, Entry>;
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Card title="1 · Scope">
        <div className="grid gap-3">
          <label className="grid gap-1">
            Draft name
            <input className={fieldCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label className="grid gap-1">
            Topic
            <input className={fieldCls} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} />
          </label>
          <label className="grid gap-1">
            Concepts
            <input type="number" min={2} max={8} className={fieldCls} value={form.n_concepts} onChange={(e) => setForm({ ...form, n_concepts: Number(e.target.value) })} />
          </label>
          <label className="grid gap-1">
            Provider
            <select className={fieldCls} value={form.provider} onChange={() => undefined}>
              <option value="stub">Template stub (offline)</option>
            </select>
            <span className="text-sm text-[var(--text-faint)]">Claude / Ollama drafts run from the CLI (docs/AUTHORING.md) and need a key or local model.</span>
          </label>
          <Button testId="generate-draft" onClick={() => gen.mutate()} disabled={gen.isPending}>
            {gen.isPending ? "Drafting…" : "Generate draft"}
          </Button>
          <ErrorBox error={gen.error} />
        </div>
      </Card>

      <Card title="2 · Draft (AI-assisted, not live)" testId="draft">
        {!draft ? (
          <p className="text-[var(--text-muted)]">Drafts are written only to data/drafts/ and marked PENDING_HUMAN_REVIEW.</p>
        ) : (
          <div className="space-y-3">
            <p className="flex flex-wrap gap-2">
              <Chip tone="remediation">reviewer: {String(draft.meta.reviewer)}</Chip>
              <Chip tone="neutral">{String(draft.meta.provider)} · {String(draft.meta.model)}</Chip>
              <Chip tone="neutral">attempts {draft.attempts.length || 1}</Chip>
            </p>
            <div>
              <h3 className="mb-1 font-medium">Prerequisite graph (check every edge)</h3>
              <ul className="space-y-1" data-testid="draft-dag">
                {concepts.map((c) => (
                  <li key={c.concept_id}>
                    <code>{c.concept_id}</code> {c.description}
                    <span className="text-[var(--text-muted)]"> ← {c.prerequisites.length ? c.prerequisites.join(", ") : "none"}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
              {Object.entries(content)
                .filter(([, e]) => e.type === "EXERCISE")
                .slice(0, 12)
                .map(([aid, e]) => (
                  <details key={aid} className="rounded-[var(--radius)] border border-[var(--border)] p-2">
                    <summary className="cursor-pointer">
                      <code>{aid}</code> {e.prompt}
                    </summary>
                    <textarea
                      aria-label={`Edit prompt ${aid}`}
                      className={`${fieldCls} mt-2 w-full`}
                      defaultValue={e.prompt}
                      onBlur={(ev) => ev.target.value !== e.prompt && edit.mutate({ [aid]: { ...e, prompt: ev.target.value } })}
                    />
                    <ol className="mt-1 list-decimal pl-6 text-sm">
                      {e.options?.map((o, i) => (
                        <li key={i} className={i === e.correct ? "font-semibold text-[var(--mastered)]" : ""}>
                          {o} {i === e.correct && "✓"}
                        </li>
                      ))}
                    </ol>
                  </details>
                ))}
            </div>
            <ErrorBox error={edit.error} />
          </div>
        )}
      </Card>

      <Card title="3 · Validation and human approval" testId="validation">
        {!report ? (
          <p className="text-[var(--text-muted)]">Schema, DAG, duplicates, answer-position bias, difficulty spread and reading length.</p>
        ) : (
          <div className="space-y-3">
            <p className="flex flex-wrap gap-2">
              {report.ok ? <Chip tone="mastered">✓ passes the loaders</Chip> : <Chip tone="violation">✗ {report.errors} error(s)</Chip>}
              <Chip tone={report.warnings ? "remediation" : "neutral"}>{report.warnings} warning(s)</Chip>
            </p>
            <ul className="max-h-60 space-y-1 overflow-y-auto text-sm">
              {report.issues.slice(0, 30).map((i, k) => (
                <li key={k}>
                  <Chip tone={i.severity === "error" ? "violation" : "remediation"}>{i.check}</Chip> {i.message}
                  {i.hint && <span className="text-[var(--text-muted)]"> — {i.hint}</span>}
                </li>
              ))}
            </ul>
            <label className="grid gap-1">
              Reviewer (your name)
              <input className={fieldCls} value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="A human name; AI names are rejected" />
            </label>
            <Button testId="approve" kind="secondary" disabled={!reviewer || approve.isPending || !report.ok} onClick={() => approve.mutate()}>
              Approve as {reviewer || "…"}
            </Button>
            <ErrorBox error={approve.error} />
            {approve.data && (
              <p data-testid="approved">
                <Chip tone="mastered">✓ approved by {approve.data.reviewer}</Chip> {approve.data.recorded.length} files recorded in the review manifest.
              </p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
