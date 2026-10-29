import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import path from "node:path";

import { OUTBOX } from "./playwright.config";

// The demo organization (scripts/seed_demo.py) is the fixture; seeding is idempotent.
export default function globalSetup() {
  rmSync(OUTBOX, { force: true });
  const backend = path.resolve(__dirname, "../../backend");
  const python = path.join(backend, process.platform === "win32" ? ".venv/Scripts/python" : ".venv/bin/python");
  execFileSync(python, ["scripts/seed_demo.py"], { cwd: backend, stdio: "inherit" });
}
