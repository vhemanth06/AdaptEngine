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
