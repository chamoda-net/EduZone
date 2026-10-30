import { ClipboardList } from "lucide-react";
import Link from "next/link";

import { Badge, EmptyState, ErrorText, FilterChips } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { applicationTone } from "@/lib/platform";
import type { ApplicationRow, ApplicationStatus } from "@eduzone/lib/types";

const FILTERS: Array<ApplicationStatus | "open" | "all"> = ["open", "changes_requested", "approved", "rejected", "all"];

/** Teacher applications, waiting ones first. "open" = submitted (what needs a decision now). */
export default async function ApplicationsPage({ searchParams }: PageProps<"/applications">) {
  const { status: raw } = await searchParams;
  const status = FILTERS.includes(raw as ApplicationStatus) ? (raw as (typeof FILTERS)[number]) : "open";
  const query = status === "all" ? "" : `?status=${status === "open" ? "submitted" : status}`;
  const res = await api<ApplicationRow[]>(`/platform/applications${query}`);

  return (
    <>
      <h1 className="font-display text-3xl font-semibold sm:text-4xl">{t("platform.apps.title")}</h1>
      <FilterChips
        items={FILTERS.map((f) => ({
          href: f === "open" ? "/applications" : `/applications?status=${f}`,
          label: f === "open" ? t("platform.apps.filter.open") : f === "all" ? t("platform.apps.filter.all") : t(`apply.status.${f}`),
          active: f === status,
        }))}
      />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && <EmptyState icon={<ClipboardList />} title={t("platform.apps.empty")} />}
      {res.ok && res.data.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.map((a) => (
            <li key={a.id}>
              <Link href={`/applications/${a.id}`} className="flex flex-col gap-1 p-4 hover:bg-sunken/50 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {a.org_name}
                    <Badge tone={applicationTone[a.status]}>{t(`apply.status.${a.status}`)}</Badge>
                  </p>
                  <p className="truncate text-sm text-muted">
                    {a.applicant_name} · {t(`platform.orgType.${a.kind}`)} · {a.applicant_phone ?? a.applicant_email}
                  </p>
                </div>
                <p className="shrink-0 text-xs text-muted">{t("platform.apps.submitted", { date: formatDateTime(a.submitted_at) })}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
