import { Building2, LogOut, Receipt } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { t } from "@eduzone/lib/i18n";
import { Avatar, ConsoleFrame, Logo } from "@eduzone/ui";

import { adminSignOut } from "../actions";

type PlatformMe = Schema<"PlatformMe">;

/** EduZone staff console. Every API call is also checked server-side (admin session,
 * network allowlist); this layout only decides what to show. */
export default async function PlatformConsoleLayout({ children }: LayoutProps<"/">) {
  const me = await api<PlatformMe>("/platform/auth/me");
  if (!me.ok) redirect("/login");

  return (
    <ConsoleFrame
      menuLabel={t("nav.menu")}
      brand={
        <Link href="/" className="block">
          <Logo name="EduZone" sub={t("platform.badge")} />
        </Link>
      }
      items={[
        { href: "/", label: t("platform.nav.tenants"), icon: <Building2 />, exact: true },
        { href: "/payments", label: t("platform.nav.payments"), icon: <Receipt /> },
      ]}
      footer={
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3 px-3 py-2">
            <Avatar name={me.data.full_name} size="sm" className="ring-brand-900" />
            <p className="truncate text-sm font-semibold text-on-brand">{me.data.full_name}</p>
          </div>
          <form action={adminSignOut}>
            <button className="flex min-h-9 w-full items-center gap-2 rounded-ez px-3 text-sm font-medium text-brand-100/80 hover:bg-brand-800 hover:text-on-brand">
              <LogOut className="size-4" />
              {t("auth.signOut")}
            </button>
          </form>
        </div>
      }
    >
      {children}
    </ConsoleFrame>
  );
}
