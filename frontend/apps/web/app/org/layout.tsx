import { Clapperboard, ExternalLink, HandCoins, Inbox, Landmark, LibraryBig, Receipt } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { SignOutButton } from "@/components/sign-out-button";
import { SiteShell } from "@/components/shell";
import { getBranding, getMe, isStaff } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";
import { Avatar, ConsoleFrame, EmptyState, Logo, buttonStyles, type NavItem } from "@eduzone/ui";

// Organization console: owners, admins and teachers. The API enforces the same rule on
// every call; this layout only decides what to show.
export default async function OrgLayout({ children }: LayoutProps<"/org">) {
  const [me, branding] = await Promise.all([getMe(), getBranding()]);
  if (!me) redirect("/login?next=/org/classes");

  if (!isStaff(me)) {
    return (
      <SiteShell width="md">
        <EmptyState
          icon={<LibraryBig />}
          title={t("org.notStaff.title")}
          body={t("org.notStaff.body")}
          action={<Link href="/" className={buttonStyles("secondary")}>{t("org.home")}</Link>}
        />
      </SiteShell>
    );
  }

  // Owners and admins also see Money (the API enforces the same rule).
  const managesAll = me.role === "owner" || me.role === "admin";
  const items: NavItem[] = [
    { href: "/org/classes", label: t("org.nav.classes"), icon: <LibraryBig /> },
    { href: "/org/requests", label: t("org.nav.requests"), icon: <Inbox /> },
    { href: "/org/payments", label: t("org.nav.payments"), icon: <Receipt /> },
    { href: "/org/earnings", label: t("org.nav.earnings"), icon: <HandCoins /> },
    ...(managesAll ? [{ href: "/org/money", label: t("org.nav.money"), icon: <Landmark /> }] : []),
    { href: "/org/media", label: t("org.nav.media"), icon: <Clapperboard /> },
  ];

  return (
    <ConsoleFrame
      menuLabel={t("nav.menu")}
      brand={
        <Link href="/org/classes" className="block">
          <Logo name={branding?.name ?? "EduZone"} sub={t("shell.console")} />
        </Link>
      }
      items={items}
      footer={
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3 px-3 py-2">
            <Avatar name={me.full_name} size="sm" className="ring-brand-900" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-on-brand">{me.full_name}</p>
              <p className="text-xs text-brand-100/60">{t(`role.${me.role}` as "role.owner")}</p>
            </div>
          </div>
          <Link
            href="/"
            className="flex min-h-9 items-center gap-2 rounded-ez px-3 text-sm font-medium text-brand-100/80 hover:bg-brand-800 hover:text-on-brand"
          >
            <ExternalLink className="size-4" />
            {t("nav.viewSite")}
          </Link>
          <SignOutButton tone="dark" />
        </div>
      }
    >
      {children}
    </ConsoleFrame>
  );
}
