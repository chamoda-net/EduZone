import type { NextConfig } from "next";

// Private network only; renders per request (session cookies).
const nextConfig: NextConfig = {
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
