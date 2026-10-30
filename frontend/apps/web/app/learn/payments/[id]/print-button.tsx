"use client";

import { Printer } from "lucide-react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button } from "@eduzone/ui";

export function PrintButton() {
  const t = useT();
  return (
    <Button type="button" variant="secondary" onClick={() => window.print()} icon={<Printer className="size-4" />} className="ez-no-print">
      {t("receipt.print")}
    </Button>
  );
}
