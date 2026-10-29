// Regenerates src/schema.ts from the backend's OpenAPI document.
//   npm run api-client           (from frontend/) export + generate
//   npm run check -w @eduzone/api-client   fails if the committed types are stale
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const backend = resolve(here, "../../../backend");
const python = [join(backend, ".venv/Scripts/python.exe"), join(backend, ".venv/bin/python")].find(existsSync);
if (!python) throw new Error(`No backend virtualenv found in ${backend}/.venv`);

const spec = join(here, "openapi.json");
const schema = join(here, "src/schema.ts");
const check = process.argv.includes("--check");
const before = check && existsSync(schema) ? readFileSync(schema, "utf8") : null;

execFileSync(python, ["-m", "scripts.export_openapi", spec], { cwd: backend, stdio: "inherit" });
const pkg = createRequire(import.meta.url).resolve("openapi-typescript/package.json");
const cli = join(dirname(pkg), "bin/cli.js");
execFileSync(process.execPath, [cli, spec, "-o", schema], {
  stdio: "inherit",
});

if (check && readFileSync(schema, "utf8") !== before) {
  console.error("src/schema.ts was stale: the API changed. Commit the regenerated file.");
  process.exit(1);
}
