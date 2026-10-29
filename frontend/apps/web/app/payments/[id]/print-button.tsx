"use client";

import { buttonClass } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";

export function PrintButton() {
  const t = useT();
  return (
    <button type="button" onClick={() => window.print()} className={`${buttonClass.secondary} print:hidden`}>
      {t("receipt.print")}
    </button>
  );
}
