"use client";

import { CircleAlert, CircleCheck, X } from "lucide-react";
import { useSyncExternalStore } from "react";

import { cx } from "./cx";

type Toast = { id: number; tone: "success" | "error"; message: string };

let toasts: Toast[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

function dismiss(id: number) {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

/** Shows a short message at the bottom of the screen (top-right on desktop). */
export function toast(message: string, tone: Toast["tone"] = "success") {
  const id = nextId++;
  toasts = [...toasts.slice(-2), { id, tone, message }];
  emit();
  setTimeout(() => dismiss(id), tone === "error" ? 6000 : 3500);
}

const EMPTY: Toast[] = [];

/** Render once in the root layout. */
export function Toaster() {
  const items = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => toasts,
    () => EMPTY,
  );
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-[60] flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:top-5 sm:right-5 sm:bottom-auto sm:items-end"
    >
      {items.map((t) => (
        <div
          key={t.id}
          role={t.tone === "error" ? "alert" : "status"}
          className={cx(
            "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-ez border bg-surface px-4 py-3 text-sm shadow-ez-lg",
            "animate-[ez-pop_.28s_var(--ez-ease)]",
            t.tone === "error" ? "border-danger/25" : "border-border",
          )}
        >
          {t.tone === "error" ? (
            <CircleAlert className="mt-px size-4.5 shrink-0 text-danger" />
          ) : (
            <CircleCheck className="mt-px size-4.5 shrink-0 text-success" />
          )}
          <p className="flex-1 font-medium">{t.message}</p>
          <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss" className="-m-1 p-1 text-subtle hover:text-foreground">
            <X className="size-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
