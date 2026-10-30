import { BookOpen, Building2, CalendarDays, Compass, House, LayoutDashboard, LockKeyhole, Receipt, Smartphone, Users } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { SignOutButton } from "@/components/sign-out-button";
import { getBranding, getSession, isStaff } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";
import { Alert, Avatar, Container, HeaderNav, Logo, TabBar, buttonStyles, cx, type NavItem } from "@eduzone/ui";

/** The site frame: sticky header with the marketplace links (and the student area when signed in),
 * page, footer, and bottom tabs on phones for signed-in students. */
export async function SiteShell({ children, width = "lg", bare = false }: {
  children: ReactNode;
  width?: "sm" | "md" | "lg";
  /** Full-bleed pages (home hero, class header) manage their own containers. */
  bare?: boolean;
}) {
  const [branding, { me, endedElsewhere }] = await Promise.all([getBranding(), getSession()]);
  // Header (desktop): the marketplace, then the student area and console.
  const items: NavItem[] = [
    { href: "/classes", label: t("nav.browse"), icon: <Compass /> },
    { href: "/teachers", label: t("nav.teachers"), icon: <Users /> },
  ];
  if (me) {
    items.push({ href: "/learn", label: t("nav.myLearning"), icon: <House /> });
    if (isStaff(me)) items.push({ href: "/teach", label: t("nav.console"), icon: <LayoutDashboard /> });
  } else {
    items.push({ href: "/institutes", label: t("nav.institutes"), icon: <Building2 /> });
  }
  // Bottom tabs (phones, signed in): the student area plus browsing.
  const tabs: NavItem[] = [
    { href: "/learn", label: t("nav.today"), icon: <House />, exact: true },
    { href: "/learn/classes", label: t("nav.myClasses"), icon: <BookOpen /> },
    { href: "/classes", label: t("nav.browse"), icon: <Compass /> },
    { href: "/learn/schedule", label: t("nav.schedule"), icon: <CalendarDays /> },
    me && isStaff(me)
      ? { href: "/teach", label: t("nav.console"), icon: <LayoutDashboard /> }
      : { href: "/learn/payments", label: t("nav.payments"), icon: <Receipt /> },
  ];

  return (
    <>
      <header className="ez-no-print sticky top-0 z-40 border-b border-border/80 bg-background/85 backdrop-blur-md">
        <Container className="flex h-16 items-center justify-between gap-4">
          <Link href="/" className="min-w-0">
            <Logo name={branding?.name ?? "EduZone"} sub={branding ? t("shell.onEduZone") : undefined} />
          </Link>
          <HeaderNav items={items} />
          <div className="flex shrink-0 items-center gap-2">
            {me ? (
              <>
                <Link href="/learn/profile" className="hidden items-center gap-2.5 rounded-full py-1 pr-3 pl-1 hover:bg-sunken lg:flex">
                  <Avatar name={me.full_name} size="sm" />
                  <span className="max-w-36 truncate text-sm font-semibold">{me.full_name}</span>
                </Link>
                <SignOutButton />
              </>
            ) : (
              <>
                <Link href="/login" className={buttonStyles("ghost", "sm", "hidden sm:inline-flex")}>
                  {t("home.signIn")}
                </Link>
                <Link href="/register" className={buttonStyles("primary", "sm")}>
                  {t("nav.join")}
                </Link>
              </>
            )}
          </div>
        </Container>
      </header>

      {(endedElsewhere || (me && !me.phone_verified && !isStaff(me))) && (
        <Container className="ez-no-print pt-4">
          {endedElsewhere ? (
            <Alert tone="warning" title={t("auth.elsewhere.title")}>{t("auth.elsewhere.body")}</Alert>
          ) : (
            <div className="flex flex-wrap items-center gap-3 rounded-ez border border-gold/30 bg-gold-100 px-4 py-3 text-sm">
              <Smartphone className="size-4.5 text-gold-strong" />
              <p className="flex-1 font-medium text-foreground">{t("phone.banner")}</p>
              <Link href="/verify-phone" className={buttonStyles("primary", "sm")}>{t("phone.bannerAction")}</Link>
            </div>
          )}
        </Container>
      )}

      <main className={cx("flex flex-1 flex-col", me && "pb-20 md:pb-0")}>
        {bare ? children : (
          <Container size={width === "lg" ? "lg" : width} className="flex flex-1 flex-col gap-8 py-8 sm:py-12">
            {children}
          </Container>
        )}
      </main>

      <SiteFooter name={branding?.name ?? "EduZone"} tenantSite={Boolean(branding)} />
      {me && <TabBar items={tabs} />}
    </>
  );
}

function SiteFooter({ name, tenantSite }: { name: string; tenantSite: boolean }) {
  return (
    <footer className="ez-no-print ez-grain mt-16 bg-brand-950 text-brand-100">
      <Container className="grid gap-10 py-12 sm:grid-cols-[1.4fr_1fr] md:pb-14">
        <div className="flex flex-col gap-4">
          <span className="text-on-brand">
            <Logo name={name} sub={tenantSite ? t("shell.onEduZone") : undefined} />
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
        <Container className="flex flex-col gap-3 py-5 text-xs text-brand-100/55 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("footer.rights", { year: new Date().getFullYear() })}</span>
          <nav className="flex flex-wrap gap-x-4 gap-y-1">
            {([["/about", "static.about.title"], ["/terms", "static.terms.title"], ["/privacy", "static.privacy.title"],
               ["/refund-policy", "static.refunds.title"], ["/contact", "static.contact.title"]] as const).map(([href, key]) => (
              <Link key={href} href={href} className="hover:text-on-brand">{t(key)}</Link>
            ))}
          </nav>
        </Container>
      </div>
    </footer>
  );
}
