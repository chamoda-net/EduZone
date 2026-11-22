import Link from "next/link";

import { Photo } from "@/components/photo";
import { subjectPhoto } from "@/lib/photos";
import { t } from "@eduzone/lib/i18n";
import type { SubjectOut } from "@eduzone/lib/types";
import { ClassCover } from "@eduzone/ui";

/** A subject on the home page and directories: a photo of the subject (or its generated cover), name and counts. */
export function SubjectTile({ s, i = 0 }: { s: SubjectOut; i?: number }) {
  const photo = subjectPhoto(s.slug) ?? subjectPhoto(s.name);
  const soon = s.class_count === 0;
  return (
    <li className="ez-rise" style={{ "--i": i } as React.CSSProperties}>
      <Link
        href={`/${s.slug}`}
        className="group relative block aspect-[4/3] overflow-hidden rounded-ez-lg shadow-ez-sm ring-1 ring-black/5 transition duration-300 ease-ez hover:-translate-y-1 hover:shadow-ez-lg"
      >
        {photo ? (
          <Photo photo={photo} ratio={0.75} alt="" sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
                 className={`absolute inset-0 h-full transition duration-700 ease-ez group-hover:scale-[1.06] ${soon ? "saturate-50" : ""}`} />
        ) : (
          <ClassCover title={s.name} subject={s.name} size="sm" className="absolute inset-0 h-full" />
        )}
        <div aria-hidden className="absolute inset-0 bg-gradient-to-t from-brand-950/85 via-brand-950/25 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 flex flex-col gap-0.5 p-3 text-on-brand sm:p-4">
          <p className="font-display text-lg leading-tight font-semibold sm:text-xl">{s.name}</p>
          <p className="text-xs text-brand-100/85">
            {soon ? t("market.subject.soon") : t("market.subject.counts", { classes: s.class_count, teachers: s.teacher_count })}
          </p>
        </div>
      </Link>
    </li>
  );
}
