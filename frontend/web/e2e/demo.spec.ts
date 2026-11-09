// The 6-minute demo script (report §10.5) in deterministic demo mode; doubles as the rehearsal.
import { expect, test } from "@playwright/test";

test("6-minute demo script", async ({ page, request }) => {
  await page.goto("/");
  await page.getByTestId("reset").click();

  // 1. Setup: C8, 10 min/day, deadline 10 -> FEASIBLE; 5 min/day -> not feasible, shortfall shown.
  await page.getByLabel("Goal concept").selectOption("C8");
  await page.getByLabel("Deadline (day)").fill("10");
  await page.getByLabel("Minutes per day").selectOption("10");
  await page.getByTestId("make-plan").click();
  await expect(page.getByTestId("setup-status")).toContainText("✓ FEASIBLE");
  await page.getByLabel("Minutes per day").selectOption("5");
  await page.getByTestId("make-plan").click();
  await expect(page.getByTestId("setup-status")).toContainText(/INFEASIBLE|UNKNOWN/);
  await expect(page.getByTestId("shortfall")).toContainText(/Short by \d+ day/);
  await page.getByLabel("Minutes per day").selectOption("10");
  await page.getByTestId("make-plan").click();
  await expect(page.getByTestId("setup-status")).toContainText("✓ FEASIBLE");

  // 2. Diagnostic: first answer with the keyboard (right key, as the demo learner knows C1),
  //    the rest by the scripted demo learner.
  await page.getByTestId("tab-diagnostic").click();
  const aid = (await page.getByTestId("diag-item-id").textContent())!;
  const content = (await (await request.get("/api/curricula/8node")).json()).content;
  await page.keyboard.press(String(content[aid].correct + 1));
  await expect(page.getByTestId("diag-items").locator("li")).toHaveCount(1);
  await expect(page.getByTestId("diag-items")).toContainText("right");
  for (let i = 0; i < 12 && (await page.getByTestId("demo-answer").isVisible()); i++) {
    await page.getByTestId("demo-answer").click();
    await expect(page.getByTestId("diag-items").locator("li")).toHaveCount(i + 2);
  }
  // Stop reasons come from the engine (which concepts get skipped depends on its current rules).
  await expect(page.getByTestId("stop-reasons").locator("tr")).toHaveCount(8);

  await page.getByTestId("tab-map").click();
  await expect(page.getByTestId("node-C1")).toHaveAttribute("data-status", "mastered");
  await expect(page.getByTestId("node-C8")).toBeVisible();

  // 3. Plan -> click a card -> "Why?" shows score components.
  await page.getByTestId("tab-plan").click();
  await page.getByTestId("timeline").locator("[data-testid^=card-]").first().click();
  await expect(page.getByTestId("why")).toContainText("unlock");
  await expect(page.getByTestId("why")).toContainText("RANKED_TOP");

  // 4. Study: answer wrong twice -> remediation, plan updated at once.
  await page.getByTestId("tab-study").click();
  let wrong = 0;
  for (let i = 0; i < 10 && wrong < 2; i++) {
    const before = await page.getByTestId("study-card").textContent();
    if (await page.getByTestId("lesson-done").isVisible()) {
      await page.getByTestId("lesson-done").click();
    } else {
      await page.getByTestId("demo-wrong").click();
      wrong++;
    }
    await expect(page.getByTestId("study-card")).not.toHaveText(before!);
  }
  expect(wrong).toBe(2);
  await expect(page.getByTestId("remediation-flag")).toBeVisible();
  await expect(page.getByTestId("replan-info")).toContainText("ms");
  await page.getByTestId("tab-plan").click();
  await expect(page.getByTestId("timeline").getByText("Remediation").first()).toBeVisible();

  // 5. Disruption: missed day -> old vs new plan diff with latency.
  await page.getByTestId("tab-disruptions").click();
  await page.getByTestId("missed-day").click();
  await expect(page.getByTestId("diff")).toBeVisible();
  await expect(page.getByTestId("latency")).toHaveText(/\d+(\.\d+)? ms/);
  await expect(page.getByTestId("new-plan")).toBeVisible();

  // 6. Autopilot and evaluation.
  await page.getByTestId("tab-autopilot").click();
  await page.getByTestId("run-autopilot").click();
  await expect(page.getByTestId("autopilot-results")).toBeVisible({ timeout: 60_000 });
  await page.getByTestId("tab-evaluation").click();
  await expect(page.getByTestId("evaluation")).toBeVisible();
});
