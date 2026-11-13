# EduZone — What's next (roadmap)

> Written 2026-11-10, after courses step C7. CLAUDE.md stays the source of truth for rules and what is built; this
> file is the plan for what comes after. Sizes: **S** = a day or two, **M** = about a week, **L** = two weeks or more
> (solo developer with Claude Code).

---

## 0. Where we are

**Built and tested** (263 backend tests, 14 browser checks):

- **Marketplace:** home, catalogue and filters, subject / teacher / class / institute pages, SEO, share tools.
- **Accounts:** Google or email + password, phone verification by SMS, new-device check, recovery, one device per
  student account.
- **Students:** one cart and one payment across teachers; the student area (classes, months, lessons, our own video
  player, receipts); late-month requests.
- **Teacher console:** classes, months, lessons, media (Bunny), students, payments, cash flow, earnings, profile,
  self-registration and approval.
- **Courses (C1–C7):** builder with EduZone review, catalogue and landing pages, buying, the course player and
  progress, reviews and certificates, coupons and wishlist, refunds with a payout hold, instructor insights, commission
  per product with changes scheduled on notice.
- **Admin app:** organizations, applications, course reviews, moderation, subjects, categories, users and devices,
  checkouts, refunds, commission, payments, audit log.
- **Foundations:** tenant isolation in the database (RLS), an append-only balanced ledger, content protection.

**Running only locally.** Nothing is deployed yet. SMS, email and payments are stand-ins: codes and emails print in
the API terminal, and payments go through a fake gateway.

---

## 1. The order we recommend

| # | Stage | Why this order | Size |
|---|---|---|---|
| 1 | **Decisions that block launch** (section 2) | Several build tasks can't start without them | — |
| 2 | **Phase 9: polish** (section 3) | Already the next step in CLAUDE.md; the UI must reach Udemy level before real users | L |
| 3 | **Launch readiness** (section 4) | Real SMS, email, payments, video, hosting, security, legal | L+ |
| 4 | **Pilot** with real teachers (section 5) | Step 10 in CLAUDE.md | M (plus weeks of running) |
| 5 | **v1.1: company sites** (section 6) | After the marketplace pilot (FRONTEND.md: "marketplace first, companies later") | L+ |
| 6 | **Backlog** (section 7) | Ideas parked on purpose | — |

Stages 2 and 3 can overlap: provider sign-ups and legal review take calendar time, so start them while polishing.

---

## 2. Decisions needed from you (blockers first)

| Decision | Blocks | Notes |
|---|---|---|
| **Hosting** (single VPS, Cloudflare in front, Railway / Fly / Render, AWS…) | Deploy, backups, custom domains, the admin app's private network | Shapes certificates and the VPN for the admin app |
| **SMS provider** (Sri Lankan: Dialog, Notify.lk, Text.lk…) | Real sign-up and new-device codes | Needs a sender ID; cost per SMS |
| **Email provider** (Amazon SES, Postmark, Resend, Brevo…) | Verification, recovery, commission notices | Needs the domain's SPF and DKIM records |
| **PayHere merchant account** (or a bank IPG) | Real payments | Also settles "collecting on behalf of organizations" (legal) |
| **Legal review result** (CBSL, gateway terms, VAT, receipts) | Terms, privacy and refund pages, receipt wording | In progress outside the codebase |
| **Who bears the gateway fee** | Confirms the default (`tenant`) | CLAUDE.md lists it as "pending final confirmation" |
| **Payout schedule and minimum** (weekly / monthly) | The payout routine, teacher terms | |
| **Recording expiry** (keep forever or N months) | Teacher expectations, Bunny costs | The schema already supports `expires_at` |
| **Plan limits per tier** (storage, bandwidth) | Bunny cost rule | Needs a Bunny pricing check |
| **Sinhala at the pilot?** | Phase 9 translation work | Ask the pilot teachers |
| **Logo** | Brand, OG images, certificate PDF | Colours and fonts are already settled |

