// W8 H.19: screenshots for the final report. Needs the API on BASE (default http://127.0.0.1:8000,
// e.g. `make demo`). Usage: node scripts/demo-screenshots.mjs  ->  docs/figures/demo_*.png
import { chromium } from "@playwright/test";
import { resolve } from "node:path";

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const OUT = resolve(import.meta.dirname, "../../../docs/figures");
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const shot = (n) => page.screenshot({ path: `${OUT}/demo_${n}.png` });
const tab = (t) => page.getByTestId(`tab-${t}`).click();

await page.goto(BASE);
await page.getByTestId("reset").click();
await page.getByTestId("make-plan").click();
await page.getByTestId("setup-status").waitFor();
await shot("setup");
await tab("diagnostic");
for (let i = 0; i < 12 && (await page.getByTestId("demo-answer").isVisible()); i++) {
  await page.getByTestId("demo-answer").click();
  await page.waitForTimeout(150);
}
await shot("diagnostic");
await tab("map");
await page.waitForTimeout(800);
await shot("map");
await tab("plan");
await page.getByTestId("timeline").locator("[data-testid^=card-]").first().click();
await page.getByTestId("propose-bad").click();
await page.getByTestId("proposal-result").waitFor();
await shot("plan_why");
await tab("study");
for (let i = 0; i < 6; i++) {
  if (await page.getByTestId("lesson-done").isVisible()) await page.getByTestId("lesson-done").click();
  else if (await page.getByTestId("demo-wrong").isVisible()) await page.getByTestId("demo-wrong").click();
  await page.waitForTimeout(300);
}
await shot("study");
await tab("disruptions");
await page.getByTestId("missed-day").click();
await page.getByTestId("diff").waitFor();
await shot("disruptions");
await tab("policy");
await page.getByTestId("run-policy").click();
await page.getByTestId("policy-decisions").waitFor();
await shot("policy_lab");
await tab("authoring");
await page.getByTestId("generate-draft").click();
await page.getByTestId("validation").getByText("passes").waitFor();
await shot("authoring");
await tab("autopilot");
await page.getByTestId("run-autopilot").click();
await page.getByTestId("autopilot-results").waitFor({ timeout: 120000 });
await page.waitForTimeout(800);
await shot("autopilot");
await tab("evaluation");
await page.waitForTimeout(1500);
await shot("evaluation");
await tab("overview");
await shot("overview");
await browser.close();
console.log("screenshots written to", OUT);
