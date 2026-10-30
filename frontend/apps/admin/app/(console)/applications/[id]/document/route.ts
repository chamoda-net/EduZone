import { cookies } from "next/headers";

import { API_URL } from "@/lib/api";
import { ACCESS_COOKIE } from "@/lib/cookies";

/** The applicant's document, streamed from the API (which checks the admin session and audits the read).
 * Never cached. */
export async function GET(_: Request, { params }: RouteContext<"/applications/[id]/document">): Promise<Response> {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) return new Response("Not found", { status: 404 });
  const token = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!token) return new Response("Please sign in", { status: 401 });
  try {
    const res = await fetch(`${API_URL}/api/v1/platform/applications/${id}/document`, {
      headers: { authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return new Response("Not available", { status: res.status });
    const headers = new Headers({ "cache-control": "no-store", "x-content-type-options": "nosniff" });
    for (const h of ["content-type", "content-disposition"]) {
      const v = res.headers.get(h);
      if (v) headers.set(h, v);
    }
    return new Response(res.body, { status: 200, headers });
  } catch {
    return new Response("The server is not reachable", { status: 503 });
  }
}
