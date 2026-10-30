import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { classMeta, priceParts } from "@/lib/catalog";
import { t } from "@eduzone/lib/i18n";
import type { PublicClass } from "@eduzone/lib/types";
import { Avatar, ClassCover } from "@eduzone/ui";

export function ClassCard({ c, footer, index = 0, href }: {
  c: PublicClass;
  footer?: ReactNode;
  index?: number;
  /** Defaults to the tenant site's class page; the student area passes /learn/classes/<id>. */
  href?: string;
}) {
  const price = priceParts(t, c);
  return (
    <Link
      href={href ?? `/classes/${c.slug}`}
      style={{ "--i": index } as React.CSSProperties}
      className="ez-rise group flex flex-col overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm transition duration-300 ease-ez hover:-translate-y-1 hover:border-border-strong hover:shadow-ez-lg"
    >
      <div className="relative overflow-hidden">
        <ClassCover
          title={c.title}
          subject={c.subject}
          imageUrl={c.cover_image_url}
          label={c.exam ? t(`exam.${c.exam}`) : null}
          className="transition duration-500 ease-ez group-hover:scale-[1.03]"
        />
        <span className="absolute top-3 right-3 grid size-9 translate-y-1 place-items-center rounded-full bg-surface/95 text-brand opacity-0 shadow-ez transition duration-300 group-hover:translate-y-0 group-hover:opacity-100">
          <ArrowUpRight className="size-4.5" />
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <p className="text-xs font-bold tracking-[0.12em] text-brand-600 uppercase">{classMeta(t, c)}</p>
        <h3 className="font-display text-xl leading-snug font-semibold text-foreground">{c.title}</h3>
        <div className="flex items-center gap-2 text-sm text-muted">
          <Avatar name={c.teacher_name} size="sm" />
          <span className="truncate">
            {c.teacher_name}
            {c.org && c.org.name !== c.teacher_name && <span className="text-subtle"> · {c.org.name}</span>}
          </span>
        </div>
        <div className="mt-auto flex items-end justify-between gap-3 border-t border-border pt-4">
          <p className="flex items-baseline gap-1">
            <span className="font-display text-2xl font-semibold tabular-nums">{price.amount}</span>
            {price.unit && <span className="text-sm text-muted">{price.unit}</span>}
          </p>
          {footer}
        </div>
      </div>
    </Link>
  );
}
