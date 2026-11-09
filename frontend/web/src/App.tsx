import { useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Session } from "./api/client";
import { TABS, store, type Ctx, type LastEvent, type Tab } from "./ctx";
import { StatusBadge } from "./components/ui";
import Setup from "./pages/Setup";
import Diagnostic from "./pages/Diagnostic";
import CurriculumMap from "./pages/CurriculumMap";
import PlanPage from "./pages/PlanPage";
import Study from "./pages/Study";
import Disruptions from "./pages/Disruptions";
import Autopilot from "./pages/Autopilot";
import Evaluation from "./pages/Evaluation";

export default function App() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("setup");
  const [sid, setSidState] = useState<string | null>(() => store.get("ae.sid"));
  const [demo, setDemo] = useState(true);
  const [lastEvent, setLastEvent] = useState<LastEvent | null>(null);

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

  const reset = () => {
    store.set("ae.sid", null);
    setSidState(null);
    setLastEvent(null);
    setTab("setup");
  };

  const ctx: Ctx = {
    sid,
    session,
    cur: curQ.data,
    demo,
    setSession,
    go: setTab,
    lastEvent,
    sendEvent: async (body, label) => {
      const oldPlan = session?.plan;
      const result = await api.event(sid!, body);
      setSession(result.session);
      setLastEvent({ result, oldPlan, label });
      return result;
    },
  };

  const Page = {
    setup: Setup,
    diagnostic: Diagnostic,
    map: CurriculumMap,
    plan: PlanPage,
    study: Study,
    disruptions: Disruptions,
    autopilot: Autopilot,
    evaluation: Evaluation,
  }[tab];

  return (
    <div className="mx-auto max-w-[1500px] p-4">
      <header className="mb-4 flex flex-wrap items-center gap-4">
        <h1 className="text-2xl font-bold">AdaptEngine demo</h1>
        <StatusBadge plan={session?.plan} testId="plan-status" />
        {session?.effective && (
          <span data-testid="effective">
            Day {session.effective.current_day} · deadline {session.effective.deadline_day} ·{" "}
            {session.effective.budget} min/day
          </span>
        )}
        <span className="flex-1" />
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} className="h-5 w-5" />
          Demo mode
        </label>
        <button
          type="button"
          data-testid="reset"
          onClick={reset}
          className="rounded-lg border border-slate-400 bg-white px-3 py-1 hover:bg-slate-100"
        >
          Reset demo
        </button>
      </header>
      <nav className="mb-4 flex flex-wrap gap-2" aria-label="Screens">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            data-testid={`tab-${key}`}
            aria-current={tab === key ? "page" : undefined}
            onClick={() => setTab(key)}
            className={`rounded-lg px-3 py-2 font-medium ${
              tab === key ? "bg-slate-900 text-white" : "border border-slate-300 bg-white hover:bg-slate-100"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>
      {sessionQ.isError && (
        <p role="alert" className="mb-3">
          Stored session not found. <button className="underline" onClick={reset}>Start over</button>
        </p>
      )}
      <main>
        <Page {...ctx} />
      </main>
    </div>
  );
}