---

## 3. Phase 9: polish (CLAUDE.md step 9)

**Quality bar: Udemy-level polish on every screen.**

### 3.1 Look and layout
- [ ] **Screen-by-screen review, 360 px and desktop:** marketplace, student area, console, admin. Fix spacing,
      overflow and empty states; add loading skeletons where they're missing. **M**
- [ ] **Admin sidebar:** it now has 13 items and scrolls with a plain white scrollbar. Group the items (Content /
      People / Money / System) or style the scroll. **S**
- [ ] **Uploads instead of links:** course covers and teacher photos are pasted links today. Upload them to Bunny
      Storage, with a crop preview. **M**
- [ ] **Profile editor:** a live preview of the public teacher page. **S**
- [ ] **Course builder:** drag-and-drop for sections and lectures (up/down buttons today). **S–M**

### 3.2 Phones and slow networks
- [ ] **Playwright at 360 px and desktop:** run the smoke suite at both sizes in CI. **S**
- [ ] **Low-end phone pass:** a cheap Android on 3G. Check the bundle size budget (FRONTEND.md), lazy loading and
      image sizes. **M**
- [ ] **Player:** a data-saver setting (lowest quality by default on mobile data); respect reduced motion. **S**
- [ ] **Caching public pages:** the marketplace pages FRONTEND.md section 12 asks for (revalidate on publish). **M**

### 3.3 Accessibility (WCAG 2.1 AA)
- [ ] **Audit:** contrast, keyboard paths, focus rings, labels (the e2e run already caught one bad label),
      screen-reader names on icon buttons, the player's controls. **M**

### 3.4 Language
- [ ] **Sinhala**, if the pilot needs it: translate the `en.ts` keys, add a language switch, use Noto Sans Sinhala,
      and embed a Sinhala font in the certificate PDF. **M–L**
- [ ] Tamil stays later (v1.1 list).

### 3.5 Emails people expect
- [ ] **Email templates (HTML and text):** verification, recovery, the decision on a teacher application, commission
      notices, refund status, the course welcome message, a receipt after payment. **M**

### 3.6 Institutes
- [ ] **Team invites:** owners invite teachers and admins by email; accept, remove, change role. This is in the v1
      scope and not built yet. **M**

---

## 4. Launch readiness (production blockers)

### 4.1 Real providers
- [ ] **SMS:** an adapter in `app/integrations/sms`, a sender ID, delivery receipts, and cost alerts. **S**
- [ ] **Email:** an adapter in `app/integrations/email`, the domain's SPF / DKIM / DMARC records, and bounce
      handling. **S**
