"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Upload } from "tus-js-client";

import { ErrorText, buttonClass } from "@eduzone/ui";
import type { MessageKey } from "@eduzone/lib/i18n";
import { useT } from "@eduzone/lib/i18n/client";

import { startVideoUpload } from "./actions";

type Status = { kind: "idle" } | { kind: "uploading"; percent: number } | { kind: "done" } | { kind: "error"; message: string };

function Progress({ percent }: { percent: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-border" role="progressbar" aria-valuenow={percent}>
      <div className="h-full bg-brand transition-[width]" style={{ width: `${percent}%` }} />
    </div>
  );
}

export function VideoUploader() {
  const t = useT();
  const router = useRouter();
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const uploadRef = useRef<Upload | null>(null);

  useEffect(() => () => void uploadRef.current?.abort(), []);

  async function onFile(file: File) {
    setStatus({ kind: "uploading", percent: 0 });
    const started = await startVideoUpload({ name: file.name, size: file.size, type: file.type });
    if (!started.ok) {
      setStatus({ kind: "error", message: started.error });
      return;
    }
    const { endpoint, headers } = started.upload.upload;
    const upload = new Upload(file, {
      endpoint,
      headers,
      metadata: { filetype: file.type, title: file.name },
      retryDelays: [0, 3000, 5000, 10000, 20000, 60000], // mobile data drops out; keep trying
      onProgress: (sent, total) => setStatus({ kind: "uploading", percent: Math.floor((sent / total) * 100) }),
      onError: () => setStatus({ kind: "error", message: t("media.uploadFailed") }),
      onSuccess: () => {
        setStatus({ kind: "done" });
        router.refresh();
      },
    });
    uploadRef.current = upload;
    upload.start();
  }

  const busy = status.kind === "uploading";
  return (
    <div className="flex flex-col gap-2">
      <p className="font-medium">{t("media.uploadVideo")}</p>
      <p className="text-xs text-muted">{t("media.uploadVideoHint")}</p>
      <label className={`${buttonClass.secondary} self-start ${busy ? "pointer-events-none opacity-50" : "cursor-pointer"}`}>
        {t("media.chooseFile")}
        <input
          type="file"
          accept="video/*"
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void onFile(file);
          }}
        />
      </label>
      {status.kind === "uploading" && (
        <>
          <Progress percent={status.percent} />
          <p className="text-sm text-muted">{t("media.uploading", { percent: status.percent })}</p>
        </>
      )}
      {status.kind === "done" && <p className="text-sm text-success">{t("media.uploaded")}</p>}
      {status.kind === "error" && <ErrorText>{status.message}</ErrorText>}
    </div>
  );
}

export function PdfUploader() {
  const t = useT();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onFile(file: File) {
    setBusy(true);
    setError(null);
    const body = new FormData();
    body.append("file", file);
    try {
      const res = await fetch("/api/upload/document", { method: "POST", body });
      if (!res.ok) {
        const json = (await res.json().catch(() => null)) as { error?: { code: string; message: string } } | null;
        // Known codes get our own wording (t returns the key itself when there is none).
        const key = `errors.${json?.error?.code}` as MessageKey;
        const ours = t(key);
        setError(ours !== key ? ours : json?.error?.message || t("errors.generic"));
      } else {
        router.refresh();
      }
    } catch {
      setError(t("errors.API_UNREACHABLE"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="font-medium">{t("media.uploadPdf")}</p>
      <p className="text-xs text-muted">{t("media.uploadPdfHint")}</p>
      <label className={`${buttonClass.secondary} self-start ${busy ? "pointer-events-none opacity-50" : "cursor-pointer"}`}>
        {busy ? t("common.saving") : t("media.chooseFile")}
        <input
          type="file"
          accept="application/pdf"
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void onFile(file);
          }}
        />
      </label>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

/** Re-renders the page every few seconds while videos are still uploading or processing. */
export function AutoRefresh({ active, seconds = 8 }: { active: boolean; seconds?: number }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => router.refresh(), seconds * 1000);
    return () => clearInterval(id);
  }, [active, seconds, router]);
  return null;
}
