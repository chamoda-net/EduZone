import { en, type MessageKey, type Messages } from "./en";

export type { MessageKey, Messages };
export type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string;

const catalogues: Record<string, Messages> = { en };

export function getMessages(lang = "en"): Messages {
  return catalogues[lang] ?? en;
}

export function makeT(messages: Messages): Translate {
  return (key, vars) => {
    const template = messages[key] ?? en[key] ?? key;
    return vars ? template.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`)) : template;
  };
}

/** Translate an API error: a known error code gets our own text, else the API's message. */
export function errorText(t: Translate, error: { code: string; message: string }): string {
  // Validation messages name the exact field and rule, which is more useful than a generic line.
  if (error.code === "VALIDATION_ERROR" && error.message) return error.message;
  const key = `errors.${error.code}` as MessageKey;
  return key in en ? t(key) : error.message || t("errors.generic");
}

// The UI language is English for v1; si/ta plug in here (user preference or cookie).
export const t = makeT(getMessages("en"));
