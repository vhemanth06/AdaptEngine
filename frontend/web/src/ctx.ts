import { useEffect } from "react";
import type { Curriculum, EventResult, Plan, Session } from "./api/client";
import type { components } from "./api/schema";

export const TABS = [
  ["setup", "1 Setup"],
  ["diagnostic", "2 Diagnostic"],
  ["map", "3 Map"],
  ["plan", "4 Plan + Why?"],
  ["study", "5 Study"],
  ["disruptions", "6 Disruptions"],
  ["autopilot", "7 Autopilot"],
  ["evaluation", "8 Evaluation"],
] as const;
export type Tab = (typeof TABS)[number][0];

export type LastEvent = { result: EventResult; oldPlan?: Plan | null; label: string };

export type Ctx = {
  sid: string | null;
  session?: Session;
  cur?: Curriculum;
  demo: boolean;
  setSession: (s: Session) => void;
  go: (t: Tab) => void;
  lastEvent: LastEvent | null;
  sendEvent: (body: components["schemas"]["EventRequest"], label: string) => Promise<EventResult>;
};

// Scripted demo learner (deterministic demo mode): knows these concepts, nothing else.
export const DEMO_KNOWN = new Set(["C1", "C2", "C3", "C6"]);
export const DEMO_SETUP = { curriculum: "8node", goal: "C8", deadline_day: 10, budget: 10 };

// Keyboard answering: digits 1-4 call handler(0..3) while active.
export function useDigitKeys(active: boolean, handler: (i: number) => void) {
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      const n = Number(e.key);
      if (n >= 1 && n <= 4) handler(n - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, handler]);
}

export const store = {
  get: (k: string) => {
    try {
      return localStorage.getItem(k);
    } catch {
      return null;
    }
  },
  set: (k: string, v: string | null) => {
    try {
      if (v === null) localStorage.removeItem(k);
      else localStorage.setItem(k, v);
    } catch {
      /* storage unavailable: session just won't survive a reload */
    }
  },
};
