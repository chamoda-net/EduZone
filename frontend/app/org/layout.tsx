import Link from "next/link";
import { redirect } from "next/navigation";

import { SignOutButton } from "@/components/sign-out-button";
import { SiteHeader } from "@/components/site-header";
import { buttonClass } from "@/components/ui";
import { t } from "@/lib/i18n";
import { getMe, isStaff } from "@/lib/session";

// Organization console: owners, admins and teachers. The API enforces the same rule on
// every call; this layout only decides what to show.
export default async function OrgLayout({ children }: LayoutProps<"/org">) {
  const me = await getMe();
  if (!me) redirect("/login?next=/org/classes");

  return (
    <>
      <SiteHeader href="/org/classes">
        <span className="hidden text-sm text-muted sm:inline">
          {me.full_name} · {t(`role.${me.role}`)}
        </span>
        <SignOutButton />
      </SiteHeader>
      {isStaff(me) ? (
        <>
          <nav className="border-b border-border bg-surface">
            <div className="mx-auto flex w-full max-w-4xl gap-4 px-4 text-sm">
              <Link href="/org/classes" className="border-b-2 border-brand py-2.5 font-medium">
                {t("org.nav.classes")}
              </Link>
            </div>
          </nav>
          <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-5 px-4 py-6">{children}</main>
        </>
      ) : (
        <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-3 px-4 py-16">
          <h1 className="text-xl font-semibold">{t("org.notStaff.title")}</h1>
          <p className="text-muted">{t("org.notStaff.body")}</p>
          <Link href="/" className={`${buttonClass.secondary} self-start`}>
            {t("org.home")}
          </Link>
        </main>
      )}
    </>
  );
}
