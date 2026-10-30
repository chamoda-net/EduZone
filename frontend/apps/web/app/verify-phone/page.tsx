import { redirect } from "next/navigation";

import { AuthFrame } from "@/components/auth-frame";
import { getMe } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";

import { PhoneForm } from "./phone-form";

/** Step 2 of registration (and changing the number later): a unique mobile number, by SMS. */
export default async function VerifyPhonePage({ searchParams }: PageProps<"/verify-phone">) {
  const { next, change } = await searchParams;
  const nextPath = typeof next === "string" ? next : "/";
  const me = await getMe();
  if (!me) redirect(`/login?next=${encodeURIComponent(`/verify-phone?next=${nextPath}`)}`);
  if (me.phone_verified && change !== "1") redirect(nextPath);

  return (
    <AuthFrame title={t("phone.title")} subtitle={t("phone.subtitle")}>
      <PhoneForm next={nextPath} />
    </AuthFrame>
  );
}
