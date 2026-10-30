import type { Metadata } from "next";

import { SiteShell } from "@/components/shell";
import { t, type MessageKey } from "@eduzone/lib/i18n";
import { Alert, PageHeader } from "@eduzone/ui";

/** About, terms, privacy, refunds, contact: required for payment gateway approval. Their final
 * wording is pending the legal review (CLAUDE.md section 2), so each shows a draft notice. */
export function staticMetadata(title: MessageKey): Metadata {
  return { title: `${t(title)} | EduZone` };
}

export function StaticPage({ title, sections }: { title: MessageKey; sections: Array<[MessageKey, MessageKey]> }) {
  return (
    <SiteShell width="md">
      <PageHeader eyebrow="EduZone" title={t(title)} />
      <Alert tone="warning">{t("static.draft")}</Alert>
      <div className="flex flex-col gap-8">
        {sections.map(([heading, body]) => (
          <section key={heading} className="flex flex-col gap-2">
            <h2 className="font-display text-xl font-semibold">{t(heading)}</h2>
            <p className="leading-relaxed whitespace-pre-line text-foreground/85">{t(body)}</p>
          </section>
        ))}
      </div>
    </SiteShell>
  );
}
