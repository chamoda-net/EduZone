import { BookOpen } from "lucide-react";

import type { Schema } from "@eduzone/api-client";
import { Card, EmptyState, ErrorText, PageHeader } from "@eduzone/ui";
import { api } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";

import { NewSubjectForm, SubjectRowForm } from "./subject-forms";

type SubjectRow = Schema<"SubjectRow">;

/** The marketplace's subjects. Each one is a page (/physics); hidden ones keep their classes but leave the site. */
export default async function SubjectsPage() {
  const res = await api<SubjectRow[]>("/platform/subjects");
  return (
    <>
      <PageHeader title={t("platform.nav.subjects")} description={t("platform.subjects.body")} />
      <Card className="flex flex-col gap-4">
        <h2 className="font-display text-xl font-semibold">{t("platform.subjects.add")}</h2>
        <NewSubjectForm />
      </Card>
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && <EmptyState icon={<BookOpen />} title={t("platform.subjects.empty")} />}
      {res.ok && res.data.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.map((s) => (
            <li key={s.id}>
              <SubjectRowForm subject={s} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
