import Link from "next/link";
import type { ReactNode } from "react";

import { getBranding } from "@/lib/session";

export async function SiteHeader({ children, href = "/" }: { children?: ReactNode; href?: string }) {
  const branding = await getBranding();
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex w-full max-w-4xl items-center justify-between gap-3 px-4 py-3">
        <Link href={href} className="flex min-w-0 items-center gap-2 font-semibold">
          <span aria-hidden className="h-7 w-7 shrink-0 rounded-lg bg-brand" />
          <span className="truncate">{branding?.name}</span>
        </Link>
        <div className="flex shrink-0 items-center gap-3">{children}</div>
      </div>
    </header>
  );
}
