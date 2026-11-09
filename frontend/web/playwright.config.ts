import { defineConfig, devices } from "@playwright/test";

// One server: the FastAPI adapter also serves the built app (npm run build first).
const PORT = 8765;

export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, viewport: { width: 1600, height: 1000 }, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1600, height: 1000 } } }],
  webServer: {
    command: `\${PYTHON:-.venv/bin/python} -m uvicorn frontend.api.app:app --host 127.0.0.1 --port ${PORT}`,
    cwd: "../..",
    url: `http://127.0.0.1:${PORT}/api/curricula`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { ADAPTENGINE_SESSIONS_DIR: "frontend/web/test-results/sessions" },
  },
});
