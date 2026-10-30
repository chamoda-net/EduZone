# EduZone — Project Guide

> Read this file before every task. It is the single source of truth for what EduZone is,
> what has been decided, and the rules the code must follow. `FRONTEND.md` is its companion for
> sites, screens, UX and the design system; backend contracts, money rules and schema live here.
> The database schema lives in `db/eduzone_v1_schema.sql`, which is authoritative for tables and columns.
>
> **Status (2026-10-30): migrating to the marketplace design.** Build steps 1-9 were built on the
> earlier one-subdomain-per-organization design. Rules below describe the **target**; paragraphs
> headed **Built (pre-migration)** describe today's code until its migration phase replaces it.
> The phases are in section 16 and `docs/frontend-migration-plan.md`.

---

## 1. What EduZone is

EduZone is a **multi-tenant learning marketplace** on `eduzone.switchops.tech`. Tuition teachers and
institutes (tenants) publish classes; students browse every approved teacher, buy months from several
teachers in **one cart and one payment**, and learn in one student area with **one account**.
Teachers have a marketable profile page (`/<subject>/<teacher>`), not their own theme. Later (v1.1),
companies get a private, fully white-label site on their own subdomain for staff training.

- **Owner:** SwitchOps Tech (Pvt) Ltd, Sri Lanka
- **Builder:** solo developer (Chamoda), assisted by Claude Code
- **Launch market:** Sri Lankan tuition teachers and institutes (O/L, A/L, Grade 5)
- **Later market:** companies running staff training (subscription-based, v1.1+)

### Kinds of user

| Surface | Who | Purpose |
|---|---|---|
| Marketplace | Everyone | Browse subjects, teachers, institutes and classes; add to cart |
| Student area (`/learn`) | Students (mostly on phones), one account across all teachers | Pay, watch, join Zoom, download tutes, receipts |
| Teacher console (`/teach/<tenant>`) | Teachers, institute owners and admins | Classes, months, lessons, media, students, payments, cash flow, profile |
| Platform admin | EduZone staff, private network only | Approve teachers, organizations, all money, payouts, Bunny usage |

---

## 2. Business decisions (settled)

| Topic | Decision |
|---|---|
| Domain | `eduzone.switchops.tech` (marketplace on one host); companies on `<company>.eduzone.switchops.tech` (v1.1) |
| First customer | Tuition teachers and institutes, on the marketplace |
| Teacher pages | `/<subject>/<teacher>`, one page per subject taught; **no teacher logo or colours** |
| Teacher onboarding | **Self-registration, then an application, then EduZone approval** before publishing or selling |
| Student account | **One account across all teachers.** Google or email + password; **unique mobile number, verified by SMS** |
| SMS OTP use | Only at registration (phone verification), on a **new device**, and for account recovery |
| Student membership | A student's `tenant_members` row is created **when they join or pay for a class** of that tenant |
| One-device rule | **Account-wide**: signing in on a new device signs out the older device |
| Teacher slug | Belongs to a **profile per person** (unique platform-wide), so one person has one page across institutes |
| Cart | Several teachers in **one checkout and one payment**; **one order per item** (as before), grouped under the checkout; the gateway fee is split across the orders |
| Revenue: individuals and institutes | EduZone takes a **commission per sale**, default **20%** (configurable per tenant) |
| Revenue: corporate (v1.1+) | Monthly subscription per organization; free to staff, no checkout |
| Who collects money | **EduZone collects all payments** through its own gateway account, then pays organizations out |
| Organization visibility | Full end-to-end cash flow: gross, gateway fees, EduZone commission, net, refunds, payouts, balance due |
| Payment methods | **Online gateway only.** No bank deposits or slip uploads. |
| Gateway | Sri Lankan gateway (PayHere or a bank IPG). Code must stay gateway-agnostic. |
| Pricing model | Monthly class fees (main), one-time courses, free classes |
| Late joiners | Students may buy **past months only if the teacher approves** the request |
| Institutes with many teachers | EduZone pays the **institute**. The institute pays its teachers itself, using EduZone's per-teacher earnings report. |
| Gateway fee bearer | Per-tenant setting, default `tenant`. **Pending final confirmation.** |
| Gateway fee timing | Book an **estimated** fee with the sale; true up with a `fee_settlement` posting from the settlement report |
| Past month | A month the teacher has **closed** (`class_months.status = 'closed'`); buying it needs an approved late request |
| Refunds on cash-flow page | Gross as sold, refunds as a separate line, commission and net shown after refunds |
| Video | **Bunny.net**: Bunny Stream for video (played in **our own hls.js player**), Bunny Storage for PDFs |
| Cost rule | No plan may let a tenant's Bunny cost exceed what EduZone earns from that tenant |
| Platform admin | Separate app, **private network (VPN) only**, two-factor sign-in |

Legal and regulatory review of "collecting on behalf of organizations" (CBSL rules, gateway
merchant terms, VAT, receipts) is in progress outside the codebase. Keep the money design
auditable so it can adapt.

---

## 3. Scope

### v1 (build now)
**Marketplace:** home, catalogue with filters, subject pages, teacher pages (with share link,
WhatsApp, QR), class pages, institutes, and the static pages the gateway requires.

**Student:** register (Google or email + password, phone verification), sign in (SMS only on a new
device), recover; a cart across teachers and one payment; request a past month and pay after approval;
Today, my classes, months, lessons (player, Zoom, tutes) **only for paid months**; schedule;
payments and printable receipts; profile.

**Teacher console:** application and approval status (draft mode until approved); classes, months,
lessons; media (Bunny); students paid / not paid; late-month inbox; manual access (scholarships, free);
payments; cash flow; per-teacher earnings (institutes); team invites (institutes); public profile
editor with share tools; payout details.

**Platform admin (private):** teacher applications; organizations (suspend, list or unlist); subjects;
checkouts and payments; balances and payouts; Bunny usage; users and devices; audit log.

**Foundations:** multi-tenancy everywhere (section 5), the ledger for all money (section 7),
content protection (section 10).

### v1.1 (later; do not build unless asked)
- Company sites: a subdomain per company, own branding, email-domain verification (DNS TXT), staff import,
  departments, assigned courses, due dates, completion reports, subscriptions
- Custom domains for companies
- Tamil UI (Sinhala at the pilot if the pilot teachers need it)

### Out of scope for now
Own video-calling system, mobile native apps, affiliate programs, SCORM/LTI, AI features, bank slip payments.

---

