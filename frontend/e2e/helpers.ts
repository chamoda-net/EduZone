import { expect, type Page } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";

import { OUTBOX } from "./playwright.config";

// Demo staff (scripts/seed_demo.py): local test values only.
export const TEACHER_EMAIL = "teacher.demo@example.com";
export const TEACHER_PHONE = "+94770000002";
export const DEMO_PASSWORD = "Demo-pass-2026";
export const STUDENT_PASSWORD = "Student-pass-2026";

/** A fresh number for each run: 077 + 7 random digits. */
export function newStudentPhone(): string {
  return `+9477${String(Math.floor(Math.random() * 1e7)).padStart(7, "0")}`;
}

export function newStudentEmail(): string {
  return `e2e-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
}

/** The newest SMS code sent to `phone` after `since` (ms), read from the API's file outbox. */
export async function latestCode(phone: string, since = 0): Promise<string> {
  let code: string | undefined;
  await expect
    .poll(() => {
      if (!existsSync(OUTBOX)) return undefined;
      const last = readFileSync(OUTBOX, "utf8").trim().split("\n").filter(Boolean)
        .map((l) => JSON.parse(l) as { phone: string; message: string; at: string })
        .filter((m) => m.phone === phone && Date.parse(m.at) >= since).at(-1);
      code = last?.message.match(/\b(\d{6})\b/)?.[1];
      return code;
    }, { message: `SMS code for ${phone}` })
    .toBeTruthy();
  return code!;
}

/** Registers a student and confirms their phone. Ends on their profile (/learn/profile). */
export async function registerStudent(page: Page, email: string, phone: string) {
  await page.goto("/register");
  await page.getByLabel("Your name").fill("E2E Student");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(STUDENT_PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page).toHaveURL(/\/verify-phone/, { timeout: 30_000 });
  const since = Date.now() - 1000;
  await page.getByLabel("Phone number").fill(phone.replace("+94", "0"));
  await page.getByRole("button", { name: "Send code" }).click();
  await page.getByLabel("Code").fill(await latestCode(phone, since));
  await page.getByRole("button", { name: "Confirm number" }).click();
  await expect(page).toHaveURL(/\/learn\/profile/, { timeout: 30_000 });
}

/** Email + password sign-in; enters the SMS code if this browser is a new device. */
export async function signIn(page: Page, email: string, password: string, phone: string, origin = "") {
  await page.goto(`${origin}/login`);
  const since = Date.now() - 1000;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  // Either the new-device code step appears or we're signed in straight away.
  const code = page.getByLabel("Code");
  await Promise.race([
    code.waitFor({ state: "visible", timeout: 30_000 }),
    page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 30_000 }),
  ]).catch(() => {});
  if (await code.isVisible()) {
    await code.fill(await latestCode(phone, since));
    await page.getByRole("button", { name: "Sign in" }).click();
  }
  await expect(page).not.toHaveURL(/\/login/, { timeout: 30_000 }); // first dev compile can be slow
}
