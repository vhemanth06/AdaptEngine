import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { DEMO_SETUP, type Ctx } from "../ctx";
import { Button, Card, Chip, ErrorBox, Segmented, StatusBadge, fieldCls } from "../components/ui";

export default function Setup({ session, sid, setSession, go }: Ctx) {
  // Engine settings fixed per session; theta null = the rules' own theta
  const engineSettings = {
    start_p: session?.start_p ?? 0.2,
    theta: (session?.theta ?? null) as number | null,
    scheduler: (session?.scheduler ?? "greedy") as "greedy" | "cpsat",
    cpsat_fallback: session?.cpsat_fallback ?? true,
  };
  const [form, setForm] = useState(() =>
    session
      ? { curriculum: session.curriculum, profile: session.profile, rules: "product" as "product" | "legacy", ...engineSettings, ...session.context } // new rules by default, even when a pre-change (legacy) session is open
      : { ...DEMO_SETUP, profile: "fitted_S1", rules: "product" as "product" | "legacy", ...engineSettings },
  );
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });
  const curricula = useQuery({ queryKey: ["curricula"], queryFn: api.curricula });
  // 8node_x10 is the default once promoted; until then the demo keeps 8node.
  useEffect(() => {
    if (!session && curricula.data?.some((c) => c.id === "8node_x10")) setForm((f) => (f.curriculum === "8node" ? { ...f, curriculum: "8node_x10" } : f));
  }, [session, curricula.data]);
  const cur = useQuery({ queryKey: ["curriculum", form.curriculum], queryFn: () => api.curriculum(form.curriculum) });
  const sameCurriculum =
    !!session &&
    session.curriculum === form.curriculum &&
    session.profile === form.profile &&
    session.rules === form.rules &&
    session.start_p === form.start_p &&
    session.scheduler === form.scheduler &&
    (form.theta === null || form.theta === session.theta);
  const ctx = { goal: form.goal, deadline_day: form.deadline_day, budget: form.budget };

  const run = useMutation({
    mutationFn: async () => {
      const id = sameCurriculum ? sid! : (await api.createSession({ curriculum: form.curriculum, profile: form.profile, rules: form.rules, start_p: form.start_p, theta: form.theta, scheduler: form.scheduler, ...ctx })).session_id;
      return api.plan(id, { ...ctx, cpsat_fallback: form.cpsat_fallback });
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
          <span>Rules</span>
          <div>
            <Segmented label="Rules" value={form.rules} options={["product", "legacy"] as const} onChange={(r) => setForm({ ...form, rules: r })} />
            <span className="ml-2 text-sm text-[var(--text-muted)]">legacy = W7 behaviour</span>
          </div>
          <label htmlFor="profile">Learner model</label>
          <select id="profile" className={field} value={form.profile} onChange={(e) => setForm({ ...form, profile: e.target.value })}>
            {(health.data?.profiles ?? [health.data?.default_profile ?? "fitted_S1"]).map((p) => (
              <option key={p} value={p}>
                {p === "w7_default" ? "W7 default (D6 heuristics)" : p}
              </option>
            ))}
          </select>
          <label htmlFor="start-p">Starting mastery</label>
          <input
            id="start-p"
            type="number"
            min={0.01}
            max={0.99}
            step={0.01}
            className={field}
            value={form.start_p}
            onChange={(e) => setForm({ ...form, start_p: Number(e.target.value) })}
          />
          <label htmlFor="theta">Mastery threshold θ</label>
          <input
            id="theta"
            type="number"
            min={0.5}
            max={0.99}
            step={0.01}
            placeholder="blank = the rules' θ"
            className={field}
            value={form.theta ?? ""}
            onChange={(e) => setForm({ ...form, theta: e.target.value === "" ? null : Number(e.target.value) })}
          />
          <span>Scheduler</span>
          <div>
            <Segmented label="Scheduler" value={form.scheduler} options={["greedy", "cpsat"] as const} onChange={(v) => setForm({ ...form, scheduler: v })} />
            <span className="ml-2 text-sm text-[var(--text-muted)]">cpsat = exact packing</span>
          </div>
          {form.scheduler === "greedy" && (
            <>
              <span>CP-SAT fallback</span>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  data-testid="cpsat-fallback"
                  checked={form.cpsat_fallback}
                  onChange={(e) => setForm({ ...form, cpsat_fallback: e.target.checked })}
                />
                <span className="text-[var(--text-muted)]">when greedy returns UNKNOWN, re-plan with CP-SAT (up to 5 s)</span>
              </label>
            </>
          )}
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
