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
import { WEB_PORT } from "./playwright.config";

const CLASS = "/classes/2027-al-physics-theory";
const MAIN = `http://localhost:${WEB_PORT}`; // the main site: no tenant in the host

test("student registers, confirms the phone, joins and pays for the open month", async ({ page }) => {
  await registerStudent(page, newStudentEmail(), newStudentPhone());
  await expect(page.getByText("You're all set")).toBeVisible();

  // The tenant site's class page sends a signed-in student to the class in their student area.
  await page.goto(CLASS);
  await expect(page).toHaveURL(/\/learn\/classes\//, { timeout: 30_000 });
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

  await page.goto("/learn/classes");
  await expect(page.getByText("You were signed out")).toBeVisible();
});

test("teacher signs in and sees their class in the console", async ({ page }) => {
  await signIn(page, TEACHER_EMAIL, DEMO_PASSWORD, TEACHER_PHONE);
  await page.goto("/teach"); // one workspace: straight into its console
  await expect(page).toHaveURL(/\/teach\/demo\/classes/, { timeout: 30_000 });
  await expect(page.getByText("2027 A/L Physics - Theory")).toBeVisible();
  await page.getByText("2027 A/L Physics - Theory").click();
  await expect(page.getByRole("heading", { name: "2027 A/L Physics - Theory" })).toBeVisible({ timeout: 30_000 });
});

test("the student area works on the main site, across organizations", async ({ page }) => {
  const email = newStudentEmail();
  const phone = newStudentPhone();
  await registerStudent(page, email, phone);
  await page.goto(CLASS);
  await expect(page).toHaveURL(/\/learn\/classes\//, { timeout: 30_000 });
  await page.getByRole("button", { name: "Join class" }).click();
  await expect(page.getByText("You are in this class")).toBeVisible();

  // Same account on the main host (no tenant in the address): sign in, see Today and the class.
  await page.goto(`${MAIN}/login`);
  await signIn(page, email, STUDENT_PASSWORD, phone, MAIN);
  await page.goto(`${MAIN}/learn`);
  await expect(page.getByText("Ready to pay")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("2027 A/L Physics - Theory").first()).toBeVisible();
  await page.goto(`${MAIN}/learn/classes`);
  await expect(page.getByText("Demo Tuition Institute").first()).toBeVisible();
});
