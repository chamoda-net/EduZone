import Link from "next/link";
import type { ReactNode } from "react";

import { classMeta, priceLabel } from "@/lib/catalog";
import { t } from "@/lib/i18n";
import type { PublicClass } from "@/lib/types";

export function ClassCard({ c, footer }: { c: PublicClass; footer?: ReactNode }) {
  return (
    <Link
      href={`/classes/${c.slug}`}
      className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4 transition hover:border-brand"
    >
      <p className="text-xs font-medium tracking-wide text-brand uppercase">{classMeta(t, c)}</p>
      <p className="text-lg leading-snug font-semibold">{c.title}</p>
      <p className="text-sm text-muted">{t("catalog.by", { name: c.teacher_name })}</p>
      <p className="mt-auto pt-2 font-medium">{priceLabel(t, c)}</p>
      {footer}
    </Link>
  );
}
