"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { cx } from "./cx";

/** A dialog that is a bottom sheet on phones and a centred card from `sm` up. */
export function Dialog({
  trigger,
  title,
  description,
  children,
  open,
  onOpenChange,
  closeLabel = "Close",
}: {
  trigger?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  closeLabel?: string;
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      {trigger && <RadixDialog.Trigger asChild>{trigger}</RadixDialog.Trigger>}
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-50 bg-brand-950/45 backdrop-blur-[2px] data-[state=open]:animate-[ez-fade_.2s_ease]" />
        <RadixDialog.Content
          className={cx(
            "fixed inset-x-0 bottom-0 z-50 max-h-[90dvh] overflow-y-auto rounded-t-ez-lg border border-border bg-surface p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-ez-lg",
            "data-[state=open]:animate-[ez-sheet_.32s_var(--ez-ease)]",
            "sm:inset-x-auto sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:w-full sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-ez-lg sm:data-[state=open]:animate-[ez-pop_.24s_var(--ez-ease)]",
          )}
        >
          <div aria-hidden className="mx-auto -mt-2 mb-4 h-1 w-10 rounded-full bg-border-strong sm:hidden" />
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <RadixDialog.Title className="font-display text-xl font-semibold">{title}</RadixDialog.Title>
              {description && <RadixDialog.Description className="mt-1 text-sm text-muted">{description}</RadixDialog.Description>}
            </div>
            <RadixDialog.Close
              aria-label={closeLabel}
              className="-m-1.5 grid size-9 shrink-0 place-items-center rounded-full text-muted hover:bg-sunken hover:text-foreground"
            >
              <X className="size-4.5" />
            </RadixDialog.Close>
          </div>
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

export const DialogClose = RadixDialog.Close;
