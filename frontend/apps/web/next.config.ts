import type { NextConfig } from "next";

// Every page depends on the request (tenant host, session cookie), so pages render
// per request; Cache Components is left off until something benefits from it.
const nextConfig: NextConfig = {
  // The Playwright suite runs its own dev server beside the usual one (e2e/playwright.config.ts).
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Pre-phase-3 URLs: the student area moved under /learn and the console under /teach/<slug>.
  async redirects() {
    return [
      { source: "/my", destination: "/learn/classes", permanent: false },
      { source: "/account", destination: "/learn/profile", permanent: false },
      { source: "/payments", destination: "/learn/payments", permanent: false },
      { source: "/payments/:id", destination: "/learn/payments/:id", permanent: false },
      { source: "/lessons/:id", destination: "/learn/lessons/:id", permanent: false },
      { source: "/org/:path*", destination: "/teach", permanent: false },
    ];
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
