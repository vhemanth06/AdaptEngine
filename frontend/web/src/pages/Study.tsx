import { useCallback, useState } from "react";
import { contentOf } from "../api/client";
import { useDemoPreset, useDigitKeys, type Ctx } from "../ctx";
import { Button, C, Card, ErrorBox, Markdown, PBar, StateBadge, checkRecords, conceptName, inline } from "../components/ui";
import NoSession from "./NoSession";

export default function Study({ session, cur, demo, sendEvent, lastEvent, go }: Ctx) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const preset = useDemoPreset();
  const aid = session?.today?.activities[0];
  const act = cur?.activities.find((a) => a.activity_id === aid);
  const entry = aid ? contentOf(cur, aid) : undefined;
  const check = aid ? checkRecords(session?.plan).get(aid) : undefined;

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
  const scripted = act ? (preset.data?.known ?? []).includes(act.target_concept) : false;
  const after = up ? session.concepts.find((c) => c.concept_id === up.concept_id) : undefined;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title={act ? `Day ${session.today?.day} · ${act.type === "LESSON" ? "Lesson" : check ? "Confirmation check" : "Question"}` : "Study"} testId="study-card">
        {!act ? (
          <p data-testid="nothing-today">
            Nothing scheduled. Plan status: <b>{session.plan?.status ?? "none"}</b>.
            {session.effective && session.effective.current_day < session.effective.deadline_day && (
              <> Today's work is done: use “Next day →” in the top bar to continue.</>
            )}
          </p>
        ) : (
          <div className="space-y-4">
            <p className="flex flex-wrap items-center gap-2 text-[var(--text-muted)]">
              <code>{aid}</code> · {conceptName(cur, act.target_concept)} · {act.duration} min
              {check && <StateBadge state="check" testId="study-check" />}
            </p>
            {check && (
              <p className="text-sm text-[var(--text-muted)]">
                Confirmation check: the diagnostic believes {act.target_concept} is known; {String(check.n_checks)} short check(s) replace
                its {String(check.minutes_full)}-minute workload.
              </p>
            )}
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
                <Button disabled={busy} onClick={() => onDigit(0)}>
                  1 · Right
                </Button>
                <Button kind="danger" disabled={busy} onClick={() => onDigit(1)}>
                  2 · Wrong
                </Button>
              </div>
            )}
            {demo && act.type === "EXERCISE" && (
              <div className="flex flex-wrap gap-3">
                {preset.data && (
                  <Button kind="secondary" testId="demo-answer" disabled={busy} onClick={() => send({ correct: scripted })}>
                    Demo learner answers ({scripted ? "right" : "wrong"})
                  </Button>
                )}
                <Button kind="secondary" testId="demo-wrong" disabled={busy} onClick={() => send({ correct: false })}>
                  Answer wrong
                </Button>
              </div>
            )}
            <p className="text-sm text-[var(--text-muted)]">Rest of today: {session.today?.activities.slice(1).join(", ") || "—"}</p>
          </div>
        )}
        <ErrorBox error={error} />
      </Card>

      <Card title="What the engine did" testId="study-feedback">
        {!up ? (
          <p className="text-[var(--text-muted)]">Answer to see the belief update and the replan.</p>
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
              <PBar p={up.p_after} theta={cur?.theta} />
            </div>
            {after && (after.diag_confident || after.confirmed) && (
              <p className="flex items-center gap-2" data-testid="study-flags">
                {after.confirmed ? <StateBadge state="confirmed" /> : <StateBadge state="check" />}
                {after.confirmed ? "The checks confirmed the diagnostic's belief." : "More checks are planned."}
              </p>
            )}
            {up.correct === false && (
              <p className="text-sm text-[var(--text-muted)]">
                A wrong answer lowers p more for easy items (low guess chance) than for hard ones (slip is expected).
              </p>
            )}
            {up.needs_remediation && (
              <p data-testid="remediation-flag" className="rounded-[var(--radius)] p-2 font-semibold text-white" style={{ background: C.vermillion }}>
                Remediation triggered: p fell below the threshold, so the engine inserts a repeat lesson.
              </p>
            )}
            {up.evidence_mastered && (
              <p className="rounded-[var(--radius)] p-2 font-semibold text-white" style={{ background: C.green }}>
                Evidence-mastered.
              </p>
            )}
            <p data-testid="replan-info">
              Replanned in <b>{fb!.session.replan_ms} ms</b>: {fb!.changes.length} activity move(s).
            </p>
            {fb!.changes.length > 0 && (
              <ul className="text-sm">
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
