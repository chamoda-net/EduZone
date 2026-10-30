"use client";

import { Building2, FileUp, GraduationCap } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import type { MessageKey } from "@eduzone/lib/i18n";
import type { TeacherApplication } from "@eduzone/lib/types";
import { Button, Card, CardTitle, Checkbox, ErrorText, Field, Input, Textarea, buttonStyles, cx, toast } from "@eduzone/ui";

type Subject = { id: string; name: string };
const MAX_SUBJECTS = 6;

/** The application form. New applications POST; an application in review is edited with PUT. The multipart
 * body (with the document) streams through /teach/apply/upload/application to the API. */
export function ApplyForm({ subjects, current, cancelHref }: {
  subjects: Subject[];
  current: TeacherApplication | null;
  cancelHref?: string;
}) {
  const t = useT();
  const router = useRouter();
  const [kind, setKind] = useState<"individual" | "institute">(current?.kind ?? "individual");
  const [picked, setPicked] = useState<string[]>(current?.subjects.map((s) => s.id) ?? []);
  const [fileName, setFileName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(id: string) {
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < MAX_SUBJECTS ? [...p, id] : p));
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = new FormData(e.currentTarget);
    try {
      const res = await fetch("/teach/apply/upload/application", { method: current ? "PUT" : "POST", body });
      if (!res.ok) {
        const json = (await res.json().catch(() => null)) as { error?: { code: string; message: string } } | null;
        const key = `errors.${json?.error?.code}` as MessageKey;
        const ours = t(key);
        setError(ours !== key ? ours : json?.error?.message || t("errors.generic"));
        return;
      }
      toast(t("apply.sent"));
      router.push("/teach/apply");
      router.refresh();
    } catch {
      setError(t("errors.API_UNREACHABLE"));
    } finally {
      setBusy(false);
    }
  }

  const kinds = [
    { value: "individual", icon: <GraduationCap className="size-5" />, title: t("apply.kind.individual"), body: t("apply.kind.individualBody") },
    { value: "institute", icon: <Building2 className="size-5" />, title: t("apply.kind.institute"), body: t("apply.kind.instituteBody") },
  ] as const;

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-6">
      <Card className="flex flex-col gap-5">
        <CardTitle>{t("apply.section.about")}</CardTitle>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1.5 text-sm font-semibold">{t("apply.kindLabel")}</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {kinds.map((k) => {
              const locked = current !== null && current.kind !== k.value;
              return (
                <label
                  key={k.value}
                  className={cx(
                    "flex min-w-0 cursor-pointer items-start gap-3 rounded-ez-lg border p-4 transition",
                    kind === k.value ? "border-brand bg-brand-50/60 ring-1 ring-brand" : "border-border hover:border-border-strong",
                    locked && "pointer-events-none opacity-50",
                  )}
                >
                  <input type="radio" name="kind" value={k.value} checked={kind === k.value} disabled={locked}
                         onChange={() => setKind(k.value)} className="sr-only" />
                  <span className={cx("grid size-10 shrink-0 place-items-center rounded-ez",
                                      kind === k.value ? "bg-brand text-on-brand" : "bg-sunken text-muted")}>
                    {k.icon}
                  </span>
                  <span className="min-w-0">
                    <span className="block font-semibold">{k.title}</span>
                    <span className="block text-sm text-muted">{k.body}</span>
                  </span>
                </label>
              );
            })}
          </div>
          {current && <p className="text-xs text-muted">{t("apply.kindLocked")}</p>}
        </fieldset>

        <Field label={t(`apply.orgName.${kind}`)} hint={t(`apply.orgName.${kind}Hint`)}>
          <Input name="org_name" required minLength={2} maxLength={120} defaultValue={current?.org_name} />
        </Field>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1.5 flex w-full items-baseline justify-between text-sm font-semibold">
            {t("apply.subjects")}
            <span className="text-xs font-normal text-subtle">{picked.length}/{MAX_SUBJECTS}</span>
          </legend>
          <div className="flex flex-wrap gap-2">
            {subjects.map((s) => {
              const on = picked.includes(s.id);
              return (
                <button
                  key={s.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(s.id)}
                  className={cx(
                    "min-h-10 rounded-full border px-4 text-sm font-medium transition",
                    on ? "border-brand bg-brand text-on-brand" : "border-border bg-surface hover:border-brand hover:text-brand",
                    !on && picked.length >= MAX_SUBJECTS && "opacity-40",
                  )}
                >
                  {s.name}
                </button>
              );
            })}
          </div>
          {picked.map((id) => <input key={id} type="hidden" name="subject_ids" value={id} />)}
          <p className="text-xs text-muted">{t("apply.subjectsHint")}</p>
        </fieldset>

        <Field label={t("apply.experience")} hint={t("apply.experienceHint")} optional={t("common.optional")}>
          <Textarea name="experience" rows={4} maxLength={2000} defaultValue={current?.experience ?? ""} />
        </Field>
      </Card>

      <Card className="flex flex-col gap-4">
        <CardTitle>{t("apply.section.document")}</CardTitle>
        <label
          className={cx(
            "flex cursor-pointer flex-col items-center gap-2 rounded-ez-lg border-2 border-dashed px-4 py-8 text-center transition",
            fileName ? "border-brand bg-brand-50/50" : "border-border hover:border-brand",
          )}
        >
          <FileUp className="size-7 text-brand" />
          <span className="font-semibold">{fileName ?? t(`apply.document.${kind}`)}</span>
          <span className="max-w-md text-xs text-muted">
            {current && !fileName ? t("apply.documentKeep", { name: current.document_name }) : t("apply.documentHint")}
          </span>
          <input
            type="file"
            name="document"
            accept="application/pdf,image/jpeg,image/png"
            required={!current}
            className="sr-only"
            onChange={(e) => setFileName(e.target.files?.[0]?.name ?? null)}
          />
        </label>
      </Card>

      <Card className="flex flex-col gap-5">
        <CardTitle>{t("apply.section.payout")}</CardTitle>
        <p className="-mt-2 text-sm text-muted">{t("apply.section.payoutBody")}</p>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label={t("apply.bank")}>
            <Input name="payout_bank_name" required minLength={2} maxLength={80} defaultValue={current?.payout_bank_name} />
          </Field>
          <Field label={t("apply.branch")} optional={t("common.optional")}>
            <Input name="payout_branch" maxLength={80} defaultValue={current?.payout_branch ?? ""} />
          </Field>
          <Field label={t("apply.accountName")}>
            <Input name="payout_account_name" required minLength={2} maxLength={120} defaultValue={current?.payout_account_name} />
          </Field>
          <Field
            label={t("apply.accountNumber")}
            hint={current ? t("apply.accountKeep", { masked: current.payout_account_masked }) : undefined}
          >
            <Input name="payout_account_number" required={!current} inputMode="numeric" autoComplete="off"
                   minLength={4} maxLength={40} placeholder={current?.payout_account_masked} />
          </Field>
        </div>
      </Card>

      <div className="flex flex-col gap-4">
        <Checkbox
          name="accept_terms"
          value="true"
          required
          label={
            <>
              {t("apply.terms")}{" "}
              <Link href="/terms" target="_blank" className="font-semibold text-brand underline-offset-2 hover:underline">
                {t("apply.termsLink")}
              </Link>
            </>
          }
        />
        <ErrorText>{error ?? undefined}</ErrorText>
        <div className="flex flex-wrap gap-3">
          <Button size="lg" loading={busy} disabled={picked.length === 0}>
            {current ? t("apply.resubmit") : t("apply.submit")}
          </Button>
          {cancelHref && <Link href={cancelHref} className={buttonStyles("ghost", "lg")}>{t("apply.cancelEdit")}</Link>}
        </div>
      </div>
    </form>
  );
}
