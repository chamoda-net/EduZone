import Link from "next/link";

import { t } from "@eduzone/lib/i18n";
import type { SubjectOut } from "@eduzone/lib/types";
import { ClassCover } from "@eduzone/ui";

/** A subject on the home page and directories: its generated cover, name and counts. */
export function SubjectTile({ s, i = 0 }: { s: SubjectOut; i?: number }) {
  return (
    <li className="ez-rise" style={{ "--i": i } as React.CSSProperties}>
      <Link
        href={`/${s.slug}`}
        className="group flex h-full flex-col overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm transition hover:-translate-y-0.5 hover:shadow-ez"
      >
        <div className="h-20 overflow-hidden sm:h-24">
          <ClassCover title={s.name} subject={s.name} size="sm" className="h-full object-cover transition duration-500 group-hover:scale-105" />
        </div>
        <div className="flex flex-1 flex-col gap-0.5 p-3 sm:p-4">
          <p className="font-display text-lg leading-tight font-semibold">{s.name}</p>
          <p className="text-xs text-muted">
            {s.class_count > 0 ? t("market.subject.counts", { classes: s.class_count, teachers: s.teacher_count }) : t("market.subject.soon")}
          </p>
        </div>
      </Link>
    </li>
  );
}
