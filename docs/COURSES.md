# EduZone — Courses (Udemy-style) addendum

> Read with `CLAUDE.md` and `FRONTEND.md`. This file adds a second product type, **Courses**, next to the
> existing **Classes** (tuition). Everything in `CLAUDE.md` still applies (tenancy, RLS, money rules,
> checkout, ledger). Where this file and `CLAUDE.md` disagree on courses, this file wins.
> The SQL below is written against `db/eduzone_v1_schema.sql`; **check it against the current
> migrations (0001–0009) before writing the Alembic migration** and adapt names if they have moved on.
>
> **Status (2026-11-09): steps C1, C2 and C3 built** (migrations 0010-0012; CLAUDE.md section 6, "How it's built
> (courses C1)", "(courses C2)" and "(courses C3)"). The player lives at `/learn/courses/<id>` (by id, like every
> `/learn` route), not `<slug>`.
> Corrections made while building, which win over the text below:
> - Certificate numbers use the prefix **`EZCERT-`** (`EZC-` is already the checkout number prefix).
> - The public catalogue is the `public_*` **views** (migration 0007), not a "catalog function"; course fields go
>   into new course views in step C2. "Pattern 17.3" means the user policies of migration 0006.
> - `course_categories.slug` uses the subject slug pattern; `classes` also gained `submitted_at`.
> - `/checkouts` is reserved too (an existing page that wasn't).
> - Commission changes (C.10): checkout reads scheduled changes whose time has come, so no daily job is needed
>   for the rate to be right; a job may later only mark them applied.

---

## 1. What changes

EduZone sells two kinds of product on one marketplace, through one cart, one checkout and one ledger:

| | **Classes** (built, phases 1–8) | **Courses** (this addendum) |
|---|---|---|
| Shape | Monthly class: months → lessons (live Zoom, recording, tute) | Self-paced: sections → lectures (video, article, PDF) |
| Price | Per month, one-time or free | **One-time or free** |
| Access | Per paid month; past months need teacher approval | **Lifetime** after purchase |
| Catalogue | Subjects, exam (Grade 5 / O/L / A/L), year, medium | **Categories**, level, language, length, rating |
| Who | Tuition teachers and institutes | Any **approved** instructor (same approval as teachers) |
| Extras | Schedule, late-month requests | Landing page, reviews, progress %, certificate, coupons, wishlist, refunds |

## 2. Decisions (settled 2026-11-02)

| Topic | Decision |
|---|---|
| Product mix | **Both**: Classes and Courses on the same marketplace |
| Who can sell courses | **EduZone approval required**, same application flow as teachers (applicant picks classes, courses or both) |
| Access length | **Lifetime** (`access_grants.expires_at IS NULL`); terms say "for as long as the course is on EduZone" |
| Currency | **LKR only** (PayHere). Keep `currency` columns; PayHere can also take USD/GBP/EUR/AUD if added later |
| First release | Course product, categories, landing page, reviews, progress + certificate, coupons + wishlist, refunds, basic instructor analytics. **Quizzes, assignments and Q&A later** |
| Commission | **20% for courses at launch**, same as classes. **SwitchOps Tech management can change it** (for everyone, one product type, or one tenant) **only with a notice period**; changes are scheduled, never immediate, and never touch past sales (section 4, C.10) |
| Refund window | **7 days from purchase and under 30% of the course complete** (section 9) |
| Certificates | **Paid courses only** (as Udemy) |
| Commission notice | **30 days** before an increase takes effect; decreases may apply sooner |
| Staff review | EduZone staff review **only the first publish** of each marketplace course |
| Free courses | **No video length cap** for now |
| Company training | Company sites (v1.1) use **the same course model**, not the tuition model (section 14) |
| Marketplace courses for company staff | **No bulk/seat deals**; staff buy on the marketplace like any student |

### Why lifetime access is affordable (Bunny check, Nov 2026)
Bunny Stream charges per use (USD 1 minimum a month): standard encoding is free; storage is
USD 0.01/GB/month (+0.01 per extra replication region); delivery is USD 0.03/GB to Asia on the
standard network, or USD 0.005/GB flat on the volume network (first 500 TB).

Rule of thumb: **~1 GB per hour watched at 720p**. With LKR ≈ 300 per USD:

| Item | Standard (Asia) | Volume network |
|---|---|---|
| One full watch of a 10-hour course | ~USD 0.30 ≈ Rs 90 | ~USD 0.05 ≈ Rs 15 |
| EduZone commission on a Rs 3,000 course | Rs 600 | Rs 600 |

Viewing is covered by the sale many times over. **The cost that never stops is storage**, paid every month,
even for courses that sell nothing (a 10-hour course in 240p–720p renditions is ~15–20 GB ≈ Rs 45–60
a month). So:
- Course videos are encoded at **240p/360p/480p/720p only** (1080p only on plans that pay for it).
- Course storage counts towards the tenant's `storage_limit_bytes`.
- Videos that buyers still have access to **cannot be deleted** (an instructor may unpublish a course to stop
  new sales; buyers keep access).
- Draft or archived courses with **zero buyers** may be purged after 90 days' notice.
- Before launch, test **volume-network** playback from Sri Lanka (fewer edge locations); use it for courses if
  quality is fine.

---

## 3. Udemy course structure (reference) and what EduZone takes

Sources: Udemy instructor help (course quality checklist, lecture formats, course goals).

| Udemy | What it is | EduZone v1 |
|---|---|---|
| **Course → Sections → Curriculum items** | Sections group the items; each item has a title, description, resources and a free-preview flag | ✅ Same |
| Video lecture | One video | ✅ `lesson_type = 'recorded'` |
| Video + slides | Video with PDF slides alongside | ✅ Recorded lecture + PDF resource (no slide sync) |
| Article lecture | Text and images in a built-in editor | ✅ New `lesson_type = 'article'` (Markdown, sanitised) |
| Lecture resources | Downloadable files, external links | ✅ `lesson_resources` (+ links later) |
| Quiz, assignment, coding exercise, practice test, lab, role play | Practice and tests | ❌ Later (quizzes and assignments first) |
| **Landing page** | Title, subtitle, description (200+ words), language, level, category/subcategory, image, promo video, instructor bio + photo | ✅ All |
| **Intended learners** | At least 4 learning objectives; requirements; who the course is for | ✅ All three lists |
| Minimums | At least 30 min of video, at least 5 lectures, HD (720p or more) | ✅ Automated publish checks (section 7) |
| Quality review | Udemy staff review before a course goes live | ✅ EduZone staff review the **first publish** of each course |
| Welcome / congratulations messages | Sent to the student on enrolling / finishing | ✅ Shown in the player (email later) |
| Pricing and coupons | One price; instructor coupons; site-wide sales | ✅ Price + tenant coupons (incl. a public sale coupon) |
| Student player | Curriculum sidebar, progress %, mark complete, resume | ✅ Reuse our hls.js player |
| Notes, bookmarks, announcements, Q&A | Student and instructor engagement | ❌ Later (Q&A first) |
| Ratings and reviews | 1–5 stars + text by enrolled students; instructor can reply | ✅ |
| Certificate of completion | On 100% completion of paid courses, with a verify link | ✅ |
| Refunds | Refund window with an abuse check | ✅ Shorter window (section 2/9) |
| Instructor analytics | Revenue, enrolments, ratings, engagement | ✅ Basic (section 10) |

---

## 4. Data model changes

Implement as Alembic migrations in this order. Keep `db/eduzone_v1_schema.sql` updated.

### C.1 Course categories (platform-level, EduZone-managed, like `subjects`)
```sql
CREATE TABLE course_categories (
    id          smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_id   smallint REFERENCES course_categories(id),      -- NULL = top level; max 2 levels (service rule)
    slug        text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{2,40}$'),   -- 'it-networking', 'cisco'
    name_en     text NOT NULL,
    name_si     text,
    name_ta     text,
    sort_order  integer NOT NULL DEFAULT 0,
    is_active   boolean NOT NULL DEFAULT true
);
GRANT SELECT ON course_categories TO eduzone_app;
```
Seed: IT & Networking, Software Development, Business, Finance & Accounting, Design, Marketing,
Languages, Personal Development, Exam Skills, Music, Health & Fitness (subcategories added by staff).

### C.2 Courses are classes with `kind = 'course'`
Reuse `classes` so cart, checkout, orders, access grants, ledger and the public catalog keep working.
```sql
ALTER TABLE classes
    ADD COLUMN kind                text NOT NULL DEFAULT 'tuition' CHECK (kind IN ('tuition','course')),
    ADD COLUMN subtitle            text CHECK (char_length(subtitle) <= 120),
    ADD COLUMN category_id         smallint REFERENCES course_categories(id),
    ADD COLUMN level               text CHECK (level IN ('beginner','intermediate','advanced','all')),
    ADD COLUMN learning_objectives text[] NOT NULL DEFAULT '{}',
    ADD COLUMN requirements        text[] NOT NULL DEFAULT '{}',
    ADD COLUMN target_audience     text[] NOT NULL DEFAULT '{}',
    ADD COLUMN promo_media_id      uuid,
    ADD COLUMN welcome_message     text,
    ADD COLUMN completion_message  text,
    ADD COLUMN total_video_seconds integer NOT NULL DEFAULT 0,   -- recomputed on publish/curriculum change
    ADD COLUMN lecture_count       integer NOT NULL DEFAULT 0,
    ADD COLUMN rating_avg          numeric(3,2),                 -- not money; display only
    ADD COLUMN rating_count        integer NOT NULL DEFAULT 0,
    ADD COLUMN review_note         text,                         -- staff note when changes are requested
    ADD COLUMN first_published_at  timestamptz,
    ADD FOREIGN KEY (tenant_id, promo_media_id) REFERENCES media_assets (tenant_id, id),
    ADD CHECK (kind <> 'course' OR pricing_model IN ('one_time','free')),
    ADD CHECK (kind <> 'course' OR (exam IS NULL AND batch_year IS NULL));

-- Courses get a staff review on first publish
ALTER TABLE classes DROP CONSTRAINT classes_status_check;
ALTER TABLE classes ADD CHECK (status IN ('draft','in_review','published','archived'));

-- Course slugs are unique platform-wide (URL /course/<slug>)
CREATE UNIQUE INDEX uq_course_slug ON classes (slug) WHERE kind = 'course';
CREATE INDEX idx_classes_courses ON classes (category_id, status) WHERE kind = 'course';
```
- `medium` is reused as the **course language** (`si`, `ta`, `en`).
- `subject_id` is optional for courses (for exam-skills courses tied to a school subject).
- `max_video_views` defaults to NULL (unlimited) for courses.

### C.3 Sections and article lectures
```sql
CREATE TABLE course_sections (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL,
    class_id    uuid NOT NULL,
    title       text NOT NULL,
    sort_order  integer NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, class_id) REFERENCES classes (tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX idx_sections_class ON course_sections (tenant_id, class_id, sort_order);

ALTER TABLE lessons
    ADD COLUMN section_id   uuid,
    ADD COLUMN article_body text,                               -- Markdown; sanitise on render
    ADD FOREIGN KEY (tenant_id, section_id) REFERENCES course_sections (tenant_id, id) ON DELETE CASCADE;
ALTER TABLE lessons DROP CONSTRAINT lessons_lesson_type_check;
ALTER TABLE lessons ADD CHECK (lesson_type IN ('live','recorded','document','article'));
ALTER TABLE lessons ADD CHECK (lesson_type <> 'article' OR article_body IS NOT NULL);
```
Service rules: course lessons have `section_id` set and `class_month_id` NULL; course lessons are never
`live`; tuition lessons never have `section_id`.

### C.4 Lecture completion (course progress)
`lesson_progress` tracks videos per resource; courses also need per-lecture completion (articles, PDFs).
```sql
CREATE TABLE lesson_completions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    student_member_id   uuid NOT NULL,
    lesson_id           uuid NOT NULL,
    source              text NOT NULL CHECK (source IN ('auto','manual')),  -- auto = video reached 90%
    completed_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (student_member_id, lesson_id),
    FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id),
    FOREIGN KEY (tenant_id, lesson_id)         REFERENCES lessons (tenant_id, id) ON DELETE CASCADE
);
```
Course progress = completed published lectures ÷ published lectures. Video lectures complete automatically at
90% watched; articles and PDFs by "Mark as complete". Students can un-mark (delete their row).

### C.5 Reviews
```sql
CREATE TABLE course_reviews (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    class_id            uuid NOT NULL,
    student_member_id   uuid NOT NULL,
    rating              smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment             text CHECK (char_length(comment) <= 2000),
    status              text NOT NULL DEFAULT 'visible' CHECK (status IN ('visible','hidden')),
    hidden_reason       text,                                  -- staff moderation
    instructor_reply    text CHECK (char_length(instructor_reply) <= 2000),
    replied_at          timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (class_id, student_member_id),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, class_id)          REFERENCES classes (tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id)
);
```
- Only a student with an **active grant** on the course may review; one review per student, editable.
- Recompute `classes.rating_avg/rating_count` from visible reviews in the same transaction.
- Refunded students' reviews are hidden automatically.
- Public reviews show rating, comment, date and the reviewer's first name + initial only.

### C.6 Certificates
```sql
CREATE TABLE certificates (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               uuid NOT NULL,
    class_id                uuid NOT NULL,
    student_member_id       uuid NOT NULL,
    certificate_no          text NOT NULL UNIQUE,              -- 'EZC-7KQ4-M2XD', random, not sequential
    student_name            text NOT NULL,                     -- snapshots at issue time
    course_title            text NOT NULL,
    instructor_name         text NOT NULL,
    total_video_seconds     integer NOT NULL,
    issued_at               timestamptz NOT NULL DEFAULT now(),
    revoked_at              timestamptz,
    revoke_reason           text,
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, class_id)          REFERENCES classes (tenant_id, id),
    FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id)
);
CREATE UNIQUE INDEX uq_certificate_active ON certificates (class_id, student_member_id) WHERE revoked_at IS NULL;
```
- Issued when progress reaches 100% on a **paid** course only. Free courses and courses obtained through a
  100% coupon or manual grant get no certificate (settled 2026-11-02).
- Public verification at `/certificates/<certificate_no>` through a narrow `SECURITY DEFINER` function that
  returns only the snapshot fields + issued/revoked status.
- PDF generated on request (server-side), A4 landscape, with a QR code to the verify page.
- Revoked on refund.

### C.7 Coupons
```sql
CREATE TABLE coupons (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    class_id            uuid,                                  -- NULL = all of this tenant's courses
    code                citext NOT NULL CHECK (code ~* '^[A-Z0-9-]{4,20}$'),
    discount_type       text NOT NULL CHECK (discount_type IN ('percent','fixed')),
    percent_bps         integer CHECK (percent_bps BETWEEN 1 AND 10000),
    amount_cents        bigint CHECK (amount_cents > 0),
    is_public           boolean NOT NULL DEFAULT false,        -- true = auto-applied "sale price" shown on the page
    max_redemptions     integer CHECK (max_redemptions > 0),   -- NULL = unlimited
    redeemed_count      integer NOT NULL DEFAULT 0,
    starts_at           timestamptz NOT NULL DEFAULT now(),
    ends_at             timestamptz NOT NULL,                  -- coupons always expire (max 90 days, service rule)
    status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
    created_by          uuid NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, code),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, class_id)   REFERENCES classes (tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, created_by) REFERENCES tenant_members (tenant_id, id),
    CHECK ((discount_type = 'percent' AND percent_bps IS NOT NULL AND amount_cents IS NULL)
        OR (discount_type = 'fixed'   AND amount_cents IS NOT NULL AND percent_bps IS NULL))
);

ALTER TABLE order_items
    ADD COLUMN list_price_cents bigint CHECK (list_price_cents >= 0),
    ADD COLUMN discount_cents   bigint NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
    ADD COLUMN coupon_id        uuid,
    ADD FOREIGN KEY (tenant_id, coupon_id) REFERENCES coupons (tenant_id, id);
-- order_items.amount_cents stays the amount actually paid = list_price_cents - discount_cents
```
Rules:
- v1: coupons apply to **courses only**. A code only discounts items of its own tenant (multi-teacher cart).
- Best single discount per item (a typed code or the public sale coupon, whichever is lower); no stacking.
- Discount rounding: `(price * percent_bps + 5000) // 10000`; the paid price never goes below 0.
- **Commission is charged on the paid amount** (`amount_cents`), as today.
- `redeemed_count` is incremented in the **webhook fulfilment transaction**, not at checkout. Checkout
  re-validates; a paid order is always honoured even if the limit was reached in the meantime.

### C.8 Wishlist
```sql
CREATE TABLE wishlist_items (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   uuid NOT NULL,
    class_id    uuid NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, class_id),
    FOREIGN KEY (tenant_id, class_id) REFERENCES classes (tenant_id, id) ON DELETE CASCADE
);
ALTER TABLE wishlist_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE wishlist_items FORCE ROW LEVEL SECURITY;
CREATE POLICY wishlist_owner ON wishlist_items
    USING (user_id = current_user_id()) WITH CHECK (user_id = current_user_id());
```
Instructors see only a **count** per course (from an admin-role job or a counting function), never who.

### C.10 Commission rates and scheduled changes
Commission becomes **per product type** with a per-tenant override, and every change is **scheduled with
notice**. `order_items.commission_bps` stays the snapshot at purchase, so a change never rewrites past sales.
```sql
-- Platform defaults per product type (one row each)
CREATE TABLE platform_commission_rates (
    kind            text PRIMARY KEY CHECK (kind IN ('tuition','course')),
    commission_bps  integer NOT NULL CHECK (commission_bps BETWEEN 0 AND 10000),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
INSERT INTO platform_commission_rates VALUES ('tuition', 2000, now()), ('course', 2000, now());

-- Per-tenant override per product type (NULL = use the platform default).
-- tenants.commission_bps is kept for now as the tuition override; migrate it into these columns.
ALTER TABLE tenants
    ADD COLUMN tuition_commission_bps integer CHECK (tuition_commission_bps BETWEEN 0 AND 10000),
    ADD COLUMN course_commission_bps  integer CHECK (course_commission_bps  BETWEEN 0 AND 10000);

-- Every change, announced in advance and applied on its effective date
CREATE TABLE commission_changes (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scope               text NOT NULL CHECK (scope IN ('platform','tenant')),
    tenant_id           uuid REFERENCES tenants(id),           -- set when scope = 'tenant'
    kind                text NOT NULL CHECK (kind IN ('tuition','course')),
    old_bps             integer NOT NULL CHECK (old_bps BETWEEN 0 AND 10000),
    new_bps             integer NOT NULL CHECK (new_bps BETWEEN 0 AND 10000),
    reason              text NOT NULL,
    announced_at        timestamptz NOT NULL DEFAULT now(),
    effective_at        timestamptz NOT NULL,
    status              text NOT NULL DEFAULT 'scheduled'
                        CHECK (status IN ('scheduled','applied','cancelled')),
    applied_at          timestamptz,
    created_by          uuid NOT NULL REFERENCES users(id),    -- platform admin
    cancelled_by        uuid REFERENCES users(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK ((scope = 'platform' AND tenant_id IS NULL) OR (scope = 'tenant' AND tenant_id IS NOT NULL)),
    CHECK (effective_at > announced_at)
);
CREATE INDEX idx_commission_changes_due ON commission_changes (effective_at) WHERE status = 'scheduled';
-- Tenants read their own and platform-wide rows (policy); only eduzone_admin writes.
```
Rules:
- **Rate used at checkout:** tenant override for the item's kind if set, else the platform default.
  Snapshot into `order_items.commission_bps` (unchanged rule).
- **Notice period:** a platform setting `COMMISSION_NOTICE_DAYS` = **30 days** (settled 2026-11-02). An **increase** must have `effective_at ≥ announced_at + notice`. A **decrease** may take
  effect sooner (it only helps the tenant).
- **Announcement:** on scheduling, every affected tenant owner gets an email and a banner in the console
  (`/teach/<tenant>/money`) showing the old rate, new rate, effective date and reason. The admin app shows
  who was notified.
- **Applying:** a daily job (as `eduzone_admin`) applies due changes in one transaction: update the default
  or override, set `status = 'applied'`, write `audit_logs`. Checkouts created before the effective time
  keep the old rate even if paid after it (rate is fixed when the checkout is created).
- **Cancelling** is allowed until the effective date, with a notice to the same tenants.
- Only one scheduled change per `(scope, tenant_id, kind)` at a time.
- Teacher terms wording (notice period, refunds, certificates) is **deferred until after the build**; build the
  mechanism now and keep the terms page as draft text.
- Tests: an increase with less notice is rejected; due changes apply once; the snapshot on old orders is
  unchanged; a checkout created before the change keeps the old rate.

### C.9 RLS and tests
- Add `course_sections`, `lesson_completions`, `course_reviews`, `certificates`, `coupons` to the
  `tenant_isolation` list.
- Student own-rows policies (pattern 17.3) for `lesson_completions`, `course_reviews`, `certificates`.
- Extend the public catalog function (17.6) with course fields: kind, subtitle, category, level, language,
  objectives, requirements, audience, length, lecture count, rating, curriculum titles + durations
  (no article bodies, no resource links), public sale price, and visible reviews.
- Required new tests: isolation for each new table; own-rows for completions/reviews/certificates;
  catalog exposes no article bodies or resource URLs; coupon maths and limits; commission on the discounted
  amount; certificate verify returns snapshot fields only; refund revokes grant + certificate + hides review.

---

## 5. Access rule (update)
Unchanged function, one addition: a course behaves like a one-time class — an active `access_grants` row for
`(student, class_id)` with `class_month_id IS NULL` opens every published lecture. Free-preview lectures are
open to everyone. Free courses grant access on "Enrol".

---

## 6. URLs and screens

Reserve these slugs (add to CLAUDE.md §5.9): `course`, `courses`, `instructor`, `certificates`, `wishlist`, `categories`.

| URL | Screen |
|---|---|
| `/` | Home gets two lanes: **Tuition classes** (as now) and **Courses** (categories, popular, top rated, new) |
| `/courses` | Course catalogue: search; filters in the URL: category, level, language, price (free/paid/max), rating (3.5+, 4+, 4.5+), length (0–2 h, 2–6 h, 6–17 h, 17 h+); sort: popular, top rated, newest, price |
| `/courses/<category>[/<sub>]` | Category page |
| `/course/<slug>` | **Landing page**: title, subtitle, rating, students, instructor, last updated, language; promo video; "What you'll learn"; curriculum (sections, lectures, durations, preview links); requirements; description; who it's for; instructor card; reviews; sticky price card (sale price, coupon field, Add to cart, Buy now, Wishlist, "Lifetime access", lectures, hours, certificate) |
| `/instructor/<teacher-slug>` | One page per person: all their courses and tuition classes |
| `/learn` | My learning: "Continue learning" tiles with progress bars, alongside tuition classes |
| `/learn/courses/<slug>` | **Course player**: video/article in the main area, curriculum sidebar with ticks and section progress, mark complete, next/previous, resources, progress %, welcome/completion message, "Leave a rating" prompt after ~25% |
| `/learn/wishlist`, `/learn/certificates` | Wishlist; certificates (download PDF, copy verify link) |
| `/certificates/<no>` | Public verification page |
| `/teach/<tenant>/courses/...` | Course builder: Landing page · Intended learners · Curriculum (drag-and-drop sections and lectures) · Pricing · Coupons · Messages · Submit for review |
| `/teach/<tenant>/courses/<id>/insights` | Analytics (section 10) |
| Admin app | Course review queue, categories, review moderation, refund queue |

Teacher pages at `/<subject>/<teacher>` stay for tuition; they link to `/instructor/<teacher-slug>`.

---

## 7. Publishing a course

**Automated checks** before "Submit for review" is allowed (Udemy minimums, adapted):
- At least **5 published lectures** and **30 minutes of video**; every video `ready`.
- Title, subtitle, description of **at least 100 words** (works for Sinhala/Tamil), cover image, category,
  level, language.
- **At least 4 learning objectives**, at least 1 requirement (may be "No prior experience needed"), at least
  1 "who this course is for".
- Price set (or free); instructor profile has a photo and bio.
- Tenant approved and active.

**Review:** `draft → in_review → published`. EduZone staff review the **first publish of each course**
(approve, or request changes with `review_note` → back to `draft`). After that, curriculum and landing-page
edits go live without review; staff can unpublish at any time (audited).

---

## 8. Checkout (update)
- Courses use the existing cart and checkout; an item is `class_id` with no month.
- At cart/checkout, apply the public sale coupon automatically and a typed code if valid (per tenant).
- `order_items` records `list_price_cents`, `discount_cents`, `coupon_id`, `amount_cents` (paid).
- Fulfilment (webhook transaction) adds: course `access_grants` (no expiry), `coupons.redeemed_count + 1`.
- Already owning a course blocks adding it again (same rule as months).

---

## 9. Refunds (courses)
Refunds are not built yet for anything; build them here and reuse for tuition later.
- A student can request a course refund **within 7 days of purchase if under 30% of the course is complete**
  and no certificate was issued (settled 2026-11-02).
- Requests that meet the rule **and** the student has fewer than 3 refunds in the last 90 days are approved
  automatically; others go to the EduZone refund queue.
- Processing: gateway partial refund on the checkout's payment (PayHere refund API, check in the sandbox) →
  `refunds` row → ledger `refund` posting (existing builder) → revoke the grant → revoke any certificate →
  hide the review → order item marked refunded. Exactly once, idempotent.
- **Payout hold:** a payout may not include course sales still inside the refund window. Available balance =
  ledger balance − net course sales of the last 7 days. Show "pending" vs "available" in the tenant's Money page.

---

## 10. Instructor analytics (basic)
Per course and per month, from existing data: enrolments (paid / free / coupon), revenue gross and net
(from the ledger, by `order_items.class_id`), refunds, average rating and count, completion rate (students at
100% ÷ enrolled), wishlist count, top coupons. Per-lecture drop-off comes later.

---

## 11. Content protection for courses
Keep the platform rules (one device per student, moving watermark, signed short-lived URLs, no download).
`max_video_views` is unlimited by default for courses. Revisit the watermark text (name + phone) after the
pilot if course buyers object.

---

## 12. Open decisions

| Decision | Recommendation |
|---|---|
| Legal wording in teacher/student terms | After the build |
| Lower commission for instructor-referred sales | Later (own coupon/link), via the same scheduled-change mechanism |
| USD pricing | Later; PayHere supports it |
| Volume vs standard Bunny network for courses | Decide after a playback test from Sri Lanka |

---

## 13. Build order (courses)

Each step includes its console/student/admin screens and tests. Tuition work is not blocked.

| Step | Scope |
|---|---|
| **C1** ✅ | Migrations C.1–C.3; categories in admin; course builder (landing page, intended learners, curriculum with sections, article lectures, pricing); automated publish checks; review queue in admin |
| **C2** ✅ | Public catalog for courses: `/courses`, category pages, `/course/<slug>` landing page, `/instructor/<slug>`, home lanes, SEO (JSON-LD `Course`, sitemap) |
| **C3** ✅ | Cart/checkout for courses; course player; `lesson_completions`; progress; My learning; welcome/completion messages |
| **C4** | Reviews and ratings (student, instructor reply, staff moderation); certificates (issue, PDF, public verify) |
| **C5** | Coupons (incl. public sale price) and wishlist |
| **C6** | Refunds (gateway call, auto-approval rule, refund queue, ledger, payout hold) |
| **C7** | Instructor analytics; commission rates per product type + scheduled changes with notice (C.10), admin screen and tenant banner |
| Later | Quizzes, assignments, Q&A, announcements, notes, USD, per-lecture analytics |

---

## 14. Company training (v1.1) reuses courses

Company sites (`<company>.eduzone.switchops.tech`, `site_type = 'company'`) deliver **trainings**, which are
courses: sections, lectures, progress, completion. They do **not** use months, live-class schedules or
late-month requests. So the course work in C1–C4 is the foundation for v1.1, and must be built to work for
both site types.

| Course feature | Marketplace | Company site |
|---|---|---|
| Course builder (sections, lectures, articles, PDFs) | `/teach/<tenant>/courses` | Same components under `/manage/courses` |
| Landing page fields | Required for publishing | Optional (title, description, objectives enough) |
| Staff review by EduZone | First publish | **None** (private to the company) |
| Listed in marketplace | Yes | **Never** (catalog function already excludes `site_type = 'company'`) |
| Access | Purchase or free enrol → `access_grants` | **Assignment** by a company admin, or self-enrol in the company catalogue → `access_grants` with `source = 'assignment'` |
| Price, cart, checkout, coupons, refunds, wishlist | Yes | **No** (company pays a subscription; learning is free to staff) |
| Progress and completion (`lesson_completions`) | Yes | Yes, plus **due dates** and overdue status |
| Certificates | Paid courses only | **Yes on completion**, company name on the certificate (company setting) |
| Reviews and ratings | Yes | Off by default |
| Reports | Instructor analytics | **Completion reports** per course, department, person; CSV export |
| Quizzes (later) | Optional | Needed sooner (pass mark counts towards completion) |

Rules for C1–C4 so v1.1 drops in cleanly:
- Course services must not assume a checkout: access always comes from `access_grants`, whatever its source.
- Keep course-builder UI components free of marketplace-only fields, or hide those fields by `site_type`.
- Add `'assignment'` to `access_grants.source` in v1.1 (not now), with a `course_assignments` table
  (`tenant_id, class_id, member_id or group, assigned_by, due_at, status`).
- The certificate rule becomes: issue if **paid** (marketplace) or **site_type = 'company'**.
- `/learn/courses/<slug>` player is shared; on a company host it shows the company branding.

**Marketplace courses and companies (settled 2026-11-02):** there are **no bulk seat deals** or company
licences for marketplace courses. Anyone, including company staff, buys a marketplace course on the
marketplace as an ordinary student: normal price, normal checkout, normal 20% commission. Company sites show
only the company's own trainings.
