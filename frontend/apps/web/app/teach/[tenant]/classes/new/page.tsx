import { teachHref } from "@/lib/workspace";
import Link from "next/link";

import { Card, buttonClass } from "@eduzone/ui";
import { t } from "@eduzone/lib/i18n";

import { createClass } from "../actions";
import { ClassForm } from "../class-form";

export default async function NewClassPage() {
  const base = await teachHref();
  return (
    <>
      <Link href={`${base}/classes`} className={`${buttonClass.link} text-sm`}>← {t("classes.back")}</Link>
      <h1 className="font-display text-3xl font-semibold sm:text-4xl">{t("classes.new")}</h1>
      <Card>
        <ClassForm action={createClass} />
      </Card>
    </>
  );
}
