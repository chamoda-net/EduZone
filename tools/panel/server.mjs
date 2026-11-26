// The EduZone panel: start, stop and watch the local system, and read its SMS codes and emails, in one window.
//
//   double-click "EduZone Panel.vbs" in the repo root (or: node tools/panel/server.mjs)
//
// Runs the database, API, website and admin app as hidden child processes (no terminal windows) and keeps their logs.
// The API it starts writes SMS codes and emails to files in ./run, which the panel shows. No dependencies.
// Local development only: refuses to run unless .env says ENVIRONMENT=local, and listens on this computer only.
import { execFile, spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const RUN = path.join(HERE, "run");
const PORT = Number(process.env.PANEL_PORT || 3999);
const SMS = path.join(RUN, "sms.jsonl");
const EMAILS = path.join(RUN, "emails.jsonl");
const SETTINGS = path.join(RUN, "settings.json");
const BACKEND = path.join(ROOT, "backend");
const FRONTEND = path.join(ROOT, "frontend");
const DEVDB = path.join(ROOT, "tools", "dev-db");
const PYTHON = path.join(BACKEND, ".venv", "Scripts", "python.exe");
const NEXT = path.join(FRONTEND, "node_modules", "next", "dist", "bin", "next");
const PG_CTL = path.join(DEVDB, "node_modules", "@embedded-postgres", "windows-x64", "native", "bin", "pg_ctl.exe");

const env = Object.fromEntries(
  (fs.existsSync(path.join(ROOT, ".env")) ? fs.readFileSync(path.join(ROOT, ".env"), "utf8") : "")
    .split(/\r?\n/).filter((l) => /^[A-Z_]+=/.test(l))
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1).trim()]),
);
const DB_PORT = Number(/:(\d+)\//.exec(env.DATABASE_URL ?? "")?.[1] ?? 54393);
fs.mkdirSync(RUN, { recursive: true });

// --- settings -----------------------------------------------------------------------------------------------
let settings = { seats: (env.SEATS_ENABLED ?? "false") === "true", easyCodes: true, openSites: false };
try { settings = { ...settings, ...JSON.parse(fs.readFileSync(SETTINGS, "utf8")) }; } catch { /* first run */ }
const saveSettings = () => fs.writeFileSync(SETTINGS, JSON.stringify(settings, null, 2));

// --- services -------------------------------------------------------------------------------------------------
const apiEnv = () => ({
  SMS_PROVIDER: "file", SMS_OUTBOX_PATH: SMS, EMAIL_PROVIDER: "file", EMAIL_OUTBOX_PATH: EMAILS,
  SEATS_ENABLED: settings.seats ? "true" : "false",
  // Testing signs in again and again: no wait between codes and no hourly limit (as the browser tests do).
  ...(settings.easyCodes ? { OTP_RESEND_COOLDOWN_SECONDS: "0", OTP_MAX_PER_PHONE_PER_HOUR: "1000", OTP_MAX_PER_IP_PER_HOUR: "1000" } : {}),
});
const SERVICES = {
  db: { name: "Database", port: DB_PORT, cmd: process.execPath, args: ["serve.mjs"], cwd: DEVDB, wait: 90 },
  api: {
    name: "API", port: 8000, cmd: PYTHON, cwd: BACKEND, env: apiEnv, wait: 60, url: "http://localhost:8000/docs",
    // No --reload: without a console uvicorn can't stop its old process and hangs. watchApi() restarts it instead.
    args: ["-m", "uvicorn", "app.main:app", "--port", "8000"],
  },
  web: { name: "Website", port: 3000, cmd: process.execPath, args: [NEXT, "dev", "--port", "3000"], cwd: path.join(FRONTEND, "apps", "web"), wait: 120, url: "http://localhost:3000" },
  admin: { name: "Admin app", port: 3001, cmd: process.execPath, args: [NEXT, "dev", "--port", "3001"], cwd: path.join(FRONTEND, "apps", "admin"), wait: 120, url: "http://localhost:3001" },
};
const ORDER = ["db", "api", "web", "admin"];
const state = Object.fromEntries(ORDER.map((id) => [id, { child: null, up: false, phase: "stopped", since: null, error: null, lines: [], seq: 0, errors: 0 }]));
let migration = { status: "unknown", message: "" };
let busy = null;                    // what a "start all / stop all" is doing now
let job = null;                     // a tool run: {name, status, output}

const ANSI = /\u001b\[[0-9;?]*[A-Za-z]/g;
const BAD = /\b(error|exception|traceback|fatal|failed)\b|⨯/i;

function log(id, text) {
  const s = state[id];
  for (const raw of text.replace(ANSI, "").split(/\r?\n/)) {
    const line = raw.trimEnd();
    if (!line) continue;
    const bad = BAD.test(line) && !/\b0 errors?\b/i.test(line);
    if (bad) s.errors += 1;
    s.lines.push({ n: ++s.seq, t: Date.now(), line: line.slice(0, 2000), bad });
  }
  if (s.lines.length > 1500) s.lines.splice(0, s.lines.length - 1500);
}

const portOpen = (port) => new Promise((resolve) => {
  const tryHost = (host) => new Promise((ok) => {
    const c = net.connect({ port, host, timeout: 500 });
    c.once("connect", () => { c.destroy(); ok(true); });
    c.once("error", () => ok(false));
    c.once("timeout", () => { c.destroy(); ok(false); });
  });
  Promise.all([tryHost("127.0.0.1"), tryHost("::1")]).then((r) => resolve(r.some(Boolean)));
});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
/** Runs a program hidden and returns {code, out}. */
const run = (cmd, args, options = {}) => new Promise((resolve) => {
  execFile(cmd, args, { windowsHide: true, maxBuffer: 4 << 20, ...options }, (err, stdout, stderr) => {
    resolve({ code: err ? (typeof err.code === "number" ? err.code : 1) : 0, out: `${stdout ?? ""}${stderr ?? ""}` });
  });
});

/** A crash can leave postmaster.pid behind, which stops PostgreSQL from starting. Removed only when no postgres.exe
 * has that id (Windows reuses ids, so "some process has it" isn't enough to keep the file). */
async function clearStaleLock() {
  const file = path.join(DEVDB, "data", "postmaster.pid");
  if (!fs.existsSync(file)) return;
  const pid = fs.readFileSync(file, "utf8").split(/\r?\n/)[0].trim();
  const { out } = await run("tasklist", ["/FI", `PID eq ${Number(pid)}`, "/FO", "CSV", "/NH"]);
  if (/postgres\.exe/i.test(out)) return;
  fs.rmSync(file, { force: true });
  log("db", "Removed a stale lock file from the last run.");
}

async function start(id) {
  const d = SERVICES[id], s = state[id];
  if (s.child || s.phase === "starting" || (await portOpen(d.port))) return true;
  for (const needed of [d.cmd, ...(d.args[0] === NEXT ? [NEXT] : [])]) {
    if (!fs.existsSync(needed)) { s.error = `Not installed: ${needed}. See docs/local-guide.md.`; s.phase = "failed"; return false; }
  }
  if (id === "db") await clearStaleLock();
  Object.assign(s, { phase: "starting", error: null, errors: 0, since: Date.now() });
  log(id, `--- ${d.name} starting ---`);
  const child = spawn(d.cmd, d.args, {
    cwd: d.cwd, windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8", FORCE_COLOR: "0", NO_COLOR: "1", ...(d.env ? d.env() : {}) },
  });
  s.child = child;
  child.stdout.on("data", (b) => log(id, b.toString("utf8")));
  child.stderr.on("data", (b) => log(id, b.toString("utf8")));
  child.on("error", (e) => { s.error = e.message; });
  child.on("exit", (code) => {
    if (s.child !== child) return;
    s.child = null;
    log(id, `--- ${d.name} ended (${code ?? "stopped"}) ---`);
    if (s.phase !== "stopping") { s.phase = "failed"; s.error ??= `It stopped by itself (code ${code}). See its log.`; }
  });
  const until = Date.now() + d.wait * 1000;
  while (Date.now() < until) {
    if (!s.child) return false;
    if (await portOpen(d.port)) { Object.assign(s, { phase: "running", up: true, since: Date.now() }); return true; }
    await sleep(400);
  }
  s.error = `Not answering after ${d.wait} seconds. See its log.`;
  s.phase = "running";
  return false;
}

async function stop(id) {
  const d = SERVICES[id], s = state[id];
  const child = s.child;
  if (!child && !(await portOpen(d.port))) { s.phase = "stopped"; s.error = null; return; }
  s.phase = "stopping";
  log(id, `--- ${d.name} stopping ---`);
  // PostgreSQL is always shut down properly, never killed.
  if (id === "db" && fs.existsSync(PG_CTL)) await run(PG_CTL, ["stop", "-D", path.join(DEVDB, "data"), "-m", "fast", "-w", "-t", "30"]);
  if (child) await run("taskkill", ["/PID", String(child.pid), "/T", "/F"]);
  else if (id !== "db") await run("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path.join(ROOT, "tools", "stop-eduzone.ps1"), "-Port", String(d.port)]);
  for (let i = 0; i < 40 && (await portOpen(d.port)); i += 1) await sleep(250);
  const left = await portOpen(d.port);
  Object.assign(s, { phase: left ? "external" : "stopped", up: left, child: left ? s.child : null, since: null, error: left ? "It is still running." : null });
}

async function migrate() {
  migration = { status: "running", message: "" };
  const { code, out } = await run(PYTHON, ["-m", "alembic", "upgrade", "head"], { cwd: BACKEND, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  const steps = out.split(/\r?\n/).filter((l) => l.includes("Running upgrade"));
  log("db", code === 0 ? (steps.length ? steps.join("\n") : "Database is up to date.") : out);
  migration = code === 0
    ? { status: "ok", message: steps.length ? `${steps.length} update${steps.length > 1 ? "s" : ""} applied` : "Up to date" }
    : { status: "failed", message: out.trim().split(/\r?\n/).slice(-1)[0] ?? "Failed" };
  return code === 0;
}

async function startAll() {
  if (busy) return;
  try {
    busy = "Starting the database";
    if (!(await start("db"))) return;
    busy = "Updating the database";
    if (!(await migrate())) return;
    busy = "Starting the API, website and admin app";
    const [, web, admin] = await Promise.all([start("api"), start("web"), start("admin")]);
    if (settings.openSites) { if (web) openUrl(SERVICES.web.url); if (admin) openUrl(SERVICES.admin.url); }
  } finally { busy = null; }
}

async function stopAll() {
  if (busy) return;
  try {
    for (const id of [...ORDER].reverse()) { busy = `Stopping the ${SERVICES[id].name.toLowerCase()}`; await stop(id); }
  } finally { busy = null; }
}

async function restart(id) {
  await stop(id);
  if (id === "db") { if (await start("db")) await migrate(); } else await start(id);
}

/** A saved .py file under backend/app restarts the API, half a second after the last change. */
let apiReload = null;
function apiChanged() {
  clearTimeout(apiReload);
  apiReload = setTimeout(async () => {
    const s = state.api;
    if (busy || ["starting", "stopping"].includes(s.phase)) return apiChanged();   // after what is running now
    if (!s.child && s.phase !== "failed") return;                                  // stopped, or started elsewhere
    log("api", "Code changed: restarting the API");
    await restart("api").catch((e) => log("api", `Restart failed: ${e.message}`));
  }, 500);
}
fs.watch(path.join(BACKEND, "app"), { recursive: true }, (_, file) => { if (file?.endsWith(".py")) apiChanged(); });

/** Keeps each service's state true, also for parts started outside the panel. */
setInterval(async () => {
  for (const id of ORDER) {
    const s = state[id];
    const up = await portOpen(SERVICES[id].port);
    s.up = up;
    if (["starting", "stopping"].includes(s.phase)) continue;
    if (up) s.phase = s.child ? "running" : "external";
    else if (!s.child && s.phase !== "failed") s.phase = "stopped";
  }
}, 1500);

// --- tools -------------------------------------------------------------------------------------------------------
const TOOLS = {
  seed_demo: { name: "Demo accounts and classes", script: "scripts/seed_demo.py" },
  seed_market: { name: "Marketplace demo", script: "scripts/seed_market.py" },
  make_admin: {
    name: "Local admin account", script: "scripts/create_platform_admin.py", quiet: true, hidden: true,
    args: ["--phone", "+94779999999", "--name", "EduZone Staff (local)"],
  },
  seed_seats: { name: "Small-group class with seats", script: "scripts/seed_seats.py" },
};
async function runTool(id) {
  const tool = TOOLS[id];
  if (!tool || job?.status === "running") return;
  job = { name: tool.name, status: "running", output: "" };
  const { code, out } = await run(PYTHON, [tool.script, ...(tool.args ?? [])], { cwd: BACKEND, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  job = { name: tool.name, status: code === 0 ? "ok" : "failed", output: tool.quiet && code === 0 ? "" : out.trim().split(/\r?\n/).slice(-6).join("\n") };
  admins.at = 0;
}

// --- codes, emails, accounts ----------------------------------------------------------------------------------------
function readLines(file, limit) {
  try {
    return fs.readFileSync(file, "utf8").split("\n").filter(Boolean).slice(-limit).reverse()
      .flatMap((l) => { try { return [JSON.parse(l)]; } catch { return []; } });
  } catch { return []; }
}
function accounts() {
  const read = (file) => { try { return fs.readFileSync(path.join(BACKEND, "scripts", file), "utf8"); } catch { return ""; } };
  const src = read("seed_demo.py");
  const get = (name) => new RegExp(`^${name} = "([^"]+)"`, "m").exec(src)?.[1] ?? "";
  return {
    password: get("DEMO_PASSWORD"),
    people: [
      { name: "Nimali Perera", role: "Student", email: get("STUDENT_EMAIL"), phone: get("STUDENT_PHONE") },
      { name: "Kasun Perera", role: "Teacher", email: get("TEACHER_EMAIL"), phone: get("TEACHER_PHONE") },
      { name: "Institute owner", role: "Owner", email: get("OWNER_EMAIL"), phone: get("OWNER_PHONE") },
    ].filter((p) => p.email),
  };
}

/** The local admins' phones and authenticator codes (scripts/dev_admin_codes.py computes them: secrets never come here).
 * Asked for only while a page showing them is open; kept a few seconds. */
let admins = { at: 0, pending: null, value: { admins: [], error: null } };
function adminCodes() {
  if (Date.now() - admins.at < 4000) return Promise.resolve(admins.value);
  admins.pending ??= run(PYTHON, ["scripts/dev_admin_codes.py"], { cwd: BACKEND, env: { ...process.env, PYTHONPATH: BACKEND, PYTHONIOENCODING: "utf-8" } })
    .then(({ code, out }) => {
      let value;
      try { value = code === 0 ? { ...JSON.parse(out.trim().split(/\r?\n/).at(-1)), error: null } : { admins: [], error: "Start the database first." }; }
      catch { value = { admins: [], error: "Could not read the admins." }; }
      admins = { at: Date.now(), pending: null, value };
      return value;
    });
  return admins.pending;
}

function openUrl(url) { spawn("rundll32", ["url.dll,FileProtocolHandler", url], { windowsHide: true, detached: true, stdio: "ignore" }).unref(); }
/** The panel in its own window (Chrome or Edge app mode), else a browser tab. */
function openPanel() {
  const url = `http://localhost:${PORT}`;
  const exe = [
    [process.env.ProgramFiles, "Google/Chrome/Application/chrome.exe"], [process.env["ProgramFiles(x86)"], "Google/Chrome/Application/chrome.exe"],
    [process.env.LOCALAPPDATA, "Google/Chrome/Application/chrome.exe"], [process.env["ProgramFiles(x86)"], "Microsoft/Edge/Application/msedge.exe"],
    [process.env.ProgramFiles, "Microsoft/Edge/Application/msedge.exe"],
  ].map(([base, rest]) => (base ? path.join(base, rest) : "")).find((p) => p && fs.existsSync(p));
  if (exe) spawn(exe, [`--app=${url}`, "--window-size=1240,900"], { detached: true, stdio: "ignore" }).unref();
  else openUrl(url);
}

// --- http ---------------------------------------------------------------------------------------------------------------
const json = (res, body, status = 200) => {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  res.end(JSON.stringify(body));
};
const view = () => ({
  busy, migration, settings, job, now: Date.now(), tools: Object.entries(TOOLS).filter(([, tool]) => !tool.hidden).map(([id, tool]) => ({ id, name: tool.name })),
  services: ORDER.map((id) => {
    const s = state[id], d = SERVICES[id];
    return { id, name: d.name, port: d.port, url: d.url ?? null, phase: s.phase, up: s.up, since: s.since, error: s.error, errors: s.errors, ours: Boolean(s.child) };
  }),
  sms: readLines(SMS, 40), emails: readLines(EMAILS, 40),
});

const server = http.createServer(async (req, res) => {
  // This computer only: a page on another site can't reach it by name tricks (Host) or post to it (custom header).
  const host = (req.headers.host ?? "").toLowerCase();
  if (host !== `localhost:${PORT}` && host !== `127.0.0.1:${PORT}`) { res.writeHead(403); res.end(); return; }
  const url = new URL(req.url ?? "/", `http://${host}`);
  if (req.method === "GET") {
    if (url.pathname === "/") {
      res.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-frame-options": "DENY" });
      res.end(fs.readFileSync(path.join(HERE, "panel.html")));
      return;
    }
    if (url.pathname === "/icon.svg") {
      const icon = path.join(FRONTEND, "apps", "web", "app", "icon.svg");
      if (!fs.existsSync(icon)) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { "content-type": "image/svg+xml" });
      res.end(fs.readFileSync(icon));
      return;
    }
    if (url.pathname === "/api/state") return json(res, view());
    if (url.pathname === "/api/accounts") return json(res, accounts());
    if (url.pathname === "/api/admin-codes") {
      if (req.headers["x-eduzone-panel"] !== "1") return json(res, { error: "forbidden" }, 403);
      return json(res, await adminCodes());
    }
    if (url.pathname === "/api/logs") {
      const s = state[url.searchParams.get("service") ?? ""];
      if (!s) return json(res, { error: "unknown service" }, 404);
      const after = Number(url.searchParams.get("after") ?? 0);
      return json(res, { lines: s.lines.filter((l) => l.n > after), last: s.seq });
    }
  }
  if (req.method === "POST" && url.pathname.startsWith("/api/")) {
    if (req.headers["x-eduzone-panel"] !== "1") return json(res, { error: "forbidden" }, 403);
    const [, , action, arg] = url.pathname.split("/");
    const known = arg in SERVICES;
    if (action === "start-all") void startAll();
    else if (action === "stop-all") void stopAll();
    else if (action === "start" && known) void start(arg);
    else if (action === "stop" && known) void stop(arg);
    else if (action === "restart" && known) void restart(arg);
    else if (action === "migrate") void migrate();
    else if (action === "tool" && arg in TOOLS) void runTool(arg);
    else if (action === "clear-errors" && known) state[arg].errors = 0;
    else if (action === "clear-messages") { for (const f of [SMS, EMAILS]) fs.rmSync(f, { force: true }); }
    else if (["seats", "easy-codes", "open-sites"].includes(action)) {
      settings[{ seats: "seats", "easy-codes": "easyCodes", "open-sites": "openSites" }[action]] = arg === "on";
      saveSettings();
      if (action !== "open-sites" && state.api.up) void restart("api");
    } else if (action === "quit") { json(res, { ok: true }); await quit(); return; }
    else return json(res, { error: "unknown action" }, 404);
    return json(res, { ok: true });
  }
  res.writeHead(404);
  res.end();
});

let quitting = false;
async function quit() {
  if (quitting) return;
  quitting = true;
  for (const id of [...ORDER].reverse()) if (state[id].child) await stop(id);
  process.exit(0);
}
process.on("SIGINT", quit);
process.on("SIGTERM", quit);

if (env.ENVIRONMENT !== "local") {
  console.error("The panel runs only with ENVIRONMENT=local in .env");
  process.exit(1);
}
server.on("error", (e) => {
  // Already running: show it.
  if (e.code === "EADDRINUSE") { openPanel(); setTimeout(() => process.exit(0), 500); } else { console.error(e); process.exit(1); }
});
server.listen(PORT, "127.0.0.1", () => {
  console.log(`EduZone panel on http://localhost:${PORT}`);
  if (!process.argv.includes("--no-window")) openPanel();
  if (process.argv.includes("--start")) void startAll();
});
