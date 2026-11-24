"use server";

import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";

export type ContactValues = { topic: string; name: string; email: string; phone: string; subject: string; message: string };
export type ContactState =
  | { sent: true; reference: string; name: string; email: string }
  | { sent?: false; error?: string; values?: ContactValues };

/** Sends the Contact form. The signed-in account (if any) travels with it, so staff can find it. Inputs are echoed
 * back on an error because React resets a form after each action. */
export async function sendContact(_: ContactState, form: FormData): Promise<ContactState> {
  const get = (name: string) => String(form.get(name) ?? "").trim();
  const values: ContactValues = {
    topic: get("topic"), name: get("name"), email: get("email"), phone: get("phone"), subject: get("subject"),
    message: String(form.get("message") ?? "").trim(),
  };
  const res = await api<Schema<"ContactSent">>("/market/contact", {
    method: "POST",
    body: { ...values, phone: values.phone || null, website: get("website") || null },
  });
  if (!res.ok) return { error: errorText(t, res.error), values };
  return { sent: true, reference: res.data.reference, name: values.name.split(/\s+/)[0] ?? values.name, email: values.email };
}
