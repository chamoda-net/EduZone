# EduZone on your machine: run it, sign in, explore

Everything built so far (migration phases 1–8), how to start it yourself, the demo accounts, and a tour of what
to try. Written 2026-11-02, after phase 8 (commit `1fb5835`).

---

## 1. What runs where

| What | Address | Started by |
|---|---|---|
| Database (PostgreSQL 16) | `localhost:54393` | `tools/dev-db` (no Docker needed) |
| API (FastAPI) | http://localhost:8000 (docs at http://localhost:8000/docs) | `uvicorn` in `backend/` |
| Website: marketplace, student area, teacher console | **http://localhost:3000** | `npm run dev:web` in `frontend/` |
| Platform admin (EduZone staff) | **http://localhost:3001** | `npm run dev:admin` in `frontend/` |

Always open the sites as **`localhost`**, not `127.0.0.1`. The dev servers only serve their scripts to `localhost`;
on `127.0.0.1` pages show but buttons and forms don't work.

Nothing leaves your machine locally: SMS codes and emails are **printed in the API's terminal**, payments go
through a **fake gateway** page, and lesson videos play from a public test stream.

---

## 2. Start the servers yourself

You need four terminals (PowerShell or Git Bash). Start them in this order.

### First time only

```powershell
# 1. Database tools (downloads PostgreSQL once, ~100 MB)
cd D:\EduZone\tools\dev-db
npm install

# 2. Backend
cd D:\EduZone\backend
python -m venv .venv            # skip if .venv already exists
.venv\Scripts\pip install -e ".[dev]"

# 3. Frontend
cd D:\EduZone\frontend
npm install
```

`D:\EduZone\.env` must exist (copy `.env.example` and fill it in; yours is already set up). The database tool
reads its port and passwords from it.

### Every day

**Terminal 1: database** (leave it running)
```powershell
cd D:\EduZone\tools\dev-db
npm start
```
Wait for `READY: PostgreSQL on localhost:54393`.

