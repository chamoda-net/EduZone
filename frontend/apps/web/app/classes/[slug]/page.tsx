import Link from "next/link";
import { notFound } from "next/navigation";

import { ActionButton } from "@eduzone/ui/action-button";
import { PayButton } from "@/components/pay-button";
import { StudentHeader } from "@/components/student-header";
import { Badge, Card, ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { classMeta, priceLabel } from "@/lib/catalog";
import { formatDateTime, formatMoney, formatMonth } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { getMe } from "@/lib/session";
import type { MonthAccess, PublicClassDetail, StudentClassView, StudentLesson, StudentMonth } from "@eduzone/lib/types";

import { joinClass, leaveClass, requestLateMonth } from "../actions";
import { RequestLateForm } from "./request-form";

const accessTone: Record<MonthAccess, string> = {
  granted: "published",
  buy: "upcoming",
  upcoming: "archived",
  request: "archived",
  pending: "draft",
  approved: "upcoming",
  rejected: "archived",
  unavailable: "archived",
};

export default async function ClassPage({ params }: PageProps<"/classes/[slug]">) {
  const { slug } = await params;
  const me = await getMe();

  // Signed in: the personal view (which months are unlocked). Otherwise: the public page.
  let view: StudentClassView | null = null;
  if (me) {
    const res = await api<StudentClassView>(`/student/classes/${encodeURIComponent(slug)}`);
    if (!res.ok) {
      if (res.status === 404) notFound();
      return <ErrorText>{errorText(t, res.error)}</ErrorText>;
    }
    view = res.data;
  } else {
    const res = await api<PublicClassDetail>(`/public/classes/${encodeURIComponent(slug)}`, { token: null });
    if (!res.ok) {
      if (res.status === 404) notFound();
      return <ErrorText>{errorText(t, res.error)}</ErrorText>;
    }
    view = {
      ...res.data,
      enrolled: false,
      has_class_access: false,
      months: res.data.months.map((m) => ({ ...m, access: m.status === "open" ? "buy" : m.status === "upcoming" ? "upcoming" : "request" })),
      lessons: res.data.lessons.map((l) => ({ ...l, unlocked: false })),
    };
  }
  const c = view.class;
  const monthly = c.pricing_model === "monthly";

  return (
    <>
      <StudentHeader />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-5 px-4 py-8">
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium tracking-wide text-brand uppercase">{classMeta(t, c)}</p>
          <h1 className="text-2xl font-semibold sm:text-3xl">{c.title}</h1>
          <p className="text-muted">{t("catalog.by", { name: c.teacher_name })} · {priceLabel(t, c)}</p>
          {c.description && <p className="whitespace-pre-line">{c.description}</p>}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {!me && (
            <Link href={`/login?next=/classes/${encodeURIComponent(slug)}`} className={buttonClass.primary}>
              {t("class.signInToJoin")}
            </Link>
          )}
          {me && !view.enrolled && (
            <ActionButton action={joinClass.bind(null, slug)} label={t("class.join")} variant="primary" />
          )}
          {me && view.enrolled && <Badge tone="published">{t("class.joined")}</Badge>}
          {view.has_class_access && <Badge tone="published">{t("class.classAccess")}</Badge>}
          {me && c.pricing_model === "one_time" && !view.has_class_access && c.one_time_price_cents !== null && (
            <PayButton classId={c.id} monthId={null}
                       label={t("pay.button", { amount: formatMoney(c.one_time_price_cents, c.currency) })} />
          )}
        </div>

        {monthly && view.months.length > 0 && (
          <Card className="flex flex-col gap-1">
            <h2 className="mb-1 text-lg font-semibold">{t("class.months")}</h2>
            <ul className="divide-y divide-border">
              {view.months.map((m) => (
                <MonthRow key={m.id} m={m} slug={slug} classId={c.id} signedIn={Boolean(me)} enrolled={view.enrolled} />
              ))}
            </ul>
          </Card>
        )}

        <Card className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold">{t("class.lessons")}</h2>
          {view.lessons.length === 0 && <p className="text-sm text-muted">{t("class.noLessons")}</p>}
          {groupByMonth(view.lessons, view.months, monthly).map((g) => (
            <div key={g.key} className="flex flex-col gap-1">
              {g.label && <h3 className="text-sm font-semibold text-muted">{g.label}</h3>}
              <ul className="divide-y divide-border">
                {g.lessons.map((l) => (
                  <li key={l.id} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      {l.unlocked ? (
                        <Link href={`/lessons/${l.id}`} className="font-medium text-brand hover:underline">{l.title}</Link>
                      ) : (
                        <span className="font-medium">{l.title}</span>
                      )}
                      <p className="text-sm text-muted">
                        {[t(`lessons.type.${l.lesson_type}`), l.scheduled_at && formatDateTime(l.scheduled_at)]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      {l.is_free_preview && <Badge tone="upcoming">{t("class.freePreview")}</Badge>}
                      {!l.unlocked && <Badge tone="archived">🔒 {t("class.locked")}</Badge>}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </Card>

        {me && view.enrolled && (
          <div className="self-start">
            <ActionButton
              action={leaveClass.bind(null, slug)}
              label={t("class.leave")}
              variant="link"
              confirm={t("class.confirmLeave")}
            />
          </div>
        )}
      </main>
    </>
  );
}

function MonthRow({ m, slug, classId, signedIn, enrolled }: {
  m: StudentMonth; slug: string; classId: string; signedIn: boolean; enrolled: boolean;
}) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-2.5">
      <div>
        <p className="font-medium">{formatMonth(m.month_start)}</p>
        <p className="text-sm text-muted">{formatMoney(m.fee_cents, m.currency)}</p>
      </div>
      <div className="flex flex-col items-end gap-1">
        {signedIn && <Badge tone={accessTone[m.access]}>{t(`class.access.${m.access}`)}</Badge>}
        {signedIn && (m.access === "buy" || m.access === "approved") && (
          <PayButton classId={classId} monthId={m.id} small
                     label={t("pay.button", { amount: formatMoney(m.fee_cents, m.currency) })} />
        )}
        {signedIn && m.access === "request" &&
          (enrolled ? (
            <RequestLateForm action={requestLateMonth.bind(null, slug, m.id)} />
          ) : (
            <span className="text-xs text-muted">{t("class.joinFirst")}</span>
          ))}
      </div>
    </li>
  );
}

function groupByMonth(lessons: StudentLesson[], months: StudentMonth[], monthly: boolean) {
  if (!monthly) return [{ key: "all", label: null as string | null, lessons }];
  return months
    .map((m) => ({ key: m.id, label: formatMonth(m.month_start) as string | null, lessons: lessons.filter((l) => l.class_month_id === m.id) }))
    .filter((g) => g.lessons.length > 0);
}
