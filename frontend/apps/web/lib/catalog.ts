import type { Translate } from "@eduzone/lib/i18n";
import { formatMoney } from "@eduzone/lib/format";
import type { ClassItem } from "@eduzone/lib/types";

export function priceLabel(t: Translate, c: Pick<ClassItem, "pricing_model" | "monthly_fee_cents" | "one_time_price_cents" | "currency">): string {
  if (c.pricing_model === "monthly" && c.monthly_fee_cents !== null) {
    return t("classes.perMonth", { amount: formatMoney(c.monthly_fee_cents, c.currency) });
  }
  if (c.pricing_model === "one_time" && c.one_time_price_cents !== null) {
    return t("classes.once", { amount: formatMoney(c.one_time_price_cents, c.currency) });
  }
  return t("classes.free");
}

export function classMeta(t: Translate, c: Pick<ClassItem, "subject" | "exam" | "batch_year" | "medium">): string {
  return [c.subject, c.exam && t(`exam.${c.exam}`), c.batch_year, c.medium && t(`medium.${c.medium}`)]
    .filter(Boolean)
    .join(" · ");
}
