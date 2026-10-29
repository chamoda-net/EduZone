import { Card } from "@/components/ui";
import { t } from "@/lib/i18n";

import { AdminLoginForm } from "./login-form";

export default function AdminLoginPage() {
  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-4 px-4 py-12">
      <div>
        <p className="text-sm font-semibold text-muted">{t("platform.title")}</p>
        <h1 className="text-2xl font-semibold">{t("platform.signIn")}</h1>
        <p className="text-sm text-muted">{t("platform.signInBody")}</p>
      </div>
      <Card>
        <AdminLoginForm />
      </Card>
    </main>
  );
}
