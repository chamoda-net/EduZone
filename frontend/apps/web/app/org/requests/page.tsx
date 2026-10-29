import Link from "next/link";

import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, ErrorText } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMonth } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { LateRequest } from "@eduzone/lib/types";

import { decideRequest } from "../classes/actions";

const TABS = ["pending", "approved", "rejected", "fulfilled"] as const;
type Tab = (typeof TABS)[number];
const tone: Record<Tab, string> = { pending: "draft", approved: "upcoming", rejected: "archived", fulfilled: "published" };

/** Students asking to buy months that are already closed. Approval lets them pay (step 7). */
export default async function RequestsPage({ searchParams }: PageProps<"/org/requests">) {
  const sp = await searchParams;
  const status: Tab = TABS.includes(sp.status as Tab) ? (sp.status as Tab) : "pending";
  const res = await api<LateRequest[]>(`/org/late-requests?status=${status}`);

  return (
    <>
      <h1 className="text-2xl font-semibold">{t("requests.title")}</h1>
      <div className="flex gap-2 overflow-x-auto">
        {TABS.map((s) => (
          <Link
            key={s}
            href={s === "pending" ? "/org/requests" : `/org/requests?status=${s}`}
            className={`rounded-full border px-3 py-1.5 text-sm whitespace-nowrap ${
              s === status ? "border-brand bg-brand text-on-brand" : "border-border bg-surface"
            }`}
          >
            {t(`requests.status.${s}`)}
          </Link>
        ))}
      </div>

      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && <p className="text-muted">{t("requests.empty")}</p>}
      {res.ok && res.data.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {res.data.map((r) => (
            <li key={r.id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="font-medium">
                  {r.student_name} <span className="text-sm font-normal text-muted">{r.student_phone}</span>
                </p>
                <p className="text-sm">
                  <Link href={`/org/classes/${r.class_id}`} className="text-brand hover:underline">{r.class_title}</Link>
                  {" · "}
                  {formatMonth(r.month_start)}
                </p>
                {r.student_note && <p className="mt-1 text-sm text-muted">“{r.student_note}”</p>}
                <p className="mt-1 text-xs text-muted">{formatDateTime(r.created_at)}</p>
              </div>
              {r.status === "pending" ? (
                <div className="flex gap-2">
                  <ActionButton action={decideRequest.bind(null, r.id, "approve")} label={t("requests.approve")} variant="primary" small />
                  <ActionButton action={decideRequest.bind(null, r.id, "reject")} label={t("requests.reject")} variant="danger" small />
                </div>
              ) : (
                <Badge tone={tone[r.status as Tab] ?? "archived"}>{t(`requests.status.${r.status as Tab}`)}</Badge>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
