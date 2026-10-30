# Migration plan: from what's built to the FRONTEND.md design

> Status: **accepted** 2026-10-30 (phase 0 done: CLAUDE.md and FRONTEND.md updated; the six decisions in
> section 2 were taken as recommended). Built so far: CLAUDE.md build steps 1–9 (commit `1dd0ccf`),
> one subdomain per organization. Target: `FRONTEND.md` (marketplace on one host, one student account
> across all teachers, cart, teacher self-registration, private admin app).
>
> Nothing has launched and there is no production data, so every change below can be made directly,
> without backwards-compatibility shims or data migrations for real users.

---

## 1. What changes, and what survives

### Survives unchanged (the expensive, well-tested core)
- The schema's tenant model: `tenants`, `tenant_members`, classes → months → lessons → resources,
  enrollments, late requests, `access_grants`, `lesson_progress`.
- **RLS per tenant**, composite foreign keys, the two database roles, audit logs.
- **Money:** orders, payments, the ledger and its posting rules, cash flow, earnings, payouts, the
  webhook pipeline (store → verify → one transaction), the gateway interface.
- Catalogue rules (status flow, pricing lock, month/lesson rules), media and Bunny uploads, the
  access rule in `learning/access.py`, manual grants, the late-request inbox.
- Platform admin backend (two-factor sign-in, organizations, payouts).

All of this stays per tenant underneath. What changes is **how a request finds its tenant and its user**,
plus a handful of new features.

### Changes

| Area | Today | FRONTEND.md | Size |
|---|---|---|---|
| Hosts | `<slug>.eduzone.lk` per organization | one host `eduzone.switchops.tech`; tenant from the **path** (`/teach/<tenant>`, `/<subject>/<teacher>/<class>`); companies keep subdomains (v1.1) | L |
| Student identity | phone OTP every sign-in; member created at first login on a tenant | **one account across all teachers**; Google or email + password; phone verified once (unique); SMS only at registration, new device, recovery | L |
| Sessions | per tenant (`user_sessions.tenant_id`), token carries `tid` | per user, account-wide; token without `tid`; tenant comes from the path + membership check | M |
| Student reads | inside one tenant | `/learn` spans every teacher: needs a **user-scoped RLS path** | M |
| Catalogue | per tenant, `/public/classes` | **marketplace across tenants**: subjects, teacher profiles, institutes, search | L |
| Teacher onboarding | staff create organizations | **self-registration → application → EduZone approval**; draft mode until approved | M |
| Checkout | one item per order, one order per payment | **cart across teachers, one payment** for several orders | L |
| Player | Bunny iframe + overlay | **own hls.js player** with watermark inside; HLS URLs signed for the CDN | M |
| Teacher branding | tenant logo + colour | **none** (profile only); colour only for company sites | S |
| Admin | `/platform` pages in the main app on `admin.<host>` | **separate app**, private network only | S |
| Frontend structure | one Next app, hand-written helpers | monorepo `apps/web`, `apps/admin`, `packages/ui`, generated API client, next-intl, react-hook-form + zod, TanStack Query | M |
| Design | ad-hoc tokens, dark mode | FRONTEND.md tokens (`--ez-*`), Inter, **no dark mode in v1** | S |

---

## 2. Decisions (taken as recommended, 2026-10-30)

1. **Orders in a cart.** FRONTEND.md says *one order per teacher*. Recommendation: **one order per item
   (as today), grouped under a new `checkouts` row with one payment**. The cart still shows items grouped by
   teacher and the receipt is per checkout, but the existing order → grant → ledger code, its tests and the
   "one item per order" rule all stay; only the gateway fee must be split across orders (largest-remainder,
   so it sums exactly). The UI looks identical either way.
