import { expect, test, type Browser, type BrowserContextOptions, type Page } from "@playwright/test";
import path from "node:path";

import { DEMO_PASSWORD, TEACHER_EMAIL, TEACHER_PHONE, newStudentEmail, newStudentPhone, registerStudent, signIn } from "./helpers";

// Screen review (phase 9): full-page screenshots of the main screens at phone (360 px) and desktop width, for each
// kind of user. Not part of the smoke suite: runs only when SCREEN_DIR is set, e.g.
//   SCREEN_DIR=../screens npx playwright test -c e2e/playwright.config.ts screens
const DIR = process.env.SCREEN_DIR ? path.resolve(process.env.SCREEN_DIR) : "";
const ONLY = process.env.SCREEN_ONLY?.split(",").filter(Boolean);    // e.g. SCREEN_ONLY=guest,teacher
test.skip(!DIR, "set SCREEN_DIR to capture the screen review");

const OWNER = { email: "owner.demo@example.com", phone: "+94770000001" };
const SIZES = {
  m: { viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 },
  d: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 },
} satisfies Record<string, BrowserContextOptions>;

type Shot = [name: string, url: string];
type State = BrowserContextOptions["storageState"];

async function settle(page: Page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  // Scroll through once so lazy images load, then back to the top.
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 700) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 120));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1500); // entrance animations (ez-rise, staggered)
}

async function shoot(browser: Browser, role: string, state: State, shots: Shot[]) {
  if (ONLY && !ONLY.includes(role)) return;
  for (const [size, options] of Object.entries(SIZES)) {
    const context = await browser.newContext({ ...options, storageState: state, locale: "en-GB" });
    const page = await context.newPage();
    for (const [name, url] of shots) {
      await page.goto(url, { timeout: 60_000 });
      await settle(page);
      // "<name>@scrolled": one screen, scrolled down, for things that appear on scroll (the sticky price bar).
      const scrolled = name.endsWith("@scrolled");
      if (scrolled) {
        await page.mouse.wheel(0, 2400);
        await page.waitForTimeout(800);
      }
      await page.screenshot({ path: path.join(DIR, `${role}-${name.replace("@", "-")}-${size}.jpg`), fullPage: !scrolled,
                              type: "jpeg", quality: 60 });
    }
    await context.close();
  }
}

async function signedIn(browser: Browser, email: string, phone: string): Promise<State> {
  const context = await browser.newContext(SIZES.d);
  const page = await context.newPage();
  await signIn(page, email, DEMO_PASSWORD, phone);
  const state = await context.storageState();
  await context.close();
  return state;
}

test.describe.configure({ timeout: 600_000 });

test("guest screens", async ({ browser }) => {
  await shoot(browser, "guest", undefined, [
    ["home", "/"],
    ["classes", "/classes"],
    ["class", "/physics/kasun-perera/2027-al-physics-theory"],
    ["teacher", "/physics/kasun-perera"],
    ["teachers", "/teachers"],
    ["institutes", "/institutes"],
    ["courses", "/courses"],
    ["course", "/course/al-physics-problem-solving"],
    ["course@scrolled", "/course/al-physics-problem-solving"],
    ["instructor", "/instructor/kasun-perera"],
    ["cart-empty", "/cart"],
    ["login", "/login"],
    ["register", "/register"],
    ["about", "/about"],
  ]);
});

test("student screens", async ({ browser }) => {
  if (ONLY && !ONLY.includes("student")) return;
  // A new student who owns the free course and the physics course (bought with the fake gateway).
  const context = await browser.newContext(SIZES.d);
  const page = await context.newPage();
  await registerStudent(page, newStudentEmail(), newStudentPhone());
  await page.goto("/course/maths-shortcuts-free");
  await page.getByRole("button", { name: "Enrol for free" }).first().click();
  await expect(page).toHaveURL(/\/learn\/courses\//, { timeout: 30_000 });
  await page.goto("/course/al-physics-problem-solving");
  await page.getByRole("button", { name: "Buy now" }).first().click();
  await expect(page).toHaveURL(/\/cart$/, { timeout: 30_000 });
  await page.getByRole("button", { name: /^Pay Rs\./ }).click();
  await page.getByRole("button", { name: "Pay", exact: true }).click();
  await expect(page.getByText("Payment received")).toBeVisible({ timeout: 30_000 });
  await page.goto("/learn/courses");
  const course = await page.getByRole("link", { name: /A\/L Physics/ }).first().getAttribute("href");
  await page.goto("/learn/payments");
  const receipt = await page.locator('a[href^="/learn/payments/"]').first().getAttribute("href");
  const state = await context.storageState();
  await context.close();

  await shoot(browser, "student", state, [
    ["today", "/learn"],
    ["classes", "/learn/classes"],
    ["courses", "/learn/courses"],
    ["player", course ?? "/learn/courses"],
    ["wishlist", "/learn/wishlist"],
    ["certificates", "/learn/certificates"],
    ["payments", "/learn/payments"],
    ["receipt", receipt ?? "/learn/payments"],
    ["schedule", "/learn/schedule"],
    ["profile", "/learn/profile"],
    ["cart", "/cart"],
  ]);
});

test("teacher screens", async ({ browser }) => {
  if (ONLY && !ONLY.includes("teacher")) return;
  const state = await signedIn(browser, TEACHER_EMAIL, TEACHER_PHONE);
  const context = await browser.newContext({ ...SIZES.d, storageState: state });
  const page = await context.newPage();
  await page.goto("/teach/demo/courses");
  const course = await page.getByRole("link", { name: /A\/L Physics: Problem Solving/ }).first().getAttribute("href");
  await page.goto("/teach/demo/classes");
  const klass = await page.locator('a[href^="/teach/demo/classes/"]').filter({ hasNotText: /New/ }).first().getAttribute("href");
  await context.close();

  await shoot(browser, "teacher", state, [
    ["home", "/teach/demo"],
    ["classes", "/teach/demo/classes"],
    ["class", klass ?? "/teach/demo/classes"],
    ["courses", "/teach/demo/courses"],
    ["builder-landing", `${course}?tab=landing`],
    ["builder-curriculum", `${course}?tab=curriculum`],
    ["builder-insights", `${course}?tab=insights`],
    ["coupons", "/teach/demo/coupons"],
    ["media", "/teach/demo/media"],
    ["requests", "/teach/demo/requests"],
    ["payments", "/teach/demo/payments"],
    ["profile", "/teach/demo/profile"],
  ]);
});

test("owner screens", async ({ browser }) => {
  if (ONLY && !ONLY.includes("owner")) return;
  const state = await signedIn(browser, OWNER.email, OWNER.phone);
  await shoot(browser, "owner", state, [
    ["money", "/teach/demo/money"],
    ["earnings", "/teach/demo/earnings"],
    ["coupons", "/teach/demo/coupons"],
  ]);
});
