// Plan FE (D94, FE-TC7): the demo walkthrough of frontend/README.md in deterministic demo mode.
// Every value comes from GET /api/demo-preset; the scripted learner only answers questions.
import { expect, test, type Page } from "@playwright/test";

type Preset = {
  curriculum: string;
  goal: string;
  deadline_day: number;
  budget: number;
  known: string[];
  tight: { deadline_day: number; budget: number };
  has_check: boolean;
  wrong_check: string | null;
};

const setBudget = (page: Page, b: number) =>
  page.getByRole("radiogroup", { name: "Minutes per day" }).getByRole("radio", { name: String(b), exact: true }).click();

async function setContext(page: Page, deadline: number, budget: number) {
  await page.getByLabel("Deadline (day)").fill(String(deadline));
  await setBudget(page, budget);
  await page.getByTestId("make-plan").click();
}

test("demo walkthrough", async ({ page, request }) => {
  test.setTimeout(240_000);
  const p: Preset = await (await request.get("/api/demo-preset")).json();
  await page.goto("/");
  await page.getByTestId("reset").click();

  // 1. Setup: demo preset (planner CP-SAT) -> feasible; the tight variant -> CP-SAT's exact answer;
  //    back -> feasible again.
  await page.getByTestId("use-demo-preset").click();
  await expect(page.getByRole("radiogroup", { name: "Planner" }).getByRole("radio", { name: "CP-SAT" })).toHaveAttribute("aria-checked", "true");
  await page.getByTestId("make-plan").click();
  await expect(page.getByTestId("setup-status")).toContainText("✓ FEASIBLE");
  await expect(page.getByTestId("session-chip")).toContainText(p.curriculum);
  await setContext(page, p.tight.deadline_day, p.tight.budget);
  await expect(page.getByTestId("setup-status")).toContainText("INFEASIBLE");
  await expect(page.getByTestId("setup-status")).toContainText("CPSAT_INFEASIBLE");
  await expect(page.getByTestId("shortfall")).toContainText(/Short by \d+ day/);
  await expect(page.getByTestId("options").locator("li").first()).toBeVisible();
  await expect(page.getByTestId("options")).toContainText(/exactly|Increase daily budget/);
  await setContext(page, p.deadline_day, p.budget);
  await expect(page.getByTestId("setup-status")).toContainText("✓ FEASIBLE");

  // 2. Diagnostic: answer right exactly on the known set until bisection stops; inferred concepts.
  await page.getByTestId("tab-diagnostic").click();
  const known = new Set(p.known);
  for (let i = 0; i < 40 && (await page.getByTestId("answer-right").isVisible()); i++) {
    const aid = (await page.getByTestId("diag-item-id").textContent())!; // E-<concept>-<difficulty>
    await page.getByTestId(known.has(aid.split("-")[1]) ? "answer-right" : "answer-wrong").click();
    await expect(page.getByTestId("diag-items").locator("li")).toHaveCount(i + 1);
    if (i === 0) await expect(page.getByTestId("diag-budget")).toContainText(/budget \d+/);
  }
  await expect(page.getByTestId("stop-reasons")).toBeVisible();
  await expect(page.getByTestId("stop-reasons")).toContainText("not asked");
  expect(await page.locator("[data-testid^=chip-inferred-]").count()).toBeGreaterThan(0);

  // 3. Curriculum map: inferred / check pending badges next to the usual states.
  await page.getByTestId("tab-map").click();
  await expect(page.getByTestId(`node-${p.goal}`)).toBeVisible();
  expect(await page.locator("[data-testid^=badge-inferred-]").count()).toBeGreaterThan(0);
  if (p.has_check) expect(await page.locator("[data-testid^=badge-check-]").count()).toBeGreaterThan(0);

  // 4. Plan + Why?: a "Check" card, then a lesson card (CP-SAT's earliest-day explanation).
  await page.getByTestId("tab-plan").click();
  if (p.has_check) {
    const check = page.locator("[data-testid^=badge-check-]").first();
    const aid = (await check.getAttribute("data-testid"))!.replace("badge-check-", "");
    await page.getByTestId(`card-${aid}`).first().click();
    await expect(page.getByTestId("why-confirmation")).toContainText("Short check instead of the full workload");
  }
  await page.getByTestId("timeline").locator("[data-testid^=card-L-]").first().click();
  await expect(page.getByTestId("why-cpsat").first()).toContainText(/Earliest possible: day \d+, because/);

  // 5. Study: answer wrong on the preset's confirmation check (fallback: on an exercise) -> replan
  // toast at once; the concept stays "check pending" (confirmation still within reach, engine rule).
  await page.getByTestId("tab-study").click();
  let concept = "";
  for (let i = 0; i < 40 && !concept; i++) {
    const aid = (await page.getByTestId("study-card").locator("code").first().textContent())!;
    const before = await page.getByTestId("study-card").textContent();
    if ((p.has_check && aid === p.wrong_check) || (!p.has_check && aid.startsWith("E-"))) {
      if (p.has_check) await expect(page.getByTestId("study-check")).toBeVisible();
      concept = aid.split("-")[1];
      await page.getByTestId("answer-wrong").click();
    } else if (await page.getByTestId("lesson-done").isVisible()) {
      await page.getByTestId("lesson-done").click();
    } else {
      // the scripted learner: right exactly on the preset's known concepts
      await page.getByTestId(p.known.includes(aid.split("-")[1]) ? "answer-right" : "answer-wrong").click();
    }
    await expect(page.getByTestId("study-card")).not.toHaveText(before!);
  }
  expect(concept).not.toBe("");
  await expect(page.getByTestId("toast").first()).toContainText("Plan updated");
  await expect(page.getByTestId("replan-info")).toContainText("ms");
  if (p.has_check) {
    await page.getByTestId("tab-map").click();
    await expect(page.getByTestId(`node-${concept}`)).toBeVisible();
    await expect(page.getByTestId(`badge-check-${concept}`)).toBeVisible();
    await expect(page.getByTestId(`badge-confirmed-${concept}`)).toHaveCount(0);
  }

  // 6. Next day: end day 1; the engine replans the remaining work from day 2 (D96).
  await page.getByTestId("tab-study").click();
  await page.getByTestId("next-day").click();
  await expect(page.getByTestId("day-chip")).toHaveText("Day 2");
  await expect(page.getByTestId("toast").last()).toContainText("Day 2");
  await expect(page.getByTestId("study-card")).toContainText("Day 2");
});
