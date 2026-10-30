import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthFrame } from "@/components/auth-frame";
import { getMe } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";

import { RegisterForm } from "./register-form";

export default async function RegisterPage({ searchParams }: PageProps<"/register">) {
  const { next } = await searchParams;
  if (await getMe()) redirect("/");
  const nextPath = typeof next === "string" ? next : undefined;

  return (
    <AuthFrame
      title={t("register.title")}
      subtitle={t("register.subtitle")}
      footer={
        <p>
          {t("register.haveAccount")}{" "}
          <Link href={nextPath ? `/login?next=${encodeURIComponent(nextPath)}` : "/login"}
                className="font-semibold text-brand hover:underline">
            {t("home.signIn")}
          </Link>
        </p>
      }
    >
      <RegisterForm next={nextPath} />
    </AuthFrame>
  );
}
