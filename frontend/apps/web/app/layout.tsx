import type { Metadata } from "next";
import { Fraunces, Instrument_Sans, Noto_Sans_Sinhala } from "next/font/google";

import { t, getMessages } from "@eduzone/lib/i18n";
import { I18nProvider } from "@eduzone/lib/i18n/client";
import { Toaster } from "@eduzone/ui";
import { getBranding } from "@/lib/session";

import "./globals.css";

// Display: Fraunces (soft, scholarly serif). Text and UI: Instrument Sans. Sinhala: Noto Sans Sinhala.
const display = Fraunces({ variable: "--font-display-serif", subsets: ["latin"], axes: ["SOFT", "opsz"] });
const body = Instrument_Sans({ variable: "--font-body", subsets: ["latin"] });
const sinhala = Noto_Sans_Sinhala({ variable: "--font-sinhala", subsets: ["sinhala"] });

export async function generateMetadata(): Promise<Metadata> {
  const branding = await getBranding();
  return { title: branding?.name ?? "EduZone" };
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const branding = await getBranding();

  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${sinhala.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <I18nProvider messages={getMessages("en")}>
          {branding ? children : <TenantNotFound />}
          <Toaster />
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
