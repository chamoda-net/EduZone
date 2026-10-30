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

// The public page of the demo physics class (scripts/seed_demo.py): /<subject>/<teacher>/<class>.
const CLASS = "/physics/kasun-perera/2027-al-physics-theory";

test("anyone can browse the marketplace: search, class, teacher", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("Subject, teacher or class").first().fill("chemistry");
  await page.getByRole("button", { name: "Search" }).first().click();
  await expect(page).toHaveURL(/\/classes\?q=chemistry/);
  await page.getByRole("link", { name: /2027 A\/L Chemistry/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "2027 A/L Chemistry - Theory" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("link", { name: "Sign in to join" })).toBeVisible();
  await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Ruwan Silva" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Ruwan Silva" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("link", { name: "WhatsApp" })).toBeVisible();
});

test("student registers, opens a class from the marketplace, joins and pays", async ({ page }) => {
  await registerStudent(page, newStudentEmail(), newStudentPhone());
  await expect(page.getByText("You're all set")).toBeVisible();

  await page.goto(CLASS);
  await page.getByRole("link", { name: "Join or pay" }).click();
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

  await page.goto("/learn");
  await expect(page.getByText("Up next")).toBeVisible();
});

test("signing in on a second device signs out the first", async ({ page, browser }) => {
  const email = newStudentEmail();
  const phone = newStudentPhone();
  await registerStudent(page, email, phone);

  const other = await browser.newContext({ baseURL: page.url() });
  const second = await other.newPage();
  await signIn(second, email, STUDENT_PASSWORD, phone, new URL(page.url()).origin); // new device: needs the SMS code
  await other.close();

  await page.goto("/learn/classes");
  await expect(page.getByText("You were signed out")).toBeVisible();
});

test("teacher signs in, sees their class and their public profile", async ({ page }) => {
  await signIn(page, TEACHER_EMAIL, DEMO_PASSWORD, TEACHER_PHONE);
  await page.goto("/teach"); // one workspace: straight into its console
  await expect(page).toHaveURL(/\/teach\/demo\/classes/, { timeout: 30_000 });
  await page.getByText("2027 A/L Physics - Theory").click();
  await expect(page.getByRole("heading", { name: "2027 A/L Physics - Theory" })).toBeVisible({ timeout: 30_000 });

  await page.goto("/teach/demo/profile");
  await expect(page.getByRole("heading", { name: "Public profile" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("link", { name: /\/physics\/kasun-perera/ })).toBeVisible();
});

test("a new user applies to teach and gets a console in draft mode", async ({ page }) => {
  await registerStudent(page, newStudentEmail(), newStudentPhone());
  await page.goto("/teach");
  await expect(page).toHaveURL(/\/teach\/apply$/);

  const name = `E2E Physics ${Date.now().toString(36)}`;
  await page.getByLabel("Name for your classes").fill(name);
  await page.getByRole("button", { name: "Physics", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "nic.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4\n% e2e\n"),
  });
  await page.getByLabel("Bank", { exact: true }).fill("Bank of Ceylon");
  await page.getByLabel("Account holder name").fill("E2E Teacher");
  await page.getByLabel("Account number").fill("0081 2345 6789");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Submit application" }).click();

  await expect(page.getByRole("heading", { name: "We are reviewing your application" })).toBeVisible();
  await expect(page.getByText("****6789")).toBeVisible();
  await page.getByRole("link", { name: "Open your console" }).click();
  await expect(page.getByText("Draft mode")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Classes" })).toBeVisible();
});

test("a guest fills a cart from two teachers, signs up and pays once", async ({ page }) => {
  // Before an account exists the cart lives in the browser.
  await page.goto(CLASS);
  await page.getByRole("button", { name: /Add .* to cart/ }).click();
  await expect(page.getByRole("link", { name: "View cart" })).toBeVisible();
  await page.goto("/mathematics/dilini-fernando/2027-ol-maths");
  await page.getByRole("button", { name: /Add .* to cart/ }).click();
  await expect(page.getByRole("link", { name: "Cart (2)" })).toBeVisible();

  // Signing up brings the cart along.
  await registerStudent(page, newStudentEmail(), newStudentPhone());
  await page.goto("/cart");
  await expect(page.getByText("2 items")).toBeVisible();
  await expect(page.getByText("2 teachers")).toBeVisible();
  await page.getByRole("button", { name: "Pay Rs. 3,500.00" }).click();
  await page.getByRole("button", { name: "Pay", exact: true }).click();

  await expect(page.getByText("Payment received")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/Paid to Dilini Fernando Maths/)).toBeVisible();
  await expect(page.getByText(/Paid to Demo Tuition Institute/)).toBeVisible();
  await page.goto("/cart");
  await expect(page.getByText("Your cart is empty")).toBeVisible();
});
