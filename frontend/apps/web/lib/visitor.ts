// Tells the API who the visitor is. The browser never calls the API, so without this every visitor would share this
// server's address, and its sign-in and SMS limits. Used by proxy.ts too, so no server-only imports here.

const KEY = process.env.WEB_SERVER_KEY ?? "";
const HOPS = Math.max(1, Number(process.env.WEB_PROXY_HOPS) || 1);
let warned = false;

/** The visitor's address from X-Forwarded-For. Each proxy adds the address it was called from at the end, so only the
 * last WEB_PROXY_HOPS entries are ours; anything before them was typed by the visitor. (With no proxy, as in local
 * development, Next puts the connection's address there.) */
export function visitorIp(forwardedFor: string | null): string | null {
  const list = (forwardedFor ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  return list.at(-HOPS) ?? null;
}

/** The headers naming the visitor to the API: none without the shared key (the API wouldn't believe them). */
export function visitorHeaders(incoming: Headers): Record<string, string> {
  if (!KEY) {
    if (process.env.NODE_ENV === "production" && !warned) {
      warned = true;
      console.error("WEB_SERVER_KEY is not set: all visitors share one sign-in limit.");
    }
    return {};
  }
  const ip = visitorIp(incoming.get("x-forwarded-for"));
  return ip ? { "x-eduzone-web-key": KEY, "x-eduzone-client-ip": ip } : {};
}
