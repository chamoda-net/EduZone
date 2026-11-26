import { expect, test, type Browser, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

import { DEMO_PASSWORD, TEACHER_EMAIL, TEACHER_PHONE, newStudentEmail, newStudentPhone, registerStudent, signIn } from "./helpers";

// Seats (docs/SEATS.md) on the small-group demo class (scripts/seed_seats.py): four seats, one free.
// With SEAT_SCREENS=<dir> every step is also photographed at 360 px and 1440 px.
const TITLE = "2027 A/L Physics - Small Group";
const PUBLIC = "/physics/kasun-perera/2027-al-physics-small-group";
const STUDENT_PHONE = "+94770000003";
const SHOTS = process.env.SEAT_SCREENS ? path.resolve(process.env.SEAT_SCREENS) : "";

async function shoot(page: Page, name: string) {
  if (!SHOTS) return;
  const before = page.viewportSize();
  for (const [size, width, height] of [["m", 360, 800], ["d", 1440, 900]] as const) {
    await page.setViewportSize({ width, height });
    await page.waitForTimeout(900);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${name} scrolls sideways at ${width}px`).toBeLessThanOrEqual(0);
    await page.screenshot({ path: path.join(SHOTS, `${name}-${size}.jpg`), fullPage: true, type: "jpeg", quality: 70 });
  }
  if (before) await page.setViewportSize(before);
}

async function student(browser: Browser, base: string): Promise<Page> {
  const context = await browser.newContext({ baseURL: base });
  const page = await context.newPage();
  await registerStudent(page, newStudentEmail(), newStudentPhone());
  return page;
}

test.beforeAll(() => {
  const backend = path.resolve(__dirname, "../../backend");
  const python = path.join(backend, process.platform === "win32" ? ".venv/Scripts/python" : ".venv/bin/python");
  execFileSync(python, ["scripts/seed_seats.py"], { cwd: backend, stdio: "inherit" });
});

test("seats: the teacher limits them, a student asks, is accepted and starts paying; the class fills up", async ({ page, browser, baseURL }) => {
  test.setTimeout(300_000);
  page.setDefaultTimeout(30_000);

  // The public page says how many seats are free.
  await page.goto(PUBLIC);
  await expect(page.getByText("1 of 4 seats free")).toBeVisible();
  await shoot(page, "public-open");
  await page.goto("/classes?q=small+group&seats=available");
  await expect(page.getByRole("link", { name: new RegExp(TITLE.replace(/[/-]/g, ".")) })).toBeVisible();
  await expect(page.getByText("1 seat left").first()).toBeVisible();
  await shoot(page, "catalogue");
  // A guest puts it in the cart (which holds nothing).
  const guest = await (await browser.newContext({ baseURL })).newPage();
  await guest.goto(PUBLIC);
  await guest.getByRole("button", { name: /^Add / }).click();
  await expect(guest.getByRole("link", { name: "View cart" })).toBeVisible();

  // The returning student sees that their seat is kept, and may pay whatever registration says.
  const old = await (await browser.newContext({ baseURL })).newPage();
  await signIn(old, "student.demo@example.com", DEMO_PASSWORD, STUDENT_PHONE);
  await old.goto("/learn");
  await expect(old.getByText(/Your seat is kept until/)).toBeVisible();
  await shoot(old, "returning-today");
  await old.getByRole("link", { name: new RegExp("Small Group") }).first().click();
  await expect(old).toHaveURL(/\/learn\/classes\//, { timeout: 30_000 });
  await expect(old.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
  await expect(old.getByRole("button", { name: "Pay Rs. 3,500.00" }).first()).toBeVisible();
  await expect(old.getByText(/Your seat is kept until/)).toBeVisible();
  await shoot(old, "returning-class");

  // The teacher sees who has the seats and asks to be asked first.
  await signIn(page, TEACHER_EMAIL, DEMO_PASSWORD, TEACHER_PHONE);
  await page.goto("/teach/demo/classes");
  await page.getByText(TITLE).click();
  await expect(page.getByText("3 of 4 seats taken")).toBeVisible();
  await expect(page.getByText(/Kept until/).first()).toBeVisible();
  await expect(page.getByText("In the class last month, no seat now")).toBeVisible();
  await page.getByText("Seat settings", { exact: true }).click();
  await shoot(page, "teacher-seats");
  await page.getByRole("radio", { name: /Ask me first/ }).check();
  await page.getByRole("button", { name: "Save seat settings" }).click();
  await expect(page.getByText("Seat settings saved.")).toBeVisible();
  await expect(page.getByText("New students ask first")).toBeVisible();
  const classUrl = page.url();

  // A student asks.
  const a = await student(browser, baseURL!);
  await a.goto(PUBLIC);
  await expect(a.getByText("The teacher accepts new students")).toBeVisible();
  await a.getByRole("link", { name: "Ask for a seat" }).first().click();
  await expect(a).toHaveURL(/\/learn\/classes\//, { timeout: 30_000 });
  await shoot(a, "student-ask");
  await a.getByLabel("A note to the teacher (optional)").fill("I study at Royal College");
  await a.getByRole("button", { name: "Ask for a seat" }).click();
  await expect(a.getByText("You asked for a seat. Waiting for the teacher.")).toBeVisible();
  await shoot(a, "student-waiting");
  const learnUrl = a.url();

  // The teacher accepts.
  await page.goto("/teach/demo/requests?type=seats");
  await expect(page.getByText("I study at Royal College")).toBeVisible();
  await shoot(page, "teacher-requests");
  await page.getByRole("button", { name: "Accept", exact: true }).click();
  await expect(page.getByText("No seat requests here.")).toBeVisible();

  // The student sees it on Today, and on the class page; starts paying, and the seat is held.
  await a.goto("/learn");
  await expect(a.getByText(`You're accepted in ${TITLE}`)).toBeVisible();
  await shoot(a, "student-today");
  await a.goto("/learn/requests");
  await expect(a.getByText("Accepted: pay now")).toBeVisible();
  await shoot(a, "student-requests");
  await a.goto(learnUrl);
  await expect(a.getByText(/You're accepted\. Pay by/)).toBeVisible();
  await shoot(a, "student-accepted");
  await a.getByRole("button", { name: "Pay Rs. 3,500.00" }).first().click();
  await expect(a.getByRole("button", { name: "Pay", exact: true })).toBeVisible();      // the gateway's page
  await a.goto(learnUrl);
  await expect(a.getByRole("timer")).toContainText(/Your seat is held while you pay: 1[45]:\d\d left/);
  await shoot(a, "student-held");

  // The class is full now: another student waits to be told, and a cart says why it can't be paid.
  const b = await student(browser, baseURL!);
  await b.goto(PUBLIC);
  await expect(b.getByText("Every seat is taken")).toBeVisible();
  await shoot(b, "public-full");
  await b.goto(learnUrl);
  await b.getByRole("button", { name: "Notify me" }).click();
  await expect(b.getByText("We'll tell you in your student area when a seat opens.")).toBeVisible();
  await shoot(b, "student-notify");
  await guest.goto("/cart");
  await expect(guest.getByText("The class is full.")).toBeVisible();
  await expect(guest.getByRole("link", { name: "Get told when a seat opens" })).toBeVisible();
  await shoot(guest, "cart");

  // The teacher releases the kept seat; the waiting student is told.
  await page.goto(classUrl);
  await expect(page.getByText("4 of 4 seats taken")).toBeVisible();
  await expect(page.getByText(/1 student is waiting to be told/)).toBeVisible();
  await page.getByRole("button", { name: "Keep longer" }).click();
  await expect(page.getByRole("heading", { name: "Keep a seat for Nimali Perera" })).toBeVisible();
  await page.getByRole("button", { name: "Keep the seat" }).click();
  await expect(page.getByText("Done.")).toBeVisible();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Release" }).click();
  await expect(page.getByText("3 of 4 seats taken")).toBeVisible();
  await b.goto("/learn");
  await expect(b.getByText(`You can ask for a seat in ${TITLE}`)).toBeVisible();

  // Keeping a seat in a full class must be on purpose.
  await page.getByRole("button", { name: "Keep a seat" }).first().click();
  await page.getByRole("button", { name: "Keep the seat" }).click();
  await expect(page.getByText("4 of 4 seats taken")).toBeVisible();
  await page.getByRole("button", { name: "Keep a seat" }).first().click();
  await page.getByRole("button", { name: "Keep the seat" }).click();
  await page.getByRole("button", { name: "Keep it and go over the limit" }).click();
  await expect(page.getByText("Over the limit by 1")).toBeVisible();
  await shoot(page, "teacher-over");

  // Closed, with the numbers hidden: the public page says so and shows no numbers.
  await page.getByText("Seat settings", { exact: true }).click();
  await page.getByRole("radio", { name: /^Closed/ }).check();
  await page.getByRole("checkbox", { name: "Show students how many seats are left" }).uncheck();
  await page.getByLabel("Number of seats").fill("9");
  await page.getByRole("button", { name: "Save seat settings" }).click();
  await expect(page.getByText("Seat settings saved.")).toBeVisible();
  await b.goto(PUBLIC);
  await expect(b.getByText("Not taking new students")).toBeVisible();
  await expect(b.getByText(/seats? (free|left)/)).toHaveCount(0);
  await shoot(b, "public-closed");
});
