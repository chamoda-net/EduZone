# Product Marketing Context

**Document version:** v1
**Last updated:** 2026-11-26

> Drafted from the codebase (CLAUDE.md, the marketplace copy in `packages/lib/src/i18n/en.ts`, docs/BRANDING.md).
> Lines marked **TODO** need facts only Chamoda or the pilot teachers can give. Nothing here is customer research yet.

## Product Overview
**One-liner:** Sri Lanka's marketplace for online tuition classes: live Zoom lessons, recordings and tutes from many teachers, one account, one payment.
**What it does:** Students find Grade 5, O/L and A/L teachers by subject, exam and medium, pay month by month (several teachers in one cart), and learn in one student area: live classes, recordings, tutes, receipts. Teachers and institutes get a public profile page, a console to run classes, collected fees and a full cash-flow view. Also sells self-paced video courses with lifetime access.
**Product category:** Online tuition classes ("online class", "A/L physics class", "Sinhala medium online tuition").
**Product type:** Two-sided marketplace (B2C on the student side, B2B2C on the teacher side).
**Business model:** Commission per sale, 20% by default (configurable per organization and per product type: tuition, course). EduZone collects every payment and pays organizations out. Companies (v1.1): monthly subscription.

## Target Audience
**Demand side:** Sri Lankan students preparing for the Grade 5 scholarship, O/L and A/L, mostly on phones; parents who pay.
**Supply side:** Individual tuition teachers and tuition institutes already teaching online or hybrid.
**Primary use case (student):** Follow a trusted teacher's monthly class online without bank slips, WhatsApp chaos or lost recordings.
**Primary use case (teacher):** Get paid on time and reach more students without building their own app or chasing payments.
**Jobs to be done:**
- Student: "Help me not fall behind before the exam, even if I miss a class."
- Parent: "Let me pay safely and see what I paid for."
- Teacher: "Collect fees, protect my recordings, and fill my class."
**Use cases:**
- Joining a class mid-year and catching up on earlier months (late-month request)
- Rewatching recordings and downloading tutes before the exam
- Following several teachers (e.g. physics, chemistry, combined maths) and paying once
- A teacher sharing their page on WhatsApp, Facebook and posters

## Personas
| Persona | Cares about | Challenge | Value we promise |
|---------|-------------|-----------|------------------|
| A/L or O/L student | Results, not missing lessons, low data use | Recordings scattered across WhatsApp/Drive; joining late | Live + recordings + tutes in one place, month by month |
| Grade 5 parent | Child's progress, safe payment, value for money | Bank slips, no receipts, unclear what's included | Card payment with a receipt per month; see every lesson |
| Individual teacher | Income, reputation, content piracy | Chasing slips, leaked recordings, tech setup | Fees collected, protected video, own shareable page |
| Institute owner | Many teachers, reporting, payouts | Splitting money per teacher, admin load | Per-teacher earnings report, one payout, team console |

## Problems & Pain Points
**Core problem:** Online tuition in Sri Lanka runs on Zoom + WhatsApp groups + bank slips. Payments are checked by hand, recordings leak or get lost, and students can't find good teachers outside word of mouth.
**Why alternatives fall short:**
- WhatsApp/Telegram groups: no access control, recordings shared freely, payment checked by screenshot
- A teacher's own custom app/website: costly to build and run, one teacher per app, a new account per teacher
- YouTube/Facebook: free content, no paid monthly access, no structure per month
**What it costs them:** Teachers lose income to sharing and unpaid months; students lose lessons and time.
**Emotional tension:** Exam-year anxiety (student and parent); teachers' fear of piracy and late payments.

## Competitive Landscape
**Direct:** Other Sri Lankan online-class platforms and teacher LMS apps — **TODO: name the 3 that pilot teachers actually use or mention.**
**Secondary:** Each teacher's own LMS/app built by a freelancer — falls short because every teacher is a separate account and payment.
**Indirect:** WhatsApp + Zoom + bank slip; physical tuition classes — falls short on reach (physical) and control (WhatsApp).

## Differentiation
**Key differentiators:**
- One student account and one cart across every teacher
- Pay month by month by card, a receipt per month, no bank slips
- Recordings protected: watermark with the student's name and phone, one device per account, view limits
- Teachers get a marketable page (`/<subject>/<teacher>`) with WhatsApp share and QR
- Full cash-flow view for teachers (gross, fees, commission, net, payouts)
**Why customers choose us:** **TODO after the pilot (verbatim reasons).**

