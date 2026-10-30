import { ImageResponse } from "next/og";

import { OG_SIZE, OgCard } from "@/components/og-card";
import { market } from "@/lib/market";
import type { MarketClassDetail } from "@eduzone/lib/types";
import { t } from "@eduzone/lib/i18n";
import { initials } from "@eduzone/ui";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Class on EduZone";

/** WhatsApp / Facebook preview for a class page: title, teacher and subject. */
export default async function Image({ params }: { params: Promise<{ subject: string; teacher: string; class: string }> }) {
  const p = await params;
  const d = await market<MarketClassDetail>(`/classes/${p.subject}/${p.teacher}/${p.class}`);
  return new ImageResponse(
    <OgCard eyebrow={d.class.subject_name} title={d.class.title} subtitle={t("market.og.withTeacher", { name: d.teacher.display_name })}
            initials={initials(d.teacher.display_name)} />,
    size,
  );
}
