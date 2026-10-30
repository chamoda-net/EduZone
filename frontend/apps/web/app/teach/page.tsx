import { Building2, ChevronRight, GraduationCap } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { SiteShell } from "@/components/shell";
import { getMe } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";
import { Badge, PageHeader, buttonStyles } from "@eduzone/ui";

/** /teach: straight into the only workspace, a choice when there are several, or the way to apply. */
export default async function TeachIndex() {
  const me = await getMe();
  if (!me) redirect("/login?next=/teach");
  if (me.workspaces.length === 0) redirect("/teach/apply");
  if (me.workspaces.length === 1) redirect(`/teach/${me.workspaces[0].slug}/classes`);

  return (
    <SiteShell width="md">
      <PageHeader eyebrow={t("shell.console")} title={t("teach.pick")} />
      <ul className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">
        {me.workspaces.map((w) => (
          <li key={w.slug} className="border-b border-border last:border-0">
            <Link href={`/teach/${w.slug}/classes`} className="group flex items-center gap-4 p-5 hover:bg-sunken/50">
              <span className="grid size-11 place-items-center rounded-ez bg-brand-50 text-brand"><Building2 className="size-5" /></span>
              <span className="min-w-0 flex-1">
                <span className="block font-semibold">{w.name}</span>
                <span className="block text-sm text-muted">{t(`role.${w.role}`)}</span>
                {w.status === "pending" && <Badge tone="warning" className="mt-1">{t("status.pending")}</Badge>}
              </span>
              <ChevronRight className="size-5 text-subtle group-hover:text-brand" />
            </Link>
          </li>
        ))}
      </ul>
      <Link href="/teach/apply" className={buttonStyles("ghost", "md", "mt-4")}>
        <GraduationCap className="size-4" />
        {t("teach.applyCta")}
      </Link>
    </SiteShell>
  );
}
