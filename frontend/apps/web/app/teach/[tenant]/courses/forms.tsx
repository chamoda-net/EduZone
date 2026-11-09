"use client";

import { Plus, X } from "lucide-react";
import { useActionState, useEffect, useRef, useState } from "react";

import type { Schema } from "@eduzone/api-client";
import { Button, ErrorText, Field, Input, Select, Textarea, cx, toast } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";

import { createCourse, type FormState } from "./actions";

type Category = Schema<"CategoryOut">;
type CourseDetail = Schema<"CourseDetail">;
type Lecture = Schema<"LectureOut">;
type Media = { id: string; name: string; kind: string; status: string };
type Action = (state: FormState, fd: FormData) => Promise<FormState>;

/** A toast once per successful save. */
function useSaved(state: FormState, message: string) {
  const shown = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (state.ok && state.at !== shown.current) {
      shown.current = state.at;
      toast(message);
    }
  }, [state, message]);
}

/** Top-level categories with their subcategories, as one grouped select. */
function CategorySelect({ categories, value }: { categories: Category[]; value?: number | null }) {
  const t = useT();
  const tops = categories.filter((c) => c.parent_id === null);
  return (
    <Select name="category_id" defaultValue={value ? String(value) : ""}>
      <option value="">{t("courses.categoryNone")}</option>
      {tops.map((top) => {
        const subs = categories.filter((c) => c.parent_id === top.id);
        return subs.length === 0 ? (
          <option key={top.id} value={top.id}>{top.name_en}</option>
        ) : (
          <optgroup key={top.id} label={top.name_en}>
            <option value={top.id}>{top.name_en}</option>
            {subs.map((s) => <option key={s.id} value={s.id}>{s.name_en}</option>)}
          </optgroup>
        );
      })}
    </Select>
  );
}

export function NewCourseForm({ categories }: { categories: Category[] }) {
  const t = useT();
  const [state, submit, pending] = useActionState(createCourse, {});
  return (
    <form action={submit} className="flex flex-col gap-4">
      <Field label={t("courses.titleLabel")} hint={t("courses.titleHint")}>
        <Input name="title" required minLength={3} maxLength={120} autoFocus />
      </Field>
      <Field label={t("courses.category")}>
        <CategorySelect categories={categories} />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <Button className="self-start" loading={pending}>{t("courses.create")}</Button>
    </form>
  );
}

function SaveRow({ state, pending }: { state: FormState; pending: boolean }) {
  const t = useT();
  return (
    <div className="flex flex-col gap-2 border-t border-border pt-4">
      <ErrorText>{state.error}</ErrorText>
      <Button className="self-start" loading={pending}>{t("courses.save")}</Button>
    </div>
  );
}

// --- landing page ---------------------------------------------------------------------------

export function LandingForm({ action, course, categories, media }: {
  action: Action; course: CourseDetail; categories: Category[]; media: Media[];
}) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  const [words, setWords] = useState(() => (course.description ?? "").split(/\s+/).filter(Boolean).length);
  useSaved(state, t("courses.saved"));
  const videos = media.filter((m) => m.kind === "video" && m.status !== "failed");
  return (
    <form action={submit} className="flex flex-col gap-5">
      <Field label={t("courses.titleLabel")}>
        <Input name="title" required minLength={3} maxLength={120} defaultValue={course.title} />
      </Field>
      <Field label={t("courses.subtitleLabel")} hint={t("courses.subtitleHint")}>
        <Input name="subtitle" maxLength={120} defaultValue={course.subtitle ?? ""} />
      </Field>
      <div className="flex flex-col gap-1.5">
        <Field label={t("courses.description")} hint={t("courses.descriptionHint")}>
          <Textarea name="description" rows={10} maxLength={20000} defaultValue={course.description ?? ""}
                    onChange={(e) => setWords(e.target.value.split(/\s+/).filter(Boolean).length)} />
        </Field>
        <p className={cx("self-end text-xs tabular-nums", words >= 100 ? "text-success" : "text-muted")}>
          {t("courses.words", { count: words })}
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={t("courses.category")}>
          <CategorySelect categories={categories} value={course.category_id} />
        </Field>
        <Field label={t("courses.levelLabel")}>
          <Select name="level" defaultValue={course.level ?? ""}>
            <option value="">—</option>
            {(["beginner", "intermediate", "advanced", "all"] as const).map((l) => (
              <option key={l} value={l}>{t(`courses.level.${l}`)}</option>
            ))}
          </Select>
        </Field>
        <Field label={t("courses.language")}>
          <Select name="medium" defaultValue={course.medium ?? ""}>
            <option value="">—</option>
            {(["si", "ta", "en"] as const).map((m) => <option key={m} value={m}>{t(`medium.${m}`)}</option>)}
          </Select>
        </Field>
      </div>
      <Field label={t("courses.cover")} hint={t("courses.coverHint")}>
        <Input name="cover_image_url" type="url" inputMode="url" placeholder="https://"
               defaultValue={course.cover_image_url ?? ""} />
      </Field>
      <Field label={t("courses.promo")} hint={t("courses.promoHint")}>
        <Select name="promo_media_id" defaultValue={course.promo_media_id ?? ""}>
          <option value="">{t("courses.promoNone")}</option>
          {videos.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </Select>
      </Field>
      {course.first_published_at === null && (
        <Field label={t("courses.address")} hint={t("courses.addressHint", { slug: course.slug })}>
          <Input name="slug" required pattern="[a-z0-9]+(-[a-z0-9]+)*" maxLength={80} defaultValue={course.slug}
                 autoCapitalize="none" spellCheck={false} className="font-mono text-sm" />
        </Field>
      )}
      <SaveRow state={state} pending={pending} />
    </form>
  );
}

