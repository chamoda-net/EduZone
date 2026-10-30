import { teachHref } from "@/lib/workspace";
import Link from "next/link";

import { api } from "@/lib/api";
import type { SubjectOut } from "@eduzone/lib/types";
import { Card, buttonClass } from "@eduzone/ui";
import { t } from "@eduzone/lib/i18n";

import { createClass } from "../actions";
import { ClassForm } from "../class-form";

export default async function NewClassPage() {
  const base = await teachHref();
  const subjects = await api<SubjectOut[]>("/market/subjects", { token: null });
  return (
    <>
      <Link href={`${base}/classes`} className={`${buttonClass.link} text-sm`}>← {t("classes.back")}</Link>
      <h1 className="font-display text-3xl font-semibold sm:text-4xl">{t("classes.new")}</h1>
      <Card>
        <ClassForm action={createClass} subjects={subjects.ok ? subjects.data : []} />
      </Card>
    </>
  );
}
