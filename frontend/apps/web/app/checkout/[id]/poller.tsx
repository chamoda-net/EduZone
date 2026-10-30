"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useT } from "@eduzone/lib/i18n/client";

import { getOrderStatus } from "@/app/learn/actions";

const EVERY_MS = 2000;
const GIVE_UP_MS = 90_000;

/** Asks for the order's status until the gateway's notification has been processed, then
 * re-renders the page. Polling only reads: it never changes the order. */
export function OrderPoller({ orderId }: { orderId: string }) {
  const t = useT();
  const router = useRouter();
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    const started = Date.now();
    let stopped = false;
    const tick = async () => {
      if (stopped) return;
      const status = await getOrderStatus(orderId);
      if (status && status !== "pending") {
        router.refresh();
        return;
      }
      if (Date.now() - started > GIVE_UP_MS) {
        setGaveUp(true);
        return;
      }
      setTimeout(tick, EVERY_MS);
    };
    const first = setTimeout(tick, EVERY_MS);
    return () => {
      stopped = true;
      clearTimeout(first);
    };
  }, [orderId, router]);

  return gaveUp ? <p className="text-sm text-muted">{t("checkout.stillWaiting")}</p> : null;
}
