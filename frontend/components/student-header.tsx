import Link from "next/link";

import { SignOutButton } from "@/components/sign-out-button";
import { SiteHeader } from "@/components/site-header";
import { buttonClass } from "@/components/ui";
import { t } from "@/lib/i18n";
import { getMe, isStaff } from "@/lib/session";

/** Header for the student side of a tenant's site. */
export async function StudentHeader() {
  const me = await getMe();
  return (
    <SiteHeader>
      {me ? (
        <>
          {isStaff(me) && (
            <Link href="/org/classes" className={`${buttonClass.link} text-sm`}>
              {t("nav.console")}
            </Link>
          )}
          <Link href="/my" className={`${buttonClass.link} text-sm`}>
            {t("nav.myClasses")}
          </Link>
          <SignOutButton />
        </>
      ) : (
        <Link href="/login" className={`${buttonClass.link} text-sm`}>
          {t("home.signIn")}
        </Link>
      )}
    </SiteHeader>
  );
}