// --- intended learners -------------------------------------------------------------------------

/** One input per item, with add and remove; submitted as repeated fields of the same name. */
function ListField({ name, label, hint, initial, min }: {
  name: string; label: string; hint: string; initial: string[]; min: number;
}) {
  const t = useT();
  const [items, setItems] = useState(() => {
    const start = initial.map((value, key) => ({ key, value }));
    while (start.length < min) start.push({ key: start.length, value: "" });
    return start;
  });
  const add = () => setItems((xs) => [...xs, { key: Math.max(-1, ...xs.map((x) => x.key)) + 1, value: "" }]);
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-semibold">{label}</legend>
      <p className="-mt-1 mb-1 text-xs text-muted">{hint}</p>
      {items.map((it, i) => (
        <div key={it.key} className="flex gap-2">
          <Input name={name} defaultValue={it.value} maxLength={160} placeholder={t("courses.itemPlaceholder")}
                 aria-label={`${label} ${i + 1}`} className="flex-1" />
          <button type="button" aria-label={t("courses.removeItem")}
                  onClick={() => setItems((xs) => xs.filter((x) => x.key !== it.key))}
                  className="grid size-11 shrink-0 place-items-center rounded-ez text-muted hover:bg-sunken hover:text-foreground">
            <X className="size-4" />
          </button>
        </div>
      ))}
      <button type="button" onClick={add}
              className="inline-flex min-h-9 items-center gap-1.5 self-start text-sm font-semibold text-brand hover:underline">
        <Plus className="size-4" />{t("courses.addItem")}
      </button>
    </fieldset>
  );
}

export function LearnersForm({ action, course }: { action: Action; course: CourseDetail }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  useSaved(state, t("courses.saved"));
  return (
    <form action={submit} className="flex flex-col gap-7">
      <ListField name="learning_objectives" label={t("courses.objectives")} hint={t("courses.objectivesHint")}
                 initial={course.learning_objectives} min={4} />
      <ListField name="requirements" label={t("courses.requirements")} hint={t("courses.requirementsHint")}
                 initial={course.requirements} min={1} />
      <ListField name="target_audience" label={t("courses.audience")} hint={t("courses.audienceHint")}
                 initial={course.target_audience} min={1} />
      <SaveRow state={state} pending={pending} />
    </form>
  );
}

// --- pricing and messages ----------------------------------------------------------------------

export function PricingForm({ action, course }: { action: Action; course: CourseDetail }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  const [paid, setPaid] = useState(course.pricing_model === "one_time");
  useSaved(state, t("courses.saved"));
  const option = (value: "free" | "one_time", title: string, body: string) => (
    <label className={cx(
      "flex cursor-pointer gap-3 rounded-ez-lg border p-4 transition",
      (value === "one_time") === paid ? "border-brand bg-brand-50 shadow-ez-sm" : "border-border hover:border-border-strong",
    )}>
      <input type="radio" name="pricing_model" value={value} checked={(value === "one_time") === paid}
             onChange={() => setPaid(value === "one_time")} className="mt-1 accent-[var(--ez-brand-700)]" />
      <span>
        <span className="block font-semibold">{title}</span>
        <span className="text-sm text-muted">{body}</span>
      </span>
    </label>
  );
  return (
    <form action={submit} className="flex flex-col gap-5">
      <div className="grid gap-3 sm:grid-cols-2">
        {option("free", t("courses.pricingFree"), t("courses.pricingFreeBody"))}
        {option("one_time", t("courses.pricingPaid"), t("courses.pricingPaidBody"))}
      </div>
      {paid && (
        <Field label={t("courses.price")} hint={t("courses.commission")}>
          <Input name="price" inputMode="decimal" required className="max-w-48 tabular-nums"
                 defaultValue={course.one_time_price_cents ? String(course.one_time_price_cents / 100) : ""} />
        </Field>
      )}
      <SaveRow state={state} pending={pending} />
    </form>
  );
}

