"use client";

import { CircleCheck, Clock3, RotateCcw, ShieldCheck, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import type { Schema } from "@eduzone/api-client";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { useT } from "@eduzone/lib/i18n/client";
import { Button, Dialog, ErrorText, Field, Select, Textarea, cx } from "@eduzone/ui";

import { requestRefund } from "../actions";

type Info = Schema<"RefundInfo">;

const REASONS = ["notExpected", "quality", "boughtByMistake", "tooHard", "other"] as const;

/** The refund card in the player: the offer while the rule allows it, then the refund's status. */
export function RefundCard({ courseId, info }: { courseId: string; info: Info }) {
  const t = useT();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<(typeof REASONS)[number]>("notExpected");
  const [details, setDetails] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, run] = useTransition();
  const r = info.refund;
  const amount = info.amount_cents != null && info.currency ? formatMoney(info.amount_cents, info.currency) : "";

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const text = `${t(`refund.reason.${reason}`)}${details.trim() ? `: ${details.trim()}` : ""}`;
    run(async () => {
      const res = await requestRefund(courseId, text);
      if (!res.ok) return setError(res.error);
      setOpen(false);
      router.refresh();
    });
  }

  // A refund waiting for EduZone or for the gateway.
  if (r && (r.status === "requested" || r.status === "approved")) {
    return (
      <Status tone="info" icon={<Clock3 />} title={t(r.status === "requested" ? "refund.requested" : "refund.approved")}
              body={t(r.status === "requested" ? "refund.requestedBody" : "refund.approvedBody",
                      { amount: formatMoney(r.amount_cents, r.currency) })} />
    );
  }
  if (r && r.status === "processed") {
    return (
      <Status tone="success" icon={<CircleCheck />} title={t("refund.processed")}
              body={t("refund.processedBody", { amount: formatMoney(r.amount_cents, r.currency),
                                                date: formatDateTime(r.processed_at ?? r.created_at) })} />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {r?.status === "rejected" && (
        <Status tone="danger" icon={<XCircle />} title={t("refund.rejected")} body={r.decision_note ?? ""} />
      )}
      {info.eligible && info.deadline && (
        <section className="flex flex-col gap-2 rounded-ez-lg border border-border bg-surface p-4">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="size-4.5 text-brand-600" />{t("refund.offerTitle")}
          </p>
          <p className="text-sm text-muted">{t("refund.offerBody", { date: formatDateTime(info.deadline) })}</p>
          <Dialog open={open} onOpenChange={setOpen} title={t("refund.dialogTitle")}
                  description={t("refund.dialogBody", { amount })} closeLabel={t("refund.close")}
                  trigger={
                    <button type="button" className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-brand hover:underline">
                      <RotateCcw className="size-4" />{t("refund.ask")}
                    </button>
                  }>
            <form onSubmit={submit} className="flex flex-col gap-4">
              <Field label={t("refund.reasonLabel")}>
                <Select value={reason} onChange={(e) => setReason(e.target.value as typeof reason)}>
                  {REASONS.map((k) => <option key={k} value={k}>{t(`refund.reason.${k}`)}</option>)}
                </Select>
              </Field>
              <Field label={t("refund.detailsLabel")} optional={t("coupons.optional")}>
                <Textarea value={details} onChange={(e) => setDetails(e.target.value)} maxLength={800} rows={3} />
              </Field>
              <p className="rounded-ez bg-sunken px-3 py-2 text-xs text-muted">{t("refund.whatHappens")}</p>
              {error && <ErrorText>{error}</ErrorText>}
              <Button type="submit" variant="danger" loading={pending} className="self-start">{t("refund.confirm", { amount })}</Button>
            </form>
          </Dialog>
        </section>
      )}
    </div>
  );
}

function Status({ tone, icon, title, body }: { tone: "info" | "success" | "danger"; icon: React.ReactNode; title: string; body: string }) {
  return (
    <section className={cx("flex gap-3 rounded-ez-lg border p-4",
                           tone === "info" && "border-info/25 bg-info-bg",
                           tone === "success" && "border-success/25 bg-success-bg",
                           tone === "danger" && "border-danger/25 bg-danger-bg")}>
      <span className={cx("mt-0.5 shrink-0 [&>svg]:size-5", tone === "info" ? "text-info" : tone === "success" ? "text-success" : "text-danger")}>{icon}</span>
      <div className="min-w-0">
        <p className="text-sm font-semibold">{title}</p>
        {body && <p className="text-sm whitespace-pre-line text-foreground/85">{body}</p>}
      </div>
    </section>
  );
}
