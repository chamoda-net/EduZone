"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

type GoogleId = {
  initialize: (options: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: "popup" }) => void;
  renderButton: (el: HTMLElement, options: Record<string, unknown>) => void;
};

declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } };
  }
}

/** "Continue with Google" via Google Identity Services. Renders nothing until a client id is
 * configured (NEXT_PUBLIC_GOOGLE_CLIENT_ID). The ID token goes to our server, never stored here. */
export function GoogleButton({ onCredential, text = "continue_with" }: {
  onCredential: (credential: string) => void;
  text?: "continue_with" | "signup_with" | "signin_with";
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const handler = useRef(onCredential);
  useEffect(() => {
    handler.current = onCredential;
  }, [onCredential]);

  useEffect(() => {
    if (!ready || !CLIENT_ID || !ref.current || !window.google) return;
    window.google.accounts.id.initialize({
      client_id: CLIENT_ID,
      callback: (r) => handler.current(r.credential),
      ux_mode: "popup",
    });
    window.google.accounts.id.renderButton(ref.current, {
      theme: "outline", size: "large", shape: "rectangular", text, width: ref.current.offsetWidth || 320,
    });
  }, [ready, text]);

  if (!CLIENT_ID) return null;
  return (
    <>
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onReady={() => setReady(true)} />
      <div ref={ref} className="flex min-h-11 w-full justify-center" />
    </>
  );
}

export const googleEnabled = Boolean(CLIENT_ID);
