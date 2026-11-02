import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { teachHref } from "@/lib/workspace";
import { t } from "@eduzone/lib/i18n";
import { Card, PageHeader } from "@eduzone/ui";

import { NewCourseForm } from "../forms";

type Category = Schema<"CategoryOut">;

export default async function NewCoursePage() {
  const base = await teachHref();
  const res = await api<Category[]>("/market/course-categories", { token: null });
  return (
    <>
      <Link href={`${base}/courses`} className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-muted hover:text-foreground">
        <ArrowLeft className="size-4" />
        {t("courses.back")}
      </Link>
      <PageHeader title={t("courses.newTitle")} description={t("courses.newBody")} />
      <Card className="max-w-2xl">
        <NewCourseForm categories={res.ok ? res.data : []} />
      </Card>
    </>
  );
}
