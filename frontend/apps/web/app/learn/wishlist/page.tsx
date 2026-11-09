import { Heart } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { AddToCartButton } from "@/components/add-to-cart";
import { CourseCard } from "@/components/course-card";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getCart, inCart } from "@/lib/cart";
import { getMe } from "@/lib/session";
import { errorText, t } from "@eduzone/lib/i18n";
import { EmptyState, ErrorText, PageHeader, buttonStyles } from "@eduzone/ui";

export const metadata: Metadata = { title: "Wishlist | EduZone", robots: { index: false } };

/** /learn/wishlist: courses saved for later, newest first, each a tap away from the cart. */
export default async function WishlistPage() {
  if (!(await getMe())) redirect("/login?next=/learn/wishlist");
  const [res, cart] = await Promise.all([api<Schema<"MarketCourse">[]>("/me/wishlist"), getCart()]);
  return (
    <SiteShell>
      <PageHeader eyebrow={t("learn.eyebrow")} title={t("wishlist.title")} description={t("wishlist.lead")}
                  actions={<Link href="/learn/courses" className={buttonStyles("secondary")}>{t("nav.myCourses")}</Link>} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && (
        <EmptyState icon={<Heart />} title={t("wishlist.empty")} body={t("wishlist.emptyBody")}
                    action={<Link href="/courses" className={buttonStyles("primary")}>{t("learnCourses.browse")}</Link>} />
      )}
      {res.ok && res.data.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {res.data.map((c, i) => (
            <div key={c.id} className="flex flex-col gap-2.5">
              <CourseCard c={c} index={i} saved />
              {c.pricing_model === "one_time" && (
                <AddToCartButton block classId={c.id} monthId={null} inCart={inCart(cart, c.id, null)} />
              )}
            </div>
          ))}
        </div>
      )}
    </SiteShell>
  );
}
