# EduZone — Frontend Design

> Companion to `CLAUDE.md`. Read both before frontend work.
> Where this file and `CLAUDE.md` disagree, **this file wins** (see section 1); `CLAUDE.md` will be
> updated to match.

---

## 1. Decisions that change `CLAUDE.md`

| Topic | Old (`CLAUDE.md`) | New |
|---|---|---|
| Domain | `eduzone.lk` | **`eduzone.switchops.tech`** |
| Teachers / institutes | Own subdomain each | **Live inside the main site** as a marketplace: `eduzone.switchops.tech/t/<slug>` |
| Companies | v1.1 corporate features | **Own private subdomain**: `<company>.eduzone.switchops.tech` |
| Public site | Branding + home page only | **Marketplace**: browse and search classes from all approved teachers |
| Teacher onboarding | Created by EduZone staff | **Self-registration**, then **EduZone approval** before publishing or selling |
| Student login | Phone OTP is primary | **Email is primary** (Google sign-in or email). **Unique mobile number required**, verified by SMS OTP |
| SMS OTP use | Every login | Only at **registration, new device, and account recovery** |
| Company staff | Not defined | Company **verifies its email domain** (DNS TXT); admin bulk-adds staff; staff with that domain can self-register |
| Platform admin | `admin.eduzone.lk` + IP allowlist | **Private: reachable only over VPN**, separate app, 2FA |

**Build order assumption:** marketplace (teachers + students) first, company subdomains after.

---

## 2. Platform map

```
                         eduzone.switchops.tech
 ┌──────────────────────────────────────────────────────────────────┐
 │  PUBLIC MARKETPLACE        /            /classes   /teachers      │
 │  TEACHER PUBLIC PAGES      /t/<slug>    /t/<slug>/c/<class-slug>  │
 │  STUDENT AREA              /learn/...   (one account, all teachers)│
 │  TEACHER / INSTITUTE CONSOLE /teach/<slug>/...                     │
 │  AUTH                      /login /register /verify-phone ...     │
 └──────────────────────────────────────────────────────────────────┘

                    <company>.eduzone.switchops.tech
 ┌──────────────────────────────────────────────────────────────────┐
 │  COMPANY LEARNING SITE  /         (staff only, fully white-label) │
 │  EMPLOYEE AREA          /learn/...                                │
 │  COMPANY CONSOLE        /manage/...                               │
 └──────────────────────────────────────────────────────────────────┘

          Private hostname, reachable only over the SwitchOps VPN
 ┌──────────────────────────────────────────────────────────────────┐
 │  PLATFORM ADMIN  (separate Next.js app, never deployed publicly)  │
 └──────────────────────────────────────────────────────────────────┘
```

| Surface | Who | Branding |
|---|---|---|
| Public marketplace | Everyone | EduZone brand |
| Teacher public page | Everyone | EduZone shell + teacher's logo and accent colour on their page |
| Student area | Registered students | EduZone brand |
| Teacher console | Teacher, institute owner/admin/teachers | EduZone brand |
| Company site | Company staff only | **Fully the company's** brand |
| Platform admin | SwitchOps staff | Plain internal UI |

---

## 3. Applications and hosting

| App | Serves | Deployed |
|---|---|---|
| `web` (Next.js) | Marketplace, teacher pages, student area, teacher console, company sites | Public |
| `admin` (Next.js) | Platform admin | **Private network only** (VPN). Its code never ships to the public server. |

One codebase (`frontend/`) with two apps sharing a `packages/ui` component library.

```
frontend/
├── apps/
│   ├── web/
│   │   ├── app/
│   │   │   ├── (marketplace)/        # /, /classes, /teachers, /t/[slug]/...
│   │   │   ├── (auth)/               # /login, /register, /verify-phone, /forgot
│   │   │   ├── (student)/learn/      # my classes, lessons, payments, profile
│   │   │   ├── (teacher)/teach/[slug]/
│   │   │   ├── (company)/            # rendered when host is a company subdomain
│   │   │   └── api/                  # BFF route handlers (proxy to FastAPI)
│   │   ├── middleware.ts             # host → site type; auth guard
│   │   └── i18n/                     # en.json, si.json, ta.json
│   └── admin/
├── packages/
│   ├── ui/                           # design system components
│   ├── api-client/                   # typed client generated from FastAPI OpenAPI
│   └── config/                       # tailwind preset, tsconfig, eslint
└── e2e/                              # Playwright
```

