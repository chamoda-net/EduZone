// Local PostgreSQL 16 for development without Docker. A stand-in for `docker compose up -d`.
//
//   cd tools/dev-db && npm install && npm start
//
// Reads the port and the three role passwords from the repo's .env (DATABASE_URL, ADMIN_DATABASE_URL,
// MIGRATION_DATABASE_URL), keeps its data in ./data between runs, and creates the database and the two
// runtime roles on the first start. Ctrl+C stops it. Local development only.
import EmbeddedPostgres from "embedded-postgres";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const envFile = path.join(here, "..", "..", ".env");
const env = Object.fromEntries(
  fs.readFileSync(envFile, "utf8").split(/\r?\n/)
    .filter((l) => /^[A-Z_]+=/.test(l))
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1).trim()]),
);
const parse = (key) => {
  const u = new URL(env[key].replace(/^postgresql\+\w+:/, "postgresql:"));
  return { user: decodeURIComponent(u.username), password: decodeURIComponent(u.password), port: Number(u.port || 5432),
           db: u.pathname.slice(1) };
};
const owner = parse("MIGRATION_DATABASE_URL");
const app = parse("DATABASE_URL");
const admin = parse("ADMIN_DATABASE_URL");

const dir = path.join(here, "data");
const fresh = !fs.existsSync(dir);
const pg = new EmbeddedPostgres({
  databaseDir: dir, user: owner.user, password: owner.password, port: owner.port, persistent: true,
  initdbFlags: ["--encoding=UTF8", "--locale=C"],
});
if (fresh) await pg.initialise();
await pg.start();
if (fresh) {
  await pg.createDatabase(owner.db);
  const c = pg.getPgClient(owner.db);
  await c.connect();
  const lit = (s) => `'${s.replaceAll("'", "''")}'`;
  await c.query(`CREATE ROLE ${app.user} LOGIN PASSWORD ${lit(app.password)}`);
  await c.query(`CREATE ROLE ${admin.user} LOGIN BYPASSRLS PASSWORD ${lit(admin.password)}`);
  await c.end();
  console.log("New database created. Next: cd backend && .venv/Scripts/alembic upgrade head");
}
console.log(`READY: PostgreSQL on localhost:${owner.port} (database ${owner.db}). Ctrl+C to stop.`);
const stop = async () => { await pg.stop(); process.exit(0); };
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
setInterval(() => {}, 1 << 30);
