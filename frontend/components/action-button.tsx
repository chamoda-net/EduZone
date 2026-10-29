"use client";

import { useActionState } from "react";

import type { FormState } from "@/app/org/classes/actions";

import { buttonClass } from "./ui";

/** A one-click Server Action (publish, close month, delete…) that shows its own error. */
export function ActionButton({
  action,
  label,
  variant = "secondary",
  confirm,
  small = false,
}: {
  action: () => Promise<FormState>;
  label: string;
  variant?: keyof typeof buttonClass;
  confirm?: string;
  small?: boolean;
}) {
  const [state, run, pending] = useActionState<FormState>(action, {});
  return (
    <form
      action={run}
      onSubmit={(e) => {
        if (confirm && !window.confirm(confirm)) e.preventDefault();
      }}
      className="inline-flex flex-col items-start gap-1"
    >
      <button className={`${buttonClass[variant]} ${small ? "min-h-9 px-3 text-sm" : ""}`} disabled={pending}>
        {label}
      </button>
      {state.error && (
        <span role="alert" className="max-w-xs text-xs text-red-700 dark:text-red-400">
          {state.error}
        </span>
      )}
    </form>
  );
}
