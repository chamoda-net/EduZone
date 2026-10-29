import Link from "next/link";
import { redirect } from "next/navigation";

import { buttonClass } from "@eduzone/ui";
import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { t } from "@eduzone/lib/i18n";

import { adminSignOut } from "../actions";

type PlatformMe = Schema<"PlatformMe">;

/** EduZone staff console. Every API call is also checked server-side (admin session,
 * network allowlist); this layout only decides what to show. */
export default async function PlatformConsoleLayout({ children }: LayoutProps<"/">) {
  const me = await api<PlatformMe>("/platform/auth/me");
  if (!me.ok) redirect("/login");

  return (
    <>
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-5 text-sm">
            <span className="font-semibold">{t("platform.title")}</span>
            <Link href="/" className={buttonClass.link}>{t("platform.nav.tenants")}</Link>
            <Link href="/payments" className={buttonClass.link}>{t("platform.nav.payments")}</Link>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-muted sm:inline">{me.data.full_name}</span>
            <form action={adminSignOut}>
              <button className={buttonClass.link}>{t("auth.signOut")}</button>
            </form>
          </div>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-4 py-6">{children}</main>
    </>
  );
}
