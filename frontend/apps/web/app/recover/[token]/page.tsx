import { AuthFrame } from "@/components/auth-frame";
import { t } from "@eduzone/lib/i18n";

import { RecoverCompleteForm } from "../recover-forms";

/** Opened from the emailed link. Nothing happens until the person presses Continue, so mail
 * scanners that open links can't spend the code or send SMS. */
export default async function RecoverTokenPage({ params }: PageProps<"/recover/[token]">) {
  const { token } = await params;
  return (
    <AuthFrame title={t("recover.newTitle")} subtitle={t("recover.newSubtitle")}>
      <RecoverCompleteForm token={token} />
    </AuthFrame>
  );
}
