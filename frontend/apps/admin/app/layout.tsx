import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { getMessages } from "@eduzone/lib/i18n";
import { I18nProvider } from "@eduzone/lib/i18n/client";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

// Private network only (CLAUDE.md section 2); never indexed.
export const metadata: Metadata = { title: "EduZone Admin", robots: { index: false, follow: false } };

export default function AdminRootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <I18nProvider messages={getMessages("en")}>{children}</I18nProvider>
      </body>
    </html>
  );
}
