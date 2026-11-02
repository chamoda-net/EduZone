import path from "node:path";

import type { NextConfig } from "next";

// Private network only; renders per request (session cookies).
// NEXT_OUTPUT=standalone (set by apps/admin/Dockerfile) builds a self-contained server for its own deploy;
// the trace root is the monorepo so the workspace packages are included.
const standalone = process.env.NEXT_OUTPUT === "standalone";

const nextConfig: NextConfig = {
  ...(standalone ? { output: "standalone" as const, outputFileTracingRoot: path.join(__dirname, "../..") } : {}),
  poweredByHeader: false,
  // Never indexed, never framed, never leaks its address in a Referer.
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Robots-Tag", value: "noindex, nofollow" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Content-Type-Options", value: "nosniff" },
      ],
    }];
  },
  transpilePackages: ["@eduzone/ui", "@eduzone/lib", "@eduzone/api-client"],
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
