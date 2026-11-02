import { History, X } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { EmptyState, ErrorText, FilterChips, PageHeader, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";

type AuditPage = Schema<"AuditPage">;

// Action prefixes worth a chip. Anything else is reachable from an organization, a user or a record.
const GROUPS = [
  ["all", null],
  ["platform", "platform."],
  ["application", "platform.application."],
  ["class", "class."],
  ["grant", "grant."],
] as const;
type Group = (typeof GROUPS)[number][0];

const KEEP = ["tenant_id", "actor_id", "entity_id"] as const;

/** Everything that changed, newest first. Filters come from the URL so other screens can link here. */
export default async function AuditLogPage({ searchParams }: PageProps<"/audit">) {
  const sp = await searchParams;
  const str = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : null);
  const group: Group = GROUPS.some(([g]) => g === sp.group) ? (sp.group as Group) : "all";
  const scope = Object.fromEntries(KEEP.flatMap((k) => (str(k) ? [[k, str(k) as string]] : [])));

  const q = new URLSearchParams({ ...scope, limit: "50" });
  const prefix = GROUPS.find(([g]) => g === group)?.[1];
  if (prefix) q.set("action", prefix);
  if (str("cursor")) q.set("cursor", str("cursor") as string);
  const res = await api<AuditPage>(`/platform/audit?${q}`);

  const href = (extra: Record<string, string>) => `/audit?${new URLSearchParams({ ...scope, ...extra })}`;
  // The first row names the organization or person the list is narrowed to.
  const first = res.ok ? res.data.items[0] : undefined;
  const scopeLabel = scope.tenant_id ? first?.tenant_name : scope.actor_id ? first?.actor_name : null;

  return (
    <>
      <PageHeader title={t("platform.nav.audit")} description={t("platform.audit.body")} />
      {Object.keys(scope).length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="rounded-full bg-brand-50 px-3 py-1 font-semibold text-brand-800">
            {scopeLabel ? t("platform.audit.only", { name: scopeLabel }) : t("platform.audit.onlyEntity")}
          </span>
          <Link href={group === "all" ? "/audit" : `/audit?group=${group}`} className={`${buttonClass.link} inline-flex items-center gap-1`}>
            <X className="size-3.5" />{t("platform.audit.clear")}
          </Link>
        </div>
      )}
      <FilterChips items={GROUPS.map(([g]) => ({
        href: href(g === "all" ? {} : { group: g }),
        label: t(`platform.audit.filter.${g}`),
        active: g === group,
      }))} />

      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.items.length === 0 && <EmptyState icon={<History />} title={t("platform.audit.empty")} />}
      {res.ok && res.data.items.length > 0 && (
        <ol className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.items.map((a) => (
            <li key={a.id} className="flex flex-col gap-1.5 p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <p className="font-mono text-sm font-semibold text-brand-800">{a.action}</p>
                <time dateTime={a.created_at} className="text-xs text-muted tabular-nums">{formatDateTime(a.created_at)}</time>
              </div>
              <p className="text-sm text-muted">
                {a.actor_user_id
                  ? <Link href={`/users/${a.actor_user_id}`} className="font-medium text-foreground hover:underline">{a.actor_name}</Link>
                  : <span className="font-medium text-foreground">{t("platform.audit.system")}</span>}
                {" · "}
                {a.tenant_id
                  ? <Link href={`/tenants/${a.tenant_id}`} className="text-brand hover:underline">{a.tenant_name}</Link>
                  : t("platform.audit.platformLevel")}
                {" · "}{a.entity_type}
                {a.ip_address && <span className="font-mono text-xs"> · {a.ip_address}</span>}
              </p>
              {a.details && Object.keys(a.details).length > 0 && (
                <details className="group text-xs">
                  <summary className="cursor-pointer text-muted select-none hover:text-foreground">{t("platform.audit.details")}</summary>
                  <pre className="mt-2 overflow-x-auto rounded-ez bg-sunken p-3 font-mono text-[0.75rem] leading-relaxed whitespace-pre-wrap break-all">
                    {JSON.stringify(a.details, null, 2)}
                  </pre>
                </details>
              )}
            </li>
          ))}
        </ol>
      )}
      {res.ok && res.data.next_cursor && (
        <Link href={href({ ...(group !== "all" ? { group } : {}), cursor: res.data.next_cursor })} className={`${buttonClass.link} self-end`}>
          {t("classes.loadMore")}
        </Link>
      )}
    </>
  );
}
