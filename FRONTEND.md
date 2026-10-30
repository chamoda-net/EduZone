# EduZone — Frontend Design

> Companion to `CLAUDE.md`. Read both before frontend work. Backend contracts, money rules and schema
> changes live in `CLAUDE.md`; this file covers sites, screens, UX and the design system.

---

## 1. Platform map

```
                              eduzone.switchops.tech
 ┌────────────────────────────────────────────────────────────────────────┐
 │ MARKETPLACE         /   /classes   /teachers   /institutes             │
 │ SUBJECT PAGES       /<subject>                    e.g. /physics         │
 │ TEACHER PAGES       /<subject>/<teacher>          e.g. /physics/jhone   │
 │ CLASS PAGES         /<subject>/<teacher>/<class>                        │
 │ INSTITUTE PAGES     /institutes/<slug>                                  │
 │ CART & CHECKOUT     /cart   /checkout/<checkout-no>                     │
 │ STUDENT AREA        /learn/...      (one account, every teacher)        │
 │ TEACHER CONSOLE     /teach/<tenant-slug>/...                            │
 │ AUTH                /login  /register  /verify-phone  /recover          │
 └────────────────────────────────────────────────────────────────────────┘

                      <company>.eduzone.switchops.tech   (v1.1)
 ┌────────────────────────────────────────────────────────────────────────┐
 │ COMPANY SITE  /    EMPLOYEE AREA  /learn/...    COMPANY CONSOLE /manage │
 └────────────────────────────────────────────────────────────────────────┘

                   Private hostname — SwitchOps VPN only
 ┌────────────────────────────────────────────────────────────────────────┐
 │ PLATFORM ADMIN  (separate Next.js app, never deployed publicly)         │
 └────────────────────────────────────────────────────────────────────────┘
```

| Surface | Who | Branding |
|---|---|---|
| Marketplace, subject, teacher, class pages | Everyone | EduZone brand. **Teachers have a profile, not their own theme.** |
| Student area, cart, checkout | Students | EduZone brand |
| Teacher console | Teachers, institute owners/admins | EduZone brand |
| Company site (v1.1) | Company staff | **Company's own brand** (logo + colour) |
| Platform admin | SwitchOps staff | Plain internal UI |

---

## 2. Applications and repository

| App | Serves | Deployed |
|---|---|---|
| `web` | Marketplace, student area, cart/checkout, teacher console, company sites | Public |
| `admin` | Platform admin | **Private network only**; its code never ships to the public server |

```
frontend/
├── apps/
│   ├── web/
│   │   ├── app/
│   │   │   ├── (marketplace)/            # /, /classes, /teachers, /institutes, /[subject]/...
│   │   │   ├── (auth)/                   # /login, /register, /verify-phone, /recover
│   │   │   ├── (shop)/                   # /cart, /checkout/[no]
│   │   │   ├── (student)/learn/
│   │   │   ├── (teacher)/teach/[tenant]/
│   │   │   ├── (company)/                # rendered when the host is a company subdomain
│   │   │   └── api/                      # BFF route handlers → FastAPI
│   │   ├── middleware.ts
│   │   └── i18n/{en,si,ta}.json
│   └── admin/
├── packages/
│   ├── ui/                               # design system
│   ├── api-client/                       # generated from FastAPI OpenAPI
│   └── config/                           # tailwind preset, tsconfig, eslint
└── e2e/                                  # Playwright
```

---

## 3. Routing and resolution

`middleware.ts` decides the site; the API always resolves and authorizes tenants itself.

| Request | Site | How the backend finds data |
|---|---|---|
| main host, `/`, `/classes`, `/teachers`, `/institutes` | marketplace | public catalog |
| main host, `/<subject>` | subject page | public catalog filtered by subject |
| main host, `/<subject>/<teacher>` | teacher page | teacher profile slug; 404 if the teacher has no published class in that subject |
| main host, `/<subject>/<teacher>/<class>` | class page | class slug within that teacher's tenant |
| main host, `/learn/...`, `/cart`, `/checkout/...` | student | signed-in user (`app.user_id`), across tenants |
| main host, `/teach/<tenant>/...` | console | tenant slug **+ membership check** |
| `<company>.eduzone.switchops.tech` | company site | host → company tenant |

Rules:
- The first path segment is matched in this order: **reserved routes** → **subject slugs** → 404.
  Subject slugs come from the EduZone-managed `subjects` list, so they can never collide with routes.
