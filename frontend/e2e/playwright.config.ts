import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

// Smoke suite against a real API and web app on their own ports (8010 / 3010), so it can run
// beside the usual dev servers. Needs the local Postgres from docker compose, migrated.
// The API runs with SMS_PROVIDER=file and EMAIL_PROVIDER=file so tests read codes and links.
export const API_PORT = 8010;
export const WEB_PORT = 3010;
export const OUTBOX = path.resolve(__dirname, ".outbox.jsonl");
export const EMAIL_OUTBOX = path.resolve(__dirname, ".email-outbox.jsonl");

const backend = path.resolve(__dirname, "../../backend");
const venvBin = process.platform === "win32" ? ".venv/Scripts" : ".venv/bin";

export default defineConfig({
  testDir: ".",
  globalSetup: "./global-setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL: `http://demo.localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    ...devices["Pixel 7"], // students are mostly on phones
  },
  webServer: [
    {
      command: `"${path.join(backend, venvBin, "uvicorn")}" app.main:app --app-dir "${backend}" --port ${API_PORT}`,
      url: `http://localhost:${API_PORT}/api/v1/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        SMS_PROVIDER: "file",
        SMS_OUTBOX_PATH: OUTBOX,
        EMAIL_PROVIDER: "file",
        EMAIL_OUTBOX_PATH: EMAIL_OUTBOX,
        SITE_SCHEME: "http",
        API_PUBLIC_URL: `http://localhost:${API_PORT}`,
        PAYMENT_GATEWAY: "fake",
        OTP_RESEND_COOLDOWN_SECONDS: "0",
        OTP_MAX_PER_PHONE_PER_HOUR: "1000",
        OTP_MAX_PER_IP_PER_HOUR: "1000",
      },
    },
    {
      command: `npm run dev -w @eduzone/web -- --port ${WEB_PORT}`,
      cwd: path.resolve(__dirname, ".."),
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { API_URL: `http://localhost:${API_PORT}`, NEXT_DIST_DIR: ".next-e2e" },
    },
  ],
});
