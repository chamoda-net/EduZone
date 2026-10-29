import { signOut } from "@/app/login/actions";
import { t } from "@/lib/i18n";

import { buttonClass } from "./ui";

export function SignOutButton() {
  return (
    <form action={signOut}>
      <button className={`${buttonClass.link} text-sm`}>{t("auth.signOut")}</button>
    </form>
  );
}
