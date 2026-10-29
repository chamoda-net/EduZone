"use client";

import { NextIntlClientProvider, useTranslations } from "next-intl";
import { useMemo, type ReactNode } from "react";

import { LOCALE, TIME_ZONE, fallback, nestMessages, wrapTranslator, type Messages, type Translate } from "./index";

export function I18nProvider({ messages, children }: { messages: Messages; children: ReactNode }) {
  const nested = useMemo(() => nestMessages(messages), [messages]);
  return (
    <NextIntlClientProvider
      locale={LOCALE}
      timeZone={TIME_ZONE}
      messages={nested}
      onError={() => {}}
      getMessageFallback={fallback}
    >
      {children}
    </NextIntlClientProvider>
  );
}

export function useT(): Translate {
  const raw = useTranslations();
  return useMemo(() => wrapTranslator(raw as unknown as Parameters<typeof wrapTranslator>[0]), [raw]);
}