- A teacher teaching several subjects has one page per subject (`/physics/jhone`, `/combined-maths/jhone`),
  each with a link to their other subjects.
- Teacher slugs are unique platform-wide (`jhone`, `jhone-perera`, …).
- Company subdomains never show marketplace content; the marketplace never lists company classes.

---

## 4. Browser security

- **BFF:** the browser only calls Next.js route handlers on the same host; they call FastAPI.
  Tokens never reach browser JavaScript.
- **Cookies:** `__Host-ez_session` — `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, **no `Domain`**.
- **No tokens** in `localStorage` / `sessionStorage`. The **cart** may live in `localStorage` until sign-in,
  then syncs to the server.
- **CSRF:** `SameSite=Lax` + CSRF token header on every state-changing request.
- **CSP:** allow only self, Bunny video/CDN hosts, the payment gateway, Google sign-in, and fonts.
- Signed video/file URLs are fetched per play and never cached or logged.
- OTP and login forms show cooldown timers from the API's rate limits.

---

## 5. Identity UX

### Student registration
1. **Continue with Google**, or email + password (verification link sent).
2. **Verify mobile** (required, unique): `07X XXX XXXX` → `+947XXXXXXXX` → 6-digit SMS OTP.
   Number already used → "This number is linked to another account" + recover link.
3. **About you**: name, preferred language, optional exam + year + school.
4. Return to where they were (class page or cart).

Users may browse and add to cart without an account; registration and phone verification happen at
**checkout**, not before.

### Sign-in
- Google or email + password. Known device: done, **no SMS**.
- **New device** → SMS OTP to the verified number → older device signed out; it shows
  "You were signed out because your account was used on another device."
- **Recovery** → email link + SMS OTP.

### Teacher / institute registration
Register as a normal user → **Teach on EduZone** → application (individual or institute, name,
profile slug, subjects, ID/business document, payout bank details, terms) → **Pending review**
(console in draft mode, publish disabled with an explanation) → **Approved** → publish.

### Company staff (v1.1)
Company email + verification link; no phone verification.

---

## 6. Screens

### 6.1 Marketplace
| Route | Screen | Key content |
|---|---|---|
| `/` | Home | Search, exam tabs (Grade 5 / O/L / A/L), subject grid, popular classes, "Starting this month", Teach on EduZone |
| `/classes` | Catalog | Filters: exam, subject, batch year, medium, price, live/recorded. Mobile: filters in a bottom sheet |
| `/<subject>` | Subject page | All teachers and classes for that subject, filter by exam/year/medium |
| `/teachers`, `/institutes` | Directories | Cards with subjects, class count |
| `/<subject>/<teacher>` | **Teacher page** | See 6.2 |
| `/<subject>/<teacher>/<class>` | Class page | What you'll learn, schedule (day/time), months with fees and status, free preview lessons, teacher card, **Add to cart / Buy now** |
| `/institutes/<slug>` | Institute page | About, teachers, classes by subject |
| `/about`, `/terms`, `/privacy`, `/refund-policy`, `/contact` | Static | Required for gateway approval |

### 6.2 Teacher page — built for teachers to market
Purpose: a page a teacher proudly shares on WhatsApp, Facebook and printed posters.

Contents (top to bottom):
1. **Photo, name, headline** (e.g. "B.Sc Physics · 12 years teaching"), subjects, medium
2. **Primary action**: "View classes" / "Join October" for the current month
3. **Classes in this subject** with schedule, fee, exam year, seats/students count (optional)
4. **Highlights**: results, qualifications (teacher-entered, short)
5. **Free preview lesson** if available
6. **About** (bio)
7. **Other subjects** this teacher teaches

Sharing tools (in the console and on the page):
- **Copy link** and **Share to WhatsApp** (pre-filled message in the teacher's chosen language)
- **QR code** download (PNG/SVG) for posters and tute covers
- Rich link preview (Open Graph image auto-generated: photo, name, subject, EduZone mark)

No teacher logo or custom colours; every teacher page looks consistent and trustworthy.

### 6.3 Cart and checkout
| Route | Screen | Key content |
|---|---|---|
| `/cart` | Cart | Items **grouped by teacher**: class, month, fee. Remove item. Total. Notes when an item became unavailable. |
| `/checkout/<no>` | Review | Sign-in / phone verification if needed → summary → **Pay Rs. X** → gateway |
| `/checkout/<no>/return` | Result | "Confirming your payment…" (polls) → success list of unlocked months with links, or failure + retry |

Rules shown to the user: past months need approval first; already-owned months can't be added.

### 6.4 Student area (`/learn`)
| Route | Screen | Key content |
|---|---|---|
| `/learn` | **Today** | Next live class (countdown + Join), "Pay for November" cards, new recordings, continue watching |
| `/learn/classes` | My classes | Every joined class across all teachers |
| `/learn/classes/<id>` | Class | Months: **Paid · Unpaid (Pay) · Closed (Request) · Pending approval** |
| `/learn/classes/<id>/m/<month>` | Month | Lessons: live, recorded, tutes |
| `/learn/lessons/<id>` | Lesson | Player, views left, Zoom button, downloads, previous/next |
| `/learn/schedule` | Schedule | Week view of upcoming live classes from all teachers |
| `/learn/payments` | Payments | Checkouts with their items grouped by teacher; **printable receipt** per checkout |
| `/learn/requests` | Requests | Past-month requests and their status |
| `/learn/profile` | Profile | Name, email, phone (verified), language, signed-in device, sign out |

### 6.5 Teacher / institute console (`/teach/<tenant>`)
| Route | Screen |
|---|---|
| `/` | Dashboard: collected this month, unpaid students, pending requests, upcoming live classes, approval status banner |
| `/classes`, `/classes/<id>` | Classes, months, lessons (add, edit, reorder, show/hide), class settings |
| `/media` | Upload video/PDF, processing status, storage used vs limit |
| `/students` | Per class/month paid vs unpaid; manual access (scholarship/free) |
| `/requests` | Late-month inbox: approve / reject with note |
| `/payments` | Orders and refund requests |
| `/cashflow` | Monthly gross, gateway fees, commission, net, refunds, paid out, **balance due** |
| `/earnings` | Institutes: net per teacher per month |
| `/team` | Institutes: invite teachers/admins by email |
| `/profile` | Teacher page editor with live preview + **share tools** (link, WhatsApp, QR) |
| `/payout` | Bank details (masked), payout history |
| `/teach/apply` | Application and approval status |

Workspace switcher in the header if the user belongs to more than one tenant.

### 6.6 Company site (v1.1)
`/` assigned courses + due dates · `/learn/...` same player, no checkout · `/manage` dashboard ·
`/manage/staff` CSV import, departments · `/manage/domains` DNS TXT status · `/manage/courses` assign ·
`/manage/reports` completion + CSV · `/manage/branding` logo and colour.

### 6.7 Platform admin (private)
Teacher applications · Tenants (suspend, list/unlist) · Subjects list · Checkouts and payments ·
Balances and payouts · Bunny usage · Users and devices · Audit log.

---

## 7. Key flows

**Buy classes from two teachers**
Physics (Jhone) October → Add to cart → Chemistry (Ana) October → Add to cart → Cart shows two groups →
Checkout → sign in / verify phone if needed → Pay once → return page confirms → both months unlocked.

**Request a past month**
Closed month → Request access (optional note) → Pending → teacher approves → notification → Pay now (via cart).

**Watch a lesson**
Lesson page → API play session (access + view count) → short-lived HLS URL → player.
Denied → plain reason and the action to fix it (Pay for this month / Views used up – contact teacher).

**Teacher onboarding**
Register → Apply → Pending (draft) → Approved → Publish first class → Profile → Share link/QR.

---

## 8. UX principles

The audience is students on budget Android phones and mobile data, parents paying fees, and teachers
who are not technical. Design every screen against these rules:

1. **The next class is never more than one tap away.** "Today" opens on the next live class or the
   lesson the student was watching.
2. **Payment status is always obvious.** Every month shows one clear pill: Paid, Unpaid, Pending, Closed.
   Never make a student guess whether they have access.
3. **Explain every block.** Locked content always says why and offers the one action that unlocks it.
4. **Ask only when needed.** Browse and build a cart without an account; ask for registration and phone
   verification only at checkout.
5. **Plain, local language.** "Pay for October", not "Purchase entitlement". Sinhala/Tamil copy written
   by native speakers, not machine-translated.
6. **Thumb-first layout.** Primary actions in the bottom half of the screen on mobile; sticky bottom bar
   on class pages and in the cart.
7. **Fast on slow networks.** Skeletons instead of spinners; content readable before images load;
   optimistic UI for small actions.
8. **Forgiving forms.** Accept `0771234567`, `077 123 4567` and `+94771234567`; keep input on errors;
   errors next to the field, in plain words.
9. **Trust signals for parents.** Clear fees, receipts, refund policy link, teacher qualifications,
   secure-payment note at checkout.
10. **Teachers are busy.** Console defaults to the most common next step (add this month's lessons,
    see who hasn't paid). Bulk actions where repetition is common.

---

## 9. Design system

### Brand
Decided 2026-10-30: **deep forest green** as the brand colour, **warm gold** for emphasis only (marks,
"new", highlights on dark), on an **ivory "paper"** page background. Direction: scholarly and modern,
calm and trustworthy for parents, premium enough to compete with global platforms. The final logo is
still to come; `LogoMark` in `packages/ui` is a placeholder (an open book whose pages form a leaf).
All components read colours from tokens only, so a logo or shade change needs no code changes.
Teachers and institutes get **no own colours** on the marketplace (section 2 of CLAUDE.md).

### Tokens
The source of truth is `frontend/packages/ui/src/tokens.css`: brand `--ez-brand-50…950`
(accent = `--ez-brand-700` `#124A33`), gold `--ez-gold-100…600`, warm neutrals (`--ez-surface` page
`#FAF8F3`, `--ez-bg` cards `#FFFFFF`, `--ez-sunken`, `--ez-border`, `--ez-text` `#14201A`), status colours
(never themed), radii 8/12/20, three shadows and one easing curve. Tailwind names map onto them
(`bg-brand`, `text-muted`, `bg-gold`, `rounded-ez-lg`, `shadow-ez`…). Helpers: `font-display`,
`ez-grain` (film grain on dark panels), `ez-ruled`, `ez-mark`, `ez-rise` (staggered page-load reveal,
`--i` = order), `ez-skeleton`; all respect `prefers-reduced-motion`.
Company colours (v1.1) replace `--ez-accent` only and are contrast-checked; `--ez-on-accent` switches
between white and near-black to meet WCAG AA.

