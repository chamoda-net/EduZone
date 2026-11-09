import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { t } from "@eduzone/lib/i18n";

import { CategoryView, categoryPage } from "../category-view";

export async function generateMetadata({ params }: PageProps<"/courses/[...path]">): Promise<Metadata> {
  const { path } = await params;
  if (path.length > 2) notFound();
  const page = await categoryPage(path.at(-1) as string);
  const title = t("market.category.metaTitle", { name: page.category.name_en });
  const description = t("market.category.lead", { name: page.category.name_en });
  return { title, description, openGraph: { title, description } };
}

/** /courses/<category> and /courses/<category>/<subcategory>. */
export default async function CourseCategoryPage({ params, searchParams }: PageProps<"/courses/[...path]">) {
  const { path } = await params;
  if (path.length > 2 || !path.every((p) => /^[a-z0-9-]+$/.test(p))) notFound();
  return <CategoryView path={path} sp={await searchParams} />;
}
