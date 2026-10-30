"use client";

import { CreditCard, LogIn, Smartphone } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { goToGateway } from "@/components/pay-button";
import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, buttonStyles } from "@eduzone/ui";

import { startCartCheckout } from "./actions";

/** Guests sign in first (their cart comes along); paying needs a verified phone; then one gateway payment. */
export function CheckoutButton({ state, label }: { state: "guest" | "verify" | "ready" | "blocked"; label: string }) {
  const t = useT();
  const router = useRouter();
  const [pending, start] = useTransition();
  const [leaving, setLeaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (state === "guest") {
    return (
      <Link href="/login?next=/cart" className={buttonStyles("primary", "lg", "w-full")}>
        <LogIn className="size-4.5" />
        {t("cart.signInToPay")}
      </Link>
    );
  }
  if (state === "verify") {
    return (
      <Link href="/verify-phone?next=/cart" className={buttonStyles("primary", "lg", "w-full")}>
        <Smartphone className="size-4.5" />
        {t("phone.bannerAction")}
      </Link>
    );
  }

  function pay() {
    setError(null);
    start(async () => {
      const res = await startCartCheckout();
      if (!res.ok) {
        if (res.code === "PHONE_NOT_VERIFIED") return router.push("/verify-phone?next=/cart");
        setError(res.error);
        router.refresh(); // show what changed in the cart
        return;
      }
      setLeaving(true);
      goToGateway(res.redirect);
    });
  }

  const busy = pending || leaving;
  return (
    <div className="flex flex-col gap-2">
      <Button type="button" size="lg" className="w-full" onClick={pay} loading={busy} disabled={state === "blocked"}
              icon={<CreditCard className="size-4.5" />}>
        {busy ? t("pay.redirecting") : label}
      </Button>
      {error && <ErrorText>{error}</ErrorText>}
    </div>
  );
}
