import { t } from "@eduzone/lib/i18n";
import { Skeleton } from "@eduzone/ui";

export default function Loading() {
  return (
    <div role="status" className="flex flex-col gap-6" aria-label={t("common.loading")}>
      <div className="flex flex-col gap-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-10 w-64" />
      </div>
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-64 rounded-ez-lg" />
        ))}
      </div>
    </div>
  );
}
