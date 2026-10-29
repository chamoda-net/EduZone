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
2. **Tenant resolution:** read the `Host` header → `<slug>.eduzone.lk` → call
   `resolve_tenant(slug)` (a `SECURITY DEFINER` function, because RLS hides `tenants` until
   `app.tenant_id` is set). Unknown or non-active tenant → 404. (v1.1 adds a custom-domain lookup first.)
3. **Every request runs in a DB transaction that begins with**
   `SET LOCAL app.tenant_id = '<tenant uuid>'`. Without it, RLS returns zero rows.
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
- Platform admins (`users.is_platform_admin`) use a separate login path and session
  (`platform_admin_sessions`, via `eduzone_admin`). `eduzone_app` cannot write `is_platform_admin`.

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

---

## 13. Frontend notes

- Mobile-first. Most students use phones on mobile data.
- Tenant branding (name, logo, primary colour) is loaded by host on the server and applied as CSS variables.
- All user-facing text goes through i18n keys from day one (`en` now; `si`, `ta` later).
- Show money as `Rs. 2,000.00`.

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
