"use client";

import { useState, useTransition } from "react";

import { startCheckout } from "@/app/classes/actions";
import { useT } from "@eduzone/lib/i18n/client";
import type { GatewayRedirect } from "@eduzone/lib/types";

import { ErrorText, buttonClass } from "@eduzone/ui";

/** Sends the browser to the gateway the way it expects: a form POST (PayHere) or a GET. */
function goToGateway(r: GatewayRedirect) {
  const form = document.createElement("form");
  form.method = r.method;
  form.action = r.url;
  for (const [name, value] of Object.entries(r.fields)) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  if (r.method === "GET" && Object.keys(r.fields).length === 0) {
    window.location.assign(r.url);   // keep the URL's own query string
    return;
  }
  document.body.appendChild(form);
  form.submit();
}

export function PayButton({ classId, monthId, label, small = false }: {
  classId: string;
  monthId: string | null;
  label: string;
  small?: boolean;
}) {
  const t = useT();
  const [pending, start] = useTransition();
  const [leaving, setLeaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function pay() {
    setError(null);
    start(async () => {
      const res = await startCheckout(classId, monthId);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setLeaving(true);
      goToGateway(res.redirect);
    });
  }

  const busy = pending || leaving;
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={pay}
        disabled={busy}
        className={`${buttonClass.primary} ${small ? "min-h-9 px-3 text-sm" : ""}`}
      >
        {busy ? t("pay.redirecting") : label}
      </button>
      {error && <ErrorText>{error}</ErrorText>}
    </div>
  );
}
