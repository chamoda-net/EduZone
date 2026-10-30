import { AuthFrame } from "@/components/auth-frame";
import { t } from "@eduzone/lib/i18n";

import { ConfirmEmailForm } from "./confirm-form";

/** Opened from the emailed link; confirms on a button press (mail scanners open links too). */
export default async function VerifyEmailPage({ searchParams }: PageProps<"/verify-email">) {
  const { token } = await searchParams;
  return (
    <AuthFrame title={t("email.title")} subtitle={t("email.subtitle")}>
      <ConfirmEmailForm token={typeof token === "string" ? token : ""} />
    </AuthFrame>
  );
}