export function MessagesForm({ action, course }: { action: Action; course: CourseDetail }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  useSaved(state, t("courses.saved"));
  return (
    <form action={submit} className="flex flex-col gap-5">
      <Field label={t("courses.welcome")} hint={t("courses.welcomeHint")}>
        <Textarea name="welcome_message" rows={4} maxLength={1000} defaultValue={course.welcome_message ?? ""} />
      </Field>
      <Field label={t("courses.completion")} hint={t("courses.completionHint")}>
        <Textarea name="completion_message" rows={4} maxLength={1000} defaultValue={course.completion_message ?? ""} />
      </Field>
      <SaveRow state={state} pending={pending} />
    </form>
  );
}

// --- curriculum ------------------------------------------------------------------------------

/** A one-line form: an input and a button (add a section, rename a section, add a lecture). */
export function InlineForm({ action, name, label, placeholder, button, initial, children }: {
  action: Action; name: string; label: string; placeholder?: string; button: string; initial?: string;
  children?: React.ReactNode;
}) {
  const [state, submit, pending] = useActionState(action, {});
  return (
    <form key={state.at} action={submit} className="flex flex-col gap-1.5">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input name={name} required maxLength={200} defaultValue={initial} placeholder={placeholder}
               aria-label={label} className="flex-1" />
        {children}
        <Button variant="secondary" loading={pending} className="shrink-0">{button}</Button>
      </div>
      <ErrorText>{state.error}</ErrorText>
    </form>
  );
}

export function LectureTypeSelect({ value }: { value?: string }) {
  const t = useT();
  return (
    <Select name="lesson_type" defaultValue={value ?? "recorded"} aria-label={t("courses.lectureType")} className="sm:w-36">
      {(["recorded", "article", "document"] as const).map((x) => <option key={x} value={x}>{t(`courses.type.${x}`)}</option>)}
    </Select>
  );
}

export function LectureForm({ action, lecture }: { action: Action; lecture: Lecture }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  const [type, setType] = useState(lecture.lesson_type);
  useSaved(state, t("courses.saved"));
  return (
    <form action={submit} className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
        <Field label={t("courses.lectureTitle")}>
          <Input name="title" required maxLength={200} defaultValue={lecture.title} />
        </Field>
        <Field label={t("courses.lectureType")}>
          <Select name="lesson_type" value={type} onChange={(e) => setType(e.target.value)}>
            {(["recorded", "article", "document"] as const).map((x) => <option key={x} value={x}>{t(`courses.type.${x}`)}</option>)}
          </Select>
        </Field>
      </div>
      {type === "article" && (
        <Field label={t("courses.article")} hint={t("courses.articleHint")}>
          <Textarea name="article_body" rows={12} maxLength={50000} required className="font-mono text-sm"
                    defaultValue={lecture.article_body ?? `# ${lecture.title}\n`} />
        </Field>
      )}
      <Field label={`${t("courses.lectureDescription")} (${t("common.optional")})`}>
        <Textarea name="description" rows={2} maxLength={5000} defaultValue={lecture.description ?? ""} />
      </Field>
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        <label className="flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" name="is_published" defaultChecked={lecture.is_published} />
          {t("courses.published")}
        </label>
        <label className="flex min-h-11 items-center gap-2 text-sm" title={t("courses.previewHint")}>
          <input type="checkbox" name="is_free_preview" defaultChecked={lecture.is_free_preview} />
          {t("courses.preview")}
        </label>
      </div>
      <ErrorText>{state.error}</ErrorText>
      <Button variant="secondary" size="sm" className="self-start" loading={pending}>{t("courses.save")}</Button>
    </form>
  );
}

/** The instructor's reply under a review (an empty reply removes it). */
export function ReplyForm({ action, initial }: { action: Action; initial: string | null }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  useSaved(state, t("courseReviews.replied"));
  return (
    <form action={submit} className="flex flex-col gap-2">
      <Field label={t("courseReviews.replyLabel")}>
        <Textarea name="reply" rows={2} maxLength={2000} defaultValue={initial ?? ""} />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <Button variant="secondary" size="sm" className="self-start" loading={pending}>{t("courseReviews.saveReply")}</Button>
    </form>
  );
}
