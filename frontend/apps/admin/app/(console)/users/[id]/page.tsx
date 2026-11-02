import { Laptop, ShieldCheck, Smartphone } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { ActionButton } from "@eduzone/ui/action-button";
import { Avatar, Badge, Card, CardTitle, DataList, ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { deviceLabel } from "@/lib/platform";

import { forgetDevice, signOutUser } from "../../../actions";

type UserDetail = Schema<"UserDetail">;
type UserSession = Schema<"UserSession">;

const REASONS = new Set(["signed_in_on_another_device", "platform_admin", "logout"]);

function endedReason(s: UserSession): string {
  if (!s.revoked_at) return t("platform.users.reason.expired");
  return REASONS.has(s.revoke_reason ?? "") ? t(`platform.users.reason.${s.revoke_reason as "logout"}`) : t("platform.users.reason.other");
}

function DeviceIcon({ ua }: { ua: string | null | undefined }) {
  const Icon = ua && /Android|iPhone|Mobile/.test(ua) ? Smartphone : Laptop;
  return <Icon className="size-4.5 shrink-0 text-brand-600" aria-hidden />;
}

/** One account: who they are, where they are signed in, the devices they trust, and their organizations. */
export default async function UserPage({ params }: PageProps<"/users/[id]">) {
  const { id } = await params;
  const res = await api<UserDetail>(`/platform/users/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const u = res.data;
  const verified = (ok: boolean) => (ok ? null : <span className="text-warning"> ({t("platform.users.unverified")})</span>);
  const signIn = [u.has_password && t("platform.users.password"), u.google_linked && t("platform.users.google")]
    .filter(Boolean).join(" · ") || t("platform.users.noSignIn");

  return (
    <>
      <Link href="/users" className={`${buttonClass.link} text-sm`}>← {t("platform.users.back")}</Link>
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Avatar name={u.full_name} size="lg" />
          <div className="min-w-0">
            <h1 className="flex flex-wrap items-center gap-2 font-display text-3xl font-semibold">
              {u.full_name}
              {u.is_platform_admin && <Badge tone="gold"><ShieldCheck className="size-3" />{t("platform.users.admin")}</Badge>}
            </h1>
            <p className="text-sm text-muted">
              {t("platform.users.joined", { date: formatDateTime(u.created_at) })} ·{" "}
              {u.last_login_at ? t("platform.users.lastLogin", { date: formatDateTime(u.last_login_at) }) : t("platform.users.never")}
            </p>
          </div>
        </div>
        {u.active_sessions > 0 && (
          <ActionButton
            variant="danger"
            action={signOutUser.bind(null, u.id)}
            label={t("platform.users.signOut")}
            confirm={t("platform.users.confirmSignOut")}
            done={t("platform.users.signedOut")}
          />
        )}
      </header>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <DataList items={[
            [t("auth.email"), <>{u.email ?? "—"}{u.email && verified(u.email_verified)}</>],
            [t("auth.phone"), <>{u.phone ?? "—"}{u.phone && verified(u.phone_verified)}</>],
            [t("platform.users.signInWith"), signIn],
            ...(u.exam ? [[t("account.exam"), `${t(`exam.${u.exam as "ol"}`)}${u.exam_year ? ` ${u.exam_year}` : ""}`] as [string, string]] : []),
            ...(u.school ? [[t("account.school"), u.school] as [string, string]] : []),
          ]} />
          <Link href={`/audit?actor_id=${u.id}`} className={`${buttonClass.link} mt-2 text-sm`}>
            {t("platform.users.activity")} →
          </Link>
        </Card>

        <Card className="flex flex-col gap-3">
          <CardTitle>{t("platform.users.memberOf")}</CardTitle>
          {u.member_of.length === 0 && <p className="text-sm text-muted">{t("platform.users.noMemberships")}</p>}
          <ul className="divide-y divide-border">
            {u.member_of.map((m) => (
              <li key={m.member_id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <Link href={`/tenants/${m.tenant_id}`} className="min-w-0 truncate font-medium text-brand hover:underline">
                  {m.tenant_name}
                </Link>
                <span className="flex shrink-0 items-center gap-2">
                  <Badge tone={m.role === "student" ? "neutral" : "brand"}>{t(`role.${m.role as "student"}`)}</Badge>
                  {m.status !== "active" && <Badge tone="warning">{t(`platform.users.member.${m.status as "invited" | "suspended" | "left"}`)}</Badge>}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="flex flex-col gap-3">
        <div>
          <CardTitle>{t("platform.users.devices")}</CardTitle>
          <p className="text-sm text-muted">{t("platform.users.devicesBody")}</p>
        </div>
        {u.devices.length === 0 && <p className="text-sm text-muted">{t("platform.users.noDevices")}</p>}
        <ul className="divide-y divide-border">
          {u.devices.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <DeviceIcon ua={d.user_agent} />
                <div className="min-w-0">
                  <p className="font-medium">{deviceLabel(d.user_agent) ?? t("platform.users.unknownDevice")}</p>
                  <p className="text-xs text-muted">
                    {t("platform.users.trusted", { date: formatDateTime(d.trusted_at) })} ·{" "}
                    {t("platform.users.seen", { date: formatDateTime(d.last_seen_at) })}
                  </p>
                </div>
              </div>
              <ActionButton
                small
                action={forgetDevice.bind(null, u.id, d.id)}
                label={t("platform.users.forget")}
                confirm={t("platform.users.confirmForget")}
                done={t("platform.users.forgotten")}
              />
            </li>
          ))}
        </ul>
      </Card>

      <Card className="flex flex-col gap-3">
        <div>
          <CardTitle>{t("platform.users.sessions")}</CardTitle>
          <p className="text-sm text-muted">{t("platform.users.sessionsBody")}</p>
        </div>
        {u.sessions.length === 0 && <p className="text-sm text-muted">{t("platform.users.noSessions")}</p>}
        <ul className="divide-y divide-border">
          {u.sessions.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
              <div className="flex min-w-0 items-center gap-3">
                <DeviceIcon ua={s.user_agent} />
                <div className="min-w-0">
                  <p className="font-medium">{deviceLabel(s.user_agent) ?? t("platform.users.unknownDevice")}</p>
                  <p className="text-xs text-muted">
                    {s.ip_address ? `${s.ip_address} · ` : ""}
                    {s.active
                      ? t("platform.users.seen", { date: formatDateTime(s.last_seen_at) })
                      : `${t("platform.users.ended", { date: formatDateTime(s.revoked_at ?? s.expires_at) })} · ${endedReason(s)}`}
                  </p>
                </div>
              </div>
              {s.active
                ? <Badge tone="success">{t("platform.users.active")}</Badge>
                : <Badge tone="neutral">{endedReason(s)}</Badge>}
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
