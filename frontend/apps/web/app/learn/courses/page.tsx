import { GraduationCap } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { MyCourseCard } from "@/components/my-course-card";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { errorText, t } from "@eduzone/lib/i18n";
import { EmptyState, ErrorText, PageHeader, buttonStyles } from "@eduzone/ui";

/** Every course the student has, most recently active first. */
export default async function MyCoursesPage() {
  if (!(await getMe())) redirect("/login?next=/learn/courses");
  const res = await api<Schema<"MyCourse">[]>("/learn/courses");
  return (
    <SiteShell>
      <PageHeader eyebrow={t("learn.eyebrow")} title={t("learnCourses.title")} description={t("learnCourses.lead")} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && (
        <EmptyState icon={<GraduationCap />} title={t("learnCourses.empty")} body={t("learnCourses.emptyBody")}
                    action={<Link href="/courses" className={buttonStyles("primary")}>{t("learnCourses.browse")}</Link>} />
      )}
      {res.ok && res.data.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {res.data.map((c, i) => <MyCourseCard key={c.id} c={c} index={i} />)}
        </div>
      )}
    </SiteShell>
  );
}