## Objections
| Objection | Response |
|-----------|----------|
| "I don't have a card" (student/parent) | **TODO:** depends on gateway methods (PayHere supports more than cards; copy currently says "by card") |
| "20% is too much" (teacher) | No build or hosting cost, payment collection, video hosting and protection, marketplace reach; compare with a custom app's cost |
| "Only one device? My child uses my phone and the laptop" | Explain why (protects lessons), how switching works (an SMS code) |
| "Will my students move?" (teacher) | Teacher keeps their own page and share link; students only register once |

**Anti-persona:** Free-content YouTubers; schools wanting a full LMS (SCORM/LTI); anyone needing bank-slip payments.

## Switching Dynamics
**Push:** Chasing payment slips; leaked recordings; WhatsApp group chaos.
**Pull:** Fees collected automatically; protected video; one page to share; one account for students.
**Habit:** Existing WhatsApp groups and Zoom links; students used to paying by bank transfer.
**Anxiety:** Losing students in the move; commission; trust in a new platform holding the money; students without cards.

## Customer Language
**How they describe the problem:** **TODO (verbatim from pilot teachers and students).**
**How they describe us:** **TODO.**
**Words to use:** class, month, tute, recording, live class, Zoom, teacher, institute, O/L, A/L, Grade 5 scholarship, Sinhala/English/Tamil medium, Rs.
**Words to avoid:** "platform" in student copy, "solution", "LMS", "content", "learners" (say students), "subscription" for tuition (say monthly fee).
**Glossary:**
| Term | Meaning |
|------|---------|
| Tute | Printed/PDF notes for a lesson |
| Month | One paid month of a monthly class (the unit students buy) |
| Past month | A month the teacher closed; buying it needs the teacher's approval |
| Medium | Language of instruction (Sinhala, English, Tamil) |
| Batch / year | Exam year a class prepares for (e.g. 2027 A/L) |

## Brand Voice
| Attribute | Means | Doesn't mean | Example line |
|-----------|-------|--------------|--------------|
| Plain | Short, concrete words a 16-year-old reads on a phone | Childish | "Pay for the month you need." |
| Reassuring | Says what happens next and what's included | Hype, pressure | "Missed a live class? The recording and the tute are waiting in your account." |
| Honest | No claims we can't back | Modest to the point of vague | "Ask the teacher for an earlier month and pay for it once they say yes." |

**Tone by context:**
- Support: a person answers; names the reference number
- Launch: calm and specific, no superlatives
- Errors: says exactly what's wrong and the button that fixes it
- Sales (teachers): money first, shown in rupees
- Social: teacher-led (teachers share their own pages)
**Terms we own:** month by month; one account for every teacher.
**Never use (and why):** "best teachers" without proof (unbacked claim); individual teachers or classes in marketing heroes (EduZone stays neutral between teachers).

## Proof Points
**Metrics:** None yet (pre-pilot). Live counts of classes, teachers and subjects are shown on the home page.
**Customers:** **TODO after the pilot.**
**Testimonials:** **TODO.**
**Value themes:**
| Theme | Proof |
|-------|-------|
| Never miss a lesson | Every paid month includes recordings and tutes |
| Safe payments | Gateway checkout, receipt per order |
| Teachers' work protected | Watermark, one device, view limits |

## Goals
**Business goal:** Launch the pilot with real tuition teachers (roadmap step 10), then grow paying students per teacher.
**Conversion action:** Student: first paid month. Teacher: submitted application.
**Current metrics:** None yet.

## Learnings
*Decisions and tested lessons. Newest first. Keep it to about 20 active entries.*
| Date | Learning | Evidence | Applies to | Status |
|------|----------|----------|------------|--------|
| 2026-11-23 | Marketing heroes, banners and bands stay neutral: no individual teacher's name, face, class or price (stock photos of students and generic product UI are fine) | Founder rejected a hero card showing one teacher's class | copywriting, cro, image | active |

## Changelog
*Newest first. One line per revision: what changed and why.*
- v1 (2026-11-26) — Initial context, drafted from the codebase; competitors, customer language and proof left as TODO for the pilot.
