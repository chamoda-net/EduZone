"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { cx } from "./cx";

export type NavItem = { href: string; label: string; icon: ReactNode; exact?: boolean };

function isActive(path: string, item: NavItem) {
  return item.exact ? path === item.href : path === item.href || path.startsWith(`${item.href}/`);
}

/** Vertical navigation for the console sidebar (and its mobile drawer). */
export function SideNav({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  const path = usePathname();
  return (
    <nav className="flex flex-col gap-0.5">
      {items.map((item) => {
        const active = isActive(path, item);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cx(
              "group relative flex min-h-11 items-center gap-3 rounded-ez px-3 text-[0.9375rem] font-medium transition-colors",
              active ? "bg-brand-800 text-on-brand" : "text-brand-100/80 hover:bg-brand-800/60 hover:text-on-brand",
            )}
          >
            {active && <span aria-hidden className="absolute top-2.5 bottom-2.5 -left-3 w-1 rounded-r-full bg-gold" />}
            <span className={cx("[&>svg]:size-[18px]", active ? "text-gold" : "text-brand-300 group-hover:text-gold-300")}>
              {item.icon}
            </span>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Mobile drawer that holds the same sidebar content. */
export function NavDrawer({ label, children }: { label: string; children: (close: () => void) => ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <RadixDialog.Root open={open} onOpenChange={setOpen}>
      <RadixDialog.Trigger
        aria-label={label}
        className="grid size-10 place-items-center rounded-ez text-foreground hover:bg-sunken lg:hidden"
      >
        <Menu className="size-5" />
      </RadixDialog.Trigger>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-50 bg-brand-950/50 backdrop-blur-[2px] lg:hidden" />
        <RadixDialog.Content className="ez-grain fixed inset-y-0 left-0 z-50 flex w-[82%] max-w-xs flex-col bg-brand-900 p-4 text-on-brand shadow-ez-lg animate-[ez-drawer_.3s_var(--ez-ease)] lg:hidden">
          <RadixDialog.Title className="sr-only">{label}</RadixDialog.Title>
          <RadixDialog.Close
            aria-label="Close"
            className="absolute top-4 right-4 grid size-9 place-items-center rounded-full text-brand-100 hover:bg-brand-800"
          >
            <X className="size-4.5" />
          </RadixDialog.Close>
          {children(() => setOpen(false))}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

/** Bottom tab bar for the student area on phones. */
export function TabBar({ items }: { items: NavItem[] }) {
  const path = usePathname();
  return (
    <nav className="ez-no-print fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface/92 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden">
      <div className="mx-auto grid max-w-md" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
        {items.map((item) => {
          const active = isActive(path, item);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cx(
                "flex min-h-15 flex-col items-center justify-center gap-1 text-[0.7rem] font-semibold transition-colors",
                active ? "text-brand" : "text-subtle hover:text-foreground",
              )}
            >
              <span
                className={cx(
                  "grid h-7 w-12 place-items-center rounded-full transition-colors [&>svg]:size-5",
                  active && "bg-brand-50",
                )}
              >
                {item.icon}
              </span>
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

/** Horizontal links in a site header, with the current page underlined. */
export function HeaderNav({ items }: { items: NavItem[] }) {
  const path = usePathname();
  return (
    <nav className="hidden items-center gap-1 md:flex">
      {items.map((item) => {
        const active = isActive(path, item);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cx(
              "relative rounded-ez px-3 py-2 text-sm font-semibold transition-colors",
              active ? "text-foreground" : "text-muted hover:text-foreground",
            )}
          >
            {item.label}
            {active && <span aria-hidden className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full bg-brand" />}
          </Link>
        );
      })}
    </nav>
  );
}
