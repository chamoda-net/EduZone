import { redirect } from "next/navigation";

import { SiteHeader } from "@/components/site-header";
import { Card } from "@eduzone/ui";
import { t } from "@eduzone/lib/i18n";
import { getMe, isStaff } from "@/lib/session";

import { LoginForm } from "./login-form";

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { next } = await searchParams;
  const me = await getMe();
  if (me) redirect(isStaff(me) ? "/org/classes" : "/");

  return (
    <>
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-4 px-4 py-10">
        <div>
          <h1 className="text-2xl font-semibold">{t("auth.title")}</h1>
          <p className="text-muted">{t("auth.subtitle")}</p>
        </div>
        <Card>
          <LoginForm next={typeof next === "string" ? next : undefined} />
        </Card>
      </main>
    </>
  );
}