---

## 4. Site and tenant resolution

`middleware.ts` decides **which site** a request belongs to:

| Host / path | Site type | Tenant context |
|---|---|---|
| `eduzone.switchops.tech` `/`, `/classes`, `/teachers` | marketplace | none (cross-tenant public catalog) |
| `eduzone.switchops.tech/t/<slug>/...` | teacher public page | teacher tenant by `<slug>` |
| `eduzone.switchops.tech/learn/...` | student area | the signed-in user; spans many tenants |
| `eduzone.switchops.tech/teach/<slug>/...` | teacher console | `<slug>`, **only if the user is a member** |
| `<company>.eduzone.switchops.tech` | company site | company tenant by subdomain |
| anything else | 404 | — |

Rules:
1. The browser may **name** a tenant (slug in the URL). The **API always resolves and verifies it**:
   tenant exists, is active, and (for consoles) the user is a member with the right role.
2. The browser never sends a tenant UUID as a trusted value.
3. Reserved slugs that no tenant can take: `admin`, `api`, `www`, `app`, `learn`, `teach`, `t`,
   `login`, `register`, `support`, `status`, `mail`, `static`, `assets`.
4. A **company subdomain never shows marketplace content**, and the marketplace never lists company classes.

---

## 5. Security in the browser

- **BFF pattern:** the browser talks only to Next.js route handlers on the same host; they call FastAPI.
  Tokens never reach browser JavaScript.
