"use client";

import { Eye, EyeOff } from "lucide-react";
import { useState, type ComponentProps } from "react";

import { cx } from "./cx";
import { inputClass } from "./forms";

/** Password field with a show/hide toggle (labels passed in, so they can be translated). */
export function PasswordInput({
  showLabel,
  hideLabel,
  ...props
}: Omit<ComponentProps<"input">, "type"> & { showLabel: string; hideLabel: string }) {
  const [shown, setShown] = useState(false);
  return (
    <div className="relative">
      <input {...props} type={shown ? "text" : "password"} className={cx(inputClass, "pr-12", props.className)} />
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        aria-label={shown ? hideLabel : showLabel}
        aria-pressed={shown}
        className="absolute inset-y-0 right-0 grid w-12 place-items-center text-subtle hover:text-foreground"
      >
        {shown ? <EyeOff className="size-4.5" /> : <Eye className="size-4.5" />}
      </button>
    </div>
  );
}

/** Six-digit SMS code: one field, large and spaced, with the phone's one-time-code autofill. */
export function CodeInput(props: Omit<ComponentProps<"input">, "type">) {
  return (
    <input
      inputMode="numeric"
      autoComplete="one-time-code"
      pattern="[0-9]{6}"
      maxLength={6}
      required
      {...props}
      className={cx(inputClass, "min-h-14 text-center font-display text-2xl tracking-[0.5em]", props.className)}
    />
  );
}
