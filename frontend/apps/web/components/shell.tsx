import { BookOpen, Compass, LayoutDashboard, LockKeyhole, Receipt } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { SignOutButton } from "@/components/sign-out-button";
import { getBranding, getMe, isStaff } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";
import { Avatar, Container, HeaderNav, Logo, TabBar, buttonStyles, cx, type NavItem } from "@eduzone/ui";

/** The student side of a tenant's site: sticky header, page, footer, and bottom tabs on phones. */
export async function SiteShell({ children, width = "lg", bare = false }: {
  children: ReactNode;
  width?: "sm" | "md" | "lg";
  /** Full-bleed pages (home hero, class header) manage their own containers. */
  bare?: boolean;
}) {
  const [branding, me] = await Promise.all([getBranding(), getMe()]);
  const items: NavItem[] = [{ href: "/", label: t("nav.browse"), icon: <Compass />, exact: true }];
  if (me) {
    items.push(
      { href: "/my", label: t("nav.myClasses"), icon: <BookOpen /> },
      { href: "/payments", label: t("nav.payments"), icon: <Receipt /> },
    );
    if (isStaff(me)) items.push({ href: "/org/classes", label: t("nav.console"), icon: <LayoutDashboard /> });
  }

  return (
    <>
      <header className="ez-no-print sticky top-0 z-40 border-b border-border/80 bg-background/85 backdrop-blur-md">
        <Container className="flex h-16 items-center justify-between gap-4">
          <Link href="/" className="min-w-0">
            <Logo name={branding?.name ?? "EduZone"} sub={t("shell.onEduZone")} />
          </Link>
          <HeaderNav items={items} />
          <div className="flex shrink-0 items-center gap-2">
            {me ? (
              <>
                <span className="hidden items-center gap-2.5 lg:flex">
                  <Avatar name={me.full_name} size="sm" />
                  <span className="max-w-36 truncate text-sm font-semibold">{me.full_name}</span>
                </span>
                <SignOutButton />
              </>
            ) : (
              <Link href="/login" className={buttonStyles("primary", "sm")}>
                {t("home.signIn")}
              </Link>
            )}
          </div>
        </Container>
      </header>

      <main className={cx("flex flex-1 flex-col", me && "pb-20 md:pb-0")}>
        {bare ? children : (
          <Container size={width === "lg" ? "lg" : width} className="flex flex-1 flex-col gap-8 py-8 sm:py-12">
            {children}
          </Container>
        )}
      </main>

      <SiteFooter name={branding?.name ?? "EduZone"} />
      {me && <TabBar items={items} />}
    </>
  );
}

function SiteFooter({ name }: { name: string }) {
  return (
    <footer className="ez-no-print ez-grain mt-16 bg-brand-950 text-brand-100">
      <Container className="grid gap-10 py-12 sm:grid-cols-[1.4fr_1fr] md:pb-14">
        <div className="flex flex-col gap-4">
          <span className="text-on-brand">
            <Logo name={name} sub={t("shell.onEduZone")} />
          </span>
          <p className="max-w-sm text-sm leading-relaxed text-brand-100/75">{t("footer.tagline")}</p>
        </div>
        <div className="flex flex-col gap-3 text-sm sm:items-end sm:text-right">
          <p className="inline-flex items-center gap-2 font-semibold text-on-brand">
            <LockKeyhole className="size-4 text-gold" />
            {t("footer.secureTitle")}
          </p>
          <p className="max-w-xs text-brand-100/70">{t("footer.secure")}</p>
        </div>
      </Container>
      <div className="border-t border-brand-900">
        <Container className="flex flex-col gap-1 py-5 text-xs text-brand-100/55 sm:flex-row sm:justify-between">
          <span>{t("footer.rights", { year: new Date().getFullYear() })}</span>
          <span>{t("app.poweredBy")}</span>
        </Container>
      </div>
    </footer>
  );
}