- **Cookies:** `__Host-ez_session`: `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, **no `Domain`**.
  A company subdomain session is never sent to the main site or other subdomains.
- **No tokens in `localStorage`** or `sessionStorage`.
- **CSRF:** `SameSite=Lax` + a CSRF token header on every state-changing request.
- **CSP:** default-src self; allow Bunny video/CDN hosts, the payment gateway, Google sign-in, and fonts only.
- **Signed video and file URLs** are fetched per play and never cached or logged.
- **Rate-limit feedback:** OTP and login forms show cooldown timers from the API.

---

## 6. Identity and sign-in UX

### Student registration (marketplace)
1. **Register**: "Continue with Google" or email + password (email verification link).
2. **Verify mobile** (required): enter `07X XXX XXXX` → normalise to `+947XXXXXXXX` → SMS OTP → verified.
   A number already used by another account is rejected with a recovery link.
3. **Profile**: name, preferred language, optional exam/year and school.
4. Land on the marketplace or return to the class they were trying to join.

### Student sign-in
- Google or email + password.
- **New device** → SMS OTP to the verified number. Signing in revokes the older device's session
  (one-device rule); the old device shows "You were signed out because you signed in on another device".

### Teacher / institute registration
1. Register like a student (same account type; a person can be both).
2. "Teach on EduZone" → **application**: individual or institute, display name, slug, subjects,
   NIC/business registration document, bank details for payouts, accept teacher terms.
3. Status page: **Pending review** → **Approved** (can publish and sell) or **Changes requested**.
4. While pending, the console works in **draft mode**: classes can be created but not published.

### Company setup (after marketplace launch)
1. EduZone staff creates the company and its subdomain.
2. Company admin adds their email domain → shown a **DNS TXT record** → verification status updates.
3. Admin bulk-adds staff (CSV of emails) or staff self-register with a matching company email.
4. Public domains (`gmail.com`, `yahoo.com`, etc.) can never be claimed.

### Platform admin
Separate app on the private network, separate admin login, **2FA required** (authenticator app or passkey).

---

## 7. Screens

### 7.1 Public marketplace (`eduzone.switchops.tech`)

| Route | Screen | Contents |
|---|---|---|
| `/` | Home | Search bar, browse by exam (Grade 5 / O/L / A/L), subject chips, featured classes, "Teach on EduZone" |
| `/classes` | Catalog | Filters: exam, subject, batch year, medium, price, teacher. Sort: newest, popular. Card grid. |
| `/teachers` | Teachers | Approved teachers and institutes with subject tags |
| `/t/<slug>` | Teacher page | Logo, bio, subjects, their published classes |
| `/t/<slug>/c/<class>` | Class page | Description, schedule, months with fees, free preview lessons, **Join / Pay** |
| `/about`, `/terms`, `/privacy`, `/refund-policy` | Static | Required for the payment gateway |

Class card: cover, title, teacher, exam + year + medium badges, `Rs. 2,000 / month`.

### 7.2 Student area (`/learn`)

| Route | Screen | Contents |
|---|---|---|
| `/learn` | **Today** (home) | Next live class with countdown + Join, unpaid-month banners, recent recordings |
| `/learn/classes` | My classes | All joined classes **across all teachers**, grouped by teacher |
| `/learn/classes/<id>` | Class | Months list: **Paid / Unpaid / Closed – request access / Pending approval** |
| `/learn/classes/<id>/m/<month>` | Month | Lessons of that month (live, recorded, tutes) |
| `/learn/lessons/<id>` | Lesson | Video player, views left, Zoom join, tute downloads, previous/next |
| `/learn/checkout/<order>` | Checkout | Order summary → pay with the gateway |
| `/learn/checkout/<order>/return` | Payment result | Polls order status: Processing → Paid / Failed |
| `/learn/payments` | Payments | History; each row opens a **printable receipt** |
| `/learn/requests` | Past-month requests | Pending / approved (pay now) / rejected |
| `/learn/profile` | Profile | Name, email, verified phone, language, devices, sign out |

### 7.3 Teacher / institute console (`/teach/<slug>`)

| Route | Screen | Contents |
|---|---|---|
| `/teach/<slug>` | Dashboard | This month: collected, unpaid students, pending requests, upcoming live classes |
| `/teach/<slug>/classes` | Classes | List, create, edit, publish (blocked until approved) |
| `/teach/<slug>/classes/<id>` | Class detail | Months, lessons (add, edit, reorder, show/hide), settings (fee, view limit, late months) |
| `/teach/<slug>/media` | Media library | Upload video/PDF, processing status, storage used vs limit, attach to lessons |
| `/teach/<slug>/students` | Students | Per class and month: paid / not paid; search; manual access (scholarship/free) |
| `/teach/<slug>/requests` | Late-month inbox | Approve / reject with a note |
| `/teach/<slug>/payments` | Payments | Orders, refunds (request a refund) |
| `/teach/<slug>/cashflow` | Cash flow | Monthly: gross, gateway fees, EduZone commission, net, refunds, paid out, **balance due** |
| `/teach/<slug>/earnings` | Teacher earnings | Institutes only: net per teacher per month |
| `/teach/<slug>/team` | Team | Institutes: invite teachers/admins by email |
| `/teach/<slug>/profile` | Public profile | Logo, accent colour (contrast-checked), bio, subjects |
| `/teach/<slug>/payout` | Payout details | Bank details (masked), payout history |
| `/teach/apply` | Application | Teacher registration and approval status |

If a user belongs to more than one tenant, a **workspace switcher** sits in the console header.

### 7.4 Company site (`<company>.eduzone.switchops.tech`)

| Route | Screen |
|---|---|
| `/` | Company-branded home: assigned courses, progress, due dates |
| `/learn/...` | Same lesson player and course pages as students, **no checkout** |
| `/manage` | Company admin dashboard: staff count, completion rate, overdue |
| `/manage/staff` | Staff list, CSV import, departments |
| `/manage/domains` | Email domains + DNS TXT verification status |
| `/manage/courses` | Courses, assign to staff/departments with due dates |
| `/manage/reports` | Completion per person/department, CSV export |
| `/manage/branding` | Logo, colours |

### 7.5 Platform admin (private)

| Screen | Contents |
|---|---|
| Teacher applications | Review documents, approve / request changes / reject |
| Tenants | All teachers, institutes, companies; status; suspend |
| Payments | All payments, failed payments, refunds |
| Balances & payouts | Balance due per tenant; record payouts with bank reference |
| Usage | Bunny storage and bandwidth per tenant vs limits |
| Users | Search users, devices, reset phone verification |
| Audit log | Every admin action |

---

## 8. Key flows

### Pay for a month
1. Class page → month → **Pay Rs. 2,000** (signed in and phone-verified, else redirect to finish setup).
2. API creates the order → redirect to the gateway.
3. Return page shows **"Confirming payment…"** and polls the order. It **never** grants access itself.
4. Paid → "You now have access to October" → button to the month.
5. Failed or cancelled → retry button, no access.

### Request a past month
1. Closed month shows **Request access**, with an optional note.
2. Status **Pending** appears on the month and in `/learn/requests`.
3. Teacher approves → student is notified → month shows **Pay now**.

### Watch a lesson
1. Lesson page asks the API for a play session (access check + view count).
2. Allowed → short-lived signed HLS URL → player starts. Denied → clear reason (not paid / views used up).

### Teacher onboarding
Register → apply → pending (draft mode) → approved → publish first class → share `eduzone.switchops.tech/t/<slug>`.

---

## 9. Video player

- **Own player**: `hls.js` (native HLS on iOS Safari) inside our container. Not Bunny's iframe.
- **Watermark** inside the player container: student's name + last digits of phone, semi-transparent,
  **moves position every ~20 seconds**, stays visible in fullscreen.
- **Fullscreen** is applied to the container (video + watermark), never the bare `<video>` element.
- **Quality**: auto by default, starting at **480p on mobile**; manual 360p / 480p / 720p / 1080p.
- **Speed**: 0.75× to 2×.
- **Resume** from the last position; progress saved every 15 seconds and on pause/exit.
- **View limit**: "2 of 3 views left" shown before play; a view counts once per play session.
- Right-click menu disabled and no download button (deterrence only; the watermark is the real protection).

---

## 10. Design system

### Principles
1. **Neutral base, one accent.** White and grey surfaces, dark text. The accent colour only for primary
   buttons, links, active states, and highlights.
2. **Any accent must work.** Teacher and company colours are contrast-checked; button text switches
   between white and near-black automatically.
3. **Mobile first.** Design at 360 px width, then scale up.
4. **Content over decoration.** Students come to study, not browse a brochure.

### Tokens (CSS variables)
```css
:root {
  --ez-brand: #2D5BFF;          /* EduZone accent (placeholder until brand is set) */
  --ez-accent: var(--ez-brand);  /* replaced per teacher page / company site */
  --ez-accent-fg: #FFFFFF;       /* computed for contrast */
  --ez-bg: #FFFFFF;
  --ez-surface: #F6F7F9;
  --ez-border: #E3E6EA;
  --ez-text: #14171C;
  --ez-text-muted: #5B6470;
  --ez-success: #1E8E3E;
  --ez-warning: #B26A00;
  --ez-danger: #C62828;
  --ez-radius: 10px;
}
```
Status colours are fixed and never replaced by a tenant's accent.

### Typography
- Latin: **Inter** (variable, subset). Sinhala: **Noto Sans Sinhala**. Tamil: **Noto Sans Tamil**.
- Load a script's font **only when that language is active**.
- Base size 16 px; minimum 14 px; line-height 1.5 (1.6 for Sinhala/Tamil).

### Components (`packages/ui`)
Built on Radix primitives (shadcn/ui style, copied into the repo, not a heavy dependency):
Button, IconButton, Input, PhoneInput (LK), OtpInput, Select, Checkbox, Switch, Textarea, FileUpload
(with progress), Dialog, Sheet (mobile drawer), Toast, Tabs, Badge, StatusPill (Paid/Unpaid/Pending/Closed),
Card, ClassCard, Table (becomes cards on mobile), EmptyState, ErrorState, Skeleton, Pagination,
Money, DateTime, Countdown, ProgressBar, StatTile, VideoPlayer, Watermark, Receipt.

### Every data screen has four states
**Loading** (skeleton), **Empty** (explains what to do next), **Error** (retry), **Success**.

### Dark mode
Not in v1. Tokens are structured so it can be added later.

---

## 11. Formatting and language

- i18n library: `next-intl`. All user-facing text uses keys; `en` complete, `si` and `ta` added before wider launch.
- Language switcher in the header and profile; choice saved to the user's profile.
- **Money:** API sends integer cents → display `Rs. 2,000.00` (lists may drop `.00`).
- **Dates:** API sends UTC → display in `Asia/Colombo`, e.g. `Sat, 4 Oct · 8:00 AM`.
- **Phone:** input accepts `07X XXX XXXX`, stored as `+947XXXXXXXX`, shown as `077 123 4567`.

---

## 12. Performance budget (students on mobile data)

| Metric | Target (mid-range Android, 4G) |
|---|---|
| Largest Contentful Paint | < 2.5 s |
| JS on marketplace and lesson pages | < 170 KB gzipped |
| Interaction to Next Paint | < 200 ms |

- Server Components by default; client components only where interaction is needed.
- `next/image` with WebP/AVIF; class covers ≤ 80 KB.
- No large chart or animation libraries on student pages; console charts load lazily.
- Marketplace catalog and teacher pages are cached and revalidated when classes change.
- Test on a real low-end Android phone before the pilot.

---

## 13. Accessibility

- WCAG 2.1 AA contrast (enforced for tenant colours too).
- Touch targets ≥ 44 × 44 px; visible focus rings; every input has a label.
- Keyboard-usable dialogs and player controls.
- Status never shown by colour alone (Paid / Unpaid pills include text).

---

## 14. Frontend tech choices

| Need | Choice |
|---|---|
| Framework | Next.js (App Router) + TypeScript (strict) |
| Styling | Tailwind CSS + CSS variables for tokens |
| Components | Radix primitives, shadcn/ui-style in `packages/ui` |
| Server data | Server Components + route handlers; TanStack Query only for client-side polling/mutations |
| Forms | react-hook-form + zod |
| API types | Generated from FastAPI's OpenAPI schema into `packages/api-client` |
| Video | hls.js |
| i18n | next-intl |
| Testing | Vitest (units), Playwright (E2E at 360 px and desktop) |

---

## 15. Backend changes this design needs

These are not frontend work, but the screens depend on them:

1. **Path-based tenant resolution** for `/t/<slug>` and `/teach/<slug>`, alongside host-based for companies.
2. **Public catalog endpoint** across tenants: published classes of approved, marketplace-listed tenants only,
   public fields only. Implemented as a narrow read path (e.g. a `SECURITY DEFINER` function or a dedicated
   view), never by disabling RLS broadly.
3. **Student cross-tenant reads**: "My classes", "Today", payments and requests span many teacher tenants.
   Needs a user-scoped read path that returns only the signed-in user's own rows.
4. **Identity**: `user_identities` (Google), email + password, email verification, phone verification
   state, new-device OTP.
5. **Teacher applications** table and approval workflow; tenant `pending` → `active`.
6. **Tenant fields**: `site_type` (`marketplace` | `company`), `is_listed`, `accent_color`.
7. **Company domains**: `tenant_email_domains` with DNS TXT verification state; public-domain blocklist.
8. **Reserved slugs** enforced in the API.

---

## 16. Build order

1. Groundwork: monorepo layout, `packages/ui` core components, tokens, i18n, middleware site resolution, BFF + cookies
2. Auth: register (Google + email), phone verification, sign-in, new-device OTP, profile
3. Marketplace: home, catalog with filters, teacher page, class page
4. Teacher application + approval status; console dashboard; classes/months/lessons (move existing slice under `/teach/<slug>`)
5. Media library + video player (with backend step 5)
6. Student area: Today, My classes, months, lessons, late-month requests; console students list and request inbox (backend step 6)
7. Checkout, return page, payments, receipts; console payments (backend step 7)
8. Cash flow, teacher earnings, team, payout details (backend step 8)
9. Platform admin app on the private network (backend step 9)
10. Company sites (after marketplace pilot)
11. Sinhala/Tamil, Playwright suite, low-end phone polish

---

## 17. Open questions

| Question | Assumption until answered |
|---|---|
| Pilot order | Marketplace teachers first, companies later |
| Cart across several teachers | One teacher per order in v1 (orders and ledger are per tenant) |
| Teacher page branding | Teacher's logo + accent on their own pages only; rest of the site is EduZone brand |
| Email sign-in method | Email + password, plus Google |
| Company staff phone verification | Not required; verified company email is enough |
| Company learning cost to staff | Free to staff; company pays a subscription |
| Institute public page | Lists its teachers and all their classes |
| EduZone brand colour and logo | Placeholder until decided |
