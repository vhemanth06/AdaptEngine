import { useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, contentOf } from "../api/client";
import { DEMO_KNOWN, useDigitKeys, type Ctx } from "../ctx";
import { Button, Card, ErrorBox, Markdown, PBar, conceptName, inline } from "../components/ui";
import NoSession from "./NoSession";

const STOP_TEXT: Record<string, string> = {
  ENTROPY: "confident (entropy below stop)",
  CONCEPT_CAP: "per-concept item cap",
  GLOBAL_CAP: "global item cap reached",
  NO_ITEMS: "no unasked items",
  SKIPPED_ANCESTOR_UNMASTERED: "skipped: a prerequisite looks unknown",
  NOT_REACHED: "not reached",
};

export default function Diagnostic(ctx: Ctx) {
  const { sid, session, cur, demo, setSession, go } = ctx;
  const diag = session?.diagnostic;
  const item = diag?.next_item;
  const entry = item ? contentOf(cur, item.activity_id) : undefined;
  const closed = !!session?.events.length;

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
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title={diag.done ? "Diagnostic finished" : `Question ${diag.items.length + 1}`} testId="diag-question">
        {closed && !diag.done && <p>The diagnostic is closed because study has started.</p>}
        {item && !closed && (
          <div className="space-y-4">
            <p className="text-slate-600">
              Concept <b>{conceptName(cur, item.concept_id)}</b> · item <code data-testid="diag-item-id">{item.activity_id}</code> (chosen by the
              engine for information gain)
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
                        className="w-full rounded-lg border border-slate-400 bg-white px-4 py-2 text-left hover:bg-slate-100"
                      >
                        <kbd className="mr-3 rounded bg-slate-200 px-2 font-mono">{i + 1}</kbd>
                        {inline(o)}
                      </button>
                    </li>
                  ))}
                </ol>
              </>
            ) : (
              <div className="flex gap-3">
                <p className="text-slate-600">No question text for this curriculum. Report the result:</p>
                <Button onClick={() => onDigit(0)}>1 · I got it right</Button>
                <Button kind="danger" onClick={() => onDigit(1)}>
                  2 · I got it wrong
                </Button>
              </div>
            )}
            {demo && (
              <Button
                kind="secondary"
                testId="demo-answer"
                disabled={answer.isPending}
                onClick={() => answer.mutate({ correct: DEMO_KNOWN.has(item.concept_id) })}
              >
                Demo learner answers ({DEMO_KNOWN.has(item.concept_id) ? "right" : "wrong"})
              </Button>
            )}
            <ErrorBox error={answer.error} />
          </div>
        )}
        {diag.done && (
          <div className="space-y-3">
            <p>
              {diag.items.length} questions asked for {diag.concept_results.length} concepts.
            </p>
            <table className="w-full text-left">
              <thead>
                <tr className="border-b">
                  <th>Concept</th>
                  <th>p</th>
                  <th>Items</th>
                  <th>Stop reason</th>
                </tr>
              </thead>
              <tbody data-testid="stop-reasons">
                {diag.concept_results.map((r) => (
                  <tr key={r.concept_id} className="border-b border-slate-200">
                    <td>{conceptName(cur, r.concept_id)}</td>
                    <td className="font-mono">{r.p.toFixed(2)}</td>
                    <td>{r.n_items}</td>
                    <td>{STOP_TEXT[r.stop_reason] ?? r.stop_reason}</td>
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
            <p className="text-base text-slate-600">Dashed line: mastery threshold θ = {theta}.</p>
          </div>
        ) : (
          <p>Live values are not available for this diagnostic configuration; they appear when it finishes.</p>
        )}
        {diag.items.length > 0 && (
          <ol className="mt-4 space-y-1 text-base" data-testid="diag-items">
            {diag.items.map((it, i) => (
              <li key={i}>
                {i + 1}. <code>{it.activity_id}</code> {it.correct ? "✓ right" : "✗ wrong"}
                {it.p_before != null && it.p_after != null && (
                  <span className="font-mono">
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
