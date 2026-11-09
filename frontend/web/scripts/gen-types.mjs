// Regenerate src/api/schema.d.ts from the FastAPI OpenAPI schema (no server needed).
// Usage: npm run gen:types   (PYTHON env var overrides the interpreter; default ../../.venv/bin/python)
import { execFileSync } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const repo = resolve(import.meta.dirname, "../../..");
const venv = resolve(repo, ".venv/bin/python");
const python = process.env.PYTHON ?? (existsSync(venv) ? venv : "python3");
const spec = execFileSync(
  python,
  ["-c", "import json; from frontend.api.app import app; print(json.dumps(app.openapi(), indent=1))"],
  { cwd: repo, encoding: "utf8" },
);
writeFileSync(resolve(import.meta.dirname, "../openapi.json"), spec);
execFileSync("npx", ["openapi-typescript", "openapi.json", "-o", "src/api/schema.d.ts"], {
  cwd: resolve(import.meta.dirname, ".."),
  stdio: "inherit",
});
