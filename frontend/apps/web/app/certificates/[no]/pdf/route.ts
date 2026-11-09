import { API_URL, userHost } from "@/lib/api";

/** The certificate's PDF, made by the API (A4 landscape, with a QR code to this site's verify page). Public, like
 * the verify page: the number is random and unguessable. */
export async function GET(_: Request, { params }: { params: Promise<{ no: string }> }): Promise<Response> {
  const { no } = await params;
  if (!/^[A-Za-z0-9-]{1,20}$/.test(no)) return new Response("Not found", { status: 404 });
  const res = await fetch(`${API_URL}/api/v1/market/certificates/${encodeURIComponent(no)}/pdf`, {
    headers: { "x-forwarded-host": await userHost() }, cache: "no-store",
  });
  if (!res.ok) return new Response("Not found", { status: 404 });
  return new Response(res.body, {
    headers: {
      "content-type": "application/pdf",
      "content-disposition": res.headers.get("content-disposition") ?? `inline; filename="${no}.pdf"`,
      "cache-control": "private, max-age=300",
    },
  });
}
