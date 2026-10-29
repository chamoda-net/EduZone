import Link from "next/link";

import { SignOutButton } from "@/components/sign-out-button";
import { SiteHeader } from "@/components/site-header";
import { buttonClass } from "@/components/ui";
import { t } from "@/lib/i18n";
import { getBranding, getMe, isStaff } from "@/lib/session";

export default async function Home() {
  const [branding, me] = await Promise.all([getBranding(), getMe()]);

  return (
    <>
      <SiteHeader>{me && <SignOutButton />}</SiteHeader>
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-10">
        <h1 className="text-3xl font-semibold tracking-tight">{t("app.tagline", { org: branding?.name ?? "" })}</h1>
        {!me && (
          <Link href="/login" className={`${buttonClass.primary} self-start`}>
            {t("home.signIn")}
          </Link>
        )}
        {me && (
          <div className="flex flex-col gap-3">
            <p className="text-muted">{t("home.signedInAs", { name: me.full_name })}</p>
            {isStaff(me) ? (
              <Link href="/org/classes" className={`${buttonClass.primary} self-start`}>
                {t("home.openConsole")}
              </Link>
            ) : (
              <p>{t("home.studentSoon")}</p>
            )}
          </div>
        )}
      </main>
      <footer className="px-4 py-6 text-center text-xs text-muted">{t("app.poweredBy")}</footer>
    </>
  );
}