## 4. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12+, **FastAPI**, Pydantic v2 |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic |
| Database | **PostgreSQL 16+** with Row-Level Security |
| Frontend | **Next.js** (App Router) + TypeScript + Tailwind; mobile-first. Monorepo `apps/web`, `apps/admin`, `packages/ui`, `packages/api-client` (see `FRONTEND.md`) |
| Background jobs | Redis + a worker (ARQ or Celery). Add only when a feature needs it (webhooks retries, emails, Bunny usage sync). |
| Video | Bunny Stream (one library per tenant) |
| Files | Bunny Storage |
| SMS / OTP | Sri Lankan SMS provider (TBD) behind an interface |
| Email | Transactional email provider (TBD) behind an interface: verification and recovery links |
| Sign-in with Google | Google OAuth / OpenID Connect client (to be created) |
| Hosting | One backend app + the public web app + Postgres + Redis; the admin app on the private network. **No microservices.** |

Architecture: **modular monolith**. One FastAPI app, split by domain modules.

### Suggested repository layout
```
eduzone/
├── CLAUDE.md
├── db/
│   └── eduzone_v1_schema.sql        # authoritative schema
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                    # config, security, db session, tenant context
│   │   ├── modules/
│   │   │   ├── auth/                # OTP, sessions, JWT
│   │   │   ├── tenants/
│   │   │   ├── members/
│   │   │   ├── catalog/             # classes, months, lessons, resources
│   │   │   ├── media/               # Bunny Stream / Storage
│   │   │   ├── enrollment/          # enrollments, late requests, access grants
│   │   │   ├── checkout/            # orders, payments, refunds, gateway adapters
│   │   │   ├── ledger/              # posting rules + cash-flow queries
│   │   │   ├── payouts/
│   │   │   └── platform_admin/
│   │   └── integrations/
│   │       ├── gateways/            # payhere.py, bank_ipg.py (one interface)
│   │       ├── bunny/
│   │       └── sms/
│   ├── migrations/                  # Alembic
│   └── tests/
└── frontend/                     # npm workspaces
    ├── apps/web/                    # public site, student area, organization console (port 3000)
    ├── apps/admin/                  # platform admin, private network only (port 3001)
    ├── packages/ui/                 # components + design tokens (tokens.css)
    ├── packages/lib/                # format, i18n (next-intl), shared types
    ├── packages/api-client/         # types generated from the API's OpenAPI document
    └── e2e/                         # Playwright smoke suite
```
Each module has `router.py`, `schemas.py` (Pydantic), `service.py` (business logic),
`repository.py` (DB access). Routers stay thin; rules live in services.

### Local development
- `.env` (copied from `.env.example`) at the repo root feeds both `docker-compose.yml` and the backend.
- Three DB roles, three URLs: `DATABASE_URL` (`eduzone_app`, asyncpg), `ADMIN_DATABASE_URL`
  (`eduzone_admin`, asyncpg), `MIGRATION_DATABASE_URL` (`eduzone_owner`, psycopg, Alembic only).
  `docker/postgres/init-roles.sh` creates the two runtime roles with passwords on first start.
