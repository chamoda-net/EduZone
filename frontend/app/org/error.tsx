"use client";

import { buttonClass } from "@/components/ui";
import { useT } from "@/lib/i18n/client";

// Unexpected failures in the console (API down, a bug). Expected API errors are shown inline.
export default function OrgError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const t = useT();
  return (
    <div className="flex flex-col items-start gap-3 py-10">
      <h1 className="text-xl font-semibold">{t("errors.generic")}</h1>
      <button className={buttonClass.secondary} onClick={() => reset()}>
        {t("common.tryAgain")}
      </button>
    </div>
  );
}