**Terminal 2: API** (leave it running; SMS codes and emails appear here)
```powershell
cd D:\EduZone\backend
.venv\Scripts\alembic upgrade head      # only needed after pulling new migrations; harmless otherwise
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

**Terminal 3: website**
```powershell
cd D:\EduZone\frontend
npm run dev:web
```

**Terminal 4: admin app**
```powershell
cd D:\EduZone\frontend
npm run dev:admin
```

Open http://localhost:3000 and http://localhost:3001. Stop any server with **Ctrl+C**.

### A brand-new, empty database

If `tools/dev-db/data` doesn't exist, `npm start` creates a fresh database. Then fill it:

```powershell
cd D:\EduZone\backend
.venv\Scripts\alembic upgrade head
.venv\Scripts\python scripts\seed_demo.py          # demo institute, owner, teacher, student, physics class
.venv\Scripts\python scripts\seed_market.py        # a second teacher's organization + a chemistry teacher
.venv\Scripts\python scripts\create_platform_admin.py --phone +94779999999 --name "EduZone Staff (local)"
```

The last command prints an **authenticator setup link**: open it on your phone with Google Authenticator,
Microsoft Authenticator or similar (or type the printed secret into the app). Both seed scripts are safe to run
again.

To start over completely: stop the database, delete `tools/dev-db/data`, and run the commands above.

### Checks and tests

```powershell
cd D:\EduZone\backend;  .venv\Scripts\pytest            # 225 tests, real database, ~2 minutes
cd D:\EduZone\frontend; npm run typecheck; npm run lint
cd D:\EduZone\frontend; npm run e2e                     # 7 browser tests; starts its own servers on 8010/3010
```
The tests need the database running (terminal 1). The e2e suite can run while your dev servers are up.

---

## 3. Demo accounts

All demo accounts use **the same local test password**: the value of `DEMO_PASSWORD` in
[backend/scripts/seed_demo.py](../backend/scripts/seed_demo.py) (line 31, the text between the quotes). Type the
value itself, not the word `DEMO_PASSWORD`.

| Who | Email | Phone | What they can do |
|---|---|---|---|
| Student | `student.demo@example.com` | +94 77 000 0003 | Nimali Perera. In the physics class with November paid; has bought more through the cart |
| Teacher | `teacher.demo@example.com` | +94 77 000 0002 | Kasun Perera, teaches physics at the demo institute |
| Owner | `owner.demo@example.com` | +94 77 000 0001 | Owner of **Demo Tuition Institute**: sees money, earnings, every class |
| Platform admin | (signs in by phone) | +94 77 999 9999 | EduZone staff, in the admin app only |

**The SMS code.** The first sign-in in a browser counts as a new device, so after the password the site asks
for a 6-digit code. Find it in **terminal 2 (API)**, in a line like `SMS to +94770000003: 123456 is your EduZone
code…`. Codes expire after 5 minutes; press "Send a new code" for another (one per minute).

**One device at a time.** Signing a student in somewhere new signs them out of the old browser ("You were signed
out"). Staff (owner, teacher) are exempt. To be student and teacher at once, use two browsers or a private
window.

**Admin sign-in** (http://localhost:3001): phone `+94779999999` → the SMS code from terminal 2 → the 6-digit code
from your authenticator app. If you never set up the authenticator, run `create_platform_admin.py` again (above):
it prints a new setup link.

Other people in the data (no password, they can't sign in): Dilini Fernando (owner of *Dilini Fernando Maths*),
Ruwan Silva (chemistry teacher at the demo institute), and many "E2E Student" and "E2E Physics …" accounts and
organizations left behind by the browser tests.

**Make your own student:** http://localhost:3000/register with any email and a phone like `0771234567`; the
confirmation code is in terminal 2.

---

## 4. The demo data

| Organization | Type | Teacher(s) | Classes |
|---|---|---|---|
| Demo Tuition Institute (`demo`) | Institute | Kasun Perera (physics), Ruwan Silva (chemistry) | **2027 A/L Physics - Theory** (Rs. 2,000/month): October *closed*, November *open*, December *upcoming*; each month a live Zoom class and a tute; November also has **Recording: Motion in one dimension** (a video). **2027 A/L Chemistry - Theory** (Rs. 2,200/month). **Grade 5 Scholarship Paper Class** (one-time Rs. 3,500, *draft*, not public) |
| Dilini Fernando Maths (`dilini-maths`) | Individual teacher | Dilini Fernando | **2026 A/L Combined Maths - Theory** (Rs. 2,500/month), **2027 O/L Mathematics** (Rs. 1,500/month) |
| E2E Physics … | Individual, *pending* | (test applicants) | Teacher applications waiting for review in the admin app |

Months: **open** = buy directly; **closed** = a past month, the student must ask and the teacher approve first;
**upcoming** = not for sale yet.

---

## 5. A guided tour

### A. As a visitor (no account): http://localhost:3000
1. **Home**: search box, exam tabs (Grade 5 / O/L / A/L), subjects, "Starting now", popular classes.
2. Search `chemistry` → the **catalogue** (`/classes`) with filters (subject, exam year, medium, format, max fee,
   sort). Filters live in the address bar, so a filtered list can be shared.
3. Open a class → the **class page** (`/chemistry/ruwan-silva/2027-al-chemistry`): months with prices, lesson
   outline (no Zoom links), teacher card, **Add to cart**.
4. Click the teacher → the **teacher page** (`/physics/kasun-perera`): headline, bio, highlights, classes,
   **share tools** (WhatsApp, copy link, QR code you can download for posters).
5. `/teachers`, `/institutes`, `/institutes/demo`, a subject page like `/physics`.
6. Add months from **two teachers** to the cart → `/cart` works without an account (kept in a cookie).
7. Footer pages: About, Terms, Privacy, Refund policy, Contact (draft wording).

### B. As the student (`student.demo@example.com`)
1. Sign in (password, then the SMS code). Your guest cart is merged into your account.
2. **Today** (`/learn`): next live classes, months ready to pay, requests waiting.
3. **My classes** → *2027 A/L Physics*: each month shows its state: *You have access* (November), *Past month*
   (October: **Ask the teacher**), *Opens soon* (December).
4. Open November's **Live class** lesson: the **Join on Zoom** button appears only because November is paid.
5. Open **Recording: Motion in one dimension** → **our own video player**: your name and phone drift over the video
   as a watermark; speed, quality, ±10 s, full screen (watermark stays), keyboard keys (Space, J/L, F, M). Watch a
   bit, leave, come back: it offers **Continue at …**. Watching 90% marks it ✓ watched. Views are counted per
   class limit.
6. **Cart and one payment:** add a month from another teacher (e.g. Dilini's O/L Maths), open `/cart` → **Pay**
   → the **fake gateway** page: *Pay* (success), *Card declined*, or *Cancel*. One payment, one order per
   organization, a combined receipt (`/checkouts/<id>`).
7. **Payments** (`/learn/payments`): every order with a printable receipt.
8. **Requests** (`/learn/requests`): past-month requests and the teacher's answers.
9. **Schedule** (`/learn/schedule`): live classes from all teachers for 30 days.
10. **Profile** (`/learn/profile`): name, exam, school, phone and email status, reset password.
11. Try the **one-device rule**: sign the student in from a private window, then go back to the first browser.

### C. As the teacher (`teacher.demo@example.com`), then the owner (`owner.demo@example.com`)
1. Sign in → `/teach` → the console for **Demo Tuition Institute** (`/teach/demo/classes`).
2. **Classes**: create a class (subject, exam, medium, monthly/one-time/free price), publish, archive.
3. Inside a class: **months** (add, open, close, fee per month), **lessons** (live with date and Zoom link,
   recorded, tute; show/hide; free preview), **lesson files** from the media library.
4. **Students** card on a class: who joined and who paid for a chosen month; **Give access** (manual or
   scholarship); remove access (not paid access).
5. **Requests**: approve or decline a student's past-month request (then the student can pay).
6. **Media**: upload a video or PDF. (Uploading needs a Bunny account, so locally it says storage isn't set up.)
7. **Payments**: orders for the organization (a teacher sees only their own classes).
8. **Earnings**: per-teacher net for a month (owner sees every teacher; a teacher sees their own line).
9. **Money** (owner only): balance EduZone owes, monthly cash flow: sales, refunds, gateway fees, commission and
   net (after refunds), payouts.
10. **Public profile** (`/teach/demo/profile`): edit the teacher page (name, link, headline, bio, highlights,
    photo link) and share it.

### C2. Build a course (teacher or owner): new in step C1
1. In the console, open **Courses** → **New course**: a title and a category.
2. The builder has five tabs: **Landing page** (subtitle, description with a word counter, category, level,
   language, cover image link, promo video), **Intended learners** (what students will learn, requirements, who
   it is for), **Curriculum** (sections and lectures: video, article or PDF; attach files; move up and down; hide;
   free preview), **Pricing** (free or a one-time price) and **Messages**.
3. The **Before you submit** checklist on the right shows what is missing; each item links to the tab that fixes
   it. Video length counts only processed videos the teacher uploaded themselves (Media), so locally you need Bunny
   or a test video to reach 30 minutes.
4. **Submit for review**: the course is locked until EduZone decides. In the admin app, **Course reviews** shows it;
   **Approve and publish** or **Request changes** (with a note the instructor sees). After approval, edits go live
   at once; **Unpublish** and **Publish again** need no review. Courses are not on the marketplace or for sale yet
   (steps C2 and C3).
5. Admin app → **Course categories**: add top categories and subcategories, rename, reorder, hide.

### C3. Browse courses (anyone): new in step C2
1. **Courses** in the header, or http://localhost:3000/courses: search, filters (category, level, language, price,
   rating, length) and sorting; category chips at the top.
2. Open **A/L Physics: Problem Solving Masterclass** (`/course/al-physics-problem-solving`): what you'll learn, the
   curriculum by section, requirements, description, who it's for, the instructor, and a price card.
3. **Preview this course** (on the cover) or a lecture's **Preview** link plays the promo video and the free-preview
   lectures without an account (locally a public test stream).
4. A category page: http://localhost:3000/courses/exam-skills. An instructor page:
   http://localhost:3000/instructor/kasun-perera (courses and live classes together).
5. The home page has a **Popular courses** lane. Re-run `scripts/seed_market.py` if you don't see the two demo
   courses.

### C4. Take a course (student): new in step C3
1. On **Mental Maths Shortcuts (Free)** press **Enrol for free** (sign in first): the player opens.
2. On **A/L Physics: Problem Solving Masterclass** press **Buy now** (or **Add to cart**), pay with the fake gateway;
   the receipt's **Open course** goes to the player.
3. The player (`/learn/courses/<id>`): video lectures play in our player and tick themselves off once you've watched
   most of them; articles and PDFs have **Mark as complete**. The sidebar shows every section with ticks; the top
   bar shows your progress. A welcome message shows at the start and a congratulations message at 100%.
4. **My learning** → **My courses** (or "Continue learning" on Today) lists your courses with progress bars.

### D. Become a teacher (any new account)
1. Register a new account at `/register` and confirm the phone.
2. Go to `/teach` → **Apply** (`/teach/apply`): teacher or institute, name, subjects, experience, identity
   document (PDF/JPG/PNG), bank details. Submit.
3. You get a console in **draft mode**: build classes and lessons, but **Publish** says to wait for approval.
4. Approve it in the admin app (section E), come back: now you can publish, and your page is public.

### E. As EduZone staff: http://localhost:3001
1. **Organizations**: every organization with balance owed, sales this month, students, storage. Open one:
   - **Marketplace listing**: *Unlist* hides it and its classes from the marketplace (console and students keep
     working), *List again* brings it back.
   - **Record a payout** (money already sent; posted to the ledger; can't exceed the balance), payout history.
   - Edit: status (active/suspended/closed), commission %, who pays gateway fees, Bunny library, limits, bank.
   - Links to its payments and its audit log.
   - **New organization** creates one with an owner email.
2. **Applications**: teacher applications waiting for review. Open one: details, **Open document** (audited),
   **Show full number** for the bank account (audited), then **Approve**, **Request changes** (with a note the
   applicant sees) or **Reject**.
3. **Subjects**: add (name, address, order), rename, reorder, hide/show. The address is fixed once created.
4. **Users**: search by email, phone (`0003` finds +94770000003) or name. A user's page shows their
   organizations, **trusted devices** (Forget) and **sessions** (Sign out everywhere).
5. **Checkouts**: every cart payment. *Needs a retry* lists checkouts paid at the gateway where an order failed;
   **Retry fulfilment** finishes them without booking anything twice.
6. **Payments**: every order across organizations.
7. **Audit log**: every change by staff, EduZone and the system, filterable; linked from organizations, users and
   checkouts.

---

## 6. Every feature built so far

### Marketplace (phase 4)
- Home with search, exam tabs, subjects, "starting now", popular classes, counts.
- Catalogue `/classes` with search and filters (q, exam, subject, year, medium, format, max fee, sort,
  organization) in the URL; paging.
- Subject pages `/<subject>`, teacher pages `/<subject>/<teacher>` (one per subject taught), class pages
  `/<subject>/<teacher>/<class>`, `/teachers`, `/institutes`, `/institutes/<slug>`.
- Teacher profiles: one per person across organizations (slug unique platform-wide), headline, bio, highlights,
  photo link; created when their first class with a subject is published; editor in the console.
- Share tools: WhatsApp, copy link, QR code (SVG download); Open Graph images for teacher and class pages;
  JSON-LD (`Person`, `Course`); `sitemap.xml`, `robots.txt`.
- Static pages: about, terms, privacy, refund policy, contact (draft, pending legal review).
- Only active, listed organizations, published classes with a subject and teacher profile, and active subjects
  appear; Zoom links, lesson descriptions and money settings never do (one narrow read path, tested).
- Old per-organization subdomains redirect to the marketplace.

### Accounts and sign-in (phase 2)
- One account across all teachers: register with email + password (8+ chars, argon2id hash), or Google (when a
  Google client ID is configured).
- Mobile number required, unique, confirmed once by SMS code (local forms like `0771234567` accepted).
- SMS code on a **new device**; trusted devices skip it.
- **One device per student**: a new sign-in signs out the old device, which explains why. Staff exempt.
- Email verification link; password recovery by email link + SMS code (signs out everywhere).
- Throttling: wrong passwords per email and IP; SMS limits (60 s cooldown, 5 per number per hour, 20 per IP per
  hour, 5 wrong guesses lock a code).
- Short-lived access tokens + rotating refresh tokens, only in httpOnly cookies; sessions checked on every request.

### Student area `/learn` (phases 3, 6, 7)
- Today, My classes, class page with per-month access states (granted, buy, upcoming, past month/request,
  pending, approved, rejected, unavailable), join/leave a class (free classes give access on joining).
- Past-month requests: one per month, only for closed months of classes that allow it.
- Lessons: Zoom button, recordings and PDF tutes **only for paid months** (or free previews).
- Our own **hls.js video player**: signed short-lived stream, watermark (name + phone, moves every ~20 s, kept in
  full screen), resume, speed, quality, keyboard shortcuts, progress saved every 15 s, ✓ watched at 90%, view
  limit per class, no download / picture-in-picture.
- PDFs open through short-lived signed links.
- Schedule (30 days), requests, payments with printable receipts, profile.

### Cart and payments (steps 7, phase 6)
- Cart across teachers (up to 20 items), guest cart in a cookie merged at sign-in, header badge, problems shown
  per item (already have it, past month needs approval, not open yet…).
- One checkout → one gateway payment → one order per item, each in its own organization; gateway fee split
  exactly across orders; each order fulfilled in its own transaction (access grant, late request fulfilled,
  ledger sale), idempotent; a failed one is retried (webhook redelivery or the admin's Retry button).
- Single-item Pay button still works. Payment needs a confirmed phone.
- Gateways behind one interface: **PayHere** (written, to be checked against its sandbox) and the **fake gateway**
  for local use. The browser's return page never grants access; it only polls.
- Webhook stores the raw event first, checks the signature, amount and currency.

### Money and the ledger (steps 7–9)
- All money in integer cents, rates in basis points, commission rounded half up, default 20% per organization.
- Append-only, balanced double-entry ledger (database triggers): sale, fee true-up, refund (builders), payout
  postings; each payment/payout booked once.
- Organization cash flow (sales, refunds, gateway fees, commission and net after refunds, payouts, balance due),
  per-teacher earnings for institutes, who bears gateway fees (organization or EduZone).
- Payouts recorded by EduZone staff, never above the balance due.

### Teacher console `/teach/<organization>` (steps 4–8, phases 3–5)
- Workspace picker when you're staff of several organizations; owner/admin/teacher roles (teachers manage only
  their own classes; anything else is a 404).
- Classes (draft → published ⇄ archived), months, lessons, lesson files; subject picker.
- Media library: video upload straight to Bunny (resumable), PDFs to Bunny Storage, processing status, preview,
  storage quota, delete when unused. (Needs Bunny keys; not configured locally.)
- Students per month, manual and scholarship access, late-month inbox, payments, earnings, money (owners/admins),
  public profile editor with share tools.

### Becoming a teacher (phase 5)
- Application form (teacher or institute, subjects, experience, identity document, bank details) → organization
  created in **draft mode** (pending) → build classes meanwhile → EduZone approves / requests changes / rejects.
- Document kept in private storage (only staff can open it, audited); account number encrypted, shown masked.

### Courses, step C1 (docs/COURSES.md)
- Course builder in the console: landing page, intended learners, curriculum (sections; video, article and PDF
  lectures; files; reorder; hide; free preview), pricing (free or one-time), messages.
- Automatic publish checks with a checklist; first publish reviewed by EduZone (approve or request changes with a
  note); later edits live at once; unpublish and publish again; withdraw from review.
- Course categories (two levels) managed in the admin app; applications say classes, courses or both.
- Course pages on the marketplace (step C2): catalogue with filters, category pages, landing page with free
  previews, instructor pages, home lane, sitemap and JSON-LD.
- Buying and taking courses (step C3): cart and checkout, free enrolment, the course player with a curriculum
  sidebar, lecture completion and progress, My courses, welcome and congratulations messages.
- Not yet: reviews and certificates (C4),
  coupons and wishlist (C5), refunds (C6), analytics and commission changes (C7).

### Platform admin (step 9, phases 5 and 8)
- Separate app, private network only (`PLATFORM_ALLOWED_CIDRS`), sign-in with SMS code + authenticator app,
  15-minute tokens, 12-hour sessions.
- Organizations (create, edit, suspend, list/unlist, payouts, usage), teacher applications, subjects, users and
  devices, checkouts with retry, payments, audit log.
- Its own deploy: Dockerfile building a standalone server, security headers (`docs/deploy-admin.md`).

### Foundations
- Multi-tenancy: every business table has `tenant_id` with forced row-level security; cross-tenant links blocked
  by composite foreign keys; user-scoped read policies for the student area and cart; isolation tests.
- Three database roles (app, admin, owner); hand-written migrations 0001–0009.
- Frontend monorepo: website, admin app, shared UI kit and design tokens (forest green, gold, Fraunces +
  Instrument Sans), next-intl text keys, generated API types, Playwright smoke tests.
- Every state-changing staff action is in the audit log.

---

## 7. Not built yet (or only partly)

- **Refunds** (the ledger builder exists; no gateway refund call or refund screen yet).
- **Real SMS and email providers** (they print to the API terminal locally).
- **Real Bunny account** checks (video upload, signed URLs and the HLS token formula must be verified against a
  real library); the daily Bunny usage sync and bandwidth warnings.
- **PayHere** sandbox check; an automatic retry job for stuck checkouts; fee true-up across a checkout's orders.
- Emails to teacher applicants on a decision; profile editor live preview; photo upload.
- Team invites for institutes; player data-saver and reduced-motion; caching of public pages.
- Sinhala/Tamil text, 360 px pass, low-end phone pass, accessibility pass (**phase 9**).
- Company sites on subdomains (v1.1).

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| "The server is not reachable" on the site | Start the API (terminal 2); check the database (terminal 1) is `READY` |
| API fails with "connection refused" to port 54393 | Start the database first |
| "The email or password is wrong" | Type the password's value from `seed_demo.py`, not the word `DEMO_PASSWORD`. Too many tries locks for a few minutes |
| No SMS code arrives | It's in the API terminal (terminal 2). Wait 60 s between codes |
| Buttons do nothing, page looks unstyled | Use `localhost`, not `127.0.0.1` |
| New pages or styles don't show in `npm run dev:*` | Stop it, delete `frontend/apps/web/.next` (or `apps/admin/.next`), start again |
| Admin sign-in fails | The authenticator code changes every 30 s and each code works once; check your phone's clock |
| "Video and file storage are not set up" in Media | Expected locally: uploads need Bunny keys. The demo recording plays from a test stream |
| A port is already in use | Another copy is running; close it, or find it with `netstat -ano | findstr :8000` |
