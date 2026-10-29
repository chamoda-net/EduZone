import type { Media, MediaStatus } from "@eduzone/lib/types";

/** Badge colours for media status (reuses the class status palette). */
export const mediaTone: Record<MediaStatus, string> = {
  ready: "published",
  processing: "upcoming",
  uploading: "upcoming",
  failed: "draft",
};

export function isPending(m: Pick<Media, "status">): boolean {
  return m.status === "uploading" || m.status === "processing";
}
