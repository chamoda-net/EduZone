import { pexels, type Photo as PhotoData } from "@/lib/photos";
import { cx } from "@eduzone/ui";

/** A stock photo at the right size for the screen: Pexels resizes and crops to `ratio` (height / width). */
export function Photo({ photo, ratio, sizes, className, priority = false, alt }: {
  photo: PhotoData;
  ratio: number;
  sizes: string;
  className?: string;
  priority?: boolean;
  alt?: string;
}) {
  const widths = [400, 640, 900, 1280, 1700];
  const srcSet = widths.map((w) => `${pexels(photo.src, w, Math.round(w * ratio))} ${w}w`).join(", ");
  return (
    // eslint-disable-next-line @next/next/no-img-element -- Pexels' CDN does the resizing; next/image would fetch twice
    <img
      src={pexels(photo.src, 900, Math.round(900 * ratio))}
      srcSet={srcSet}
      sizes={sizes}
      alt={alt ?? photo.alt}
      width={900}
      height={Math.round(900 * ratio)}
      loading={priority ? "eager" : "lazy"}
      fetchPriority={priority ? "high" : undefined}
      decoding="async"
      className={cx("block h-auto w-full object-cover", className)}
    />
  );
}
