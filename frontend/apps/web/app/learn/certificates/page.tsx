import { Award, Download } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { siteOrigin } from "@/lib/site";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { Badge, EmptyState, ErrorText, PageHeader, buttonStyles } from "@eduzone/ui";

import { CopyLink } from "./copy-link";

/** The student's certificates: download each, or share its public verify link. */
export default async function CertificatesPage() {
  if (!(await getMe())) redirect("/login?next=/learn/certificates");
  const res = await api<Schema<"CertificateOut">[]>("/learn/certificates");
  const origin = await siteOrigin();
  return (
    <SiteShell>
      <PageHeader eyebrow={t("learn.eyebrow")} title={t("cert.title")} description={t("cert.lead")} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && (
        <EmptyState icon={<Award />} title={t("cert.empty")} body={t("cert.emptyBody")}
                    action={<Link href="/learn/courses" className={buttonStyles("secondary")}>{t("nav.myCourses")}</Link>} />
      )}
      {res.ok && res.data.length > 0 && (
        <ul className="grid gap-4 md:grid-cols-2">
          {res.data.map((c) => (
            <li key={c.certificate_no} className="flex flex-col gap-4 rounded-ez-lg border border-border bg-surface p-5 shadow-ez-sm">
              <div className="flex items-start gap-3">
                <span className="grid size-11 shrink-0 place-items-center rounded-full bg-gold/15 text-gold-strong"><Award className="size-5" /></span>
                <div className="min-w-0">
                  <p className="font-display text-lg leading-snug font-semibold">{c.course_title}</p>
                  <p className="text-sm text-muted">{c.instructor_name} · {c.org_name}</p>
                  <p className="mt-1 text-xs text-muted">
                    {t("cert.issued", { date: formatDateTime(c.issued_at).split(",")[0] })} · <span className="font-mono">{c.certificate_no}</span>
                  </p>
                </div>
                {c.revoked_at && <Badge tone="danger" className="ml-auto">{t("cert.revoked")}</Badge>}
              </div>
              {!c.revoked_at && (
                <div className="flex flex-wrap gap-2">
                  <a href={`${c.verify_path}/pdf`} className={buttonStyles("primary", "sm")}><Download className="size-4" />{t("cert.download")}</a>
                  <Link href={c.verify_path} className={buttonStyles("secondary", "sm")}>{t("cert.view")}</Link>
                  <CopyLink url={`${origin}${c.verify_path}`} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </SiteShell>
  );
}
