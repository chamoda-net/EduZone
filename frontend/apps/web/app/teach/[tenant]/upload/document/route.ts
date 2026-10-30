import { cookies } from "next/headers";

import { API_URL } from "@/lib/api";
import { ACCESS_COOKIE } from "@/lib/cookies";

/** PDF upload into a workspace: streams the multipart body straight through to the API, so a
 * 50 MB file is never held in a Server Action payload. Excluded from proxy.ts (see its matcher). */
export async function POST(request: Request, { params }: RouteContext<"/teach/[tenant]/upload/document">): Promise<Response> {
  const { tenant } = await params;
  if (!/^[a-z0-9-]+$/.test(tenant)) {
    return Response.json({ error: { code: "NOT_FOUND", message: "Not found." } }, { status: 404 });
  }
  const host = request.headers.get("host") ?? "";
  // Same-origin only. The lax session cookie already blocks cross-site posts; this is a second lock.
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== host) {
    return Response.json({ error: { code: "ACCESS_DENIED", message: "Cross-site upload refused." } }, { status: 403 });
  }

  const token = (await cookies()).get(ACCESS_COOKIE)?.value;
  const headers: Record<string, string> = {
    "content-type": request.headers.get("content-type") ?? "",
    "x-forwarded-host": host,
  };
  if (token) headers.authorization = `Bearer ${token}`;

  try {
    const res = await fetch(`${API_URL}/api/v1/teach/${tenant}/media/documents`, {
      method: "POST",
      headers,
      body: request.body,
      // Required by Node's fetch to stream a request body.
      duplex: "half",
    } as RequestInit & { duplex: "half" });
    return new Response(res.body, { status: res.status, headers: { "content-type": "application/json" } });
  } catch {
    return Response.json({ error: { code: "API_UNREACHABLE", message: "The server is not reachable." } }, { status: 503 });
  }
}
