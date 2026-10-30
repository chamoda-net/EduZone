"use client";

import { Eye } from "lucide-react";
import { useActionState, useState } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, Field, Textarea } from "@eduzone/ui";

import type { ActionState as FormState } from "@eduzone/ui";

/** The masked number, and on request the full one (the API writes an audit row each time). */
export function RevealAccount({ masked, reveal }: { masked: string; reveal: () => Promise<{ number?: string; error?: string }> }) {
  const t = useT();
  const [shown, setShown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (shown) return <span className="font-mono tabular-nums">{shown}</span>;
  return (
    <span className="flex flex-col items-end gap-1">
      <span className="flex items-center gap-2">
        <span className="font-mono">{masked}</span>
        <button
          type="button"
          disabled={busy}
          title={t("platform.apps.revealAudit")}
          onClick={async () => {
            setBusy(true);
            const r = await reveal();
            setBusy(false);
            if (r.number) setShown(r.number);
            else setError(r.error ?? t("errors.generic"));
          }}
          className="inline-flex items-center gap-1 text-xs font-semibold text-brand hover:underline"
        >
          <Eye className="size-3.5" />
          {t("platform.apps.reveal")}
        </button>
      </span>
      {error && <span className="text-xs text-danger">{error}</span>}
    </span>
  );
}

export function DecisionForm({ action, canApprove }: {
  action: (state: FormState, fd: FormData) => Promise<FormState>;
  canApprove: boolean;
}) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  const confirmFor: Record<string, string> = {
    approve: t("platform.apps.confirmApprove"),
    reject: t("platform.apps.confirmReject"),
  };
  return (
    <form
      action={submit}
      onSubmit={(e) => {
        const decision = (e.nativeEvent as SubmitEvent).submitter?.getAttribute("value") ?? "";
        if (confirmFor[decision] && !window.confirm(confirmFor[decision])) e.preventDefault();
      }}
      className="flex flex-col gap-3"
    >
      <Field label={t("platform.apps.note")} hint={t("platform.apps.noteHint")}>
        <Textarea name="note" rows={3} maxLength={2000} />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <div className="flex flex-wrap gap-2">
        {canApprove && (
          <Button name="decision" value="approve" loading={pending}>{t("platform.apps.approve")}</Button>
        )}
        {canApprove && (
          <Button name="decision" value="request_changes" variant="secondary" disabled={pending}>
            {t("platform.apps.requestChanges")}
          </Button>
        )}
        <Button name="decision" value="reject" variant="danger" disabled={pending}>{t("platform.apps.reject")}</Button>
      </div>
    </form>
  );
}
