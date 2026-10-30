import { ImageResponse } from "next/og";

import { OG_SIZE, OgCard } from "@/components/og-card";
import { market } from "@/lib/market";
import type { TeacherPage } from "@eduzone/lib/types";
import { t } from "@eduzone/lib/i18n";
import { initials } from "@eduzone/ui";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Teacher on EduZone";

/** WhatsApp / Facebook preview for a teacher page: name, subject and headline. */
export default async function Image({ params }: { params: Promise<{ subject: string; teacher: string }> }) {
  const p = await params;
  const { teacher, subject } = await market<TeacherPage>(`/teachers/${p.teacher}?subject=${encodeURIComponent(p.subject)}`);
  return new ImageResponse(
    <OgCard eyebrow={t("market.og.teacherEyebrow", { subject: subject?.name ?? "" })} title={teacher.display_name}
            subtitle={teacher.headline ?? t("market.teacher.classes", { count: teacher.class_count })}
            initials={initials(teacher.display_name)} />,
    size,
  );
}
