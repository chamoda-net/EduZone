import { LogOut } from "lucide-react";

import { signOut } from "@/app/login/actions";
import { t } from "@eduzone/lib/i18n";
import { buttonStyles, cx } from "@eduzone/ui";

export function SignOutButton({ tone = "light" }: { tone?: "light" | "dark" }) {
  return (
    <form action={signOut}>
      <button
        aria-label={t("auth.signOut")}
        className={cx(
          buttonStyles("ghost", "sm"),
          tone === "dark" && "w-full justify-start text-brand-100/80 hover:bg-brand-800 hover:text-on-brand",
        )}
      >
        <LogOut className="size-4" />
        <span className={tone === "light" ? "hidden sm:inline" : undefined}>{t("auth.signOut")}</span>
      </button>
    </form>
  );
}
