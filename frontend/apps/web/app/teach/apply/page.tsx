import { ArrowRight, BadgeCheck, CircleCheck, ClipboardList, Hammer, PencilLine, Rocket } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { formatDateTime } from "@eduzone/lib/format";
import { t } from "@eduzone/lib/i18n";
import type { SubjectOut, TeacherApplication } from "@eduzone/lib/types";
import { Alert, Badge, type BadgeTone, Card, CardTitle, DataList, buttonStyles } from "@eduzone/ui";

import { ApplyForm } from "./apply-form";

export const metadata: Metadata = { title: "Teach on EduZone", robots: { index: false } };

const TONE: Record<TeacherApplication["status"], BadgeTone> = {
  submitted: "info", changes_requested: "warning", approved: "success", rejected: "danger",
};

/** /teach/apply: the application to teach (phase 5), then its status. Needs a verified phone. */
export default async function ApplyPage({ searchParams }: PageProps<"/teach/apply">) {
  const me = await getMe();
  if (!me) redirect("/login?next=/teach/apply");
  if (!me.phone_verified) redirect("/verify-phone?next=/teach/apply");
  const { edit } = await searchParams;

  const [mine, subjects] = await Promise.all([
    api<TeacherApplication | null>("/me/teacher-application"),
    api<SubjectOut[]>("/market/subjects", { token: null }),
  ]);
  const app = mine.ok ? mine.data : null;
  const subjectList = subjects.ok ? subjects.data.map((s) => ({ id: s.id, name: s.name })) : [];

  const editing = app?.status === "changes_requested" || (app?.status === "submitted" && edit === "1");
  const showForm = !app || app.status === "rejected" || editing;

  return (
    <SiteShell width="md">
      <header className="ez-rise flex flex-col gap-4 pb-8">
        <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{t("apply.eyebrow")}</p>
        <h1 className="font-display text-4xl leading-tight font-semibold text-balance sm:text-5xl">{t("apply.title")}</h1>
        {(!app || app.status === "rejected") && <p className="max-w-2xl text-lg text-muted">{t("apply.lead")}</p>}
      </header>

      <Steps current={!app || app.status === "rejected" ? 0 : app.status === "approved" ? 2 : 1} />

      <div className="mt-8 flex flex-col gap-6">
        {app?.status === "rejected" && (
          <Alert tone="danger" title={t("apply.rejected.title")}>
            {app.review_note && <p className="whitespace-pre-line">{app.review_note}</p>}
            <p>{t("apply.rejected.body")}</p>
          </Alert>
        )}
        {app?.status === "changes_requested" && (
          <Alert tone="warning" title={t("apply.changes.title")}>
            <p className="whitespace-pre-line">{app.review_note}</p>
          </Alert>
        )}

        {app?.status === "submitted" && !editing && (
          <Card className="flex flex-col gap-4">
            <div className="flex items-start gap-4">
              <span className="grid size-12 shrink-0 place-items-center rounded-full bg-brand-50 text-brand">
                <ClipboardList className="size-6" />
              </span>
              <div className="flex min-w-0 flex-col gap-1">
                <h2 className="font-display text-2xl font-semibold">{t("apply.review.title")}</h2>
                <p className="text-muted">{t("apply.review.body", { date: formatDateTime(app.submitted_at) })}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href={`/teach/${app.tenant_slug}/classes`} className={buttonStyles("primary")}>
                {t("apply.review.openConsole")}
                <ArrowRight className="size-4" />
              </Link>
              <Link href="/teach/apply?edit=1" className={buttonStyles("secondary")}>
                <PencilLine className="size-4" />
                {t("apply.review.edit")}
              </Link>
            </div>
          </Card>
        )}

        {app?.status === "approved" && (
          <Card className="flex flex-col gap-4">
            <div className="flex items-start gap-4">
              <span className="grid size-12 shrink-0 place-items-center rounded-full bg-success/10 text-success">
                <BadgeCheck className="size-6" />
              </span>
              <div className="flex min-w-0 flex-col gap-1">
                <h2 className="font-display text-2xl font-semibold">{t("apply.approved.title")}</h2>
                <p className="text-muted">{t("apply.approved.body")}</p>
              </div>
            </div>
            <Link href={`/teach/${app.tenant_slug}/classes`} className={buttonStyles("primary", "md", "self-start")}>
              {t("apply.review.openConsole")}
              <ArrowRight className="size-4" />
            </Link>
          </Card>
        )}

        {showForm ? (
          <ApplyForm
            subjects={subjectList}
            current={editing ? app : null}
            cancelHref={app?.status === "submitted" ? "/teach/apply" : undefined}
          />
        ) : (
          app && (
            <Card>
              <CardTitle action={<Badge tone={TONE[app.status]}>{t(`apply.status.${app.status}`)}</Badge>}>
                {t("apply.summaryTitle")}
              </CardTitle>
              <DataList
                items={[
                  [t("apply.kindLabel"), t(`apply.kind.${app.kind}`)],
                  [t(`apply.orgName.${app.kind}`), app.org_name],
                  [t("apply.summaryAddress"), `/teach/${app.tenant_slug}`],
                  [t("apply.subjects"), app.subjects.map((s) => s.name).join(", ")],
                  [t(`apply.document.${app.kind}`), app.document_name],
                  [t("apply.bank"), [app.payout_bank_name, app.payout_branch].filter(Boolean).join(", ")],
                  [t("apply.accountNumber"), `${app.payout_account_name} · ${app.payout_account_masked}`],
                ]}
              />
            </Card>
          )
        )}
      </div>
    </SiteShell>
  );
}

function Steps({ current }: { current: number }) {
  const steps = [
    { icon: <PencilLine className="size-4.5" />, title: t("apply.steps.apply"), body: t("apply.steps.applyBody") },
    { icon: <Hammer className="size-4.5" />, title: t("apply.steps.prepare"), body: t("apply.steps.prepareBody") },
    { icon: <Rocket className="size-4.5" />, title: t("apply.steps.live"), body: t("apply.steps.liveBody") },
  ];
  return (
    <ol className="grid gap-3 sm:grid-cols-3">
      {steps.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li
            key={s.title}
            style={{ "--i": i } as React.CSSProperties}
            className={`ez-rise flex min-w-0 items-start gap-3 rounded-ez-lg border p-4 ${
              active ? "border-brand bg-brand-50/60" : "border-border bg-surface"
            }`}
          >
            <span
              className={`grid size-9 shrink-0 place-items-center rounded-full ${
                done ? "bg-brand text-on-brand" : active ? "bg-brand-900 text-gold" : "bg-sunken text-muted"
              }`}
            >
              {done ? <CircleCheck className="size-4.5" /> : s.icon}
            </span>
            <span className="min-w-0">
              <span className="block font-semibold">{s.title}</span>
              <span className="block text-sm text-muted">{s.body}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
