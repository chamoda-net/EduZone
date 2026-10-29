"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useT } from "@/lib/i18n/client";

const ITEMS = [
  { href: "/org/classes", key: "org.nav.classes" },
  { href: "/org/requests", key: "org.nav.requests" },
  { href: "/org/payments", key: "org.nav.payments" },
  { href: "/org/media", key: "org.nav.media" },
] as const;

export function OrgNav() {
  const t = useT();
  const path = usePathname();
  return (
    <nav className="border-b border-border bg-surface">
      <div className="mx-auto flex w-full max-w-4xl gap-5 px-4 text-sm">
        {ITEMS.map((item) => {
          const active = path.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`border-b-2 py-2.5 font-medium ${active ? "border-brand" : "border-transparent text-muted"}`}
            >
              {t(item.key)}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
