"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useT } from "@/lib/i18n/client";

const ITEMS = [
  { href: "/org/classes", key: "org.nav.classes", ownersOnly: false },
  { href: "/org/requests", key: "org.nav.requests", ownersOnly: false },
  { href: "/org/payments", key: "org.nav.payments", ownersOnly: false },
  { href: "/org/earnings", key: "org.nav.earnings", ownersOnly: false },
  { href: "/org/money", key: "org.nav.money", ownersOnly: true },
  { href: "/org/media", key: "org.nav.media", ownersOnly: false },
] as const;

/** `managesAll`: owners and admins also see Money (the API enforces the same rule). */
export function OrgNav({ managesAll }: { managesAll: boolean }) {
  const t = useT();
  const path = usePathname();
  return (
    <nav className="border-b border-border bg-surface">
      <div className="mx-auto flex w-full max-w-4xl gap-5 overflow-x-auto px-4 text-sm whitespace-nowrap">
        {ITEMS.filter((item) => managesAll || !item.ownersOnly).map((item) => {
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
