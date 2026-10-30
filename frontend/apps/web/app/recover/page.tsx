import Link from "next/link";

import { AuthFrame } from "@/components/auth-frame";
import { t } from "@eduzone/lib/i18n";

import { RecoverRequestForm } from "./recover-forms";

export default function RecoverPage() {
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
      <RecoverRequestForm />
    </AuthFrame>
  );
}
