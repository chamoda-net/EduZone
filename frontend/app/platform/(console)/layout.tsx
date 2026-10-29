import Link from "next/link";
import { redirect } from "next/navigation";

import { buttonClass } from "@/components/ui";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";

import { adminSignOut } from "../actions";

type PlatformMe = { user_id: string; full_name: string; phone: string | null };

/** EduZone staff console. Every API call is also checked server-side (admin session,
 * network allowlist); this layout only decides what to show. */
export default async function PlatformConsoleLayout({ children }: LayoutProps<"/platform">) {
  const me = await api<PlatformMe>("/platform/auth/me");
  if (!me.ok) redirect("/platform/login");

  return (
    <>
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-5 text-sm">
            <span className="font-semibold">{t("platform.title")}</span>
            <Link href="/platform" className={buttonClass.link}>{t("platform.nav.tenants")}</Link>
            <Link href="/platform/payments" className={buttonClass.link}>{t("platform.nav.payments")}</Link>
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