### Typography
- Headings: **Fraunces** (variable serif, soft optical axis), via `font-display`.
- Text and UI: **Instrument Sans**. Sinhala: **Noto Sans Sinhala**; Tamil: **Noto Sans Tamil** (later).
  All through `next/font` (self-hosted, subset, no layout shift).
- Scale: 12 / 14 / 15 (UI) / 16 (base) / 18 / 24 / 30 / 36 / 48–66 (hero). Line-height 1.5; 1.6 for
  Sinhala and Tamil. Eyebrows: 12 px bold, 0.14em tracking, upper case, brand-600.
- Numbers in tables and money use tabular figures; big amounts use the display face.

### Components (`packages/ui`, Radix primitives, shadcn/ui style)
Built so far (design foundation): Button (7 variants, 3 sizes, loading), Field/Input/Select/Textarea/
Checkbox, Badge, StatusPill, Card, CardTitle, PageHeader, Alert, EmptyState, Skeleton, StatTile,
DataList, Avatar, Logo, ClassCover (generated book-cover artwork when a class has no image), FilterChips,
Dialog (bottom sheet on phones), Toast, SideNav/NavDrawer/ConsoleFrame (console), HeaderNav/TabBar
(student site). A dev-only style guide shows them all at `/design` in `apps/web`. Still to build as
screens need them:
Button, IconButton, Input, PasswordInput, PhoneInput (LK), OtpInput, Select, Combobox, Checkbox, Switch,
Textarea, FileUpload (progress, resumable), Dialog, BottomSheet, Toast, Tabs, Badge, **StatusPill**,
Card, **ClassCard**, **TeacherCard**, **MonthRow**, **CartGroup**, Table (cards on mobile), EmptyState,
ErrorState, Skeleton, Pagination, **Money**, DateTime, Countdown, ProgressBar, StatTile, **VideoPlayer**,
Watermark, **Receipt**, **ShareSheet** (link, WhatsApp, QR), StickyActionBar.

