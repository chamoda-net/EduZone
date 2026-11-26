import Link from "next/link";

import { AuthFrame } from "@/components/auth-frame";
import { rememberedEmail } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";

import { RecoverRequestForm } from "./recover-forms";

export default async function RecoverPage() {
  return (
    <AuthFrame
      title={t("recover.title")}
      subtitle={t("recover.subtitle")}
      footer={
        <Link href="/login" className="font-semibold text-brand hover:underline">
          {t("recover.back")}
        </Link>
      }
    >
      <RecoverRequestForm email={await rememberedEmail()} />
    </AuthFrame>
  );
}
