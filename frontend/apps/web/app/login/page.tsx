import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthFrame } from "@/components/auth-frame";
import { getSession, isStaff } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";
import { Alert } from "@eduzone/ui";

import { LoginForm } from "./login-form";

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { next } = await searchParams;
  const { me, endedElsewhere } = await getSession();
  if (me) redirect(isStaff(me) ? "/teach" : "/learn");
  const nextPath = typeof next === "string" ? next : undefined;

  return (
    <AuthFrame
      title={t("auth.title")}
      subtitle={t("auth.subtitle")}
      footer={
        <p>
          {t("auth.noAccount")}{" "}
          <Link href={nextPath ? `/register?next=${encodeURIComponent(nextPath)}` : "/register"}
                className="font-semibold text-brand hover:underline">
            {t("auth.createAccount")}
          </Link>
        </p>
      }
    >
      <div className="flex flex-col gap-5">
        {endedElsewhere && <Alert tone="warning" title={t("auth.elsewhere.title")}>{t("auth.elsewhere.body")}</Alert>}
        <LoginForm next={nextPath} />
      </div>
    </AuthFrame>
  );
}
