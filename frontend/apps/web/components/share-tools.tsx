"use client";

import { Check, Copy, Download, QrCode } from "lucide-react";
import { useState } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, Dialog, buttonStyles, cx, toast } from "@eduzone/ui";

/** Share a public page: copy the link, send it on WhatsApp, or download a QR code for posters. */
export function ShareTools({ url, message, compact = false }: { url: string; message: string; compact?: boolean }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const path = new URL(url).pathname;
  const qr = `/qr?path=${encodeURIComponent(path)}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast(t("share.copied"));
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast(t("share.copyFailed"), "error");
    }
  }

  return (
    <div className={cx("flex flex-wrap gap-2", compact && "gap-1.5")}>
      <a
        href={`https://wa.me/?text=${encodeURIComponent(`${message} ${url}`)}`}
        target="_blank"
        rel="noopener noreferrer"
        className={buttonStyles("primary", compact ? "sm" : "md")}
      >
        <svg viewBox="0 0 24 24" aria-hidden className="size-4.5 fill-current">
          <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.1l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8s-.4-.1-.6.1-.7.8-.8 1-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.3-.4.7-1.4.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6a2.7 2.7 0 0 0 1.8-1.2 2.2 2.2 0 0 0 .1-1.2c0-.1-.2-.2-.4-.3Z" />
        </svg>
        {t("share.whatsapp")}
      </a>
      <Button type="button" variant="secondary" size={compact ? "sm" : "md"} onClick={copy}
              icon={copied ? <Check className="size-4" /> : <Copy className="size-4" />}>
        {copied ? t("share.copiedShort") : t("share.copy")}
      </Button>
      <Dialog
        title={t("share.qrTitle")}
        description={t("share.qrBody")}
        trigger={
          <Button type="button" variant="secondary" size={compact ? "sm" : "md"} icon={<QrCode className="size-4" />}>
            {t("share.qr")}
          </Button>
        }
      >
        <div className="flex flex-col items-center gap-4">
          {/* eslint-disable-next-line @next/next/no-img-element -- an SVG we generate */}
          <img src={qr} alt={t("share.qrAlt")} className="size-56 rounded-ez border border-border bg-white p-3" />
          <p className="max-w-full truncate text-xs text-muted">{url}</p>
          <a href={`${qr}&download=1`} download className={buttonStyles("primary", "md", "w-full")}>
            <Download className="size-4" />
            {t("share.qrDownload")}
          </a>
        </div>
      </Dialog>
    </div>
  );
}
