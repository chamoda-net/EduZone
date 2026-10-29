import type { NextConfig } from "next";

// Every page depends on the request (tenant host, session cookie), so pages render
// per request; Cache Components is left off until something benefits from it.
const nextConfig: NextConfig = {
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
