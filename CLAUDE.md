# EduZone — Project Guide

> Read this file before every task. It is the single source of truth for what EduZone is,
> what has been decided, and the rules the code must follow.
> The database schema lives in `db/eduzone_v1_schema.sql`, which is authoritative for tables and columns.

---

## 1. What EduZone is

EduZone is a **multi-tenant, white-label learning platform**. An organization (a tuition teacher,
an institute, and later a company) gets its own branded learning site on a subdomain
(`<slug>.eduzone.lk`) and, in v1.1, on its own domain. Students of that organization log in,
pay fees, watch recorded lessons, join live classes, and download tutes. They only ever see
that organization's world.

- **Owner:** SwitchOps Tech (Pvt) Ltd, Sri Lanka
- **Builder:** solo developer (Chamoda), assisted by Claude Code
- **Launch market:** Sri Lankan tuition teachers and institutes (O/L, A/L, Grade 5)
- **Later market:** companies running staff training (subscription-based, v1.1+)

### Three kinds of user

| Console | Who | Purpose |
|---|---|---|
| Platform admin | EduZone staff | Create/suspend organizations, see all money, record payouts, monitor Bunny usage |
| Organization console | Owner, admin, teacher | Classes, months, lessons, videos, students, payments, cash flow |
| Student app | Students (mostly on phones) | Browse, pay, watch, join Zoom, download tutes, see receipts |

---

## 2. Business decisions (settled)

| Topic | Decision |
|---|---|
| First customer | Tuition teachers and institutes |
| Revenue: individuals and institutes | EduZone takes a **commission per sale**, default **20%** (configurable per tenant) |
| Revenue: corporate (v1.1+) | Monthly subscription per organization |
| Who collects money | **EduZone collects all payments** through its own gateway account, then pays organizations out |
| Organization visibility | Full end-to-end cash flow: gross, gateway fees, EduZone commission, net, refunds, payouts, balance due |
| Payment methods | **Online gateway only.** No bank deposits or slip uploads. |
| Gateway | Sri Lankan gateway (PayHere or a bank IPG). Code must stay gateway-agnostic. |
| Pricing model | Monthly class fees (main), one-time courses, free classes |
| Late joiners | Students may buy **past months only if the teacher approves** the request |
| Institutes with many teachers | EduZone pays the **institute**. The institute pays its teachers itself, using EduZone's per-teacher earnings report. |
| Gateway fee bearer | Per-tenant setting, default `tenant`. **Pending final confirmation.** |
| Items per order (v1) | **One** (one month or one course). Service-enforced; a cart can come later. |
| Gateway fee timing | Book an **estimated** fee with the sale; true up with a `fee_settlement` posting from the settlement report |
| Past month | A month the teacher has **closed** (`class_months.status = 'closed'`); buying it needs an approved late request |
| Refunds on cash-flow page | Gross as sold, refunds as a separate line, commission and net shown after refunds |
| Video | **Bunny.net** — Bunny Stream for video, Bunny Storage for PDFs |
| Cost rule | No plan may let a tenant's Bunny cost exceed what EduZone earns from that tenant |

Legal and regulatory review of "collecting on behalf of organizations" (CBSL rules, gateway
merchant terms, VAT, receipts) is in progress outside the codebase. Keep the money design
auditable so it can adapt.

---

## 3. Scope

### v1 (build now)
**Student**
- Sign up / log in with phone OTP (email optional)
- Browse published classes of the current organization
- Join a class; pay for a month or a one-time course via the gateway
- Request a past month; pay after teacher approval
- Watch recorded videos, join Zoom links, and download tutes, **only for paid months**
- Payment history and receipts

**Organization console**
- Create classes, months, lessons (live / recorded / document)
- Upload videos to Bunny and PDFs; attach them to lessons; add Zoom links
- Student list per class: paid / not paid this month
- Approve or reject late-month requests
- Manual access grants (scholarships, free access)
- Cash-flow page (monthly) and per-teacher earnings (institutes)

**Platform admin (minimal)**
- Create organizations and their owners
- See all payments; record payouts; see each tenant's balance due
- See Bunny usage per tenant

**Foundations required in v1 even though only a few tenants exist**
- Multi-tenancy everywhere (see section 5)
- Ledger for all money (see section 7)
- Content protection basics (see section 8)

### v1.1 (later; do not build unless asked)
- Custom domains (CNAME + TXT verification, automatic TLS)
- Organization self-signup and onboarding
- Full platform admin console
- Richer organization and student consoles
- Corporate features: departments, assigned courses, due dates, completion reports, subscriptions
- Sinhala and Tamil UI translations (the i18n structure must exist from v1)

### Out of scope for now
Own video-calling system, mobile native apps, marketplace across tenants, affiliate programs,
SCORM/LTI, AI features, bank slip payments.

