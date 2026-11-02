import type { Schema } from "@eduzone/api-client";
import { Card, ErrorText, PageHeader } from "@eduzone/ui";
import { api } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";

import { CategoryRow, NewCategoryForm } from "./category-forms";

type Category = Schema<"CategoryOut">;

/** Course categories: top level, each with its subcategories underneath. */
export default async function CourseCategoriesPage() {
  const res = await api<Category[]>("/platform/course-categories");
  const all = res.ok ? res.data : [];
  const tops = all.filter((c) => c.parent_id === null);
  return (
    <>
      <PageHeader title={t("platform.nav.courseCategories")} description={t("platform.categories.body")} />
      <Card className="flex flex-col gap-4">
        <h2 className="font-display text-xl font-semibold">{t("platform.categories.add")}</h2>
        <NewCategoryForm parents={tops} />
      </Card>
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      <ul className="flex flex-col gap-3">
        {tops.map((top) => {
          const subs = all.filter((c) => c.parent_id === top.id);
          return (
            <li key={top.id} className="overflow-hidden rounded-ez-lg border border-border bg-surface">
              <CategoryRow category={top} />
              {subs.length > 0 && (
                <ul className="divide-y divide-border border-t border-border bg-sunken/30 pl-6">
                  {subs.map((s) => <li key={s.id}><CategoryRow category={s} /></li>)}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}
