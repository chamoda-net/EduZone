import { KeyRound, Mail, Smartphone, Sparkles } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { SiteShell } from "@/components/shell";
import { getMe } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";
import { Alert, Avatar, Badge, Card, CardTitle, PageHeader, buttonStyles } from "@eduzone/ui";

import { ProfileForm, ResendEmailButton } from "./account-forms";

/** "About you" and sign-in details. Opened after registration with ?welcome=1. */
export default async function AccountPage({ searchParams }: PageProps<"/account">) {
  const me = await getMe();
  if (!me) redirect("/login?next=/account");
  const { welcome } = await searchParams;

  return (
    <SiteShell width="md">
      <PageHeader eyebrow={t("account.eyebrow")} title={t("account.title")} description={t("account.subtitle")} />
      {welcome === "1" && (
        <Alert tone="success" title={t("account.welcome.title")}>
          {t("account.welcome.body")}
        </Alert>
      )}

      <Card className="flex flex-col gap-5">
        <div className="flex items-center gap-4">
          <Avatar name={me.full_name} size="lg" />
          <div>
            <p className="font-display text-xl font-semibold">{me.full_name}</p>
            <p className="text-sm text-muted">{me.email ?? me.phone}</p>
          </div>
        </div>
        <CardTitle>{t("account.about")}</CardTitle>
        <ProfileForm me={me} />
      </Card>

      <Card className="flex flex-col gap-1">
        <CardTitle className="mb-2">{t("account.signIn")}</CardTitle>
        <Row
          icon={<Mail />}
          label={t("auth.email")}
          value={me.email ?? "—"}
          status={me.email && (me.email_verified
            ? <Badge tone="success" dot>{t("account.verified")}</Badge>
            : <Badge tone="warning" dot>{t("account.unverified")}</Badge>)}
          action={me.email && !me.email_verified && <ResendEmailButton />}
        />
        <Row
          icon={<Smartphone />}
          label={t("auth.phone")}
          value={me.phone ?? "—"}
          status={me.phone_verified
            ? <Badge tone="success" dot>{t("account.verified")}</Badge>
            : <Badge tone="warning" dot>{t("account.unverified")}</Badge>}
          action={
            <Link href="/verify-phone?change=1&next=/account" className={buttonStyles("secondary", "sm")}>
              {me.phone_verified ? t("account.changePhone") : t("account.addPhone")}
            </Link>
          }
        />
        <Row
          icon={<KeyRound />}
          label={t("auth.password")}
          value={me.has_password ? "••••••••" : t("account.noPassword")}
          action={<Link href="/recover" className={buttonStyles("secondary", "sm")}>{me.has_password ? t("account.resetPassword") : t("account.setPassword")}</Link>}
        />
      </Card>

      <p className="flex items-center gap-2 text-xs text-muted">
        <Sparkles className="size-3.5 text-gold" />
        {t("account.oneDevice")}
      </p>
    </SiteShell>
  );
}

function Row({ icon, label, value, status, action }: {
  icon: ReactNode; label: string; value: string; status?: ReactNode; action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-4 border-t border-border py-4 first-of-type:border-0">
      <span className="grid size-10 shrink-0 place-items-center rounded-ez bg-brand-50 text-brand [&>svg]:size-4.5">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold tracking-wide text-muted uppercase">{label}</p>
        <p className="flex flex-wrap items-center gap-2 truncate font-medium">
          {value} {status}
        </p>
      </div>
      {action}
    </div>
  );
}
