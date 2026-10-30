import { Avatar, cx } from "@eduzone/ui";

/** The teacher's photo when they've added one, else their initials. */
export function TeacherAvatar({ name, photo, size = "md", className }: {
  name: string;
  photo: string | null;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}) {
  if (size === "xl") {
    return photo ? (
      // eslint-disable-next-line @next/next/no-img-element -- teacher photos come from our CDN at any size
      <img src={photo} alt="" className={cx("size-28 rounded-full object-cover ring-4 ring-surface shadow-ez-lg", className)} />
    ) : (
      <Avatar name={name} size="lg" className={cx("size-28! text-3xl ring-4 shadow-ez-lg", className)} />
    );
  }
  if (!photo) return <Avatar name={name} size={size} className={className} />;
  const dims = { sm: "size-8", md: "size-10", lg: "size-14" }[size];
  // eslint-disable-next-line @next/next/no-img-element -- teacher photos come from our CDN at any size
  return <img src={photo} alt="" className={cx("shrink-0 rounded-full object-cover ring-2 ring-surface", dims, className)} />;
}
