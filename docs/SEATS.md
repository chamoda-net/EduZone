# EduZone — Seats and registration for classes

> Read with `CLAUDE.md`. **Status (2026-11-24): design agreed; all steps (S1 to S4) built** (migrations 0018 to 0020,
> `app/modules/seats`, `tests/test_seats.py`, `tests/test_seat_renewals.py`, `tests/test_seat_requests.py`,
> `frontend/e2e/seats.spec.ts`). Off for teachers until `SEATS_ENABLED=true`. Demo: `scripts/seed_seats.py`. Everything in `CLAUDE.md` still applies
> (tenancy, RLS, money rules, checkout).

## 1. What it is

A tuition class can have a limited number of seats, and its teacher decides whether new students may join.
Two separate controls:

| Control | Options |
|---|---|
| **Seats** | No limit (default, today's behaviour), or a number |
| **Registration** (new students only) | **Open**, **Ask me first**, **Closed** |

A class without a seat limit still has registration. Self-paced courses have neither.

## 2. Agreed

| Topic | Decision |
|---|---|
| Returning students | Keep their seat for the next month until a **renewal date** |
| Renewal date | The **7th** by default, chosen by the teacher; at least **3 days** when a month opens late |
| Payment after the hold, class now full | **Keep the student**, alert the teacher |
| Seat numbers | The teacher may hide "3 seats left" and show only Open or Full |
| Seat limit | One number per class, changeable at any time; nobody is ever removed by lowering it |
| Who decides | The class's teacher, and the organization's owner and admins |
| Seat request | Optional note from the student |
| Waiting list | "Notify me" first; automatic offers later |
| Paying | The seat is held for **15 minutes** |
| Accepted request | The seat is held for **48 hours** |
| Cart | Holds nothing until payment starts |
| Scholarships and free places | Take a seat; staff may go over the limit after a warning |
| Past months | Take no seat; today's late-month approval is unchanged |
| Start date (optional) | Registration switches by itself on that date to open, ask or closed |

## 3. Also agreed (found while checking the code)

1. **Leaving the class gives up next month's kept seat.** A paid month stays paid, and its seat stays taken until the
   month is over. This gives students a clear way to say "I'm not continuing". Rejoining doesn't bring the seat back
   (they are a new student again); staff can.
2. **At most 3 unfinished payment holds per student, class and day** (declined cards don't count), so nobody can keep
   a seat blocked by restarting payment.
   Starting again reuses a hold that is still running and doesn't make it longer.
3. **A student who joins last month late** (after the next month has opened) needs no approval for the next month but
   gets no kept seat. Otherwise two open months could sell more seats than exist.
4. **A past month bought late never counts** as a seat or as "was in the class last month".
5. **Seat requests need a verified phone**, like paying. After a refusal the student may ask again for another month.
6. **"Notify me" shows in the student area** ("A seat opened in ..."). It also emails once a provider is chosen. It must
   not promise an email before that.
7. **Leaving a free class ends access to it.** Today it keeps access, which would let a seat be freed and kept.
8. **Cards of limited classes count seats taken**, not joined students. Today joining is free and starting a payment
   also joins, so the numbers would contradict each other.

9. **Built in S3:** staff may accept a refused or expired request later, and take an unpaid acceptance back. Accepting
   into a full class is refused (add a seat first). "Notify me" is offered only when the class can't be joined now.
   When numbers are hidden the student count on the card is hidden too, as it would give them away.
   A guest's cart shows seats as a new student would find them; a returning student can renew once signed in.

## 4. Rules

**Seats taken** for a monthly class are counted per month; for one-time and free classes once for the class:

1. active access that takes a seat (paid, scholarship, manual, free while still enrolled)
2. payments running now (a pending order whose hold has not ended)
3. accepted requests not yet paid and not expired
4. kept seats of returning students who have not renewed, until the renewal date

One student never counts twice.

**Returning student** for a month: had a seat in the class's latest earlier month that was ever open, gained before this
month opened; still enrolled; not suspended; not refunded. A holiday month with no class month doesn't break it.

**Renewal date** is fixed when the month first opens: the later of the end of the renewal day in that month and
opening + 3 days, Colombo time. The teacher can move it for that month (moving it later brings lapsed seats back, even
over the limit), and keep (up to 60 days) or release one student's seat; keeping one when the class is full needs a
confirmation. A month set back to upcoming forgets its dates and opens afresh.

**May this student pay for this month now?** In this order:

| Case | Answer |
|---|---|
| Already has access | `ALREADY_HAS_ACCESS` (as today) |
| Month closed | Late-month rules, no seat check (as today) |
| Has a running hold, accepted request, or kept seat | Yes |
| No seat free | `CLASS_FULL` |
| Was in the class last month | Yes |
| Registration closed | `REGISTRATION_CLOSED` |
| Registration asks first | `SEAT_REQUEST_REQUIRED` |
| Otherwise | Yes |

**Counting needs no background job:** holds, accepted requests and kept seats simply stop counting when their time passes.

## 5. Data (next free migration number)

| Table | Change |
|---|---|
| `classes` | `seat_limit` (1 to 10000, NULL = no limit), `show_seat_count`, `registration`, `starts_on`, `registration_after_start`, `renewal_day` (1 to 28, default 7). Courses: all at defaults (check constraint) |
| `class_months` | `opened_at` (existing open and closed months got `created_at`), `renew_until` |
| `access_grants` | `takes_seat` (default true; false for a late-month purchase) |
| `orders` | `seat_held_until`: a pending order **is** the hold, so a failed or cancelled payment frees it at once |
| `seat_requests` (built) | class, month, student, note, status pending / approved / rejected / withdrawn / used, decided by, `held_until`; one row per student, class and month |
| `seat_keeps` (built) | month, student, keep or release, `keep_until`, decided by |
| `seat_waits` (built) | class, student, created |

New tables: `tenant_id`, forced RLS, composite foreign keys, explicit grants, isolation tests. Students read their own
requests and waits across organizations through SELECT-only user policies.

The public view `public_seats` has `seat_limit`, `seats_left`, `is_full` and `registration` per class or open month. Counting
is in SQL functions shared by the service and the view (`seat_holders`). When the teacher hides numbers the **view** returns
NULL for both numbers and only says open or full. Never names, requests or waiting counts.

## 6. Code

- **One module, `app/modules/seats`**, holds every rule of section 4. Nothing else counts seats.
- **Last seat:** the class row is locked (`FOR NO KEY UPDATE`) in the transaction that takes a seat, then seats are
  counted. The cart already uses one transaction per item, so two locks are never held together.
- **`price_item()`** asks the seat rule (read-only), so the Pay button, cart states and checkout agree. **`create_order()`**
  takes the hold, for both payment paths (cart and single Pay).
- **Enrolment moves from starting a payment to finishing it** (`fulfil_order()`), so abandoned payments no longer join.
- **Abandoned checkouts:** when one item of a cart fails, the orders already created stay `pending` today. They must be
  marked failed, or their seats stay held for 15 minutes.
- **`fulfil_order()`** always gives access. If the class was full and the hold had ended, it writes an audit row and the
  console shows "over by 1". Money rules don't change.
- **Other places that take or free a seat:** manual grants (`learning/org.py`, `allow_over_limit`), free join and leave
  (`learning/service.py`), revoking a grant. No change to course enrolment.
- Guests' cart preview checks the public state only; the real check happens when they pay.

## 7. API

| Who | Endpoint |
|---|---|
| Staff | class settings on `PATCH /classes/{id}`; `GET /classes/{id}/seats?month_id=` (each seat and why it is taken) |
| Staff | `GET /seat-requests?status=`, `POST /seat-requests/{id}/decision` |
| Staff | `PUT /months/{id}/seat-keeps/{member_id}` (keep until / release), `renew_until` on `PATCH /months/{id}` |
| Student | `POST /learn/classes/{id}/seat-request {class_month_id?, note?}`, `DELETE` to withdraw |
| Student | `PUT/DELETE /learn/classes/{id}/seat-wait` |
| Student | `GET /learn/classes/{id}`: each month also says why it can or can't be paid, and until when a seat is kept |
| Public | market class: limit, seats left (unless hidden), registration; catalogue filter `seats=available` |

All staff changes are audited. A class the caller may not manage is a 404, as everywhere.

## 8. Screens

- **Console, class page:** Seats card (limit, registration, start date, renewal day, show or hide numbers); seat icons per
  month (paid, kept, paying, accepted, free), with keep or release on a student; "over by 1" alert; waiting count.
- **Console, Requests:** seat requests next to late-month requests.
- **Marketplace:** "Small group · 10 seats", "3 seats left", "Full", "Ask to join", "Registration closed"; a filter; a
  "Already in this class? Renew" link when the public state is full or closed.
- **Student:** renew banner with the date, request and its answer with the time left to pay, a "seat held" timer at
  checkout, "Notify me" and "A seat opened".
- **Cart:** each new problem in plain words, with the action that solves it.

Phone width first, all text in i18n keys, status never by colour alone.

## 9. Steps

| Step | What | Done when |
|---|---|---|
| **S1** (built) | Migration, seats module, holds and enrolment change in both payment paths, staff API | Backend tests below pass; no class can set a limit that checkout ignores |
| **S2** (built) | Renewals: opening dates, kept seats, keep and release | Renewal tests pass |
| **S3** (built) | Seat requests, notify list, public fields and filter | Request and public-view tests pass |
| **S4** (built) | Console, marketplace, student and cart screens | Playwright at 360 px and 1440 px, e2e checks |

Turn it on with `SEATS_ENABLED=true`. Before launch: check how long a PayHere payment can take (`SEAT_HOLD_MINUTES`), and how
fast the catalogue stays with many limited classes.

## 10. Tests that must exist

- Two students, one seat, same moment: exactly one hold. Run through both payment paths.
- A hold ends, fails or is cancelled: the seat is free. A cart that fails halfway frees every seat.
- Late payment on a full class: access given, booked once, flagged; the webhook repeated changes nothing.
- Restarting payment neither doubles nor extends a hold; the fourth hold in a day is refused.
- Renewals: kept until the last second of the date; month opened late; holiday gap; two months open; left, refunded,
  suspended, late-bought and skipped students; keep and release.
- Registration open, ask, closed and the start-date switch, for new and returning students.
- Accepted request expires, is used once, and can't be accepted into a full class.
- Lowering the limit, going over with a manual grant, and turning limits on for a running class.
- Hidden numbers never appear in any public response.
- Isolation for each new table; a teacher can't see or decide another teacher's class.
- Classes without a limit behave exactly as today, except enrolment after payment and leaving free classes.

## 11. Not in this version

Numbered seats, automatic waiting-list offers, email and SMS reminders (until providers are chosen), a different limit
per month, seats on courses. Seats limit access on EduZone; they can't stop a student forwarding a Zoom link.
