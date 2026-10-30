import QRCode from "qrcode";

import { siteOrigin } from "@/lib/site";

/** QR code (SVG) for a page of this site, for posters and tute covers. Only our own paths are
 * encoded, so the endpoint can't be used to make QR codes pointing anywhere else. */
export async function GET(request: Request): Promise<Response> {
  const params = new URL(request.url).searchParams;
  const path = params.get("path") ?? "/";
  if (!path.startsWith("/") || path.startsWith("//") || path.length > 300) {
    return new Response("Bad path", { status: 400 });
  }
  const svg = await QRCode.toString(`${await siteOrigin()}${path}`, {
    type: "svg",
    margin: 1,
    errorCorrectionLevel: "M",
    color: { dark: "#0a2a1dff", light: "#ffffffff" },
  });
  const headers: Record<string, string> = {
    "content-type": "image/svg+xml",
    "cache-control": "public, max-age=86400",
  };
  if (params.get("download")) {
    const name = path.split("/").filter(Boolean).join("-") || "eduzone";
    headers["content-disposition"] = `attachment; filename="${name}-qr.svg"`;
  }
  return new Response(svg, { headers });
}
