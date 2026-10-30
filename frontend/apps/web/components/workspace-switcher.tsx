"use client";

import { ArrowLeftRight } from "lucide-react";
import { useRouter } from "next/navigation";

import type { Workspace } from "@eduzone/lib/types";

/** Shown in the console sidebar when the account is staff of more than one organization. */
export function WorkspaceSwitcher({ current, workspaces, label }: {
  current: string;
  workspaces: Workspace[];
  label: string;
}) {
  const router = useRouter();
  return (
    <label className="mx-1 mb-2 flex items-center gap-2 rounded-ez bg-brand-800/70 px-3 py-2 text-sm text-brand-100">
      <ArrowLeftRight className="size-4 shrink-0 text-gold" />
      <span className="sr-only">{label}</span>
      <select
        value={current}
        onChange={(e) => router.push(`/teach/${e.target.value}/classes`)}
        className="min-w-0 flex-1 cursor-pointer bg-transparent font-semibold text-on-brand outline-none [&>option]:text-foreground"
      >
        {workspaces.map((w) => (
          <option key={w.slug} value={w.slug}>{w.name}</option>
        ))}
      </select>
    </label>
  );
}
