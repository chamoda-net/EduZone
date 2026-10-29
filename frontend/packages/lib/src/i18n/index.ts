import { createTranslator, type AbstractIntlMessages } from "next-intl";

import { en, type MessageKey, type Messages } from "./en";

export type { MessageKey, Messages };
export type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string;

// Messages are ICU (next-intl). Display formats stay in Asia/Colombo (CLAUDE.md section 12).
export const LOCALE = "en";
export const TIME_ZONE = "Asia/Colombo";

const catalogues: Record<string, Messages> = { en };

export function getMessages(lang = LOCALE): Messages {
  return catalogues[lang] ?? en;
}

/** Catalogues keep flat dotted keys; next-intl reads the same keys as nested namespaces. */
export function nestMessages(messages: Messages): AbstractIntlMessages {
  const root: AbstractIntlMessages = {};
  for (const [key, text] of Object.entries(messages)) {
    const parts = key.split(".");
    let node = root;
    for (const part of parts.slice(0, -1)) node = (node[part] ??= {}) as AbstractIntlMessages;
    node[parts.at(-1)!] = text;
  }
  return root;
}

// A missing key or variable falls back to English, then to the key, instead of throwing.
export function fallback({ key, namespace }: { key: string; namespace?: string }): string {
  const full = (namespace ? `${namespace}.${key}` : key) as MessageKey;
  return en[full] ?? full;
}

type Raw = (key: string, vars?: Record<string, string | number>) => string;

export function wrapTranslator(raw: Raw): Translate {
  return (key, vars) => raw(key, vars);
}

export function makeT(messages: Messages, locale = LOCALE): Translate {
  const raw = createTranslator({
    locale,
    timeZone: TIME_ZONE,
    messages: nestMessages(messages),
    onError: () => {},
    getMessageFallback: fallback,
  }) as unknown as Raw;
  return wrapTranslator(raw);
}

/** Translate an API error: a known error code gets our own text, else the API's message. */
export function errorText(t: Translate, error: { code: string; message: string }): string {
  // Validation messages name the exact field and rule, which is more useful than a generic line.
  if (error.code === "VALIDATION_ERROR" && error.message) return error.message;
  const key = `errors.${error.code}` as MessageKey;
  return key in en ? t(key) : error.message || t("errors.generic");
}

// The UI language is English for v1; si/ta plug in here (user preference or cookie).
export const t = makeT(getMessages(LOCALE));
