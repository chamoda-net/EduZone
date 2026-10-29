import { t } from "@eduzone/lib/i18n";

export default function Loading() {
  return (
    <div role="status" className="flex flex-col gap-3" aria-label={t("common.loading")}>
      <div className="h-8 w-48 animate-pulse rounded-lg bg-border" />
      <div className="h-24 animate-pulse rounded-xl bg-border/60" />
      <div className="h-24 animate-pulse rounded-xl bg-border/60" />
    </div>
  );
}
