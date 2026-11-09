"use client";

import { Link2 } from "lucide-react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, toast } from "@eduzone/ui";

export function CopyLink({ url }: { url: string }) {
  const t = useT();
  return (
    <Button variant="ghost" size="sm" icon={<Link2 className="size-4" />}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(url);
                toast(t("cert.copied"));
              } catch {
                toast(t("share.copyFailed"));
              }
            }}>
      {t("cert.copy")}
    </Button>
  );
}
