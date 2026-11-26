"use client";

import { useActionState, useEffect, useRef, useState, useTransition } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import type { ClassItem, Registration } from "@eduzone/lib/types";
import { Button, Checkbox, Dialog, ErrorText, Field, Input, Select, cx, toast } from "@eduzone/ui";

import { grantSeat, type SeatFormState } from "../seat-actions";

type Action = (state: SeatFormState, fd: FormData) => Promise<SeatFormState>;

/** Runs `done` once for each successful result. */
function useDone(state: SeatFormState, done: () => void) {
  const seen = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (state.ok && state.at !== seen.current) {
      seen.current = state.at;
      done();
    }
  });
}

/** How many seats, who may join, when that switches, and until when returning students' seats are kept. */
export function SeatSettingsForm({ action, c }: { action: Action; c: ClassItem }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  const [registration, setRegistration] = useState<Registration>(c.registration);
  const [starts, setStarts] = useState(c.starts_on ?? "");
  useDone(state, () => toast(t("seats.saved")));
  return (
    <form action={submit} className="flex flex-col gap-5">
      <Field label={t("seats.limit")} optional={t("seats.optional")} hint={t("seats.limitHint")}>
        <Input name="seat_limit" type="number" inputMode="numeric" min={1} max={10000} defaultValue={c.seat_limit ?? ""} className="sm:max-w-40" />
      </Field>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-semibold">{t("seats.registration")}</legend>
        <div className="grid gap-2.5 sm:grid-cols-3">
          {(["open", "ask", "closed"] as const).map((r) => (
            <label
              key={r}
              className={cx(
                "flex cursor-pointer gap-3 rounded-ez border p-3.5 transition has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-brand/15",
                registration === r ? "border-brand bg-brand-50" : "border-border-strong bg-surface hover:border-brand/50",
              )}
            >
              <input type="radio" name="registration" value={r} checked={registration === r} onChange={() => setRegistration(r)}
                     className="mt-0.5 size-4.5 shrink-0 accent-brand" />
              <span>
                <span className="block text-sm font-semibold">{t(`seats.option.${r}`)}</span>
                <span className="block text-xs leading-relaxed text-muted">{t(`seats.option.${r}Hint`)}</span>
              </span>
            </label>
          ))}
        </div>
        <p className="text-xs text-muted">{t("seats.registrationHint")}</p>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("seats.startsOn")} optional={t("seats.optional")}>
          <Input name="starts_on" type="date" value={starts} onChange={(e) => setStarts(e.target.value)} />
        </Field>
        <Field label={t("seats.afterStart")}>
          <Select name="registration_after_start" defaultValue={c.registration_after_start ?? ""} disabled={!starts}>
            <option value="">{t("seats.afterStartNone")}</option>
            {(["open", "ask", "closed"] as const).map((r) => <option key={r} value={r}>{t(`seats.option.${r}`)}</option>)}
          </Select>
        </Field>
        {c.pricing_model === "monthly" && (
          <Field label={t("seats.renewalDay")} hint={t("seats.renewalDayHint")} className="sm:col-span-2">
            <Select name="renewal_day" defaultValue={String(c.renewal_day)} className="sm:max-w-40">
              {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>{d}</option>)}
            </Select>
          </Field>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <Checkbox name="show_seat_count" defaultChecked={c.show_seat_count} label={t("seats.showCount")} />
        <p className="pl-7 text-xs text-muted">{t("seats.showCountHint")}</p>
      </div>
      <ErrorText>{state.error}</ErrorText>
      <Button loading={pending} className="self-start">{t("seats.save")}</Button>
    </form>
  );
}

/** Moves a month's renewal date. Moving a passed date later brings lapsed seats back, so it asks first. */
export function RenewDateForm({ action, value, passed, lapsed }: { action: Action; value: string; passed: boolean; lapsed: number }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  useDone(state, () => toast(t("seats.done")));
  return (
    <form
      action={submit}
      onSubmit={(e) => {
        const chosen = String(new FormData(e.currentTarget).get("renew_until") ?? "");
        if (passed && lapsed > 0 && chosen > value && !window.confirm(t("seats.renewConfirm", { count: lapsed }))) e.preventDefault();
      }}
      className="flex flex-wrap items-center gap-2"
    >
      <label htmlFor="renew_until" className="text-sm text-muted">{t("seats.renewTitle")}</label>
      <div className="w-44"><Input id="renew_until" name="renew_until" type="date" required defaultValue={value} key={value} /></div>
      <Button variant="secondary" size="sm" loading={pending}>{t("seats.renewSave")}</Button>
      <ErrorText>{state.error}</ErrorText>
    </form>
  );
}

/** Keep one student's seat until a day; after CLASS_FULL it offers to go over the limit. */
export function KeepSeatDialog({ action, name, label, defaultDay, maxDay }: {
  action: Action; name: string; label: string; defaultDay: string; maxDay: string;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [state, submit, pending] = useActionState(action, {});
  useDone(state, () => { setOpen(false); toast(t("seats.done")); });
  const full = state.code === "CLASS_FULL";
  return (
    <Dialog open={open} onOpenChange={setOpen} title={t("seats.keepTitle", { name })} description={t("seats.keepBody")}
            trigger={<Button type="button" variant="secondary" size="sm">{label}</Button>}>
      <form action={submit} className="flex flex-col gap-4">
        <Field label={t("seats.keepUntil")}>
          <Input name="keep_until" type="date" required defaultValue={defaultDay} max={maxDay} />
        </Field>
        {full && <input type="hidden" name="allow_over_limit" value="on" />}
        <ErrorText>{state.error}</ErrorText>
        <Button loading={pending} variant={full ? "danger" : "primary"} className="self-start">
          {full ? t("seats.keepOver") : t("seats.keepSave")}
        </Button>
      </form>
    </Dialog>
  );
}

/** Give a student access; when every seat is taken it asks before going over the limit. */
export function GrantButton({ classId, memberId, monthId, source, label }: {
  classId: string; memberId: string; monthId: string | null; source: "manual" | "scholarship"; label: string;
}) {
  const t = useT();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string>();
  function give() {
    setError(undefined);
    start(async () => {
      let res = await grantSeat(classId, memberId, monthId, source, false);
      if (res.code === "CLASS_FULL") {
        if (!window.confirm(t("seats.grantOver"))) return;
        res = await grantSeat(classId, memberId, monthId, source, true);
      }
      if (res.error) setError(res.error);
    });
  }
  return (
    <span className="inline-flex flex-col items-start gap-1">
      <Button type="button" variant="secondary" size="sm" loading={pending} onClick={give}>{label}</Button>
      {error && <span role="alert" className="max-w-xs text-xs font-medium text-danger">{error}</span>}
    </span>
  );
}
