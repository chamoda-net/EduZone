import { cookies } from "next/headers";

import { API_URL } from "@/lib/api";
import { ACCESS_COOKIE } from "@/lib/cookies";

/** The teacher application (fields + ID document): streams the multipart body straight through to the API,
 * so the document is never held in a Server Action payload. POST applies, PUT resubmits. Excluded from
 * proxy.ts (its matcher skips teach/<x>/upload/). */
async function forward(request: Request, method: "POST" | "PUT"): Promise<Response> {
  const host = request.headers.get("host") ?? "";
  // Same-origin only. The lax session cookie already blocks cross-site posts; this is a second lock.
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== host) {
    return Response.json({ error: { code: "ACCESS_DENIED", message: "Cross-site upload refused." } }, { status: 403 });
  }

  const token = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!token) return Response.json({ error: { code: "UNAUTHORIZED", message: "Please sign in." } }, { status: 401 });
  try {
    const res = await fetch(`${API_URL}/api/v1/me/teacher-application`, {
      method,
      headers: {
        "content-type": request.headers.get("content-type") ?? "",
        "x-forwarded-host": host,
        authorization: `Bearer ${token}`,
      },
      body: request.body,
      // Required by Node's fetch to stream a request body.
      duplex: "half",
    } as RequestInit & { duplex: "half" });
    return new Response(res.body, { status: res.status, headers: { "content-type": "application/json" } });
  } catch {
    return Response.json({ error: { code: "API_UNREACHABLE", message: "The server is not reachable." } }, { status: 503 });
  }
}

export function POST(request: Request): Promise<Response> {
  return forward(request, "POST");
}

export function PUT(request: Request): Promise<Response> {
  return forward(request, "PUT");
}
