// The demo script (final report R§3.6) in deterministic demo mode; doubles as the rehearsal.
import { expect, test, type Page } from "@playwright/test";

const budget = (page: Page, b: string) =>
  page.getByRole("radiogroup", { name: "Minutes per day" }).getByRole("radio", { name: b, exact: true }).click();

test("8-minute demo script", async ({ page, request }) => {
  await page.goto("/");
  await page.getByTestId("reset").click();

  // 1. Setup: C8, 10 min/day, deadline 10 -> FEASIBLE; 5 min/day -> not feasible, shortfall shown.
  await page.getByLabel("Goal concept").selectOption("C8");
  await page.getByLabel("Deadline (day)").fill("10");
  await budget(page, "10");
  await page.getByTestId("make-plan").click();
  await expect(page.getByTestId("setup-status")).toContainText("✓ FEASIBLE");
  await budget(page, "5");
  await page.getByTestId("make-plan").click();
  await expect(page.getByTestId("setup-status")).toContainText(/INFEASIBLE|UNKNOWN/);
  await expect(page.getByTestId("shortfall")).toContainText(/Short by \d+ day/);
  await budget(page, "10");
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
  const known = new Set(["C1", "C2", "C3", "C6"]); // scripted demo learner
  for (let i = 0; i < 12 && (await page.getByTestId("demo-right").isVisible()); i++) {
    const id = (await page.getByTestId("diag-item-id").textContent())!; // e.g. E-C3-0.8
    await page.getByTestId(known.has(id.split("-")[1]) ? "demo-right" : "demo-wrong").click();
    await expect(page.getByTestId("diag-items").locator("li")).toHaveCount(i + 2);
  }
  // Stop reasons come from the engine (which concepts get skipped depends on its current rules).
  await expect(page.getByTestId("stop-reasons").locator("tr")).toHaveCount(7); // goal C8's path: C4 is not diagnosed

  await expect(page.getByTestId("stop-reasons")).toContainText("inferred from a later concept");

  await page.getByTestId("tab-map").click();
  await expect(page.getByTestId("node-C1")).not.toHaveAttribute("data-status", "mastered");
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

  // 6. Autopilot: belief vs reality.
  await page.getByTestId("tab-autopilot").click();
  await page.getByTestId("run-autopilot").click();
  await expect(page.getByTestId("autopilot-results")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("belief-vs-reality")).toContainText("false mastery");

  // 7. Policy Lab: bandit candidates + propensities; a forced bad agent output is rejected.
  await page.getByTestId("tab-policy").click();
  await page.getByRole("radiogroup", { name: "Ranking policy" }).getByRole("radio", { name: "bandit_frozen" }).click();
  await page.getByTestId("run-policy").click();
  await expect(page.getByTestId("policy-decisions")).toContainText("propensity");
  await page.getByRole("radiogroup", { name: "Ranking policy" }).getByRole("radio", { name: "agent_bad" }).click();
  await page.getByTestId("run-policy").click();
  await expect(page.getByTestId("fallback-badge").first()).toContainText("AGENT_FALLBACK");

  // 8. Plan proposer: the engine rejects an invalid agent plan with its reasons.
  await page.getByTestId("tab-plan").click();
  await page.getByTestId("propose-bad").click();
  await expect(page.getByTestId("proposal-result")).toContainText("PREREQUISITE_ORDER");

  // 9. Evaluation.
  await page.getByTestId("tab-evaluation").click();
  await expect(page.getByTestId("evaluation").or(page.getByText("Final grid not found"))).toBeVisible();
});
