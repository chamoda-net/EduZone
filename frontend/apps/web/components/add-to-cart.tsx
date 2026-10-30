"use client";

import { Check, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { addToCart } from "@/app/cart/actions";
import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, buttonStyles, cx, toast } from "@eduzone/ui";

/** Adds a month (or a one-time class) to the cart, for guests too; then offers the way to the cart. */
export function AddToCartButton({ classId, monthId, label, inCart = false, small = false, block = false }: {
  classId: string;
  monthId: string | null;
  label?: string;
  inCart?: boolean;
  small?: boolean;
  block?: boolean;
}) {
  const t = useT();
  const router = useRouter();
  const [pending, start] = useTransition();
  const [added, setAdded] = useState(inCart);
  const [error, setError] = useState<string | null>(null);

  if (added) {
    return (
      <Link href="/cart" className={buttonStyles("secondary", small ? "sm" : block ? "lg" : "md", cx(block && "w-full"))}>
        <Check className="size-4 text-success" />
        {small ? t("cart.inCart") : t("cart.view")}
      </Link>
    );
  }

  function add() {
    setError(null);
    start(async () => {
      const res = await addToCart(classId, monthId);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setAdded(true);
      toast(t("cart.added"));
      router.refresh();
    });
  }

  return (
    <div className={cx("flex flex-col gap-2", block ? "w-full" : "items-end")}>
      <Button
        type="button"
        variant="outline"
        onClick={add}
        loading={pending}
        size={small ? "sm" : block ? "lg" : "md"}
        icon={<ShoppingCart className="size-4" />}
        className={block ? "w-full" : undefined}
      >
        {label ?? t("cart.add")}
      </Button>
      {error && <ErrorText>{error}</ErrorText>}
    </div>
  );
}
