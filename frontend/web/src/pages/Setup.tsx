import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type DemoPreset } from "../api/client";
import { DIAGNOSTICS, MODELS, MODEL_LABEL, PLANNERS, PLANNER_LABEL, useDemoPreset, useHealth, type Ctx } from "../ctx";
import { Button, Card, Chip, ErrorBox, Segmented, StatusBadge, fieldCls } from "../components/ui";

type Form = {
  curriculum: string;
  goal: string;
  deadline_day: number;
  budget: number;
  model_profile: DemoPreset["model_profile"];
  diagnostic_method: DemoPreset["diagnostic_method"];
  planner_method: DemoPreset["planner_method"];
};

// Engine defaults (sweep, heuristic, greedy) unless a session exists; "Use demo preset" fills D94's.
const DEFAULT_FORM: Form = {
  curriculum: "8node_x10",
  goal: "C8",
  deadline_day: 10,
  budget: 10,
  model_profile: "heuristic",
  diagnostic_method: "sweep",
  planner_method: "greedy",
};

const EXACT = new Set(["CPSAT_INFEASIBLE"]);

export default function Setup({ session, sid, setSession, go, demo }: Ctx) {
  const [form, setForm] = useState<Form>(() =>
    session
      ? {
          curriculum: session.curriculum,
          ...session.context,
          model_profile: session.model_profile as Form["model_profile"],
          diagnostic_method: session.diagnostic_method as Form["diagnostic_method"],
          planner_method: session.planner_method as Form["planner_method"],
        }
      : DEFAULT_FORM,
  );
  // Follow the session shown (it may load after this screen opens, or be replaced)
  const sessionId = session?.session_id;
  useEffect(() => {
    if (!session) return;
    setForm({
      curriculum: session.curriculum,
      ...session.context,
      model_profile: session.model_profile as Form["model_profile"],
      diagnostic_method: session.diagnostic_method as Form["diagnostic_method"],
      planner_method: session.planner_method as Form["planner_method"],
    });
  }, [sessionId]);
  const health = useHealth();
  const preset = useDemoPreset();
  const curricula = useQuery({ queryKey: ["curricula"], queryFn: api.curricula });
  const cur = useQuery({ queryKey: ["curriculum", form.curriculum], queryFn: () => api.curriculum(form.curriculum) });
  // The switches and the curriculum are fixed per session; goal, deadline and budget replan it.
  const sameSession =
    !!session &&
    session.curriculum === form.curriculum &&
    session.model_profile === form.model_profile &&
    session.diagnostic_method === form.diagnostic_method &&
    session.planner_method === form.planner_method;
  const ctx = { goal: form.goal, deadline_day: form.deadline_day, budget: form.budget };
  // Once the session has a plan, the curriculum and switches are locked; "New session…" unlocks
  const [unlocked, setUnlocked] = useState(false);
  const locked = !!session?.plan && !unlocked;
  const LOCK = "fixed for this session; use New session… to start another";
  const lockOthers = <T extends string>(opts: readonly T[], value: T) =>
    (locked ? Object.fromEntries(opts.filter((o) => o !== value).map((o) => [o, LOCK])) : {}) as Partial<Record<T, string>>;
  const keepSession = () => {
    setUnlocked(false);
    if (session)
      setForm({
        ...form,
        curriculum: session.curriculum,
        model_profile: session.model_profile as Form["model_profile"],
        diagnostic_method: session.diagnostic_method as Form["diagnostic_method"],
        planner_method: session.planner_method as Form["planner_method"],
      });
  };

  const run = useMutation({
    mutationFn: async () => {
      const id = sameSession
        ? sid!
        : (
            await api.createSession({
              curriculum: form.curriculum,
              model_profile: form.model_profile,
              diagnostic_method: form.diagnostic_method,
              planner_method: form.planner_method,
              ...ctx,
            })
          ).session_id;
      return api.plan(id, ctx);
    },
    onSuccess: (s) => {
      setSession(s);
      setUnlocked(false);
    },
  });

  const noOrtools = health.data && !health.data.ortools_available ? "needs the [cpsat] extra" : undefined;
  const plan = session?.plan;
  const goalInfo = cur.data?.concepts.find((c) => c.concept_id === form.goal);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card
        title="Goal, deadline, daily time and switches"
        actions={
          demo && preset.data ? (
            <Button
              size="sm"
              kind="secondary"
              testId="use-demo-preset"
              onClick={() => {
                const p = preset.data!;
                setUnlocked(true); // the preset starts a new session
                setForm({
                  curriculum: p.curriculum,
                  goal: p.goal,
                  deadline_day: p.deadline_day,
                  budget: p.budget,
                  model_profile: p.model_profile,
                  diagnostic_method: p.diagnostic_method,
                  planner_method: p.planner_method,
                });
              }}
            >
              Use demo preset
            </Button>
          ) : null
        }
      >
        <div className="grid grid-cols-[auto_1fr] items-center gap-3">
          <label htmlFor="cur">Curriculum</label>
          <select
            id="cur"
            className={fieldCls}
            disabled={locked}
            title={locked ? LOCK : undefined}
            value={form.curriculum}
            onChange={(e) => setForm({ ...form, curriculum: e.target.value })}
          >
            {curricula.data?.map((c) => (
              <option key={c.id} value={c.id} disabled={!c.reviewed} title={c.review_error ?? undefined}>
                {c.id} ({c.concepts} concepts{c.has_content ? ", with content" : ", no content"}
                {c.reviewed ? "" : ", UNREVIEWED"})
              </option>
            ))}
          </select>
          <label htmlFor="goal">Goal concept</label>
          <select id="goal" className={fieldCls} value={form.goal} onChange={(e) => setForm({ ...form, goal: e.target.value })}>
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
            className={fieldCls}
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
          <span>Diagnostic</span>
          <div>
            <Segmented
              label="Diagnostic"
              testId="switch-diagnostic"
              value={form.diagnostic_method}
              options={DIAGNOSTICS}
              disabled={lockOthers(DIAGNOSTICS, form.diagnostic_method)}
              onChange={(v) => setForm({ ...form, diagnostic_method: v })}
            />
            <span className="ml-2 text-sm text-[var(--text-muted)]">bisection adds confirmation checks</span>
          </div>
          <span>Item model</span>
          <Segmented
            label="Item model"
            testId="switch-model"
            value={form.model_profile}
            options={MODELS}
            labels={MODEL_LABEL}
            disabled={lockOthers(MODELS, form.model_profile)}
            onChange={(v) => setForm({ ...form, model_profile: v })}
          />
          <span>Planner</span>
          <div>
            <Segmented
              label="Planner"
              testId="switch-planner"
              value={form.planner_method}
              options={PLANNERS}
              labels={PLANNER_LABEL}
              disabled={{ hybrid: noOrtools, cpsat: noOrtools, ...lockOthers(PLANNERS, form.planner_method) }}
              onChange={(v) => setForm({ ...form, planner_method: v })}
            />
            {noOrtools && <span className="ml-2 text-sm text-[var(--text-muted)]">CP-SAT and hybrid {noOrtools}</span>}
          </div>
        </div>
        {goalInfo && (
          <p className="mt-3 text-sm text-[var(--text-muted)]">
            {goalInfo.description} · prerequisites: {goalInfo.prerequisites.join(", ") || "none"}
          </p>
        )}
        <p className="mt-2 text-sm text-[var(--text-faint)]" data-testid="switch-lock">
          {locked
            ? "Curriculum and switches are fixed for this session. Goal, deadline and daily time re-plan it."
            : session?.plan
              ? "Changing the curriculum or a switch starts a new session from day 1; the current one is left as it is."
              : "The curriculum and switches are fixed once the session has a plan. Goal, deadline and daily time can always re-plan it."}
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Button testId="make-plan" onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? "Planning…" : sameSession ? "Re-plan" : "Start session and plan"}
          </Button>
          {locked && (
            <Button kind="secondary" testId="new-session" onClick={() => setUnlocked(true)}>
              New session…
            </Button>
          )}
          {session?.plan && unlocked && (
            <Button kind="ghost" testId="keep-session" onClick={keepSession}>
              Keep current session
            </Button>
          )}
        </div>
        <ErrorBox error={run.error} onRetry={() => run.mutate()} />
      </Card>

      <Card title="Engine answer" testId="setup-result">
        {!plan ? (
          <p className="text-[var(--text-muted)]">Pick a goal and press the button. The engine checks feasibility at once.</p>
        ) : (
          <div className="space-y-3">
            <StatusBadge plan={plan} testId="setup-status" />
            {plan.status === "FEASIBLE" ? (
              <p>
                Fits in {plan.days.length} study days. Planned in <b>{session?.replan_ms} ms</b>.
              </p>
            ) : (
              <>
                <p data-testid="shortfall">
                  Short by <b>{plan.shortfall_days} day(s)</b>.
                  {EXACT.has(plan.reason ?? "") && <Chip tone="accent">exact (CP-SAT proved it)</Chip>}
                </p>
                {plan.options.length > 0 && (
                  <ul className="list-disc pl-6" data-testid="options">
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
