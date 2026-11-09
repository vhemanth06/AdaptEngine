// Typed fetch client; types are generated from the FastAPI OpenAPI schema (npm run gen:types).
import type { components } from "./schema";

type S = components["schemas"];
export type CurriculumSummary = S["CurriculumSummary"];
export type Curriculum = S["CurriculumDetail"];
export type Session = S["SessionOut"];
export type Plan = S["PlanOut"];
export type PlanDay = S["PlanDayOut"];
export type ConceptState = S["ConceptState"];
export type EventResult = S["EventResult"];
export type Trace = S["TraceOut"];
export type SimulateOut = S["SimulateOut"];
export type SimulateRequest = S["SimulateRequest"];
export type Evaluation = S["EvaluationOut"];
export type TraceRecord = Record<string, unknown>;

async function req<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = (data as { detail?: unknown }).detail;
    throw new Error(typeof d === "string" ? d : JSON.stringify(d ?? res.statusText));
  }
  return data as T;
}

export const api = {
  curricula: () => req<CurriculumSummary[]>("/curricula"),
  curriculum: (id: string) => req<Curriculum>(`/curricula/${id}`),
  createSession: (b: S["CreateSession"]) => req<Session>("/sessions", b),
  session: (sid: string) => req<Session>(`/sessions/${sid}`),
  answer: (sid: string, b: S["DiagnosticAnswer"]) => req<Session>(`/sessions/${sid}/diagnostic/answer`, b),
  plan: (sid: string, b: S["PlanRequest"]) => req<Session>(`/sessions/${sid}/plan`, b),
  event: (sid: string, b: S["EventRequest"]) => req<EventResult>(`/sessions/${sid}/events`, b),
  trace: (sid: string, aid: string) =>
    req<Trace>(`/sessions/${sid}/trace?activity_id=${encodeURIComponent(aid)}`),
  simulate: (b: Partial<SimulateRequest> & Pick<SimulateRequest, "curriculum" | "goal">) =>
    req<SimulateOut>("/simulate", b),
  evaluation: () => req<Evaluation>("/evaluation"),
};

// Content entries follow data/content/README.md; absent for curricula without a content file.
export type ContentEntry = {
  type: "LESSON" | "EXERCISE";
  title?: string;
  markdown?: string;
  prompt?: string;
  options?: string[];
  correct?: number;
  explanation?: string;
};
export const contentOf = (c: Curriculum | undefined, aid: string) =>
  c?.content?.[aid] as ContentEntry | undefined;
