import { Award, BadgeCheck, Download, ShieldAlert } from "lucide-react";
import type { Metadata } from "next";

import type { Schema } from "@eduzone/api-client";
import { SiteShell } from "@/components/shell";
import { formatLength } from "@/lib/courses";
import { market } from "@/lib/market";
import { formatDateTime } from "@eduzone/lib/format";
import { t } from "@eduzone/lib/i18n";
import { buttonStyles, cx } from "@eduzone/ui";

type Verify = Schema<"CertificateVerify">;

const load = async (params: Promise<{ no: string }>) => market<Verify>(`/certificates/${encodeURIComponent((await params).no)}`);

export async function generateMetadata({ params }: PageProps<"/certificates/[no]">): Promise<Metadata> {
  const c = await load(params);
  return { title: t("cert.metaTitle", { no: c.certificate_no }), robots: { index: false } };
}

/** /certificates/<no>: anyone can check that a certificate is genuine (snapshot fields and status only). */
export default async function VerifyCertificatePage({ params }: PageProps<"/certificates/[no]">) {
  const c = await load(params);
  const date = (iso: string) => formatDateTime(iso).split(",")[0];
  return (
    <SiteShell width="md">
      <div className={cx("flex items-start gap-3 rounded-ez-lg border p-4",
                         c.valid ? "border-success/25 bg-success-bg text-success" : "border-danger/25 bg-danger-bg text-danger")}>
        {c.valid ? <BadgeCheck className="mt-0.5 size-6 shrink-0" /> : <ShieldAlert className="mt-0.5 size-6 shrink-0" />}
        <div>
          <p className="font-semibold">{c.valid ? t("cert.valid") : t("cert.invalid")}</p>
          <p className="text-sm text-foreground/80">
            {c.valid ? t("cert.validBody", { date: date(c.issued_at) }) : t("cert.invalidBody", { date: date(c.revoked_at ?? c.issued_at) })}
          </p>
        </div>
      </div>

      <section className="relative overflow-hidden rounded-ez-lg border-[6px] border-brand-800 bg-surface p-8 text-center shadow-ez-lg sm:p-12">
        <div aria-hidden className="pointer-events-none absolute inset-3 rounded border border-gold/60" />
        <Award className="mx-auto size-10 text-gold" />
        <p className="mt-2 text-xs font-bold tracking-[0.2em] text-gold-strong uppercase">{t("cert.verifyTitle")}</p>
        <p className="mt-6 text-sm text-muted">{t("cert.awardedTo")}</p>
        <p className="font-display text-3xl font-semibold sm:text-4xl">{c.student_name}</p>
        <p className="mt-5 text-sm text-muted">{t("cert.forCourse")}</p>
        <p className="font-display text-2xl font-semibold text-brand-800">{c.course_title}</p>
        <p className="mt-2 text-sm text-muted">{t("cert.taughtBy", { name: c.instructor_name, org: c.org_name })}</p>
        <p className="text-sm text-muted">{t("cert.length", { length: formatLength(t, c.total_video_seconds) })}</p>
        <p className="mt-6 font-mono text-xs text-muted">{t("cert.no", { no: c.certificate_no })}</p>
      </section>

      {c.valid && (
        <a href={`/certificates/${c.certificate_no}/pdf`} className={buttonStyles("primary", "lg", "self-center")}>
          <Download className="size-4.5" />{t("cert.download")}
        </a>
      )}
    </SiteShell>
  );
}
