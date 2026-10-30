"use client";

import { useEffect, useState } from "react";

/** Seconds left until `seconds` from `since` (ms); ticks once a second. For resend cooldowns. */
export function useCountdown(seconds: number | undefined, since: number | undefined): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  if (!seconds || !since) return 0;
  return Math.max(0, Math.ceil((since + seconds * 1000 - now) / 1000));
}
