import { execFileSync } from "node:child_process";
import path from "node:path";

// Each run's "applies to teach" test opens a pending organization (slug e2e-...): remove them afterwards.
export default function globalTeardown() {
  const backend = path.resolve(__dirname, "../../backend");
  const python = path.join(backend, process.platform === "win32" ? ".venv/Scripts/python" : ".venv/bin/python");
  execFileSync(python, ["scripts/purge_e2e.py"], { cwd: backend, stdio: "inherit" });
}
