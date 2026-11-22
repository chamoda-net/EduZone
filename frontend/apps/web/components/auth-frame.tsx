import { CalendarCheck, MonitorPlay, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Photo } from "@/components/photo";
import { PHOTOS } from "@/lib/photos";
import { getBranding } from "@/lib/session";
import { t } from "@eduzone/lib/i18n";
import { Logo } from "@eduzone/ui";

/** Sign-in, registration, phone check and recovery: brand panel on desktop, form on the right. */
export async function AuthFrame({ title, subtitle, children, footer }: {
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const branding = await getBranding();
  const name = branding?.name ?? "EduZone";
  const sub = branding ? t("shell.onEduZone") : undefined;
  return (
    <div className="grid min-h-dvh flex-1 lg:grid-cols-[1fr_1.05fr]">
      <aside className="ez-grain relative hidden flex-col justify-between overflow-hidden bg-brand-900 p-12 text-on-brand lg:flex">
        {/* A student studying, under the brand green so the words stay readable. */}
        <Photo photo={PHOTOS.thinking} ratio={1.25} sizes="50vw" priority className="absolute inset-0 h-full object-[65%_center]" />
        <div aria-hidden className="absolute inset-0 bg-gradient-to-t from-brand-950 via-brand-900/85 to-brand-900/40" />
        <div aria-hidden className="absolute inset-0 bg-gradient-to-r from-brand-950/70 to-transparent" />
        <Link href="/" className="relative">
          <Logo name={name} sub={sub} />
        </Link>
        <div className="relative flex max-w-md flex-col gap-8">
          <h2 className="font-display text-5xl leading-[1.05] font-semibold">
            {t("auth.panel.title")} <span className="text-gold-300 italic">{t("auth.panel.titleMark")}</span>
          </h2>
          <ul className="flex flex-col gap-4 text-brand-100/85">
            {[
              [<MonitorPlay key="a" />, t("auth.panel.point1")],
              [<CalendarCheck key="b" />, t("auth.panel.point2")],
              [<ShieldCheck key="c" />, t("auth.panel.point3")],
            ].map(([icon, text], i) => (
              <li key={i} className="flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-full bg-brand-800 text-gold [&>svg]:size-4.5">{icon}</span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-brand-100/50">{t("app.poweredBy")}</p>
      </aside>

      <main className="flex flex-col px-5 py-8 sm:px-10">
        <Link href="/" className="lg:hidden">
          <Logo name={name} sub={sub} />
        </Link>
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-8 py-10">
          <div className="ez-rise flex flex-col gap-2">
            <h1 className="font-display text-4xl font-semibold">{title}</h1>
            {subtitle && <p className="text-muted">{subtitle}</p>}
          </div>
          <div className="ez-rise" style={{ "--i": 1 } as React.CSSProperties}>
            {children}
          </div>
          {footer && <div className="text-sm text-muted">{footer}</div>}
        </div>
      </main>
    </div>
  );
}
