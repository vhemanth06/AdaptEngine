import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Curriculum, type EventResult, type Plan, type Session } from "./api/client";
import type { components } from "./api/schema";

// Plan FE (D92): eight screens grouped in the sidebar (Learner / Adaptation / Evidence).
export const TABS = [
  ["overview", "Overview", "Learner"],
  ["setup", "Setup", "Learner"],
  ["diagnostic", "Diagnostic", "Learner"],
  ["map", "Curriculum map", "Learner"],
  ["plan", "Plan + Why?", "Learner"],
  ["study", "Study", "Learner"],
  ["disruptions", "Disruptions", "Adaptation"],
  ["autopilot", "Autopilot", "Evidence"],
] as const;
export type Tab = (typeof TABS)[number][0];
export const GROUPS = ["Learner", "Adaptation", "Evidence"] as const;

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

// The fixed demo preset and scripted learner (D94) come from the API, never from the browser.
export const useDemoPreset = () =>
  useQuery({ queryKey: ["demo-preset"], queryFn: api.demoPreset, staleTime: Infinity });

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });

// Keyboard answering: digits 1-4 call handler(0..3) while active.
export function useDigitKeys(active: boolean, handler: (i: number) => void) {
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLSelectElement ||
        e.target instanceof HTMLTextAreaElement
      )
        return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
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

// Display names of redo's three switches (Setup, top bar, Autopilot)
export const DIAGNOSTICS = ["sweep", "bisection"] as const;
export const MODELS = ["heuristic", "fitted_assist09", "fitted_ct"] as const;
export const PLANNERS = ["greedy", "hybrid", "cpsat"] as const;
export const MODEL_LABEL: Record<string, string> = {
  heuristic: "heuristic",
  fitted_assist09: "fitted ASSISTments",
  fitted_ct: "fitted Cognitive Tutor",
};
export const PLANNER_LABEL: Record<string, string> = { greedy: "greedy", hybrid: "hybrid", cpsat: "CP-SAT" };
