import { ExternalLink } from "lucide-react";
import Link from "next/link";

import { ShareTools } from "@/components/share-tools";
import { TeacherAvatar } from "@/components/teacher-avatar";
import { api } from "@/lib/api";
import { mainOrigin } from "@/lib/site";
import { errorText, t } from "@eduzone/lib/i18n";
import type { TeacherProfile } from "@eduzone/lib/types";
import { Alert, Card, CardTitle, ErrorText, PageHeader } from "@eduzone/ui";

import { ProfileForm } from "./profile-form";

/** The teacher's public page: edit it, see where it lives, and share it. */
export default async function ProfilePage() {
  const res = await api<TeacherProfile>("/me/teacher-profile");
  const origin = await mainOrigin();
  if (!res.ok) return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  const p = res.data;

  return (
    <>
      <PageHeader eyebrow={t("shell.console")} title={t("profile.title")} description={t("profile.subtitle")} />
      <div className="grid gap-6 lg:grid-cols-[1fr_360px] [&>*]:min-w-0">
        <Card>
          <ProfileForm profile={p} origin={origin} />
        </Card>
        <div className="flex flex-col gap-6">
          <Card className="flex flex-col items-center gap-3 text-center">
            <TeacherAvatar name={p.display_name} photo={p.photo_url} size="xl" />
            <p className="font-display text-xl font-semibold">{p.display_name}</p>
            {p.headline && <p className="text-sm text-muted">{p.headline}</p>}
          </Card>
          <Card className="flex flex-col gap-4">
            <CardTitle>{t("profile.share")}</CardTitle>
            {p.public_paths.length === 0 ? (
              <Alert tone="info">{t("profile.notPublic")}</Alert>
            ) : (
              p.public_paths.map((path) => (
                <div key={path} className="flex flex-col gap-2 border-t border-border pt-4 first-of-type:border-0 first-of-type:pt-0">
                  <Link href={path} target="_blank" className="inline-flex items-center gap-1.5 truncate text-sm font-semibold text-brand hover:underline">
                    {origin}{path}
                    <ExternalLink className="size-3.5 shrink-0" />
                  </Link>
                  <ShareTools url={`${origin}${path}`} message={t("market.teacher.shareMessage", { name: p.display_name, subject: "" })} compact />
                </div>
              ))
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
