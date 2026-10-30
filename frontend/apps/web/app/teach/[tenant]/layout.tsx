import { Clapperboard, ExternalLink, Hourglass, HandCoins, Inbox, Landmark, LibraryBig, Receipt, UserRound } from "lucide-react";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { SignOutButton } from "@/components/sign-out-button";
import { SiteShell } from "@/components/shell";
import { WorkspaceSwitcher } from "@/components/workspace-switcher";
import { getMe } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";
import { Avatar, ConsoleFrame, EmptyState, Logo, buttonStyles, type NavItem } from "@eduzone/ui";

// Teacher / institute console for one workspace (/teach/<slug>). Only its owners, admins and
// teachers get in; the API checks the same membership on every call.
export default async function TeachLayout({ children, params }: LayoutProps<"/teach/[tenant]">) {
  const { tenant } = await params;
  if (!/^[a-z0-9-]+$/.test(tenant)) notFound();
  const base = `/teach/${tenant}`;
  const me = await getMe();
  if (!me) redirect(`/login?next=${encodeURIComponent(base)}`);

  const workspace = me.workspaces.find((w) => w.slug === tenant);
  if (!workspace) {
    return (
      <SiteShell width="md">
        <EmptyState
          icon={<LibraryBig />}
          title={t("org.notStaff.title")}
          body={t("org.notStaff.body")}
          action={<Link href="/learn" className={buttonStyles("secondary")}>{t("org.home")}</Link>}
        />
      </SiteShell>
    );
  }

  // Owners and admins also see Money (the API enforces the same rule).
  const managesAll = workspace.role === "owner" || workspace.role === "admin";
  const items: NavItem[] = [
    { href: `${base}/classes`, label: t("org.nav.classes"), icon: <LibraryBig /> },
    { href: `${base}/requests`, label: t("org.nav.requests"), icon: <Inbox /> },
    { href: `${base}/payments`, label: t("org.nav.payments"), icon: <Receipt /> },
    { href: `${base}/earnings`, label: t("org.nav.earnings"), icon: <HandCoins /> },
    ...(managesAll ? [{ href: `${base}/money`, label: t("org.nav.money"), icon: <Landmark /> }] : []),
    { href: `${base}/media`, label: t("org.nav.media"), icon: <Clapperboard /> },
    { href: `${base}/profile`, label: t("org.nav.profile"), icon: <UserRound /> },
  ];

  return (
    <ConsoleFrame
      menuLabel={t("nav.menu")}
      brand={
        <Link href={`${base}/classes`} className="block">
          <Logo name={workspace.name} sub={t("shell.console")} />
        </Link>
      }
      items={items}
      footer={
        <div className="flex flex-col gap-1">
          {me.workspaces.length > 1 && (
            <WorkspaceSwitcher current={workspace.slug} workspaces={me.workspaces} label={t("teach.switch")} />
          )}
          <div className="flex items-center gap-3 px-3 py-2">
            <Avatar name={me.full_name} size="sm" className="ring-brand-900" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-on-brand">{me.full_name}</p>
              <p className="text-xs text-brand-100/60">{t(`role.${workspace.role}`)}</p>
            </div>
          </div>
          <Link
            href="/learn"
            className="flex min-h-9 items-center gap-2 rounded-ez px-3 text-sm font-medium text-brand-100/80 hover:bg-brand-800 hover:text-on-brand"
          >
            <ExternalLink className="size-4" />
            {t("teach.studentArea")}
          </Link>
          <SignOutButton tone="dark" />
        </div>
      }
    >
      {workspace.status === "pending" && (
        <div className="mb-6 flex flex-col gap-3 rounded-ez-lg border border-gold/40 bg-gold/10 p-4 sm:flex-row sm:items-center">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-brand-900 text-gold">
            <Hourglass className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold">{t("draft.title")}</p>
            <p className="text-sm text-muted">{t("draft.body")}</p>
          </div>
          <Link href="/teach/apply" className={buttonStyles("secondary", "sm", "self-start sm:self-center")}>
            {t("draft.link")}
          </Link>
        </div>
      )}
      {children}
    </ConsoleFrame>
  );
}
