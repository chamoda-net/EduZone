"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getCheckoutStatus } from "@/app/cart/actions";
import { useT } from "@eduzone/lib/i18n/client";

const EVERY_MS = 2000;
const GIVE_UP_MS = 90_000;

/** Asks for the checkout's status until the gateway's notification has been processed, then re-renders the
 * page. Polling only reads: it never changes anything. */
export function CheckoutPoller({ checkoutId }: { checkoutId: string }) {
  const t = useT();
  const router = useRouter();
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    const started = Date.now();
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      if (stopped) return;
      const status = await getCheckoutStatus(checkoutId);
      if (status && status !== "pending") {
        router.refresh();
        return;
      }
      if (Date.now() - started > GIVE_UP_MS) {
        setGaveUp(true);
        return;
      }
      timer = setTimeout(tick, EVERY_MS);
    };
    timer = setTimeout(tick, EVERY_MS);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [checkoutId, router]);

  return gaveUp ? <p className="text-sm text-muted">{t("checkout.stillWaiting")}</p> : null;
}
