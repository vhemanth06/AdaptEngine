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
export type Health = S["Health"];
export type DraftOut = S["DraftOut"];
export type PolicyPreview = S["PolicyPreviewOut"];
export type Propose = S["ProposeOut"];
export type Strategy = S["StrategyOut"];

async function req<T>(path: string, body?: unknown, method?: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: method ?? (body === undefined ? "GET" : "POST"),
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("The API is not reachable. Start it with `make demo` (or `make demo-api`).");
  }
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
  health: () => req<Health>("/health"),
  policyPreview: (sid: string, policy: S["PolicyPreviewRequest"]["policy"]) =>
    req<PolicyPreview>(`/sessions/${sid}/policy-preview`, { policy }),
  propose: (sid: string, mode: S["ProposeRequest"]["mode"]) => req<Propose>(`/sessions/${sid}/propose-plan`, { mode }),
  strategy: (sid: string) => req<Strategy>(`/sessions/${sid}/strategy`),
  draft: (b: S["DraftRequest"]) => req<DraftOut>("/authoring/draft", b),
  getDraft: (name: string) => req<DraftOut>(`/authoring/drafts/${encodeURIComponent(name)}`),
  editDraft: (name: string, content: Record<string, Record<string, unknown>>) =>
    req<DraftOut>(`/authoring/drafts/${encodeURIComponent(name)}`, { content }, "PUT"),
  approve: (name: string, reviewer: string) =>
    req<{ approved: boolean; reviewer: string; recorded: string[] }>("/authoring/approve", { name, reviewer }),
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
