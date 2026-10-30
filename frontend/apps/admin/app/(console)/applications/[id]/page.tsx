import { FileText } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge, Card, CardTitle, DataList, ErrorText, buttonClass, buttonStyles } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { applicationTone } from "@/lib/platform";
import type { ApplicationDetail } from "@eduzone/lib/types";

import { decideApplication, revealAccount } from "../../../actions";
import { DecisionForm, RevealAccount } from "./review";

export default async function ApplicationPage({ params }: PageProps<"/applications/[id]">) {
  const { id } = await params;
  const res = await api<ApplicationDetail>(`/platform/applications/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const a = res.data;

  return (
    <>
      <Link href="/applications" className={`${buttonClass.link} text-sm`}>← {t("platform.apps.title")}</Link>
      <div className="flex flex-col gap-1">
        <h1 className="flex flex-wrap items-center gap-2 font-display text-3xl font-semibold">
          {a.org_name} <Badge tone={applicationTone[a.status]}>{t(`apply.status.${a.status}`)}</Badge>
        </h1>
        <p className="text-sm text-muted">
          {t(`platform.orgType.${a.kind}`)} · /teach/{a.tenant_slug} · {t("platform.apps.submitted", { date: formatDateTime(a.submitted_at) })}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle>{t("platform.apps.applicant")}</CardTitle>
          <DataList
            items={[
              [t("platform.apps.name"), a.applicant_name],
              [t("auth.phone"), a.applicant_phone ?? "—"],
              [t("auth.email"), a.applicant_email ?? "—"],
              [t("platform.apps.subjects"), a.subjects.map((s) => s.name).join(", ")],
              [t("platform.apps.terms", { version: a.terms_version }), ""],
            ]}
          />
          {a.experience && (
            <div className="mt-4 flex flex-col gap-1">
              <p className="text-sm font-semibold">{t("platform.apps.experience")}</p>
              <p className="text-sm whitespace-pre-line text-muted">{a.experience}</p>
            </div>
          )}
        </Card>

        <div className="flex flex-col gap-4">
          <Card className="flex flex-col gap-3">
            <CardTitle>{t("platform.apps.document")}</CardTitle>
            <a href={`/applications/${a.id}/document`} target="_blank" rel="noreferrer"
               className={buttonStyles("secondary", "md", "self-start")}>
              <FileText className="size-4" />
              {t("platform.apps.openDocument")}
            </a>
            <p className="text-xs text-muted">{a.document_name} · {t("platform.apps.documentAudit")}</p>
          </Card>
          <Card className="flex flex-col gap-3">
            <CardTitle>{t("platform.apps.payout")}</CardTitle>
            <DataList
              items={[
                [t("apply.bank"), [a.payout_bank_name, a.payout_branch].filter(Boolean).join(", ")],
                [t("apply.accountName"), a.payout_account_name],
                [t("apply.accountNumber"), <RevealAccount key="n" masked={a.payout_account_masked} reveal={revealAccount.bind(null, a.id)} />],
              ]}
            />
          </Card>
        </div>
      </div>

      <Card className="flex flex-col gap-3">
        <CardTitle>{t("platform.apps.decision")}</CardTitle>
        {a.review_note && (
          <div className="rounded-ez border border-border bg-sunken/50 p-3 text-sm">
            <p className="font-semibold">{t("apply.note")}</p>
            <p className="whitespace-pre-line text-muted">{a.review_note}</p>
          </div>
        )}
        {a.reviewed_at && (
          <p className="text-xs text-muted">
            {t("platform.apps.reviewed", { date: formatDateTime(a.reviewed_at), name: a.reviewed_by_name ?? "—" })}
          </p>
        )}
        {a.status === "submitted" && <DecisionForm action={decideApplication.bind(null, a.id)} canApprove />}
        {a.status === "changes_requested" && (
          <>
            <p className="text-sm text-muted">{t("platform.apps.waiting")}</p>
            <DecisionForm action={decideApplication.bind(null, a.id)} canApprove={false} />
          </>
        )}
        {(a.status === "approved" || a.status === "rejected") && (
          <Link href={`/tenants/${a.tenant_id}`} className={`${buttonClass.link} self-start`}>{t("platform.apps.openTenant")} →</Link>
        )}
      </Card>
    </>
  );
}
