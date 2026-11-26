# Marketplace marketing audit (2026-11-26)

A first pass over the public marketplace, using the installed marketing skills (`.claude/skills/`: cro, copywriting,
seo-audit, programmatic-seo, schema, signup, ai-seo, site-architecture) against `.agents/product-marketing.md`.
Read from the code, not from analytics: there is no traffic yet, so every item is a hypothesis to check after the pilot.

Pages covered: home (`app/page.tsx`), subject (`app/[subject]`), teacher (`app/[subject]/[teacher]`), class
(`app/[subject]/[teacher]/[class]`), root layout, sitemap, robots, register, plus the copy in `en.ts`.

**What already works:** a clear promise ("month by month"), a three-step how-it-works, an FAQ that answers the real
objections (paying, joining late, missed classes), neutral heroes, share tools on teacher and class pages, JSON-LD on
teacher, class and course pages, a sitemap of every public page, and a short sign-up (name, email, password or Google,
with the phone asked only at checkout).

---

## P1: fix before the pilot (small, high impact)

**Done 2026-11-26** (all six): root metadata and home metadata, canonicals on every public page, robots, public
free previews (migration 0021), the schedule line, the buy-first button, the new headline and the stats threshold.
Correction: the cart and checkout pages already said noindex; only robots.txt was missing them.

### 1. The home page has no description, and the site has no `metadataBase`
`app/layout.tsx` sets only `title: "EduZone"`; `app/page.tsx` has no metadata. So the most important page has the
title "EduZone" and no meta description, and Google will write its own snippet.
- Add to the root layout: `metadataBase` (the main origin), a title template (`%s | EduZone`), a default description
  (reuse `about.meta`), `openGraph.siteName`, `locale: "en_LK"`.
- Give the home page its own title, e.g. "Online tuition classes for Grade 5, O/L and A/L | EduZone".
- Check a production build: the `opengraph-image.tsx` files on teacher and class pages need an absolute base URL, or
  their `og:image` points at the wrong host.

### 2. No canonical URLs
Nothing sets `alternates.canonical`. The subject page's `?exam=` filter, catalogue filters, tenant-subdomain
redirects and `?coupon=` links all create duplicate URLs. Set a canonical on every public page (path without query,
or with the one query that defines the page; see item 6).

### 3. Free previews of tuition lessons need a sign-in
On the class page a "Free preview" badge links to `/login?next=/learn/lessons/<id>`. A visitor deciding whether to
pay meets a sign-in wall at the moment of highest intent. Courses already play previews for anyone
(`POST /market/course/{slug}/preview`); do the same for tuition free-preview lessons, then ask for an account with
"Join this class" under the player.

### 4. The class page doesn't say *when* the class meets
For a live monthly class, "when is it?" is the first question, and the page answers it only through individual
lesson dates further down. Show the usual time in the price card and on class cards ("Saturdays, 8:00 am · Zoom"),
derived from the live lessons of the open month, or add a schedule field to the class form.

### 5. The guest's main button says "Sign in to join"
For a guest the primary button is about signing in, not about the class; "Add to cart" sits below it. Lead with the
outcome and the month: **"Join December – Rs. 2,500"** (adds to cart, then sign-in or register at checkout, which the
cart already handles). Keep "Already have an account? Sign in" as a text link. For signed-in students, "Join or pay"
is vague: say "Pay for December" or "Join for free".

### 6. Unproven claim in the hero
"Learn from Sri Lanka's best teachers" can't be backed yet, and the home page shows live counts right under it
(at the pilot: "4 classes · 2 teachers"). Either change the headline to something true on day one ("Online tuition
from Sri Lankan teachers, month by month") or hide the stats strip until the numbers are worth showing (for example
20+ classes).

---

## P2: SEO structure (the marketplace's main free channel)

### 7. Subject × exam × medium pages (programmatic SEO)
People search "A/L physics online class", "O/L maths Sinhala medium", "grade 5 scholarship online class". Today
the only subject page is `/<subject>`, its exam filter is a query string, and medium has no filter at all.
- Make indexable pages per subject and exam, e.g. `/physics/a-level`, `/maths/o-level`, `/grade-5-scholarship`.
  Route conflict: `/<subject>/<teacher>` already uses the second segment, so reserve the exam slugs
  (`a-level`, `o-level`, `grade-5`) in `is_reserved_slug()` for teacher slugs.
- Add medium as a filter (and later as a page segment when there are enough classes: `/physics/a-level/sinhala-medium`).
- Only publish a page that has at least one class (or noindex it), so the set never looks thin.

### 8. Subject pages are thin
A subject page is a name, two counts and cards. Add an EduZone-written intro per subject (a `description` on
`subjects`, edited in the admin app), a short FAQ, and links to the exam pages from item 7. This is also what AI
answers quote.

### 9. Structured data gaps
- Class pages use `Course` without `hasCourseInstance` (Google's course rich results need it: `courseMode: "online"`,
  `courseSchedule` / `startDate`) and without `provider` as an organization; the offer price is per month without
  saying so in a machine-readable way.
- No `BreadcrumbList` on subject, teacher and class pages (the class page already renders a breadcrumb).
- No `Organization` + `WebSite` on the home page.
- `FAQPage` on the home FAQ: no rich result for most sites now, but cheap and useful for AI answers.

### 10. Robots and indexing
`robots.ts` disallows sign-in and console paths but not `/cart`, `/checkouts`, `/checkout` (singular is there) or
`/certificates/<no>/pdf`. Add `/cart` and `/checkouts`, and `noindex` on those pages.

---

## P3: conversion and positioning (after the pilot gives real data)

### 11. Payment methods
The copy says "by card" in the FAQ, trust lines and how-it-works. Many students and parents in Sri Lanka don't have
a card. If the gateway offers more (PayHere offers mobile wallets and others), say so near the pay button; if not,
this is likely the biggest leak in the funnel and worth raising in the gateway decision.

### 12. Parents as buyers
For Grade 5 and many O/L students, the parent pays. The FAQ title names parents, but nothing else does. Ideas: a
"Send to a parent to pay" share of the cart, and a line about receipts per month near the price.

### 13. The one-device rule as an objection
The FAQ mentions "one device at a time" under "Can I learn on my phone?", which turns a yes into a doubt. Move it to
its own question ("Why can I use only one device?") and explain switching (an SMS code).

### 14. The hero's "New: courses" pill
The first thing in the hero points to courses, while launch is about tuition. Keep it once courses have stock; until
then a pill about the pilot (e.g. "December classes are open") serves the main goal better.

### 15. Social proof for tuition
Courses have ratings and reviews; tuition classes and teacher pages have none. After the pilot, collect a few
testimonials per teacher (or reuse the review model) and show them on teacher pages. Until then, teacher
"highlights" (results, years teaching) carry the trust; the profile editor should prompt for them.

### 16. Measure the funnel
There is no analytics yet. Before the pilot, decide the few events that matter: class page viewed → add to cart →
checkout started → paid; teacher application started → submitted. Without them none of the items above can be
judged.

---

## Suggested order
1. Items 1, 2, 10 (metadata, canonicals, robots): one small change.
2. Items 3, 4, 5, 6 (class page and hero): the pages teachers will share during the pilot.
3. Item 16 (events), so the pilot produces data.
4. Items 7, 8, 9 (SEO structure) once there are enough classes per subject.
5. Items 11 to 15 with pilot feedback; fill the TODOs in `.agents/product-marketing.md` from the same interviews.
