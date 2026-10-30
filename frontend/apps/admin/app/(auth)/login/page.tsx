import { ShieldCheck } from "lucide-react";

import { t } from "@eduzone/lib/i18n";
import { Card, Logo } from "@eduzone/ui";

import { AdminLoginForm } from "./login-form";

export default function AdminLoginPage() {
  return (
    <main className="ez-grain relative flex flex-1 flex-col items-center justify-center overflow-hidden bg-brand-900 px-4 py-12">
      <svg aria-hidden viewBox="0 0 600 600" className="absolute -top-56 -right-56 w-[680px] opacity-50">
        {[110, 170, 230, 290].map((r) => (
          <circle key={r} cx="300" cy="300" r={r} fill="none" stroke="var(--ez-brand-600)" />
        ))}
      </svg>
      <div className="relative flex w-full max-w-sm flex-col gap-6">
        <div className="text-on-brand">
          <Logo name="EduZone" sub={t("platform.badge")} />
        </div>
        <Card className="ez-rise flex flex-col gap-5 shadow-ez-lg">
          <div className="flex flex-col gap-1.5">
            <h1 className="font-display text-3xl font-semibold">{t("platform.signIn")}</h1>
            <p className="text-sm text-muted">{t("platform.signInBody")}</p>
          </div>
          <AdminLoginForm />
        </Card>
        <p className="flex items-center justify-center gap-2 text-xs text-brand-100/60">
          <ShieldCheck className="size-3.5" />
          {t("platform.privateNote")}
        </p>
      </div>
    </main>
  );
}
