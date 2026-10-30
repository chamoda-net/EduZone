import { expect, test } from "@playwright/test";

import {
  DEMO_PASSWORD,
  STUDENT_PASSWORD,
  TEACHER_EMAIL,
  TEACHER_PHONE,
  newStudentEmail,
  newStudentPhone,
  registerStudent,
  signIn,
} from "./helpers";

const CLASS = "/classes/2027-al-physics-theory";

test("student registers, confirms the phone, joins and pays for the open month", async ({ page }) => {
  await registerStudent(page, newStudentEmail(), newStudentPhone());
  await expect(page.getByText("You're all set")).toBeVisible();

  await page.goto(CLASS);
  await page.getByRole("button", { name: "Join class" }).click();
  await expect(page.getByText("You are in this class")).toBeVisible();

  await page.getByRole("button", { name: "Pay Rs. 2,000.00" }).click();
  // The fake gateway's page is served by the API (local only).
  await page.getByRole("button", { name: "Pay", exact: true }).click();

  await expect(page.getByText("Payment received")).toBeVisible({ timeout: 20_000 });
  await page.getByRole("link", { name: "Go to the class" }).click();
  // November now shows access, and its lessons open.
  await expect(page.getByRole("listitem").filter({ hasText: "November 2026" }).getByText("You have access")).toBeVisible();
  await expect(page.getByRole("link", { name: /Live class/ })).toBeVisible();
});

test("signing in on a second device signs out the first", async ({ page, browser }) => {
  const email = newStudentEmail();
  const phone = newStudentPhone();
  await registerStudent(page, email, phone);

  const other = await browser.newContext();
  const second = await other.newPage();
  await signIn(second, email, STUDENT_PASSWORD, phone); // new device: needs the SMS code
  await other.close();

  await page.goto("/my");
  await expect(page.getByText("You were signed out")).toBeVisible();
});

test("teacher signs in and sees their class in the console", async ({ page }) => {
  await signIn(page, TEACHER_EMAIL, DEMO_PASSWORD, TEACHER_PHONE);
  await page.goto("/org/classes");
  await expect(page.getByText("2027 A/L Physics - Theory")).toBeVisible();
  await page.getByText("2027 A/L Physics - Theory").click();
  await expect(page.getByRole("heading", { name: "2027 A/L Physics - Theory" })).toBeVisible({ timeout: 30_000 });
});
