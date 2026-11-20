import { useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, contentOf } from "../api/client";
import { useDigitKeys, type Ctx } from "../ctx";
import { Button, Card, ErrorBox, Markdown, PBar, StateBadge, conceptName, inline } from "../components/ui";
import NoSession from "./NoSession";

// The engine's stop reasons in plain words (display only, D45)
const STOP_TEXT: Record<string, string> = {
  ENTROPY: "Confident: entropy below the stop",
  CONFIDENT: "Confident: run ended",
  INFERRED: "Inferred: not asked",
  CONCEPT_CAP: "Concept cap: item limit for this concept",
  GLOBAL_CAP: "Global cap: question budget used",
  NO_ITEMS: "No informative items left",
  SKIPPED_ANCESTOR_UNMASTERED: "Skipped: a prerequisite looks unknown",
  NOT_REACHED: "Not reached",
};

export default function Diagnostic(ctx: Ctx) {
  const { sid, session, cur, setSession, go } = ctx;
  const diag = session?.diagnostic;
  const item = diag?.next_item;
  const entry = item ? contentOf(cur, item.activity_id) : undefined;
  const closed = !!session?.events.length;

  const skip = useMutation({
    mutationFn: () => api.plan(sid!, {}),
    onSuccess: (s) => {
      setSession(s);
      go("plan");
    },
  });
  const answer = useMutation({
    mutationFn: (b: { choice?: number; correct?: boolean }) => api.answer(sid!, { activity_id: item!.activity_id, ...b }),
    onSuccess: setSession,
  });
  const onDigit = useCallback(
    (i: number) => {
      if (answer.isPending || !item) return;
      if (entry?.options) answer.mutate({ choice: i });
      else if (i < 2) answer.mutate({ correct: i === 0 });
    },
    [answer, item, entry],
  );
  useDigitKeys(!!item && !closed, onDigit);

  if (!session || !diag) return <NoSession go={go} />;
  const theta = cur?.theta ?? 0.85;
  const nMax = typeof diag.info?.n_max === "number" ? diag.info.n_max : null;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title={diag.done ? "Diagnostic finished" : `Question ${diag.items.length + 1}`} testId="diag-question">
        {closed && !diag.done && <p>The diagnostic is closed because study has started.</p>}
        {item && !closed && (
          <div className="mb-3 flex flex-wrap items-center gap-3 text-sm text-[var(--text-muted)]">
            <span className="tabular" data-testid="diag-budget">
              Question {diag.items.length + 1}
              {nMax != null && ` · budget ${nMax}`}
            </span>
            {nMax != null && (
              <div className="h-1.5 flex-1 rounded-full bg-[var(--surface-3)]">
                <div
                  className="h-1.5 rounded-full bg-[var(--accent)] transition-all"
                  style={{ width: `${Math.min(100, (diag.items.length / nMax) * 100)}%` }}
                />
              </div>
            )}
            <span className="flex-1" />
            <Button size="sm" kind="ghost" testId="skip-diagnostic" onClick={() => skip.mutate()} disabled={skip.isPending}>
              Skip → plan from the prior
            </Button>
          </div>
        )}
        {item && !closed && (
          <div className="space-y-4">
            <p className="text-[var(--text-muted)]">
              Concept <b>{conceptName(cur, item.concept_id)}</b> · item <code data-testid="diag-item-id">{item.activity_id}</code> (chosen
              by the engine for information gain)
            </p>
            {entry?.prompt ? (
              <>
                <Markdown text={entry.prompt} />
                <ol className="space-y-2">
                  {entry.options?.map((o, i) => (
                    <li key={i}>
                      <button
                        type="button"
                        onClick={() => onDigit(i)}
                        className="w-full rounded-[var(--radius)] border border-[var(--border-strong)] bg-[var(--surface)] px-4 py-2 text-left transition-colors hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]"
                      >
                        <kbd className="mr-3 rounded bg-[var(--surface-3)] px-2 font-mono text-sm">{i + 1}</kbd>
                        {inline(o)}
                      </button>
                    </li>
                  ))}
                </ol>
              </>
            ) : (
              <div className="flex gap-3">
                <p className="text-[var(--text-muted)]">No question text for this curriculum. Report the result:</p>
                <Button onClick={() => onDigit(0)}>1 · I got it right</Button>
                <Button kind="danger" onClick={() => onDigit(1)}>
                  2 · I got it wrong
                </Button>
              </div>
            )}
            {/* report the result directly, without picking an option */}
            <div className="flex flex-wrap gap-3">
              <Button kind="secondary" testId="answer-right" disabled={answer.isPending} onClick={() => answer.mutate({ correct: true })}>
                ✓ Answer right
              </Button>
              <Button kind="secondary" testId="answer-wrong" disabled={answer.isPending} onClick={() => answer.mutate({ correct: false })}>
                ✗ Answer wrong
              </Button>
            </div>
            <ErrorBox error={answer.error} />
          </div>
        )}
        {diag.done && (
          <div className="space-y-3">
            <p>
              {diag.items.length} questions asked for {diag.concept_results.length} concepts.
            </p>
            <table className="w-full text-left">
              <thead className="text-sm text-[var(--text-muted)]">
                <tr className="border-b border-[var(--border)]">
                  <th className="py-1 pr-4">Concept</th>
                  <th className="pr-4">p</th>
                  <th className="pr-4">Items</th>
                  <th>Stop reason</th>
                </tr>
              </thead>
              <tbody data-testid="stop-reasons">
                {diag.concept_results.map((r) => (
                  <tr key={r.concept_id} className="border-b border-[var(--border)]">
                    <td className="py-1 pr-4">{conceptName(cur, r.concept_id)}</td>
                    <td className="tabular pr-4 font-mono">{r.p.toFixed(2)}</td>
                    <td className="tabular pr-4">{r.n_items}</td>
                    <td className="flex flex-wrap items-center gap-2 py-1">
                      {r.stop_reason === "INFERRED" && (
                        <StateBadge state="inferred" testId={`chip-inferred-${r.concept_id}`} />
                      )}
                      {r.stop_reason === "INFERRED" ? "not asked" : (STOP_TEXT[r.stop_reason] ?? r.stop_reason)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Button onClick={() => go("map")}>Next: curriculum map</Button>
          </div>
        )}
      </Card>

      <Card title="Belief per concept (p of mastery)">
        {diag.live_p ? (
          <div className="space-y-2">
            {Object.entries(diag.live_p).map(([c, p]) => (
              <PBar key={c} p={p} theta={theta} label={conceptName(cur, c)} />
            ))}
            <p className="text-sm text-[var(--text-muted)]">Dashed line: mastery threshold θ = {theta}.</p>
          </div>
        ) : (
          <p>Live values are not available for this diagnostic configuration; they appear when it finishes.</p>
        )}
        {diag.items.length > 0 && (
          <ol className="mt-4 space-y-1" data-testid="diag-items">
            {diag.items.map((it, i) => (
              <li key={i}>
                {i + 1}. <code>{it.activity_id}</code> {it.correct ? "✓ right" : "✗ wrong"}
                {it.p_before != null && it.p_after != null && (
                  <span className="tabular font-mono">
                    {" "}
                    p {it.p_before.toFixed(2)} → {it.p_after.toFixed(2)}
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
