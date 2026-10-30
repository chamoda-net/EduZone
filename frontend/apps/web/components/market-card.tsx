import { ArrowUpRight, MonitorPlay, Users, Video } from "lucide-react";
import Link from "next/link";

import { TeacherAvatar } from "@/components/teacher-avatar";
import { classMeta, priceParts } from "@/lib/catalog";
import { formatMonth } from "@eduzone/lib/format";
import { t } from "@eduzone/lib/i18n";
import type { MarketClass } from "@eduzone/lib/types";
import { Badge, ClassCover } from "@eduzone/ui";

/** A class on the marketplace: cover, what and who, how it runs, price. */
export function MarketClassCard({ c, index = 0 }: { c: MarketClass; index?: number }) {
  const price = priceParts(t, {
    pricing_model: c.pricing_model,
    monthly_fee_cents: c.open_month_fee_cents ?? c.monthly_fee_cents,
    one_time_price_cents: c.one_time_price_cents,
    currency: c.currency,
  });
  return (
    <Link
      href={c.path}
      style={{ "--i": index } as React.CSSProperties}
      className="ez-rise group flex flex-col overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm transition duration-300 ease-ez hover:-translate-y-1 hover:border-border-strong hover:shadow-ez-lg"
    >
      <div className="relative overflow-hidden">
        <ClassCover
          title={c.title}
          subject={c.subject_name}
          imageUrl={c.cover_image_url}
          label={c.exam ? t(`exam.${c.exam}`) : null}
          className="transition duration-500 ease-ez group-hover:scale-[1.03]"
        />
        {c.open_month_start && (
          <Badge tone="gold" className="absolute bottom-3 left-3 shadow-ez-sm">
            {t("market.card.joinMonth", { month: formatMonth(c.open_month_start) })}
          </Badge>
        )}
        <span className="absolute top-3 right-3 grid size-9 translate-y-1 place-items-center rounded-full bg-surface/95 text-brand opacity-0 shadow-ez transition duration-300 group-hover:translate-y-0 group-hover:opacity-100">
          <ArrowUpRight className="size-4.5" />
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <p className="truncate text-xs font-bold tracking-[0.12em] text-brand-600 uppercase">
          {classMeta(t, { subject: c.subject_name, exam: c.exam, batch_year: c.batch_year, medium: c.medium })}
        </p>
        <h3 className="font-display text-xl leading-snug font-semibold text-foreground">{c.title}</h3>
        <div className="flex min-w-0 items-center gap-2 text-sm text-muted">
          <TeacherAvatar name={c.teacher_name} photo={c.teacher_photo_url} size="sm" />
          <span className="truncate">
            {c.teacher_name}
            {c.org_type === "institute" && <span className="text-subtle"> · {c.org_name}</span>}
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {c.has_live && <Badge tone="brand"><Video className="size-3" />{t("market.card.live")}</Badge>}
          {c.has_recorded && <Badge tone="info"><MonitorPlay className="size-3" />{t("market.card.recorded")}</Badge>}
          {c.has_free_preview && <Badge tone="gold">{t("class.freePreview")}</Badge>}
        </div>
        <div className="mt-auto flex items-end justify-between gap-3 border-t border-border pt-4">
          <p className="flex min-w-0 flex-wrap items-baseline gap-x-1">
            <span className="font-display text-2xl font-semibold whitespace-nowrap tabular-nums">{price.amount}</span>
            {price.unit && <span className="text-sm text-muted">{price.unit}</span>}
          </p>
          {c.students > 0 && (
            <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium whitespace-nowrap text-muted">
              <Users className="size-3.5" />
              {t("market.card.students", { count: c.students })}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