### Every data screen has four states
**Loading** (skeleton) · **Empty** (what to do next) · **Error** (retry) · **Success**.

### Dark mode
Not in v1; tokens allow it later.

---

## 10. Video player

- Own player: **hls.js** (native HLS on iOS Safari), inside our container — not Bunny's iframe.
- **Watermark** inside the container: student name + last 4 phone digits, semi-transparent,
  repositions every ~20 s, visible in fullscreen.
- **Fullscreen** applies to the container (video + watermark).
- **Quality**: auto, starting at 480p on mobile; manual 360p–1080p. **Data saver** toggle in profile caps at 360p.
- Speed 0.75×–2×; resume position; progress saved every 15 s and on pause/exit.
- "2 of 3 views left" shown before play; a view counts once per play session.
- No download button, context menu disabled (deterrence; the watermark is the real protection).

---

## 11. Formatting and language

- `next-intl`; all text via keys. **Pilot: English complete; Sinhala for the student area if the pilot
  teachers need it.** Tamil before wider launch.
- Language switcher in the header and profile; saved to the user.
- Money: integer cents from the API → `Rs. 2,000.00` (lists may drop `.00`).
- Dates: UTC from the API → `Asia/Colombo`, e.g. `Sat, 4 Oct · 8:00 AM`.
- Phone shown as `077 123 4567`.

