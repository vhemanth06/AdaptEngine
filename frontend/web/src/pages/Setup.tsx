import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { DEMO_SETUP, type Ctx } from "../ctx";
import { Button, Card, Chip, ErrorBox, Segmented, StatusBadge, fieldCls } from "../components/ui";

export default function Setup({ session, sid, setSession, go }: Ctx) {
  const [form, setForm] = useState(() =>
    session ? { curriculum: session.curriculum, profile: session.profile, ...session.context } : { ...DEMO_SETUP, profile: "w7_default" },
  );
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });
  const curricula = useQuery({ queryKey: ["curricula"], queryFn: api.curricula });
  const cur = useQuery({ queryKey: ["curriculum", form.curriculum], queryFn: () => api.curriculum(form.curriculum) });
  const sameCurriculum = !!session && session.curriculum === form.curriculum && session.profile === form.profile;
  const ctx = { goal: form.goal, deadline_day: form.deadline_day, budget: form.budget };

  const run = useMutation({
    mutationFn: async () => {
      const id = sameCurriculum ? sid! : (await api.createSession({ curriculum: form.curriculum, profile: form.profile, ...ctx })).session_id;
      return api.plan(id, ctx);
    },
    onSuccess: setSession,
  });

  const plan = session?.plan;
  const field = fieldCls;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Goal, deadline and daily time">
        <div className="grid grid-cols-[auto_1fr] items-center gap-3">
          <label htmlFor="cur">Curriculum</label>
          <select
            id="cur"
            className={field}
            value={form.curriculum}
            onChange={(e) => setForm({ ...form, curriculum: e.target.value })}
          >
            {curricula.data?.map((c) => (
              <option key={c.id} value={c.id} disabled={!c.reviewed}>
                {c.id} ({c.concepts} concepts{c.has_content ? ", with content" : ", no content"}
                {c.reviewed ? "" : ", UNREVIEWED"})
              </option>
            ))}
          </select>
          <label htmlFor="goal">Goal concept</label>
          <select id="goal" className={field} value={form.goal} onChange={(e) => setForm({ ...form, goal: e.target.value })}>
            {cur.data?.concepts.map((c) => (
              <option key={c.concept_id} value={c.concept_id}>
                {c.concept_id} {c.description}
              </option>
            ))}
          </select>
          <label htmlFor="deadline">Deadline (day)</label>
          <input
            id="deadline"
            type="number"
            min={1}
            max={365}
            className={field}
            value={form.deadline_day}
            onChange={(e) => setForm({ ...form, deadline_day: Number(e.target.value) })}
          />
          <span>Minutes per day</span>
          <div>
            <Segmented
              label="Minutes per day"
              value={form.budget}
              options={cur.data?.allowed_budgets ?? [5, 10, 15, 30]}
              onChange={(b) => setForm({ ...form, budget: b })}
            />
          </div>
          <label htmlFor="profile">Learner model</label>
          <select id="profile" className={field} value={form.profile} onChange={(e) => setForm({ ...form, profile: e.target.value })}>
            {(health.data?.profiles ?? ["w7_default"]).map((p) => (
              <option key={p} value={p}>
                {p === "w7_default" ? "W7 default (D6 heuristics)" : p}
              </option>
            ))}
          </select>
        </div>
        {cur.data && (
          <p className="mt-3 text-sm text-[var(--text-muted)]">
            {cur.data.concepts.find((c) => c.concept_id === form.goal)?.description} · prerequisites:{" "}
            {cur.data.concepts.find((c) => c.concept_id === form.goal)?.prerequisites.join(", ") || "none"}
          </p>
        )}
        <div className="mt-4 flex gap-3">
          <Button testId="make-plan" onClick={() => run.mutate()} disabled={run.isPending}>
            {sameCurriculum ? "Re-plan" : "Start session and plan"}
          </Button>
        </div>
        <ErrorBox error={run.error} />
      </Card>

      <Card title="Engine answer" testId="setup-result">
        {!plan ? (
          <p className="text-slate-600">Pick a goal and press the button. The engine checks feasibility at once.</p>
        ) : (
          <div className="space-y-3">
            <StatusBadge plan={plan} testId="setup-status" />
            {session?.feasibility_warning && (
              <p data-testid="feasibility-warning">
                <Chip tone="remediation">⚠ Realistic estimate</Chip> {session.feasibility_warning}
              </p>
            )}
            {plan.status === "FEASIBLE" ? (
              <p>
                Fits in {plan.days.length} study days. Planned in <b>{session?.replan_ms} ms</b>.
              </p>
            ) : (
              <>
                <p data-testid="shortfall">
                  Short by <b>{plan.shortfall_days} day(s)</b>.
                </p>
                {plan.options.length > 0 && (
                  <ul className="list-disc pl-6">
                    {plan.options.map((o) => (
                      <li key={o}>{o}</li>
                    ))}
                  </ul>
                )}
                {plan.best_effort_days.length > 0 && (
                  <p>
                    Best effort (D42): a {plan.best_effort_days.length}-day schedule toward the deepest reachable concept is
                    shown on the Plan screen.
                  </p>
                )}
              </>
            )}
            <div className="flex gap-3">
              <Button kind="secondary" onClick={() => go("diagnostic")}>
                Next: diagnostic
              </Button>
              <Button kind="secondary" onClick={() => go("plan")}>
                See plan
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
