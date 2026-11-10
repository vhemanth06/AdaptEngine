// W8 H.17: every screen renders in light and dark (visual snapshots), plus failure states.
import { expect, test } from "@playwright/test";

const TABS = ["overview", "setup", "diagnostic", "map", "plan", "study", "disruptions", "policy", "authoring", "autopilot", "evaluation"];

for (const theme of ["light", "dark"] as const) {
  test(`all screens render (${theme})`, async ({ page, request }) => {
    const s = await (await request.post("/api/sessions", { data: { curriculum: "8node", goal: "C8", deadline_day: 10, budget: 10 } })).json();
    await request.post(`/api/sessions/${s.session_id}/plan`, { data: {} });
    await page.addInitScript(([sid, th]) => {
      localStorage.setItem("ae.sid", sid);
      localStorage.setItem("ae.theme", th);
    }, [s.session_id, theme]);
    await page.goto("/");
    for (const t of TABS) {
      await page.getByTestId(`tab-${t}`).click();
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByText(/screen failed to render/)).toHaveCount(0);
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveScreenshot(`${t}-${theme}.png`, { fullPage: false, maxDiffPixelRatio: 0.02, mask: [page.getByTestId("code-hash")] });
    }
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
  await page.route("**/api/**", (r) => r.abort());
  await page.getByTestId("tab-evaluation").click();
  await expect(page.getByRole("alert")).toContainText(/not reachable|Failed/);
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});
