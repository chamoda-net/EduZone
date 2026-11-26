import type { MetadataRoute } from "next";

/** Lets phones add EduZone to the home screen with the app icon (files from docs/brand/logo/web-icons). */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "EduZone",
    short_name: "EduZone",
    start_url: "/",
    display: "standalone",
    theme_color: "#0e3a28",
    background_color: "#faf8f3",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icon-maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
