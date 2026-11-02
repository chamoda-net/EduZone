import { Search, ShieldCheck, Users } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { Avatar, Badge, Button, EmptyState, ErrorText, Input, PageHeader } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";

type UserRow = Schema<"UserRow">;

/** Find an account by email, phone (any form, or its last digits) or name. */
export default async function UsersPage({ searchParams }: PageProps<"/users">) {
  const { q: raw } = await searchParams;
  const q = typeof raw === "string" ? raw.trim() : "";
  const res = q.length >= 2 ? await api<UserRow[]>(`/platform/users?${new URLSearchParams({ q })}`) : null;

  return (
    <>
      <PageHeader title={t("platform.nav.users")} />
      <form role="search" className="flex flex-col gap-1.5">
        <div className="flex gap-2">
          <label htmlFor="q" className="sr-only">{t("platform.users.search")}</label>
          <Input id="q" name="q" type="search" defaultValue={q} minLength={2} required autoFocus
                 placeholder={t("platform.users.search")} className="flex-1" />
          <Button icon={<Search className="size-4" />}>{t("market.search.go")}</Button>
        </div>
        <p className="text-xs text-muted">{t("platform.users.hint")}</p>
      </form>

      {res === null && <EmptyState icon={<Users />} title={t("platform.users.start")} />}
      {res && !res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res?.ok && res.data.length === 0 && <EmptyState icon={<Search />} title={t("platform.users.none", { q })} />}
      {res?.ok && res.data.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.map((u) => (
            <li key={u.id}>
              <Link href={`/users/${u.id}`} className="flex items-center gap-3 p-4 hover:bg-sunken/50">
                <Avatar name={u.full_name} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {u.full_name}
                    {u.is_platform_admin && (
                      <Badge tone="gold"><ShieldCheck className="size-3" />{t("platform.users.admin")}</Badge>
                    )}
                  </p>
                  <p className="truncate text-sm text-muted">
                    {[u.email, u.phone].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <div className="hidden shrink-0 text-right text-xs text-muted sm:block">
                  <p>{t("platform.users.sessionsActive", { count: u.active_sessions })}</p>
                  <p>{u.last_login_at ? t("platform.users.lastLogin", { date: formatDateTime(u.last_login_at) })
                    : t("platform.users.never")}</p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
