import "server-only";

import { userHost } from "./api";

/** The main site (BASE_DOMAIN, e.g. eduzone.switchops.tech; `localhost` in development): no
 * tenant in the host. Tenant subdomains stay until the marketplace (phase 4) replaces them. */
export async function isMainHost(): Promise<boolean> {
  const hostname = (await userHost()).toLowerCase().split(":")[0];
  return hostname === (process.env.BASE_DOMAIN ?? "localhost").toLowerCase();
}
