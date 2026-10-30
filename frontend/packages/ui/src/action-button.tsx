"use client";

import { useActionState, useEffect, useRef } from "react";

import { Button, type ButtonVariant } from "./button";
import { toast } from "./toast";
import type { ActionState } from "./ui";

/** A one-click Server Action (publish, close month, delete…) that shows its own error,
 * and a toast on success when `done` is given. */
export function ActionButton({
  action,
  label,
  variant = "secondary",
  confirm,
  small = false,
  done,
}: {
  action: () => Promise<ActionState>;
  label: string;
  variant?: ButtonVariant;
  confirm?: string;
  small?: boolean;
  done?: string;
}) {
  const [state, run, pending] = useActionState<ActionState>(action, {});
  const shown = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (done && state.ok && state.at !== shown.current) {
      shown.current = state.at;
      toast(done);
    }
  }, [done, state]);

  return (
    <form
      action={run}
      onSubmit={(e) => {
        if (confirm && !window.confirm(confirm)) e.preventDefault();
      }}
      className="inline-flex flex-col items-start gap-1"
    >
      <Button variant={variant} size={small ? "sm" : "md"} loading={pending}>
        {label}
      </Button>
      {state.error && (
        <span role="alert" className="max-w-xs text-xs font-medium text-danger">
          {state.error}
        </span>
      )}
    </form>
  );
}
