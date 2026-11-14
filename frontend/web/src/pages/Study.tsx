import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, contentOf } from "../api/client";
import { useDigitKeys, type Ctx } from "../ctx";
import { Button, C, Card, Chip, ErrorBox, Markdown, PBar, conceptName, inline } from "../components/ui";
import NoSession from "./NoSession";

export default function Study({ session, cur, demo, sendEvent, lastEvent, go }: Ctx) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const aid = session?.today?.activities[0];
  const act = cur?.activities.find((a) => a.activity_id === aid);
  const entry = aid ? contentOf(cur, aid) : undefined;

  const send = useCallback(
    async (b: { choice?: number; correct?: boolean }) => {
      if (!aid || busy) return;
      setBusy(true);
      setError(null);
      try {
        await sendEvent({ kind: "COMPLETED", activity_id: aid, ...b }, "study");
      } catch (e) {
        setError(e);
      } finally {
        setBusy(false);
      }
    },
    [aid, busy, sendEvent],
  );
  const onDigit = useCallback(
    (i: number) => {
      if (act?.type !== "EXERCISE") return;
      if (entry?.options) send({ choice: i });
      else if (i < 2) send({ correct: i === 0 });
    },
    [act, entry, send],
  );
  useDigitKeys(!!act, onDigit);

  if (!session) return <NoSession go={go} />;
  const fb = lastEvent?.label === "study" ? lastEvent.result : null;
  const up = fb?.update;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <StrategyChip sid={session.session_id} version={session.events.length} />
      <Card title={act ? `Day ${session.today?.day} · ${act.type === "LESSON" ? "Lesson" : "Question"}` : "Study"} testId="study-card">
        {!act ? (
          <p data-testid="nothing-today">
            Nothing scheduled. Plan status: <b>{session.plan?.status ?? "none"}</b>.
          </p>
        ) : (
          <div className="space-y-4">
            <p className="text-slate-600">
              <code>{aid}</code> · {conceptName(cur, act.target_concept)} · {act.duration} min
            </p>
            {act.type === "LESSON" ? (
              <>
                {entry?.markdown ? <Markdown text={entry.markdown} /> : <p>(No lesson text for this curriculum.)</p>}
                <Button testId="lesson-done" disabled={busy} onClick={() => send({})}>
                  Mark lesson done
                </Button>
              </>
            ) : entry?.prompt ? (
              <>
                <Markdown text={entry.prompt} />
                <ol className="space-y-2">
                  {entry.options?.map((o, i) => (
                    <li key={i}>
                      <button
                        type="button"
                        disabled={busy}
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
                <Button disabled={busy} onClick={() => onDigit(0)}>
                  1 · Right
                </Button>
                <Button kind="danger" disabled={busy} onClick={() => onDigit(1)}>
                  2 · Wrong
                </Button>
              </div>
            )}
            {demo && act.type === "EXERCISE" && (
              <div className="flex gap-3">
                <Button kind="secondary" testId="demo-right" disabled={busy} onClick={() => send({ correct: true })}>
                  Demo: answer right
                </Button>
                <Button kind="secondary" testId="demo-wrong" disabled={busy} onClick={() => send({ correct: false })}>
                  Demo: answer wrong
                </Button>
              </div>
            )}
            <p className="text-base text-slate-600">Rest of today: {session.today?.activities.slice(1).join(", ") || "—"}</p>
          </div>
        )}
        <ErrorBox error={error} />
      </Card>

      <Card title="What the engine did" testId="study-feedback">
        {!up ? (
          <p className="text-slate-600">Answer to see the belief update and the replan.</p>
        ) : (
          <div className="space-y-3">
            {up.correct != null && (
              <p className="text-xl font-bold" style={{ color: up.correct ? C.green : C.vermillion }}>
                {up.correct ? "✓ Right" : "✗ Wrong"}
              </p>
            )}
            {up.explanation && <Markdown text={up.explanation} />}
            <div>
              {conceptName(cur, up.concept_id)}: p {up.p_before.toFixed(2)} → {up.p_after.toFixed(2)}
              <PBar p={up.p_after} theta={session?.theta ?? cur?.theta} />
            </div>
            {up.correct === false && (
              <p className="text-base text-slate-600">
                A wrong answer lowers p more for easy items (low guess chance) than for hard ones (slip is expected).
              </p>
            )}
            {up.needs_remediation && (
              <p data-testid="remediation-flag" className="rounded-lg p-2 font-semibold text-white" style={{ background: C.vermillion }}>
                Remediation triggered: p fell below the threshold, so the engine inserts a repeat lesson.
              </p>
            )}
            {up.evidence_mastered && (
              <p className="rounded-lg p-2 font-semibold text-white" style={{ background: C.green }}>
                Evidence-mastered.
              </p>
            )}
            <p data-testid="replan-info">
              Replanned in <b>{fb!.session.replan_ms} ms</b>: {fb!.changes.length} activity move(s).
            </p>
            {fb!.changes.length > 0 && (
              <ul className="text-base">
                {fb!.changes.slice(0, 8).map((c) => (
                  <li key={c.activity_id}>
                    <code>{c.activity_id}</code>: {c.old_day == null ? "new" : `day ${c.old_day}`} →{" "}
                    {c.new_day == null ? "done / dropped" : `day ${c.new_day}`}
                  </li>
                ))}
              </ul>
            )}
            <Button kind="secondary" onClick={() => go("plan")}>
              See updated plan
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

// N.3: the A3 orchestrator's choice from the engine's closed option set (stub unless a model is connected)
function StrategyChip({ sid, version }: { sid: string; version: number }) {
  const q = useQuery({ queryKey: ["strategy", sid, version], queryFn: () => api.strategy(sid) });
  if (!q.data) return <div className="lg:col-span-2" />;
  const s = q.data;
  return (
    <div className="flex flex-wrap items-center gap-2 lg:col-span-2" data-testid="strategy">
      <Chip tone="accent" title={s.rationale ?? undefined}>
        Agent strategy: {s.choice}
      </Chip>
      <span className="text-sm text-[var(--text-muted)]">
        chosen from {s.options.map((o) => String(o.id)).join(" · ")} ({s.source}; engine default {s.default})
      </span>
    </div>
  );
}