2. **Student membership.** Recommendation: create the student's `tenant_members` row **when they join or pay
   for a class** of that teacher, not at sign-in (there's no tenant at sign-in any more).
3. **One-device rule.** FRONTEND.md signs out the older device on a new-device sign-in. Confirm it is now
   **account-wide** (today it is per tenant).
4. **Teacher identity.** Teacher slug is "unique platform-wide" and pages are `/<subject>/<teacher>`.
   Recommendation: the slug belongs to a **teacher profile per person** (`teacher_profiles.user_id`), so a
   teacher at two institutes still has one page; institute teachers appear under their own name with the
   institute shown on the card.
5. **External accounts you'll need to create:** a Google OAuth client (Google sign-in) and an email
   sending provider (verification and recovery links). Both are new; neither exists yet.
6. **CLAUDE.md is the spec for backend contracts.** It still says subdomains, phone-OTP-first and
   "marketplace across tenants: out of scope". Phase 0 rewrites those sections; confirm you want that
   (FRONTEND.md section 17 suggests yes).

---

## 3. Phases

Each phase ends with the app working and the test suite green. Order follows FRONTEND.md section 16,
with the backend work each frontend phase depends on.

### Phase 0 — Spec (no code) ✅ done
- Update CLAUDE.md: domain, tenancy (path + membership instead of host), identity, sessions, user-scoped
  reads, marketplace in scope, cart/checkout model, teacher applications, subjects, player URLs,
  build order. Move "Decisions" from section 2 above into it.
- Commit FRONTEND.md together with it so the two never disagree in the repo.

### Phase 1 — Frontend groundwork (no behaviour change) ✅ done
Done as below, with these differences: no `packages/config` (each app keeps its small eslint/tsconfig;
revisit if they drift); shared code lives in `packages/lib` (format, i18n, types); hand-written types move
to `@eduzone/api-client` screen by screen, because the backend still types several enums as `str`;
react-hook-form + zod not added yet (they come with the first form a phase rewrites). Also fixed: a new
student had to retype the OTP code after entering their name (found by the smoke suite).

- Monorepo: move today's app to `frontend/apps/web`, `app/platform/*` to `frontend/apps/admin`;
  `packages/ui` (move `components/ui.tsx` and friends, switch to `--ez-*` tokens, Inter), `packages/config`.
- `packages/api-client` generated from FastAPI's OpenAPI; replace hand-written types in `lib/types.ts`.
- next-intl replacing `lib/i18n` (keys keep their names); react-hook-form + zod for forms as they're touched.
- Playwright smoke suite on today's flows (sign-in, class, pay with the fake gateway, console) so later
  phases can't silently break them.
- Drop dark mode styles.

### Phase 1b — Design foundation ✅ done
Added at the user's request before phase 2, so new screens are built once at the final quality bar:
brand (forest green, gold, ivory), Fraunces + Instrument Sans, the component kit and page frames in
`packages/ui`, generated class covers, every existing student, console and admin screen restyled, and a
dev-only style guide at `/design`. Tenant colours are no longer applied (marketplace decision).

### Phase 2 — Identity (backend + frontend) **[L]** ✅ done
Built as below, with these choices: the new-device check is a signed 10-minute challenge plus an SMS code
(no extra table); accounts without a verified phone sign in without a code (nothing to check yet, and they
can't pay); staff of any organization are exempt from the one-device rule; membership is created on join,
pay or opening a file, and looked up per request on the tenant host until phase 3 moves it to the path;
organization owners are created by email and set their password through recovery; pages opened from email
links act only on a button press. Cookie names get the `__Host-` prefix in production only (local http
can't set Secure cookies). Google sign-in is built and tested with a fake verifier; it needs a real client id.
Backend:
- Schema: `user_identities` (provider, subject, e.g. Google), `email_verifications` and `recovery_tokens`
  (hashed, expiring), `users.phone_verified_at` becomes required for checkout; `user_devices` (trusted
  device ids per user).
- Sessions: `user_sessions.tenant_id` → nullable then dropped; one-device rule account-wide (per decision 3).
- Tokens: no `tid`; `CurrentMember` becomes `CurrentUser` + a per-request membership lookup for console routes.
- Endpoints: register (email + password, argon2/bcrypt), verify email, Google sign-in (OIDC, ID token
  verified server-side), sign-in, new-device OTP, recovery (email link + SMS OTP), phone verification
  (unique; "linked to another account" error), profile.
- Reuse: OTP limits, phone normalisation, refresh rotation, the device cookie.
Frontend: `/register`, `/login`, `/verify-phone`, `/recover`, `/learn/profile`; cookie becomes
`__Host-ez_session` (Secure; needs https locally or a dev exception).
Tests: replace phone-OTP-login tests; keep isolation tests.

### Phase 3 — Path tenancy and the cross-tenant student area **[M]** ✅ done
Built as below, with these choices: the console routes are mounted twice (`/teach/{tenant_slug}` takes the
tenant from the path; `/org` keeps the host for the tenant sites until phase 4). The student area uses the
user-scoped policies for lists of the user's own rows (memberships, payments) and, for anything about a
class, finds the class's tenant by id (`resolve_entity_tenant`) and runs there, so the access rule is
untouched and the catalogue tables need no user policy. Today and Schedule loop over the user's tenants.
`user_is_staff_anywhere()` now belongs to `eduzone_admin` (it saw no rows under forced RLS as the migration
role unless that role is a superuser, as it is locally). Middleware routing by subject slug comes with
phase 4 (no subjects yet); the main host's `/` is a sign-in welcome until then.
Backend:
- `tenant_from_path(slug)` for `/teach/<tenant>` routes: resolve + **membership check** (staff role) →
  same `tenant_transaction()` as today. Host resolution stays for company sites (v1.1).
- **User-scoped reads** for `/learn`, cart and payments: `SET LOCAL app.user_id`, plus extra RLS policies on
  student-owned tables (`tenant_members` own rows; `class_enrollments`, `access_grants`, `late_month_requests`,
  `lesson_progress`, `orders`, `order_items`, `payments` where the student member belongs to `app.user_id`).
  Reads only; writes still happen inside the class's tenant transaction. New isolation tests: user A never
  sees user B's rows; a user sees their rows across two tenants.
- The access rule is unchanged; it runs inside the class's tenant.
Frontend: `/teach/<tenant>/...` (move `/org/*`), workspace switcher, `/learn` (Today, classes, class, month,
lesson, schedule, requests, payments), middleware routing per FRONTEND.md section 3.

### Phase 4 — Marketplace **[L]**
Backend:
- `subjects` (platform-managed, slug), `classes.subject_id`; `teacher_profiles` (slug unique, photo,
  headline, bio, highlights, subjects); institutes = `tenants.org_type = 'institute'` with a public slug.
- `tenants.is_listed` + approval state; the public catalogue as **one narrow read path** across tenants
  (a `SECURITY DEFINER` function set or an admin-owned view exposing public fields only, for listed and
  approved tenants and published classes). Never by relaxing RLS.
- Search/filter endpoint (exam, subject, year, medium, price, live/recorded); start with Postgres
  full-text + indexes.
Frontend: `/`, `/classes`, `/<subject>`, `/<subject>/<teacher>`, `/<subject>/<teacher>/<class>`, `/teachers`,
`/institutes[/<slug>]`, static pages; cached + revalidated on change (Cache Components may come back here),
Open Graph images, sitemap, structured data, ShareSheet (link, WhatsApp, QR).

### Phase 5 — Teacher self-registration and approval **[M]**
Backend: `teacher_applications` (individual/institute, profile slug, subjects, document in **private**
storage, payout bank details, terms version); creating an application creates a `pending` tenant with the
applicant as owner; publishing and selling refused until approved; admin review endpoints (approve /
request changes / reject) with audit rows.
Frontend: `/teach/apply` and status; console draft-mode banners; profile editor with live preview; admin
"Teacher applications" screen.

### Phase 6 — Cart and multi-teacher checkout **[L]**
Backend (per decision 1):
- `checkouts` (platform-level: user, number, total, status) and `checkout_payments` (gateway attempt,
  idempotency key, fee). Each order gets `checkout_id`; still one item per order.
- Server cart (`cart_items` per user; browser cart in localStorage until sign-in, then merged).
- Checkout: validate every item (rules from today's `create_checkout`), create one pending order per item in
  its own tenant transaction, one payment for the total.
- Webhook: store/verify as today, then fulfil **each order in its own tenant transaction**; allocate the
  gateway fee across orders (largest remainder); idempotent per order. Partial failure handling: if one
  tenant transaction fails, the payment stays recorded and the order is retried (no refunds triggered
  automatically).
Frontend: `/cart` grouped by teacher, sticky bar, `/checkout/<no>` (sign-in + phone verification here),
return page polling the checkout, receipts per checkout.
Tests: two teachers in one payment; fee allocation sums exactly; replayed webhook; one tenant failing.

### Phase 7 — Own video player **[M]**
Backend: play session returns a **signed HLS playlist URL** (Bunny Stream's pull zone with token auth,
short TTL) instead of the iframe embed; save progress (`lesson_progress.last_position_sec`, every 15 s).
Frontend: `VideoPlayer` with hls.js (native HLS on iOS), quality, speed, resume, data-saver cap, watermark
inside the fullscreen container (name + last 4 digits), reduced-motion support.
Needs a real Bunny library to verify.

### Phase 8 — Private admin app **[S]**
Done mostly in phase 1 (move). Add: deploy separately; API admin routes accept only the VPN range
(`PLATFORM_ALLOWED_CIDRS`, already built); new screens: teacher applications, subjects list, list/unlist,
users and devices.

### Phase 9 — Polish
Sinhala (if pilot teachers need it), Playwright suite at 360 px and desktop, performance budget check on a
real low-end Android phone, accessibility pass.

### Later (v1.1)
Company sites on subdomains (host resolution kept from today's code), email-domain verification, staff import.

---

## 4. Risks

- **Cross-tenant reads are the new security boundary.** Today every query is inside one tenant. User-scoped
  policies must be narrow and tested as hard as tenant isolation.
- **Checkout across tenants** splits one payment into several tenant transactions; the ledger must still
  book each payment portion exactly once and sum to the gateway amount.
- **Identity** brings passwords, email links and Google tokens: hashing, token expiry, rate limits and
  account-linking rules (same email via Google and password) need care.
- **Scope.** Phases 2–6 are each about the size of two of the original build steps. A pilot on the current
  subdomain design could run in parallel if timing matters (see section 5).

## 5. Alternative: pilot first, migrate after
The current build already covers one teacher end to end (catalogue, pay, watch, cash flow, payouts). If a
pilot teacher is waiting, a smaller path is: harden for the pilot (real SMS, PayHere sandbox check, Bunny
check, refunds, hosting) on one teacher's subdomain, then run phases 0–9 with real feedback.
