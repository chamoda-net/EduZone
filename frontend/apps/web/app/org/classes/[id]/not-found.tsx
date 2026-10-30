import Link from "next/link";

import { buttonClass } from "@eduzone/ui";
import { t } from "@eduzone/lib/i18n";

export default function ClassNotFound() {
  return (
    <div className="flex flex-col items-start gap-3 py-10">
      <h1 className="font-display text-2xl font-semibold">{t("classes.notFound")}</h1>
      <Link href="/org/classes" className={buttonClass.secondary}>
        {t("classes.back")}
      </Link>
    </div>
  );
}