---

## 4. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12+, **FastAPI**, Pydantic v2 |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic |
| Database | **PostgreSQL 16+** with Row-Level Security |
| Frontend | **Next.js** (App Router) + TypeScript + Tailwind; mobile-first |
| Background jobs | Redis + a worker (ARQ or Celery). Add only when a feature needs it (webhooks retries, emails, Bunny usage sync). |
| Video | Bunny Stream (one library per tenant) |
| Files | Bunny Storage |
| SMS / OTP | Sri Lankan SMS provider (TBD) behind an interface |
| Hosting | One backend app + one frontend app + Postgres + Redis. **No microservices.** |

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
└── frontend/
    └── app/
        ├── (student)/
        ├── (org)/                   # organization console
        └── (platform)/              # platform admin
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
   `otp_codes`, `gateway_webhook_events`, `platform_admin_sessions`) are the only exceptions.
2. **Tenant resolution:** read `X-Forwarded-Host` if present (set by the frontend server or a
   reverse proxy, which can't override `Host`), else the `Host` header → `<slug>.eduzone.lk` → call
   `resolve_tenant(slug)` (a `SECURITY DEFINER` function, because RLS hides `tenants` until
   `app.tenant_id` is set). Unknown or non-active tenant → 404. (v1.1 adds a custom-domain lookup first.)
3. **Every request runs in a DB transaction that begins with**
   `SET LOCAL app.tenant_id = '<tenant uuid>'`. Without it, RLS returns zero rows.
   In code (`app/core/tenancy.py`): tenant-facing routes take `session: TenantSession`
   (or `tenant: CurrentTenant` if they need no DB). This is a FastAPI dependency rather than
   middleware, so platform and webhook routes simply don't use it. It commits before the
   response is sent and rolls back on any error. Services and jobs use `tenant_transaction(tenant_id)`.
4. **Never accept `tenant_id` from the client.** It always comes from the resolved request context.
5. The app connects as role **`eduzone_app`** (subject to RLS). Platform admin endpoints and
   background jobs use **`eduzone_admin`** (BYPASSRLS) through a separate session factory.
   Never use `eduzone_admin` for tenant-facing endpoints.
6. Cross-tenant links are blocked by **composite foreign keys** `(tenant_id, id)`.
   New tables referencing tenant data must follow the same pattern. Rows that carry both
   `class_id` and `class_month_id` use `(tenant_id, class_id, class_month_id)` so the month
   must belong to that class.
   Gateway webhooks are the one request type without a tenant host: find the tenant with
   `resolve_payment_tenant(gateway, idempotency_key)`, then run a normal tenant transaction.
   New `eduzone_app` grants are given explicitly in each migration; money tables and
   `audit_logs` never get DELETE.
7. A user is global; their role is per tenant (`tenant_members`). Authorization always checks
   the member row for the current tenant, never a global role.
8. Tests must include an isolation test for every new tenant-scoped table.
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
- **Student** (`/api/v1/student/...`, any signed-in member):
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
- **Playback:** issue **token-authenticated, short-lived** embed/play URLs only after the access check.
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

- **One active device per student** by default: on new login, revoke older `user_sessions`
  for that tenant (setting can allow N devices later).
- **Watermark overlay** in our player with the student's name and phone, moving position.
- **Short-lived signed video URLs**; never expose permanent Bunny URLs.
- **View limit:** `classes.max_video_views`; increment `lesson_progress.view_count` when a
  play session starts. Block when the limit is reached.
- Zoom links are hidden until the access check passes.

---

## 11. Auth

- Phone OTP is the primary login (E.164 numbers, e.g. `+94771234567`). Store only `code_hash`;
  expire after a few minutes; limit attempts; rate-limit per number and IP.
- Short-lived access JWT (includes `user_id`, `tenant_id`, `member_id`, `role`) +
  refresh token stored **hashed** in `user_sessions`.
- A JWT issued for tenant A must be rejected on tenant B's host.

Implemented in `app/modules/auth` (routes under `/api/v1/auth`, shared by students and staff on
the tenant host):
- `POST /otp/request` → 6-digit code by SMS, HMAC-hashed with `OTP_SECRET`, valid 5 minutes.
  Limits: 60 s resend cooldown, 5 per phone per hour, 20 per IP per hour (`otp_codes.request_ip`).
- `POST /otp/verify` → token pair. 5 wrong guesses lock the code; a wrong guess is committed in
  its own transaction so it counts. A new phone gets `NAME_REQUIRED` (code not spent) until
  `full_name` is sent. First login on a tenant creates a `student` member; `suspended` members get 403.
- `POST /refresh` rotates the refresh token (old one stops working). `POST /logout`, `GET /me`.
- The one-device rule revokes a **student's** other sessions in that tenant on login; staff may
  use several devices. `CurrentMember` checks the session row on **every** request, so revocation
  and suspension take effect immediately, and the role comes from the member row, not the token.
- Phone input accepts local forms (`0771234567`, `94771234567`) and is normalised to E.164.
- SMS goes through `app.integrations.sms` (`SMS_PROVIDER=console` logs the code locally).
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
- **Frontend:** served only on `admin.<base domain>` (`proxy.ts` sends every other path there to `/platform`,
  and tenant hosts get 404 for `/platform`), with its own cookies (`ez_padmin_*`). Pages: `/platform/login`,
  `/platform` (organizations), `/platform/tenants/new`, `/platform/tenants/[id]` (figures, record payout,
  history, edit), `/platform/payments`. FRONTEND.md wants this as a separate app on the private network;
  the pages are self-contained under `app/platform/` so they can move.

---

## 12. API conventions

- REST, JSON, prefix `/api/v1`.
- Route groups: `/api/v1/student/...`, `/api/v1/org/...`, `/api/v1/platform/...`,
  `/api/v1/public/...` (tenant branding, published classes), `/api/v1/webhooks/...`.
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

- Mobile-first. Most students use phones on mobile data.
- Tenant branding (name, logo, primary colour) is loaded by host on the server and applied as CSS variables.
- All user-facing text goes through i18n keys from day one (`en` now; `si`, `ta` later).
- Show money as `Rs. 2,000.00`.

### How the frontend is built (`frontend/`, Next.js 16, App Router)
- Read `frontend/AGENTS.md` first: Next 16 differs from older versions (e.g. `proxy.ts`
  replaces middleware). Its docs ship in `frontend/node_modules/next/dist/docs/`.
- **Backend calls happen only on the Next server** (`lib/api.ts`: Server Components and Server
  Actions), sending `X-Forwarded-Host` with the user's host. The browser never calls the API.
- **Tokens live in httpOnly cookies** (`lib/cookies.ts`); browser JavaScript never sees them.
  `proxy.ts` refreshes the access token shortly before it expires and drops dead sessions.
  A per-browser `ez_device` cookie is the `device_id` for the one-device rule.
- **Every page renders per request** (tenant host + session); `cacheComponents` is off.
- **i18n:** keys in `lib/i18n/en.ts`; server code uses `t`, client components `useT()`.
  API errors go through `errorText()` (known codes get our own text).
- **Formatting:** `lib/format.ts` (money from cents, Colombo date/time, `<input type="datetime-local">`
  read as Colombo time with a fixed +05:30 offset).
- Routes: `/` (tenant home), `/login`, `/org/classes` (+ `/new`, `/[id]` with months, lessons and lesson
  files), `/org/media` (+ `/[id]` preview). Videos upload from the browser straight to Bunny (tus-js-client);
  PDFs go through the streaming route `/api/upload/document`, which proxy.ts skips.
  Student routes: `/classes/[slug]`, `/my`, `/lessons/[id]`, `/checkout/[id]`, `/payments[/[id]]`.
- Local dev: `API_URL` in `frontend/.env.local`; open `http://<slug>.localhost:3000` with the API
  on `BASE_DOMAIN=localhost`. Checks: `npx next typegen && npx tsc --noEmit`, `npx eslint .`, `npx next build`.

---

## 14. Coding conventions

- Type hints everywhere; Pydantic models for every request/response.
- Business rules live in services, not routers or SQL views.
- Database changes go through Alembic migrations. The first migration reproduces
  `db/eduzone_v1_schema.sql`; keep that file updated as the human-readable reference.
- Tests: pytest with a real PostgreSQL (not SQLite). Required test categories:
  tenant isolation, access rule, ledger posting balances, webhook idempotency.
- Secrets only from environment / secret manager. Never commit `.env`.
- Keep it simple: no microservices, no premature caching, no features from v1.1 unless asked.

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

---

## 16. Build order for v1

1. Repo, Docker Compose (Postgres + Redis), FastAPI skeleton, Alembic baseline from the schema
2. Tenant resolution middleware + DB session with `SET LOCAL app.tenant_id` + isolation tests
3. Auth: phone OTP, sessions, JWT, one-device rule
4. Catalog: classes, months, lessons (org console APIs)
5. Bunny integration: upload signatures, webhooks, signed playback, PDFs
6. Enrollment + late-month requests + access rule
7. Checkout: orders, gateway adapter, webhook, ledger posting (with tests)
8. Cash-flow and teacher-earnings endpoints
9. Platform admin minimum: tenants, payouts, usage
10. Next.js: student app, then organization console, then platform admin
11. Pilot with one real tuition teacher