---

## 12. Performance budget

| Metric | Target (mid-range Android, 4G) |
|---|---|
| Largest Contentful Paint | < 2.5 s |
| JS on marketplace, class and lesson pages | < 170 KB gzipped |
| Interaction to Next Paint | < 200 ms |

- Server Components by default; client components only where needed.
- Marketplace, subject, teacher and class pages are statically cached and revalidated when classes change
  (also good for search engines).
- `next/image`, WebP/AVIF, covers ≤ 80 KB, teacher photos ≤ 60 KB.
- Console charts lazy-loaded; no heavy chart library on student pages.
- Test on a real low-end Android phone before the pilot.

---

## 13. Accessibility

WCAG 2.1 AA contrast · touch targets ≥ 44 px · visible focus · labelled inputs · keyboard-usable dialogs
and player · status never by colour alone · respects reduced-motion (watermark moves without animation).

---

## 14. SEO and sharing

- Teacher and class pages are the main way students find EduZone: server-rendered, clean titles
  ("Jhone — A/L Physics Classes | EduZone"), descriptions, `Course` / `Person` structured data.
- Auto-generated Open Graph images for teacher and class pages (WhatsApp/Facebook previews).
- Sitemap of all public subject, teacher and class pages.

---

## 15. Frontend tech choices

| Need | Choice |
|---|---|
| Framework | Next.js (App Router) + TypeScript strict |
| Styling | Tailwind + CSS variable tokens |
| Components | Radix primitives, shadcn/ui-style in `packages/ui` |
| Data | Server Components + route handlers; TanStack Query for polling and mutations |
| Forms | react-hook-form + zod |
| API types | Generated from FastAPI OpenAPI |
| Video | hls.js |
| QR codes | Generated server-side (small library) |
| i18n | next-intl |
| Tests | Vitest + Playwright (360 px and desktop) |

---

## 16. Build order (frontend)

1. Groundwork: monorepo, tokens, core components, i18n, middleware routing, BFF + cookies
2. Auth rework: Google + email, phone verification, new-device OTP, recovery, profile
3. Marketplace: home, catalog, subject pages, teacher pages, class pages, institutes
4. Teacher application + approval states; move existing console slice under `/teach/<tenant>`;
   profile editor + share tools
5. Media library + video player
6. Student area: Today, My classes, months, lessons, schedule, requests; console students + inbox
7. Cart, checkout, return page, payments, receipts; console payments
8. Cash flow, earnings, team, payout details
9. Platform admin app (private)
10. Polish: Sinhala, Playwright suite, low-end phone pass
11. v1.1: company sites

---

## 17. Resolved and open

| Topic | Decision |
|---|---|
| Pilot order | Marketplace first, companies later ✅ |
| Multi-teacher cart | One checkout, one payment; one order per item, grouped by teacher on screen ✅ |
| Teacher branding | No logo/colour; marketable profile at `/<subject>/<teacher>` ✅ |
| Company staff | Free to staff, no checkout, no phone verification ✅ |
| Sign-in | Google or email + password; SMS only at registration, new device, recovery ✅ |
| EduZone brand | **Open** — placeholder tokens until announced |
| Institute URL | `/institutes/<slug>` (assumed) |
| Sinhala at pilot | **Open** — depends on pilot teachers |