- The database must use **UTF-8** encoding (Sinhala and Tamil text). The Docker image does by default.
- Migrations are hand-written SQL (no autogenerate: RLS, triggers and `SECURITY DEFINER`
  functions can't be expressed by it). `0001` runs `backend/migrations/sql/0001_baseline.sql`,
  a **frozen** copy of `db/eduzone_v1_schema.sql`; never edit it, add a new migration instead.

```bash
docker compose up -d
cd backend && python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/alembic upgrade head
.venv/Scripts/pytest
.venv/Scripts/uvicorn app.main:app --reload
```
(`.venv/bin/` instead of `.venv/Scripts/` on macOS/Linux.)

---

## 5. Multi-tenancy rules (non-negotiable)

1. **Every business table has `tenant_id`.** Platform-level tables (`tenants`, `users`,
   `otp_codes`, `gateway_webhook_events`, `platform_admin_sessions`, `platform_admins`, the identity tables
   `user_sessions`, `user_devices`, `user_identities`, `email_verifications`, `recovery_tokens`,
   `login_attempts`, and the planned `subjects`, `teacher_profiles`, `teacher_applications`, `checkouts`,
   `checkout_payments` and `cart_items`) are the only exceptions.
2. **How a request finds its tenant (target):**
   - **Teacher console** `/teach/<tenant>/...`: tenant slug from the path, `resolve_tenant(slug)`, then a
     **membership check** (active staff member of that tenant), then the tenant transaction.
   - **Class pages and their actions** (`/<subject>/<teacher>/<class>`): the class's own tenant, found from its
     public identifiers; any write (join, request, checkout item) runs in that tenant's transaction.
   - **Company sites (v1.1):** host to company tenant, as built today.
   - Unknown, non-active or (for public pages) unlisted or unapproved tenant: 404.

   **Built (phase 3):** `current_tenant()` takes the `{tenant_slug}` path parameter when the route has one
   (the console at `/api/v1/teach/{tenant_slug}/...`), else the host (`X-Forwarded-Host` or `Host`,
   `<slug>.<base>`, still used by the pre-migration tenant sites and the same staff routes under `/org`).
   The membership check is `StaffActor` (owner/admin/teacher of that tenant). Student routes under
   `/api/v1/learn/...` name a class/month/lesson/resource/order by id; `resolve_entity_tenant(kind, id)`
   (SECURITY DEFINER, active tenants only) finds its tenant and the request runs in that tenant's
   transaction with the user's member row there (`learn/service.py: in_tenant_of`). The main host
   (`BASE_DOMAIN` itself) serves `/learn`, `/teach` and sign-in; `site_url()` accepts it for email links.
3. **Every tenant request runs in a DB transaction that begins with**
   `SET LOCAL app.tenant_id = '<tenant uuid>'`. Without it, RLS returns zero rows.
   In code (`app/core/tenancy.py`): routes take `session: TenantSession`; services and jobs use
   `tenant_transaction(tenant_id)`. It commits before the response is sent and rolls back on any error.
4. **User-scoped reads (built, phase 3, migration 0006).** The student area, cart and payment history span
   many tenants. They run in `user_transaction(user_id)` (`SET LOCAL app.user_id`, no tenant) where extra
   **SELECT-only** RLS policies show only the signed-in user's own rows: their `tenant_members` rows and those
   tenants, enrollments, grants, late requests, progress, orders, order items and payments. Catalogue tables
   (classes, months, lessons) have no user policy: anything about a class runs in that class's tenant
   transaction. Writes always happen inside the tenant transaction. Never set `app.user_id` and
   `app.tenant_id` in the same transaction. `tests/test_learn.py` holds the user isolation tests.
5. **Public marketplace reads** go through **one narrow read path** (a `SECURITY DEFINER` function set or
   an admin-owned view) exposing public fields of listed, approved tenants and published classes only.
   Never by relaxing tenant RLS.
6. **Never accept `tenant_id` or `user_id` from the client.** They come from the resolved path or the session.
7. The app connects as role **`eduzone_app`** (subject to RLS). Platform admin endpoints and
   background jobs use **`eduzone_admin`** (BYPASSRLS) through a separate session factory.
   Never use `eduzone_admin` for tenant- or student-facing endpoints.
8. Cross-tenant links are blocked by **composite foreign keys** `(tenant_id, id)`.
   New tables referencing tenant data must follow the same pattern. Rows that carry both
   `class_id` and `class_month_id` use `(tenant_id, class_id, class_month_id)` so the month
   must belong to that class.
   Gateway webhooks arrive without a tenant: find it with `resolve_payment_tenant(gateway, idempotency_key)`
   (target: the checkout, then each order's tenant), then run normal tenant transactions.
   New `eduzone_app` grants are given explicitly in each migration; money tables and
   `audit_logs` never get DELETE.
9. A user is global; their role is per tenant (`tenant_members`). Authorization always checks
   the member row for the current tenant, never a global role.
10. Tests must include an isolation test for every new tenant-scoped table.
    `tests/test_isolation.py` already fails if any table with `tenant_id` lacks a forced RLS
    policy; add behavioural read/write tests for a table when a module starts using it
    (the `seed` fixture in `tests/conftest.py` gives two active tenants and a suspended one).

---

## 6. Data model overview

Full definitions are in `db/eduzone_v1_schema.sql`. Summary:

```
tenants ─┬─ tenant_members (role: owner/admin/teacher/student) ── users (global)
         │
         ├─ classes (teacher_member_id, pricing_model, monthly_fee_cents)
         │    └─ class_months (month_start, fee override)
         │         └─ lessons (live / recorded / document, zoom_join_url)
         │              └─ lesson_resources ── media_assets (Bunny video / PDF)
         │
         ├─ class_enrollments          student joined a class
         ├─ late_month_requests        pending → approved/rejected → fulfilled
         ├─ access_grants              THE access table (per month or per class)
         ├─ lesson_progress            view count, position, completion
         │
         ├─ orders ── order_items (teacher + commission snapshot)
         │     └─ payments ── refunds
         ├─ payouts
         ├─ ledger_transactions ── ledger_entries   (append-only, balanced)
         │
         ├─ user_sessions              device sessions, one-device rule
         ├─ tenant_usage_daily         Bunny storage / bandwidth per day
         └─ audit_logs
```

**Planned for the marketplace** (added by the migration phases and mirrored in the schema file as they land):
- Identity (phase 2, **built**, migration 0005): `user_identities` (Google), `email_verifications`,
  `recovery_tokens` (hashed, expiring), `user_devices` (trusted devices), `login_attempts`, profile columns
  on `users`; `user_sessions` lost `tenant_id` (sessions are per user).
- Marketplace (phase 4): `subjects` (EduZone-managed slugs), `classes.subject_id`, `teacher_profiles`
  (slug unique platform-wide, photo, headline, bio, highlights), `tenants.is_listed`.
- Onboarding (phase 5): `teacher_applications` (document in private storage); new tenants start `pending`.
- Cart (phase 6): `cart_items` (per user), `checkouts` and `checkout_payments` (platform-level: one
  payment for many orders); `orders.checkout_id`.

**Views** (RLS-aware, `security_invoker`):
- `v_tenant_cashflow_monthly`: gross (as sold), refunds (own line), gateway fees (incl. true-ups),
  commission and net (both **after** refunds), paid out. UI labels must say "after refunds".
- `v_tenant_balance`: what EduZone owes the tenant now
- `v_teacher_earnings_monthly`: per-teacher net (for institutes)

### Access rule (one function, used everywhere)
A student can open a lesson if **any** of these is true:
- `lesson.is_free_preview` and the lesson is published
- Monthly class: an active `access_grants` row exists for `(student, lesson.class_month_id)`
- One-time / free class: an active `access_grants` row exists for `(student, class_id)` with `class_month_id IS NULL`

Active means `revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())`.
Zoom links and video playback URLs are returned **only** after this check passes.

### How it's built (step 6: `app/modules/learning`)
- **The rule lives only in `learning/access.py`** (`LESSON_UNLOCKED` SQL, `lesson_for_student`,
  `class_lessons_for_student`, `active_grant_for`). Students also never see unpublished lessons or
  draft classes. Archived classes stay visible to students who still hold a grant in them.
- **Public** (`/api/v1/public/classes[/{slug}]`): published classes, months with effective fee,
  published lesson outlines. Never Zoom links, descriptions of locked lessons, or media.
- **Student** (`/api/v1/student/...` on a tenant host; the same actions by id under `/api/v1/learn/...` since phase 3):
  `GET classes` (mine), `GET classes/{slug}` (per-month `access`: granted | buy | upcoming | request |
  pending | approved | rejected | unavailable), `POST/DELETE classes/{slug}/enroll` (joining a free
  class creates its `free` grant; leaving keeps access), `POST months/{id}/late-request` (enrolled,
  closed month, class allows it, one request per month: a rejected one can't be repeated),
  `GET lessons/{id}`, `POST resources/{id}/open` (access check → +1 view for videos, atomically refused
  at `classes.max_video_views` → signed URL + watermark identity).
- **Org** (`/api/v1/org/...`): `GET classes/{id}/students?month_id=` (joined or granted students with
  access for that month), `POST classes/{id}/grants` (manual | scholarship; also enrols),
  `POST grants/{id}/revoke` (never `purchase` grants: those go through refunds),
  `GET late-requests?status=`, `POST late-requests/{id}/decision` (approve | reject; only the class's
  teacher or an owner/admin). Approval lets the student pay (step 7 marks it `fulfilled`).
- **Frontend:** `/` is the public catalogue, `/classes/[slug]` the class page (public or personal),
  `/my`, `/lessons/[id]` (Zoom button, watermarked player that drifts name + phone over the video,
  PDF opener), and in the console a Students card on each class plus `/org/requests`.
- PDFs are protected only by short-lived signed URLs; once opened they can be saved. `is_downloadable`
  is advisory for now.

---

## 7. Money rules (non-negotiable)

1. **All money is `BIGINT` cents.** LKR 2,000.00 = `200000`. No floats, no `Decimal` in the DB.
   Python uses `int` for cents.
2. **Rates are basis points.** 2000 = 20.00%.
3. **Rounding:** `commission = (amount_cents * commission_bps + 5000) // 10000` (round half up).
4. `order_items` **snapshots** `commission_bps` and `teacher_member_id` at purchase time.
   Changing a tenant's rate never changes history.
5. **The ledger is the source of truth** for cash flow. Never compute balances from
   `orders` or `payments`.
6. **Ledger is append-only.** No UPDATE/DELETE (DB triggers block it). Corrections are new
   `adjustment` transactions.
7. **Every ledger transaction must sum to zero.** Enforced by a deferred DB trigger.
8. Each payment, refund, and payout is booked **exactly once** (unique indexes).
9. Sign convention: positive = debit, negative = credit.

### Accounts
| Account | Meaning |
|---|---|
| `gateway_clearing` | Money held at / settled from the gateway (EduZone asset) |
| `gateway_fees` | Gateway charges (expense) |
| `platform_commission` | EduZone revenue |
| `tenant_payable` | What EduZone owes the organization (per tenant) |
| `bank` | EduZone bank account |

### Posting: successful sale
Let `G` = gross, `F` = gateway fee, `C` = commission on `G`.
Post per order item where possible, and set `teacher_member_id` on `tenant_payable` entries.

| Account | Fee borne by platform | Fee borne by tenant (default) |
|---|---|---|
| gateway_clearing | `+(G − F)` | `+(G − F)` |
| gateway_fees | `+F` | `+F`, then `−F` |
| platform_commission | `−C` | `−C` |
| tenant_payable | `−(G − C)` | `−(G − C)`, then `+F` |

Worked example (tested): G = 200000, F = 6000, C = 40000, tenant bears fee → tenant net **154000**.

`F` at sale time is an **estimate**: `(G * fee_estimate_bps + 5000) // 10000`, with the rate
configured per gateway in app config (not in the DB). Store it in `payments.gateway_fee_cents`.

### Posting: fee settlement (true-up)
When the gateway's settlement report gives the actual fee `A`, let `D = A − F`. If `D ≠ 0`,
post one `fee_settlement` transaction for that payment (unique per payment):
`gateway_fees +D`, `gateway_clearing −D`; if the tenant bears the fee, also
`tenant_payable +D`, `gateway_fees −D` (with `teacher_member_id` set). `D` may be negative.

### Posting: refund (reverse proportionally)
`tenant_payable +` tenant's share, `platform_commission +` commission share,
`gateway_clearing −` amount refunded. Gateway fees are usually not returned by the gateway,
so who absorbs them follows `gateway_fee_bearer`.

### Posting: payout
`tenant_payable +X`, `bank −X`, linked to a `payouts` row. Created only by platform admin.

### Reports (step 8: `app/modules/ledger/service.py`, read-only, ledger only)
- `GET /api/v1/org/cashflow?from=YYYY-MM&to=YYYY-MM` (default: last 12 months, max 36): every month in
  the range (zeros included, Colombo calendar months) from `v_tenant_cashflow_monthly`, range totals, and
  `balance_due_cents` from `v_tenant_balance` (all time). **Owners and admins only** (403 for teachers).
- `GET /api/v1/org/earnings?month=YYYY-MM` (default: this month): per teacher, from ledger entries joined
  to their order item's teacher: payments count, gross, refunds, commission, net. Owners/admins see every
  teacher; a teacher sees only their own line.
- Console: `/org/money` (balance due, range presets, totals, monthly table; cards on phones) and
  `/org/earnings` (month by month). The "Money" nav item shows for owners and admins only.
- When EduZone bears gateway fees, the fees line is labelled as paid by EduZone and doesn't reduce net.

---

## 8. Payment flow

**Target (phase 6): one cart and one payment across teachers.** The cart holds items from several
teachers. Checkout creates one `checkouts` row and, for each item, a `pending` order with exactly one item
**in that item's tenant** (the rules below apply per item), then **one** `checkout_payments` attempt for the
total. The webhook stores and verifies as below, then fulfils **each order in its own tenant transaction**
(grant, late request, ledger sale). The gateway fee is allocated across the orders by largest remainder so
it sums exactly; each order is booked once; a failed tenant transaction is retried, never auto-refunded.
The steps below describe one order and stay true for each order of a checkout.

1. Student clicks **Pay** → create `orders` (`pending`) + **exactly one** `order_items` row
   (v1 rule, enforced in the service: one month or one course per order).
   - A month is buyable directly while `class_months.status = 'open'`. Once the teacher sets it
     to `closed`, it is a past month: require an `approved` `late_month_requests` row and link it
     on the item. `upcoming` months are not buyable yet.
   - Reject if the student already has an active grant for that month or class.
2. Create `payments` (`initiated`) with a unique `idempotency_key`; redirect to the gateway.
3. Gateway calls our **webhook / notify URL**:
   - Store the raw payload in `gateway_webhook_events` **first** (unique `(gateway, event_ref)`).
   - Verify the signature. If invalid, mark it and stop.
   - Verify amount and currency match the order exactly.
4. In **one DB transaction**: payment `succeeded` → order `paid` → `access_grants`
   (`source = 'purchase'`) → late request `fulfilled` → ledger `sale` posting.
5. The browser return URL **never** grants access. It only shows status by polling the order.
6. Webhooks may arrive twice or out of order; processing must be idempotent.

Gateway integration sits behind one interface in `integrations/gateways/`:
`create_checkout(order) -> redirect`, `verify_webhook(request) -> GatewayEvent`,
`refund(payment, amount) -> result`. Never store card numbers; `card_last4` only.

### How it's built (step 7: `app/modules/checkout`, `app/modules/ledger`, `app/integrations/gateways`)
- **Gateways:** `get_gateway()` returns `PayHereGateway` (checkout form + MD5 hash, notify verification;
  re-check the formulas against the PayHere sandbox before launch) or `FakeGateway` (local only: a page at
  `/api/v1/dev/fake-gateway/<key>` with Pay / Card declined / Cancel that posts a signed notification).
  `refund()` is not implemented yet. Settings: `PAYMENT_GATEWAY`, `PAYHERE_*`, `GATEWAY_FEE_ESTIMATE_BPS`,
  `API_PUBLIC_URL` (notify URL base), `SITE_SCHEME` (return URL scheme).
- **Checkout** (`POST /api/v1/student/checkout {class_id, class_month_id?}`): checks the rules above,
  enrols the student, creates order + one item (commission and teacher snapshot) + payment with a random
  `idempotency_key` (sent to the gateway as its order id), and returns `{order, redirect}`; the browser
  posts the redirect form. `GET /student/orders[/{id}]` (history excludes pending; the return page polls),
  `GET /org/orders` (teachers: their classes only).
- **Webhook** (`POST /api/v1/webhooks/{payhere|fake}`, form-encoded): `process_notification` stores the raw
  event (repeat = `duplicate`), rejects a bad signature with 400 (row kept, `process_error` set), finds the
  tenant with `resolve_payment_tenant`, then `_apply` in one tenant transaction. Success after failure wins;
  failure after success is ignored; amount/currency mismatch leaves the order pending. Paying twice for the
  same access books the money but adds no second grant (logged: needs a refund).
- **Ledger** (`ledger/posting.py`): pure entry builders `sale_entries`, `fee_settlement_entries`,
  `refund_entries`, `payout_entries` + `post()` (refuses unbalanced input). `checkout.service.settle_fee()`
  books the true-up (platform admin / reconciliation job, step 9). Tests: `test_ledger.py`, `test_checkout.py`.
- **Frontend:** Pay buttons on the class page (months marked buy/approved, one-time classes),
  `/checkout/[id]` (return page polling the order), `/payments` + `/payments/[id]` (printable receipt),
  console `/org/payments`.
- **Test cleanup:** `purge_tenants()` in `tests/conftest.py` deletes test tenants as the schema owner with
  triggers paused (the ledger is append-only even for `eduzone_admin`). Test databases only.
- Open: refunds (gateway API + refund flow), PayHere needs an email (phone-only students have none),
  receipts wording pending the legal review of collecting on behalf of organizations.

---

## 9. Video, files, and cost control (Bunny)

- **One Bunny Stream library per tenant** (`tenants.bunny_library_id`). Library API keys
  live in the **secret manager / env**, never in the DB or in logs.
- **Upload:** the browser uploads directly to Bunny (TUS) using a short-lived signature from
  our API; we create `media_assets` (`uploading`) first. Bunny's webhook updates the status to
  `processing` → `ready` / `failed` and records duration and size.
- **Playback:** issue **token-authenticated, short-lived** URLs only after the access check. Target (phase 7):
  a signed **HLS playlist** URL for our own hls.js player (not Bunny's iframe); progress saved every 15 s.
- **PDFs** go to Bunny Storage under `/<tenant_id>/...` and are served through signed URLs.
- **Usage sync:** a daily job pulls storage and bandwidth per library into `tenant_usage_daily`.
- **Limits:** `storage_limit_bytes` (blocks new uploads when reached) and
  `bandwidth_limit_bytes` per month (warn at 80%; action at 100% is a business decision,
  so default to warn plus notify the platform admin).
- Bunny pricing must be checked before plan limits are set. Plan rule: a tenant's maximum Bunny
  cost must stay below EduZone's expected earnings from that tenant.

### How it's built (step 5: `app/integrations/bunny`, `app/modules/media`)
- **Keys from env only:** `BUNNY_STREAM_LIBRARIES` (JSON `{"<library_id>": {"api_key", "token_key"}}`),
  `BUNNY_STORAGE_*`, `BUNNY_CDN_*`, `BUNNY_WEBHOOK_TOKEN`. Missing config → 503 `MEDIA_NOT_CONFIGURED`.
  Setting `tenants.bunny_library_id` (platform admin, step 9; by SQL until then) enables video for a tenant.
- **Video upload:** `POST /org/media/videos` creates the Bunny video + a `media_assets` row (`uploading`)
  and returns a TUS endpoint and signed headers (valid 12 h); the browser uploads with tus-js-client.
- **Status:** never trust the webhook payload: `POST /webhooks/bunny/stream?token=…` only says which video
  changed, and we re-read it from Bunny (`resolve_bunny_library_tenant()` finds the tenant, migration 0003).
  `GET /org/media/{id}` also syncs a pending video, which covers missed webhooks and local dev.
- **PDFs:** `POST /org/media/documents` (multipart, `%PDF-` check, 50 MB) → Bunny Storage at
  `<tenant_id>/documents/<asset_id>/<safe-name>.pdf`, sent with a SHA-256 checksum.
- **Quota:** sum of non-deleted, non-failed `media_assets.size_bytes` vs `storage_limit_bytes` (409 `STORAGE_LIMIT_REACHED`).
- **Signed URLs:** `signing.embed_url` (Stream embed token, 4 h) and `signing.cdn_url` (pull zone token,
  10 min). `media.service.signed_url()` is what student playback (step 6) calls after the access check.
- **Lesson files:** `lesson_resources`; videos only on live/recorded lessons, never downloadable.
  Media in use can't be deleted; deleting removes it at Bunny and marks the row `deleted`.
- Teachers see the files they uploaded; owners/admins see all (same rule as classes).
- Tests use `FakeBunny` (httpx MockTransport) in `tests/test_media.py`; no Bunny account needed.
  **Re-check the signature formulas and video status codes against a real Bunny library before launch.**
- Not built yet: the daily usage sync into `tenant_usage_daily` and bandwidth warnings (with step 9).

---

## 10. Content protection (v1)

- **One active device per account:** signing in on a new device (after its SMS code) signs out
  the older device, which then explains why. Staff of any organization are exempt (built, phase 2).
- **Watermark** inside our player container (visible in fullscreen): the student's name and the last
  4 digits of their phone, repositioning about every 20 s.
- **Short-lived signed video URLs**; never expose permanent Bunny URLs.
- **View limit:** `classes.max_video_views`; increment `lesson_progress.view_count` when a
  play session starts. Block when the limit is reached.
- Zoom links are hidden until the access check passes.

---

## 11. Auth

**Target (phase 2):**
- Sign-in with **Google** (ID token verified server-side) or **email + password** (strong hash; email
  verified by link). One account per person across all tenants.
- **Phone:** required and **unique**, verified once by SMS OTP (E.164, local forms accepted). SMS OTP is also
  used for a **new device** and for **recovery** (email link + SMS). OTP rules stay: only `code_hash` stored,
  short expiry, attempt lock, rate limits per number and IP.
- Short-lived access JWT (`user_id`, session) + refresh token stored **hashed**; sessions are per user.
  Console requests add a **membership check** for the tenant in the path on every request.
- People may browse and fill a cart without an account; registration and phone verification happen at checkout.

**Built (phase 2)** in `app/modules/auth` (routes under `/api/v1/auth`; migration 0005):
- **Accounts are global.** Access JWTs carry only `sub` (user) and `sid` (session); sessions
  (`user_sessions`) are per account. `CurrentUser` checks the session row on **every** request.
  `CurrentMember` adds the member row for the tenant of the request (today: the host) on every request:
  `member_id`/`role` are None until the student joins or pays there (`ensure_student_member()` in the
  enroll, checkout and open-file paths creates it). Suspended members get 403 on that tenant only.
  `StaffActor` requires owner/admin/teacher membership in that tenant.
- `POST /register` (email, password of 8+ characters, name, device) signs in, trusts the device and emails a
  verification link. `POST /login` returns `{status: signed_in, tokens}` or, on an unknown device of an
  account with a verified phone, `{status: device_check, device_check: {challenge, phone_hint}}` and sends an
  SMS code; then `POST /device/verify` (the challenge is a 10-minute signed JWT bound to that device) or
  `POST /device/resend`. A wrong password and an unknown email give the same `LOGIN_INVALID`; failures are
  throttled per email and per IP (`login_attempts`). Passwords: argon2id (`passwords.py`).
- **One device per account:** every sign-in revokes the account's other sessions with reason
  `signed_in_on_another_device` (the old device then gets `SIGNED_IN_ELSEWHERE`), except for staff of any
  tenant (`user_is_staff_anywhere()`, SECURITY DEFINER).
- **Phone** (`POST /phone/request`, `/phone/verify`): unique (`PHONE_IN_USE` 409), verified once; the device
  that verified it becomes trusted. **Checkout requires a verified phone** (`PHONE_NOT_VERIFIED` 403).
- **Email:** `POST /email/verify {token}`, `POST /email/resend`. **Recovery:** `POST /recovery/request`
  (always 202) emails a link `/recover/<token>` (30 min, single use); `POST /recovery/start` sends an SMS code
  when the account has a verified phone; `POST /recovery/complete` sets the password, signs out everywhere
  and signs in on this device. Organization owners created by the platform admin start with no password and
  set one this way.
- **Google** (`POST /google {id_token}`): verified against Google's keys (`google.py`, `GOOGLE_CLIENT_ID`;
  unset gives 503 `GOOGLE_NOT_CONFIGURED`). Links by subject, else by verified email; an existing account
  whose email was never verified loses its password and sessions when the real owner arrives with Google.
- `GET/PATCH /me` (profile: name, language, exam, exam year, school; plus membership here).
- **Email links are built from the request's host only on routes that resolve a tenant** (register,
  resend, recovery request), so a forged Host header can't put someone else's domain into our emails.
- SMS codes for every purpose go through `auth/otp.py` (`issue`/`consume`; hashed with the purpose; 60 s
  resend cooldown, 5 per number per hour, 20 per IP per hour, 5 wrong guesses lock a code).
- SMS: `app.integrations.sms`; email: `app.integrations.email`. Both `console` (log) or `file` (JSON lines at
  `SMS_OUTBOX_PATH` / `EMAIL_OUTBOX_PATH`, `ENVIRONMENT=local` only, for browser tests).
- Phone input accepts local forms (`0771234567`, `94771234567`) and is normalised to E.164.
- `client_ip()` uses the direct peer address; behind a proxy or CDN it must read the trusted
  forwarded header instead.
- Platform admins (`users.is_platform_admin`) use a separate login path and session
  (`platform_admin_sessions`, via `eduzone_admin`). `eduzone_app` cannot write `is_platform_admin`.

### Platform admin (step 9: `app/modules/platform`)
- **Create an admin:** `python scripts/create_platform_admin.py --phone … --name …` (sets
  `is_platform_admin`, stores a TOTP secret in `platform_admins` (migration 0004, no `eduzone_app` grant),
  prints the authenticator setup link once, and ends that admin's sessions). Running it again issues a new secret.
- **Sign-in** (`/api/v1/platform/auth/...`): `otp/request` (same 202 for everyone; SMS only to real admins)
  → `login {phone, code, totp}` (SMS code checked first so guesses are counted; then the authenticator code,
  one-time per 30 s step; one error message for any failure) → tokens with `typ: "platform"` (never accepted by
  tenant routes, and tenant tokens never by platform routes). Access 15 min; session 12 h, not extended by refresh.
- **Network allowlist:** `PLATFORM_ALLOWED_CIDRS` (e.g. the VPN range). Empty is allowed only with
  `ENVIRONMENT=local`; otherwise every platform route is a 404.
- **Endpoints** (each takes `Admin` + `AdminTx`, an `eduzone_admin` transaction): `GET/POST /tenants`
  (create with owner: existing users keep their name; reserved slugs refused), `GET/PATCH /tenants/{id}`
  (status, commission, fee bearer, branding colour, Bunny library, limits, payout bank display fields),
  `GET/POST /tenants/{id}/payouts` (records money already sent: `payouts` row `sent` + ledger payout posting,
  refused above the balance due), `GET /payments` (all organizations, cursor). Every change writes `audit_logs`
  (`platform.*`); tenant-scoped rows set `app.tenant_id` in the admin transaction first.
- **Usage:** tenant rows show storage (from `media_assets`) and this month's bandwidth from
  `tenant_usage_daily`. The daily Bunny usage sync job is **not built yet** (needs Bunny's account API).
- **New organizations** are created with the owner's **email** (`owner_email`); a new owner sets a password
  with "Forgot password" on the site and verifies their phone on first sign-in.
- **Frontend:** its own Next app, `frontend/apps/admin` (port 3001, private network, `noindex`), with its own
  cookies (`ez_padmin_*`, `SameSite=Strict`) and token refresh in its `proxy.ts`. Pages: `/login`,
  `/` (organizations), `/tenants/new`, `/tenants/[id]` (figures, record payout, history, edit), `/payments`.
  It calls only `/api/v1/platform/...` and sends no tenant host.

---

## 12. API conventions

- REST, JSON, prefix `/api/v1`.
- Route groups (target): `/api/v1/public/...` (marketplace), `/api/v1/auth/...`, `/api/v1/me/...`
  (the signed-in user across tenants: learn area, cart, checkouts, payments), `/api/v1/teach/{tenant}/...`
  (console, membership-checked), `/api/v1/platform/...`, `/api/v1/webhooks/...`.
  **Built (phase 3):** `/learn/...` (student area, any host), `/teach/{tenant_slug}/...` (console); the
  pre-migration `/student/...`, `/org/...` and `/public/...` still work on tenant hosts until phase 4.
- Money in API payloads: integer cents plus `currency`. The frontend formats for display.
- Dates: ISO 8601 UTC in the API; display in `Asia/Colombo`.
- Pagination: cursor-based for long lists (`limit`, `cursor`).
- Errors: `{ "error": { "code": "ACCESS_DENIED", "message": "..." } }`.
- Every state-changing org/platform action writes an `audit_logs` row.

### How the code follows these (from step 4)
- **Staff routes** take `actor: StaffActor` (owner/admin/teacher, else 403) plus `session: TenantSession`.
  `actor.manages_all` is true for owners and admins; a teacher manages only classes they teach.
  Anything the caller may not manage is a **404**, never a 403, so its existence doesn't leak.
- **Audit:** services call `app.core.audit.write_audit` in the same transaction as the change.
- **Pagination:** `app.core.pagination` (opaque cursor over `created_at DESC, id DESC`, limit 1–100,
  response `{items, next_cursor}`).
- **Partial updates (PATCH):** only fields sent are applied; fields in `non_nullable` may be
  omitted but not set to null; unknown fields are 422.
- **ORM models** (`app/modules/*/models.py`) map existing tables only; migrations stay hand-written SQL.
- **Deletes** that hit a foreign key return 409 `IN_USE` (run inside a savepoint).

### Catalogue rules (`/api/v1/org`, step 4)
- Classes: `GET/POST /classes`, `GET/PATCH/DELETE /classes/{id}`. Slug is generated from the
  title when omitted (409 `SLUG_TAKEN` on clash). Status flow: draft → published/archived,
  published → archived, archived → published; never back to draft. `pricing_model` can change
  only on a draft class with no months or lessons. Only draft classes can be deleted.
  Only owners/admins assign or reassign the teacher, who must be active staff of the tenant.
- Months (monthly classes only): `GET/POST /classes/{id}/months`, `PATCH/DELETE /months/{id}`.
  `month_start` is the 1st of a month; `fee_cents` NULL means the class fee (`effective_fee_cents`
  in responses). A month with lessons can't be deleted.
- Lessons: `GET/POST /classes/{id}/lessons` (`?month_id=`), `PATCH/DELETE /lessons/{id}`.
  Monthly-class lessons need a month of that class; others must have none. Live lessons need
  `scheduled_at` (with time zone); only live lessons may have a Zoom link (https only).

---

## 13. Frontend notes

**`FRONTEND.md` is the frontend spec** (sites, routes, screens, UX principles, design tokens, player,
performance budget, SEO). Constants that stay true: mobile-first, all text through i18n keys, money shown
as `Rs. 2,000.00`, dates in `Asia/Colombo`, backend calls only from the Next server (BFF), tokens only in
httpOnly cookies.

### Built (pre-migration): the frontend today (`frontend/`, Next.js 16, App Router)
- **Monorepo** (npm workspaces, phase 1): `apps/web` (everything tenant-facing), `apps/admin` (platform
  admin), `packages/ui` (components, `tokens.css`), `packages/lib` (`format`, `i18n`, `types`, `orders`),
  `packages/api-client`. Apps import `@eduzone/ui`, `@eduzone/lib/<module>`, `@eduzone/api-client`
  (listed in `transpilePackages`); `@/` stays app-local (`lib/api.ts`, `lib/cookies.ts`, `lib/session.ts`).
- Read `frontend/apps/web/AGENTS.md` first: Next 16 differs from older versions (e.g. `proxy.ts`
  replaces middleware). Its docs ship in `frontend/node_modules/next/dist/docs/`.
- **Design system** (FRONTEND.md section 9): forest green brand, gold accents, ivory paper; Fraunces
  headings (`font-display`), Instrument Sans text, Noto Sans Sinhala. Colours, radii and shadows come only
  from `--ez-*` in `packages/ui/src/tokens.css` via Tailwind names (`brand`, `gold`, `sunken`, `muted`,
  `border-strong`, status `success|warning|danger|info` + `-bg`, `rounded-ez*`, `shadow-ez*`). No raw palette
  classes, no dark mode, no tenant colours (a tenant's `primary_color` is no longer applied).
- **Building screens:** use the kit in `@eduzone/ui` (Button/`buttonStyles`, Field, Card, PageHeader,
  EmptyState for every empty list, StatusPill for access states, ClassCover for class imagery, Skeleton in
  `loading.tsx`), the student frame `components/shell.tsx` (`SiteShell`; `bare` for full-bleed pages) and
  `ConsoleFrame` for consoles. Custom CSS helpers go in tokens.css inside `@layer components`, so Tailwind
  utilities still override them. Review new components on the dev-only `/design` page.
  If new classes don't show up in `next dev`, stop it and delete the app's `.next` (stale Turbopack cache).
- **Backend calls happen only on the Next server** (`lib/api.ts`: Server Components and Server
  Actions), sending `X-Forwarded-Host` with the user's host. The browser never calls the API.
- **Tokens live in httpOnly cookies** (`lib/cookies.ts`: `ez_session`, `ez_refresh`, `ez_device`, prefixed
  `__Host-` in production); browser JavaScript never sees them.
  `proxy.ts` refreshes the access token shortly before it expires and drops dead sessions.
  A per-browser `ez_device` cookie is the `device_id` for the one-device rule.
- **Every page renders per request** (tenant host + session); `cacheComponents` is off.
- **i18n:** keys in `packages/lib/src/i18n/en.ts`; server code uses `t`, client components `useT()`.
  Both run on next-intl (ICU messages: `{name}` variables, no `<tags>` in text). Keys stay flat and dotted
  and are nested for next-intl, so a key can't also be the prefix of another (`lessons.type` vs
  `lessons.type.live`: use `lessons.typeLabel`). API errors go through `errorText()`.
- **API types:** `npm run api-client` (from `frontend/`) exports the OpenAPI document
  (`backend/scripts/export_openapi.py`) and regenerates `packages/api-client/src/schema.ts`; use
  `Schema<"Name">`. Commit both after any API change; `npm run check -w @eduzone/api-client` fails when
  stale. Hand-written types in `@eduzone/lib/types` move over as screens are touched (the backend still
  types several enums as plain `str`).
- **Formatting:** `packages/lib/src/format.ts` (money from cents, Colombo date/time, `<input type="datetime-local">`
  read as Colombo time with a fixed +05:30 offset).
- Routes: `/` (tenant home, or the main host's welcome), `/login`, the console `/teach/<slug>/classes`
  (+ `/new`, `/[id]` with months, lessons and lesson files), `/teach/<slug>/media` (+ `/[id]` preview), requests,
  payments, earnings, money. Videos upload from the browser straight to Bunny (tus-js-client); PDFs go through
  the streaming route `/teach/<slug>/upload/document`, which proxy.ts skips. Student routes: `/learn/...` (below),
  the tenant site's public `/classes/[slug]`, and the gateway return page `/checkout/[id]`.
  **Phase 3:** the student area is `/learn` (Today, `/learn/classes[/<id>]`, `/learn/lessons/<id>`,
  `/learn/schedule`, `/learn/requests`, `/learn/payments[/<id>]`, `/learn/profile`) and calls only
  `/api/v1/learn/...` (by id, any host). The console is `/teach/<slug>/...` (`/teach` picks a workspace; a
  switcher shows when the account is staff of several); `proxy.ts` puts the slug in the `x-ez-workspace`
  request header, `api("~/classes")` means `/teach/<slug>/classes`, and links use `teachHref()` or the layout's
  `base`. PDF uploads stream through `/teach/<slug>/upload/document`. The main host (`BASE_DOMAIN` in
  `.env.local`) serves `/learn`, `/teach` and sign-in; its `/` sends signed-in people to `/learn`. On a tenant
  host the public class page sends signed-in students to `/learn/classes/<id>`. Old URLs (`/my`, `/account`,
  `/payments`, `/lessons/<id>`, `/org/...`) redirect (next.config.ts). Staff = `me.workspaces` is not empty.
  Identity (phase 2): `/login` (password or Google, then the SMS code on a new device), `/register`,
  `/verify-phone` (`?next=`, `?change=1`), `/recover`, `/recover/[token]`, `/verify-email`, `/learn/profile`.
  All identity server actions live in `app/login/actions.ts`; `next` is always checked to be a same-site
  path. Pages opened from email links act only on a button press (mail scanners open links). Pay sends an
  unverified student to `/verify-phone?next=<class>`. When the one-device rule ends a session, `proxy.ts`
  leaves an `ez_notice` cookie and the site shows "You were signed out" (`getSession().endedElsewhere`).
  The Google button shows only when `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is set.
- Local dev (from `frontend/`): `npm install`, then `npm run dev:web` (open `http://<slug>.localhost:3000`
  with the API on `BASE_DOMAIN=localhost`) and `npm run dev:admin` (`http://localhost:3001`). Each app
  has `API_URL` in its `.env.local`. Checks: `npm run typecheck`, `npm run lint`, `npm run build`.
- **Smoke suite:** `npm run e2e` (Playwright; first time `npx playwright install chromium`). It starts
  its own API (port 8010, `SMS_PROVIDER=file` so tests read OTP codes from `e2e/.outbox.jsonl`) and web
  app (port 3010, build dir `.next-e2e`), so it runs beside the dev servers; it needs the migrated local
  database and seeds the `demo` organization; it also sets `EMAIL_PROVIDER=file`. Covers: a student
  registers, confirms the phone, joins and pays with the fake gateway; a second browser signs the first out;
  the teacher signs in (with the new-device code) and opens the console. Add a test for each flow a later
  phase changes.
- **Demo sign-in (local):** `scripts/seed_demo.py` gives the demo owner and teacher an email and a local
  test password (constants at the top of that file). The first sign-in in a browser asks for the SMS code,
  which `SMS_PROVIDER=console` writes to the API log.

---

## 14. Coding conventions

- Type hints everywhere; Pydantic models for every request/response.
- Business rules live in services, not routers or SQL views.
- Database changes go through Alembic migrations. The first migration reproduces
  `db/eduzone_v1_schema.sql`; keep that file updated as the human-readable reference.
- Tests: pytest with a real PostgreSQL (not SQLite). Required test categories:
  tenant isolation, access rule, ledger posting balances, webhook idempotency.
- Secrets only from environment / secret manager. Never commit `.env`.
- Keep it simple: no microservices, no premature caching (public marketplace pages are the planned
  exception, per `FRONTEND.md`), no features from v1.1 unless asked.

---

## 15. Open decisions

| Decision | Status |
|---|---|
| Gateway provider and whether it allows collecting on behalf of tenants | In progress (legal + gateway) |
| Who bears the gateway fee | Default `tenant`; confirm |
| Recording availability window (expiry after N months?) | Undecided; schema supports `expires_at` |
| Payout schedule (weekly / monthly) and minimum amount | Undecided |
| Commission tiers for large teachers | Idea: 20% normally, lower above a monthly volume |
| SMS provider | Undecided |
| Plan limits per tier | Needs Bunny pricing check |
| EduZone brand | Colours and fonts decided (forest green + gold, Fraunces + Instrument Sans); logo still placeholder |
| Sinhala at the pilot | Depends on the pilot teachers |
| Email provider | Undecided |
| Institute URL | `/institutes/<slug>` (assumed) |

---

## 16. Build order

### Done (on the pre-migration design)
1. Repo, Docker Compose (Postgres + Redis), FastAPI skeleton, Alembic baseline from the schema
2. Tenant resolution + DB session with `SET LOCAL app.tenant_id` + isolation tests
3. Auth: phone OTP, sessions, JWT, one-device rule
4. Catalog: classes, months, lessons (console APIs)
5. Bunny integration: upload signatures, webhooks, signed playback, PDFs
6. Enrollment + late-month requests + access rule
7. Checkout: orders, gateway adapter, webhook, ledger posting
8. Cash-flow and teacher-earnings endpoints
9. Platform admin minimum: tenants, payouts, usage
(Each step shipped with its Next.js screens.)

### Migration to the marketplace (details: `docs/frontend-migration-plan.md`)
0. Spec: this file and `FRONTEND.md` agree (done)
1. Frontend groundwork: monorepo, `packages/ui` tokens, generated API client, next-intl, Playwright smoke suite (done)
2. Identity: Google + email/password, phone verification, new-device OTP, recovery, account-wide sessions (done)
3. Path tenancy (`/teach/<tenant>` + membership) and the cross-tenant student area (user-scoped RLS reads) (done)
4. Marketplace: subjects, teacher profiles, public read path, subject/teacher/class/institute pages, SEO, share tools
5. Teacher self-registration and approval
6. Cart and one payment across teachers (checkouts, fee allocation, per-tenant fulfilment)
7. Own hls.js video player with signed HLS URLs and progress
8. Private admin app (separate deploy) and its new screens
9. Polish: Sinhala if needed, Playwright at 360 px and desktop, low-end phone pass, accessibility

### Then
10. Pilot with real tuition teachers
11. v1.1: company sites
