import type { Metadata } from "next";
import { Geist, Noto_Sans_Sinhala } from "next/font/google";
import type { CSSProperties } from "react";

import { userHost } from "@/lib/api";
import { isAdminHost } from "@/lib/cookies";
import { t, getMessages } from "@/lib/i18n";
import { I18nProvider } from "@/lib/i18n/client";
import { getBranding } from "@/lib/session";

import "./globals.css";

const sans = Geist({ variable: "--font-geist", subsets: ["latin"] });
// Class titles and names are often in Sinhala.
const sinhala = Noto_Sans_Sinhala({ variable: "--font-sinhala", subsets: ["sinhala"] });

export async function generateMetadata(): Promise<Metadata> {
  if (isAdminHost(await userHost())) return { title: "EduZone Admin", robots: { index: false, follow: false } };
  const branding = await getBranding();
  return { title: branding?.name ?? "EduZone" };
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // The admin host has no tenant: EduZone's own plain styling, no branding lookup.
  const admin = isAdminHost(await userHost());
  const branding = admin ? null : await getBranding();
  const style = { "--brand": branding?.primary_color ?? "#1e6fd9" } as CSSProperties;

  return (
    <html lang="en" className={`${sans.variable} ${sinhala.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-sans" style={style}>
        <I18nProvider messages={getMessages("en")}>
          {admin || branding ? children : <TenantNotFound />}
        </I18nProvider>
      </body>
    </html>
  );
}

function TenantNotFound() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-3 px-4 py-16">
      <h1 className="text-2xl font-semibold">{t("tenant.notFound.title")}</h1>
      <p className="text-muted">{t("tenant.notFound.body")}</p>
    </main>
  );
}
