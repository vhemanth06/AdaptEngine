import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Curriculum, type Session } from "./api/client";
import { TABS, store, type Ctx, type LastEvent, type Tab } from "./ctx";
import { Button, ErrorBoundary, LoadingCard, ToastProvider, conceptName, useToast } from "./components/ui";
import { Footer, Page, Sidebar, TopBar } from "./shell/AppShell";
import CommandPalette, { type Command } from "./shell/CommandPalette";
import Overview from "./pages/Overview";
import Setup from "./pages/Setup";
import Diagnostic from "./pages/Diagnostic";
import PlanPage from "./pages/PlanPage";
import Study from "./pages/Study";
import Disruptions from "./pages/Disruptions";
import PolicyLab from "./pages/PolicyLab";
import AuthoringStudio from "./pages/AuthoringStudio";

// React Flow and Recharts screens are loaded on demand (H.16 bundle budget).
const CurriculumMap = lazy(() => import("./pages/CurriculumMap"));
const Autopilot = lazy(() => import("./pages/Autopilot"));
const Evaluation = lazy(() => import("./pages/Evaluation"));

const SUBTITLE: Record<Tab, string> = {
  overview: "Where the learner is and what happens next.",
  setup: "Goal, deadline and daily time; the engine answers with a feasibility verdict at once.",
  diagnostic: "Adaptive questions; the belief update after every answer.",
  map: "Prerequisite structure and why concepts are locked or unlocked.",
  plan: "The day-by-day plan; every card explains itself.",
  study: "Lessons and questions; the closed loop replans after every answer.",
  disruptions: "Missed days, budget and deadline changes; old vs new plan.",
  policy: "Ranking policies only re-order engine-approved options; every choice is logged and checked.",
  authoring: "AI drafts content; a human reviews it; the engine only accepts reviewed content.",
  autopilot: "Simulated learners: belief vs reality.",
  evaluation: "Final pre-registered results on held-out seeds, wins and losses.",
};

function initialTheme() {
  const saved = store.get("ae.theme");
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  );
}

function Shell() {
  const qc = useQueryClient();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>(() => (store.get("ae.sid") ? "overview" : "setup"));
  const [sid, setSidState] = useState<string | null>(() => store.get("ae.sid"));
  const [demo, setDemo] = useState(true);
  const [theme, setTheme] = useState(initialTheme);
  const [lastEvent, setLastEvent] = useState<LastEvent | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    store.set("ae.theme", theme);
  }, [theme]);

  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });
  const sessionQ = useQuery({ queryKey: ["session", sid], queryFn: () => api.session(sid!), enabled: !!sid });
  const session = sessionQ.data;
  const curId = session?.curriculum;
  const curQ = useQuery({ queryKey: ["curriculum", curId], queryFn: () => api.curriculum(curId!), enabled: !!curId });

  const setSession = useCallback(
    (s: Session) => {
      qc.setQueryData(["session", s.session_id], s);
      store.set("ae.sid", s.session_id);
      setSidState(s.session_id);
    },
    [qc],
  );

  const reset = useCallback(() => {
    store.set("ae.sid", null);
    setSidState(null);
    setLastEvent(null);
    setTab("setup");
  }, []);

  const sendEvent: Ctx["sendEvent"] = async (body, label) => {
    const oldPlan = session?.plan;
    const result = await api.event(sid!, body);
    setSession(result.session);
    setLastEvent({ result, oldPlan, label });
    if (result.changes.length)
      toast(`Plan updated: ${result.changes.length} ${result.changes.length === 1 ? "activity" : "activities"} moved`, "remediation");
    return result;
  };

  const ctx: Ctx = { sid, session, cur: curQ.data, demo, setSession, go: setTab, lastEvent, sendEvent };

  const commands: Command[] = useMemo(
    () => [
      ...TABS.map(([key, label]) => ({ id: `go-${key}`, label, group: "Go to", run: () => setTab(key) })),
      {
        id: "miss",
        label: "Miss today (MISSED event)",
        group: "Action",
        run: () => {
          if (sid) sendEvent({ kind: "MISSED" }, "palette").catch((e) => toast(String(e), "violation"));
          setTab("disruptions");
        },
      },
      { id: "theme", label: "Toggle light / dark theme", group: "Action", run: () => setTheme((t) => (t === "dark" ? "light" : "dark")) },
      { id: "reset", label: "Reset demo", group: "Action", run: reset },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sid, session, reset],
  );

  const Screen = {
    overview: Overview,
    setup: Setup,
    diagnostic: Diagnostic,
    map: CurriculumMap,
    plan: PlanPage,
    study: Study,
    disruptions: Disruptions,
    policy: PolicyLab,
    authoring: AuthoringStudio,
    autopilot: Autopilot,
    evaluation: Evaluation,
  }[tab];
  const title = TABS.find((t) => t[0] === tab)![1];

  return (
    <div className="flex min-h-screen">
      <Sidebar tab={tab} go={setTab} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          session={session}
          demo={demo}
          setDemo={setDemo}
          theme={theme}
          toggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          reset={reset}
        />
        <main className="flex-1">
          <Page title={title} subtitle={SUBTITLE[tab]}>
            {sessionQ.isError && (
              <div role="alert" className="mb-4 rounded-[var(--radius)] border border-[var(--remediation)] bg-[var(--remediation-soft)] p-3">
                Stored session not found ({String((sessionQ.error as Error).message)}).{" "}
                <button className="underline" onClick={reset}>
                  Start over
                </button>
              </div>
            )}
            <ErrorBoundary key={tab} name={title}>
              <Suspense fallback={<LoadingCard label={`Loading ${title}`} />}>
                <Screen {...ctx} />
              </Suspense>
            </ErrorBoundary>
          </Page>
        </main>
        <Footer health={health.data} />
      </div>
      <CommandPalette commands={commands} />
      <GoalReached session={session} cur={curQ.data} />
    </div>
  );
}

// The engine plans no new learning once every required concept is believed mastered.
const GOAL_DONE = new Set(["GOAL_ALREADY_MASTERED", "CONSOLIDATION"]);

function GoalReached({ session, cur }: { session?: Session; cur?: Curriculum }) {
  const [closed, setClosed] = useState<string | null>(null);
  const key = session ? `ae.congrats.${session.session_id}` : null;
  const reached = !!session?.plan?.reason && GOAL_DONE.has(session.plan.reason);
  const open = !!key && reached && closed !== key && !store.get(key);
  const close = useCallback(() => {
    if (key) store.set(key, "1");
    setClosed(key);
  }, [key]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={close}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="goal-reached-title"
        data-testid="goal-reached"
        className="ae-in w-[440px] max-w-[92vw] space-y-4 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-6 text-center shadow-[var(--shadow-overlay)]"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-4xl" aria-hidden="true">🎉</p>
        <h2 id="goal-reached-title" className="text-2xl font-bold">
          Congrats, goal reached!
        </h2>
        <p>
          You have mastered <b>{conceptName(cur, session!.context.goal)}</b> and its prerequisites.
        </p>
        <Button testId="goal-reached-close" onClick={close}>
          Nice!
        </Button>
      </div>
    </div>
  );
}
