// Plan FE (D95, FE-TC8 to FE-TC10): every screen in light and dark, failure states, palette,
// theme and keys. Screenshots are saved as pictures only and never compared pixel by pixel.
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

const TABS = ["overview", "setup", "diagnostic", "map", "plan", "study", "disruptions", "autopilot"];
const OUT = process.env.AE_FIGURES ? resolve("../../docs/figures") : resolve("test-results/screens");
const shotPath = (t: string, theme: string) =>
  process.env.AE_FIGURES ? `${OUT}/ui_${t}_${theme}.png` : `${OUT}/${t}-${theme}.png`;

async function seededSession(request: import("@playwright/test").APIRequestContext) {
  const p = await (await request.get("/api/demo-preset")).json();
  const body = {
    curriculum: p.curriculum,
    goal: p.goal,
    deadline_day: p.deadline_day,
    budget: p.budget,
    model_profile: p.model_profile,
    diagnostic_method: p.diagnostic_method,
    planner_method: p.planner_method,
  };
  const s = await (await request.post("/api/sessions", { data: body })).json();
  let view = s;
  const known = new Set<string>(p.known);
  while (!view.diagnostic.done) {
    const it = view.diagnostic.next_item;
    view = await (
      await request.post(`/api/sessions/${s.session_id}/diagnostic/answer`, {
        data: { activity_id: it.activity_id, correct: known.has(it.concept_id) },
      })
    ).json();
  }
  return s.session_id as string;
}

for (const theme of ["light", "dark"] as const) {
  test(`all screens render (${theme})`, async ({ page, request }) => {
    const sid = await seededSession(request);
    await page.addInitScript(
      ([s, th]) => {
        localStorage.setItem("ae.sid", s);
        localStorage.setItem("ae.theme", th);
      },
      [sid, theme],
    );
    await page.emulateMedia({ reducedMotion: "reduce" }); // no half-faded nav state in the shots
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    for (const t of TABS) {
      await page.getByTestId(`tab-${t}`).click();
      await expect(page.getByTestId(`tab-${t}`)).toHaveAttribute("aria-current", "page");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByText(/screen failed to render/)).toHaveCount(0);
      if (t === "autopilot") {
        await page.getByTestId("run-autopilot").click(); // 20 learners: a figure with results
        await expect(page.getByTestId("autopilot-results")).toBeVisible({ timeout: 60_000 });
      }
      await page.waitForLoadState("networkidle");
      await page.screenshot({ path: shotPath(t, theme) });
    }
    // removed in Plan FE (D92)
    for (const gone of ["Policy Lab", "Authoring Studio", "Evaluation"])
      await expect(page.getByRole("navigation", { name: "Screens" }).getByText(gone, { exact: true })).toHaveCount(0);
  });
}

test("unknown stored session shows a recovery message", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("ae.sid", "0".repeat(32)));
  await page.goto("/");
  await expect(page.getByRole("alert").filter({ hasText: "Stored session not found" })).toBeVisible();
  await page.getByRole("button", { name: "Start over" }).click();
  await expect(page.getByTestId("make-plan")).toBeVisible();
});

test("API down shows an inline error with retry, not a blank screen", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("make-plan")).toBeVisible();
  await page.route("**/api/**", (r) => r.abort());
  await page.getByTestId("make-plan").click();
  await expect(page.getByRole("alert")).toContainText(/not reachable/);
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

test("command palette jumps to a screen", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Control+k");
  await expect(page.getByTestId("palette")).toBeVisible();
  await page.getByLabel("Search commands").fill("Autopilot");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Autopilot");
});

test("theme toggle switches data-theme", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("ae.theme", "light"));
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByTestId("theme-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("keys 1-4 answer in the diagnostic", async ({ page, request }) => {
  const s = await (
    await request.post("/api/sessions", { data: { curriculum: "8node", goal: "C8", deadline_day: 10, budget: 10 } })
  ).json();
  await page.addInitScript((sid) => localStorage.setItem("ae.sid", sid), s.session_id);
  await page.goto("/");
  await page.getByTestId("tab-diagnostic").click();
  await expect(page.getByTestId("diag-item-id")).toBeVisible();
  await page.keyboard.press("1");
  await expect(page.getByTestId("diag-items").locator("li")).toHaveCount(1);
});

test("a finished day shows as complete until Next day", async ({ page, request }) => {
  const s = await (
    await request.post("/api/sessions", { data: { curriculum: "8node", goal: "C8", deadline_day: 10, budget: 10 } })
  ).json();
  const sid = s.session_id;
  let view = await (await request.post(`/api/sessions/${sid}/plan`, { data: {} })).json();
  const first: string = view.today.activities[0];
  await page.addInitScript((id) => localStorage.setItem("ae.sid", id), sid);
  await page.goto("/");
  await page.getByTestId("tab-study").click();
  await expect(page.getByTestId("day-chip")).toHaveText("Day 1");
  while (view.today) {
    // do day 1's work through the API (right on every exercise)
    const aid: string = view.today.activities[0];
    const data = aid.startsWith("E-") ? { kind: "COMPLETED", activity_id: aid, correct: true } : { kind: "COMPLETED", activity_id: aid };
    view = (await (await request.post(`/api/sessions/${sid}/events`, { data })).json()).session;
  }
  await page.reload();
  await page.getByTestId("tab-study").click();
  await expect(page.getByTestId("day-complete")).toHaveText("✓ Day 1 complete");
  await expect(page.getByTestId("day-chip")).toHaveText("Day 1"); // stays on day 1
  await page.getByTestId("study-next-day").click();
  await expect(page.getByTestId("day-chip")).toHaveText("Day 2");
  await expect(page.getByTestId("study-card")).toContainText("Day 2 ·");
  await expect(page.getByTestId("study-card").locator("code").first()).not.toHaveText(first);
  await page.getByTestId("next-day").click(); // the top-bar button does the same
  await expect(page.getByTestId("day-chip")).toHaveText("Day 3");
});

test("setup locks the curriculum and switches once the session has a plan", async ({ page, request }) => {
  const s = await (
    await request.post("/api/sessions", { data: { curriculum: "8node", goal: "C8", deadline_day: 10, budget: 10 } })
  ).json();
  await request.post(`/api/sessions/${s.session_id}/plan`, { data: {} });
  await page.addInitScript((id) => localStorage.setItem("ae.sid", id), s.session_id);
  await page.goto("/");
  await page.getByTestId("tab-setup").click();
  const bisection = page.getByTestId("switch-diagnostic").getByRole("radio", { name: "bisection" });
  await expect(bisection).toBeDisabled();
  await expect(page.getByLabel("Curriculum")).toBeDisabled();
  await expect(page.getByTestId("make-plan")).toHaveText("Re-plan");
  // goal, deadline and budget still re-plan the same session
  await page.getByLabel("Deadline (day)").fill("12");
  await page.getByTestId("make-plan").click();
  await expect(page.getByTestId("session-chip")).toContainText(s.session_id.slice(0, 6));

  await page.getByTestId("new-session").click();
  await expect(bisection).toBeEnabled();
  await bisection.click();
  await expect(page.getByTestId("make-plan")).toHaveText("Start session and plan");
  await page.getByTestId("keep-session").click(); // back to the current session's switches, locked
  await expect(bisection).toBeDisabled();
  await expect(page.getByTestId("make-plan")).toHaveText("Re-plan");
});
