"use client";

import { createContext, use, useMemo, type ReactNode } from "react";

import { makeT, type Messages, type Translate } from "./index";

const I18nContext = createContext<Messages | null>(null);

export function I18nProvider({ messages, children }: { messages: Messages; children: ReactNode }) {
  return <I18nContext value={messages}>{children}</I18nContext>;
}

export function useT(): Translate {
  const messages = use(I18nContext);
  if (!messages) throw new Error("useT must be used inside I18nProvider");
  return useMemo(() => makeT(messages), [messages]);
}
