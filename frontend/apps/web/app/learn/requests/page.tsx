import { ChevronRight, MessageSquareText } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { formatDateTime, formatMonth } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { MyRequest } from "@eduzone/lib/types";
import { EmptyState, ErrorText, PageHeader, StatusPill, type PillState } from "@eduzone/ui";

const pill: Record<MyRequest["status"], PillState> = {
  pending: "pending",
  approved: "unpaid",
  rejected: "closed",
  fulfilled: "paid",
  cancelled: "closed",
};

/** Past months the student asked teachers for, across every teacher. */
export default async function RequestsPage() {
  if (!(await getMe())) redirect("/login?next=/learn/requests");
  const res = await api<MyRequest[]>("/learn/requests");

  return (
    <SiteShell width="md">
      <PageHeader eyebrow={t("learn.eyebrow")} title={t("learn.requests.title")} description={t("learn.requests.subtitle")} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && (
        <EmptyState icon={<MessageSquareText />} title={t("learn.requests.empty")} body={t("learn.requests.emptyBody")} />
      )}
      {res.ok && res.data.length > 0 && (
        <ul className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">
          {res.data.map((r, i) => (
            <li key={r.id} className="ez-rise border-b border-border last:border-0" style={{ "--i": i } as React.CSSProperties}>
              <Link href={`/learn/classes/${r.class_id}`} className="group flex items-center gap-4 p-4 hover:bg-sunken/50 sm:p-5">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{r.class_title} · {formatMonth(r.month_start)}</p>
                  <p className="truncate text-sm text-muted">{r.org.name} · {formatDateTime(r.created_at)}</p>
                  {r.decision_note && (
                    <p className="mt-1 text-sm text-foreground/80">{t("learn.requests.teacherSaid", { note: r.decision_note })}</p>
                  )}
                </div>
                <StatusPill state={pill[r.status]}>{t(`learn.requests.status.${r.status}`)}</StatusPill>
                <ChevronRight className="hidden size-5 text-subtle group-hover:text-brand sm:block" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </SiteShell>
  );
}
