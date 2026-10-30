"use client";

import type { ReactNode } from "react";

import { NavDrawer, SideNav, type NavItem } from "./nav";

/** Console layout: dark sidebar from `lg` up; a top bar with a drawer on smaller screens. */
export function ConsoleFrame({
  brand,
  items,
  footer,
  menuLabel,
  children,
}: {
  brand: ReactNode;
  items: NavItem[];
  footer?: ReactNode;
  menuLabel: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-1">
      <aside className="ez-grain sticky top-0 hidden h-dvh w-68 shrink-0 flex-col bg-brand-900 px-3 py-5 text-on-brand lg:flex">
        <div className="px-3 pb-6">{brand}</div>
        <div className="flex-1 overflow-y-auto">
          <SideNav items={items} />
        </div>
        {footer && <div className="mt-4 border-t border-brand-800 pt-4">{footer}</div>}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-2 border-b border-border bg-background/90 px-3 backdrop-blur-md lg:hidden">
          <NavDrawer label={menuLabel}>
            {(close) => (
              <div className="flex h-full flex-col">
                <div className="px-3 pt-1 pb-6">{brand}</div>
                <div className="flex-1 overflow-y-auto">
                  <SideNav items={items} onNavigate={close} />
                </div>
                {footer && <div className="mt-4 border-t border-brand-800 pt-4">{footer}</div>}
              </div>
            )}
          </NavDrawer>
          <div className="min-w-0 text-foreground [&_svg]:size-8">{brand}</div>
        </header>
        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-6 sm:px-6 lg:px-10 lg:py-10">{children}</main>
      </div>
    </div>
  );
}
