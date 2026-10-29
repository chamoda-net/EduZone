import { expect, test } from "@playwright/test";

import { TEACHER_PHONE, newStudentPhone, signIn } from "./helpers";

const CLASS = "/classes/2027-al-physics-theory";

test("student signs in, joins a class and pays for the open month", async ({ page }) => {
  await signIn(page, newStudentPhone(), "E2E Student");

  await page.goto(CLASS);
  await page.getByRole("button", { name: "Join class" }).click();
  await expect(page.getByText("You are in this class")).toBeVisible();

  await page.getByRole("button", { name: "Pay Rs. 2,000.00" }).click();
  // The fake gateway's page is served by the API (local only).
  await page.getByRole("button", { name: "Pay", exact: true }).click();

  await expect(page.getByText("Payment received")).toBeVisible({ timeout: 20_000 });
  await page.getByRole("link", { name: "Go to the class" }).click();
  await expect(page.getByRole("button", { name: /^Pay Rs/ })).toHaveCount(0);
});

test("teacher opens the console and sees their class", async ({ page }) => {
  await signIn(page, TEACHER_PHONE);
  await page.goto("/org/classes");
  await expect(page.getByText("2027 A/L Physics - Theory")).toBeVisible();
  await page.getByText("2027 A/L Physics - Theory").click();
  await expect(page.getByRole("heading", { name: "2027 A/L Physics - Theory" })).toBeVisible();
});
