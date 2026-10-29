import { expect, type Page } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";

import { OUTBOX } from "./playwright.config";

export const TEACHER_PHONE = "+94770000002"; // scripts/seed_demo.py

/** A fresh student number for each run: 077 + 7 random digits. */
export function newStudentPhone(): string {
  return `+9477${String(Math.floor(Math.random() * 1e7)).padStart(7, "0")}`;
}

async function latestCode(phone: string): Promise<string> {
  let code: string | undefined;
  await expect
    .poll(() => {
      if (!existsSync(OUTBOX)) return undefined;
      const lines = readFileSync(OUTBOX, "utf8").trim().split("\n").filter(Boolean);
      const last = lines.map((l) => JSON.parse(l) as { phone: string; message: string })
        .filter((m) => m.phone === phone).at(-1);
      code = last?.message.match(/\b(\d{6})\b/)?.[1];
      return code;
    }, { message: `OTP for ${phone}` })
    .toBeTruthy();
  return code!;
}

/** Signs in with phone OTP; `name` is asked only for a new number. */
export async function signIn(page: Page, phone: string, name?: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number").fill(phone.replace("+94", "0"));
  await page.getByRole("button", { name: "Send code" }).click();
  await page.getByLabel("Code").fill(await latestCode(phone));
  await page.getByRole("button", { name: "Sign in" }).click();
  if (name) {
    // A new number is asked for a name; the code stays filled in.
    await expect(page.getByLabel("Code")).not.toHaveValue("");
    await page.getByLabel("Your name").fill(name);
    await page.getByRole("button", { name: "Sign in" }).click();
  }
  await expect(page).not.toHaveURL(/\/login/);
}