- [ ] **Google sign-in:** create the OAuth client and set `GOOGLE_CLIENT_ID` and `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. **S**

### 4.2 Payments (PayHere)
- [ ] **Sandbox check:** the checkout hash, notify verification, amounts and currency, a cancel and a decline.
      CLAUDE.md marks these "re-check before launch". **S**
- [ ] **Email for phone-only students:** PayHere needs an email address, and phone-only students have none. Ask for
      one at checkout, or send a placeholder if PayHere allows it. **S**
- [ ] **Refund API:** an OAuth app and a partial-refund check. Until then refunds are recorded by hand in the admin
      app (built). **S**
- [ ] **Settlement report:** import the gateway's report and run the fee true-up (`settle_fee`), including across a
      checkout's orders. **M**
- [ ] **Automatic retry of stuck checkouts:** check whether PayHere re-sends on an error first. **S**

### 4.3 Video (Bunny)
- [ ] **Real library:** verify upload signatures, the webhook, status codes, signed embed and CDN URLs, and the HLS
      token formula (all marked "re-check before launch"). **S–M**
- [ ] **Daily usage sync** into `tenant_usage_daily`, warnings at 80% of bandwidth, a notice to staff at 100%. **M**
- [ ] **Plan limits:** set storage and bandwidth per tier so Bunny's cost never exceeds what EduZone earns from that
      organization (the cost rule). **S**

### 4.4 Background jobs
- [ ] **Redis and a worker (ARQ)**, as planned in CLAUDE.md. **M** Jobs:
  - Bunny usage sync (daily)
  - `apply_commission_changes` (daily; checkout is already correct without it)
  - checkout retry
  - sending emails and SMS off the request path
  - refund retries at the gateway
  - reminders (pending applications, refunds waiting)

### 4.5 Hosting and operations
- [ ] **Environments:** staging and production, the same set-up, with seed data only on staging. **M**
- [ ] **Postgres:** managed, daily backups plus point-in-time restore, **one restore drill before launch**, and UTF-8
      encoding. **S–M**
- [ ] **DNS and certificates:** `eduzone.switchops.tech`, an API host, a wildcard `*.eduzone.switchops.tech` ready for
      company sites. **S**
- [ ] **Secrets:** in a secret manager. Never in the repo or the database (`JWT_SECRET`, `PAYOUT_ENCRYPTION_KEY`,
      Bunny keys, PayHere keys). **S**
- [ ] **Behind a proxy or CDN:** make `client_ip()` read the trusted forwarded header (CLAUDE.md note), and set
      `X-Forwarded-Proto`. **S**
- [ ] **Admin app:** on the private network / VPN with `PLATFORM_ALLOWED_CIDRS` (`docs/deploy-admin.md`). **S**
- [ ] **CI:** lint, typecheck, the backend tests and the e2e suite on every push; deploy on merge. **M**
- [ ] **Monitoring:** error tracking (e.g. Sentry) for the API and both web apps, structured logs, uptime checks,
      alerts on payment webhook errors. **S–M**
- [ ] **Runbook:** recording a payout, refunding by hand, retrying a checkout, suspending an organization, restoring
      a backup. **S**

### 4.6 Security and privacy
- [ ] **Security review:** auth flows, rate limits, file uploads, signed URLs, admin access, dependency audit. **M**
- [ ] **Headers:** CSP, HSTS, frame-ancestors on the web app (the admin app already sends some). **S**
- [ ] **Sri Lanka's Personal Data Protection Act:** privacy notice, data retention, a way to delete an account and
      export one's data. **M**

### 4.7 Legal and content
- [ ] **Final pages:** terms, privacy and refund policy (drafts today), and teacher terms (notice period,
      refunds, certificates, payouts). **S** (once the legal text is ready)
- [ ] **Receipts:** wording that matches the legal model (collecting on behalf of organizations). **S**
- [ ] **Brand:** the logo into `LogoMark`, the favicons, OG images and the certificate. **S**

---

## 5. Pilot (CLAUDE.md step 10)

- [ ] **Recruit** 3–5 teachers or institutes (a mix of O/L, A/L and one course creator).
- [ ] **Onboard by hand:** apply, approve, set their Bunny library, help publish the first class or course.
- [ ] **Support:** a WhatsApp group and a daily look at the admin queues (applications, refunds, stuck checkouts).
- [ ] **Measure:** sign-ups, phone-verification drop-off, cart-to-payment conversion, video errors, refund rate,
      Bunny cost per teacher compared with commission earned.
- [ ] **Two-week feedback cycles:** fix the top issues, then widen.
- [ ] **Decide** the Sinhala and recording-expiry questions from real use.

---

## 6. v1.1: company sites

### 6.1 What it is
A private training site per company, for its staff:
- **The site:** branded with the company's logo and colour. It never shows marketplace content, and its trainings
  never appear on the marketplace.
- **Staff:** join with their company email, then learn for free.
- **Training:** EduZone's course model (sections, lectures, progress, certificates), **assigned** to staff with due
  dates instead of sold.
- **Paying:** the company pays EduZone a **monthly subscription**.

Groundwork already in place:
- tenant isolation;
- finding the organization from the host (kept from the pre-marketplace design);
- courses whose access comes from access grants rather than payments (COURSES.md section 14).

### 6.2 Addresses: both options
| Option | Example | What it takes | Plan |
|---|---|---|---|
| **EduZone subdomain** | `abcbank.eduzone.switchops.tech` | One wildcard DNS record and one wildcard certificate; live the moment the company is created | **Every company, always** |
| **Their own subdomain** | `training.abc.com` | They add a CNAME to us, plus a TXT record to prove ownership; we issue a certificate automatically (Caddy on-demand TLS or Cloudflare for SaaS) | **Add-on**, recommended form |
| **Their bare domain** | `abctraining.com` | Like the row above, but DNS can't CNAME a bare domain: an A record to a fixed IP, or an ALIAS record | Add-on, supported |

On custom domains, Google sign-in needs care: Google only accepts registered origins. Use a central sign-in on
EduZone that redirects back, or email + password only. Sign-in cookies are kept per host, which is already how ours
work.

### 6.3 Decisions to settle first
- **Pricing:** per staff member, a flat tier or a fixed plan; a trial or not.
- **Paying:** by card through the gateway, or an invoice paid by bank transfer.
- **Joining:** anyone with a verified company email, or only people a company admin invited.
- **Who builds trainings:** company admins, EduZone on their behalf, or both.
- **Video limits per plan:** the cost rule applies here too.
- **Leavers:** what happens to the account and certificates of someone who leaves the company.
- **Hosting:** decides how custom-domain certificates are issued (section 4.5).

### 6.4 Build steps (after a spec, `docs/COMPANIES.md`, settles the decisions)
| Step | Content | Size |
|---|---|---|
| **K0** | Spec: `docs/COMPANIES.md` (decisions, schema, screens, tests), the same approach as COURSES.md | S |
| **K1** | Company tenants and sites: `site_type = company`, host resolution for company subdomains, branding (logo and a contrast-checked accent colour), the company home page, company sign-in without phone verification, never listed on the marketplace | L |
| **K2** | Domain verification and staff: DNS TXT check of the email domain, invites and joining by verified email, CSV import, departments, roles (company admin / staff) | M–L |
| **K3** | Trainings and assignment: `/manage/courses` builder (no EduZone review, no price), assigning to people or departments with due dates, an `assignment` access type, a `course_assignments` table, "Assigned to me" and overdue status | L |
| **K4** | Reports and certificates: completion by course, department and person, CSV export, certificates on completion with the company name | M |
| **K5** | Subscriptions: plans, billing (gateway card or invoice), ledger entries for subscription revenue, suspension when unpaid, trial | L |
| **K6** | Admin app: create a company, choose its plan, usage compared with plan and with video cost, subscription status | M |
| **K7** | Custom domains: a domains table, CNAME and TXT checks, automatic certificates, the sign-in redirect for custom domains | M |
| **Later** | Quizzes with pass marks (companies need them sooner), SSO with Google Workspace / Microsoft 365 | — |

---

## 7. Backlog (parked on purpose)

- **Courses:** quizzes, assignments, Q&A; per-lecture drop-off in insights; links as lecture resources; email
  versions of the welcome and completion messages; an article preview in the builder.
- **Commission:** lower commission for sales a teacher refers (own link or coupon), through the existing
  scheduled-change mechanism; volume tiers for large teachers.
- **Tuition:** refunds for months (the course refund code is built to be reused).
- **Language:** Tamil.
- **Out of scope** (CLAUDE.md): our own video calling, native mobile apps, affiliates, SCORM/LTI, AI features, bank
  slip payments.

---

## 8. Next three moves

1. **Answer section 2:** hosting, SMS and email providers, PayHere account. Start the sign-ups now; they take days.
2. **Start phase 9** (section 3), beginning with the 360 px / desktop screen review and the admin sidebar.
3. **In parallel, set up staging** (section 4.5) so every polished screen can be checked on a real phone over the
   internet.
