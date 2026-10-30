import type { Metadata } from "next";
import { Fraunces, Instrument_Sans, Noto_Sans_Sinhala } from "next/font/google";

import { getMessages } from "@eduzone/lib/i18n";
import { I18nProvider } from "@eduzone/lib/i18n/client";
import { Toaster } from "@eduzone/ui";

import "./globals.css";

// Display: Fraunces (soft, scholarly serif). Text and UI: Instrument Sans. Sinhala: Noto Sans Sinhala.
const display = Fraunces({ variable: "--font-display-serif", subsets: ["latin"], axes: ["SOFT", "opsz"] });
const body = Instrument_Sans({ variable: "--font-body", subsets: ["latin"] });
const sinhala = Noto_Sans_Sinhala({ variable: "--font-sinhala", subsets: ["sinhala"] });

// Private network only (CLAUDE.md section 2); never indexed.
export const metadata: Metadata = { title: "EduZone Admin", robots: { index: false, follow: false } };

export default function AdminRootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${sinhala.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <I18nProvider messages={getMessages("en")}>
          {children}
          <Toaster />
        </I18nProvider>
      </body>
    </html>
  );
}
