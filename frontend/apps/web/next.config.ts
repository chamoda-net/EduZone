import type { NextConfig } from "next";

// Every page depends on the request (tenant host, session cookie), so pages render
// per request; Cache Components is left off until something benefits from it.
const nextConfig: NextConfig = {
  // The Playwright suite runs its own dev server beside the usual one (e2e/playwright.config.ts).
  distDir: process.env.NEXT_DIST_DIR || ".next",
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
