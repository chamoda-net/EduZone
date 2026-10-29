// Display formatting. The API speaks cents and UTC; people see rupees and Colombo time.

const TIME_ZONE = "Asia/Colombo";
const COLOMBO_OFFSET = "+05:30"; // Sri Lanka has no daylight saving time

export function formatMoney(cents: number, currency = "LKR"): string {
  const amount = (cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency === "LKR" ? `Rs. ${amount}` : `${currency} ${amount}`;
}

/** "2,000" / "2000.5" -> 200050. Returns null for anything that isn't a plain amount. */
export function rupeesToCents(input: string): number | null {
  const clean = input.replace(/[,\s]/g, "").replace(/^Rs\.?/i, "");
  const match = /^(\d{1,10})(?:\.(\d{1,2}))?$/.exec(clean);
  if (!match) return null;
  return Number(match[1]) * 100 + Number((match[2] ?? "").padEnd(2, "0"));
}

export function centsToRupeesInput(cents: number | null): string {
  if (cents === null) return "";
  return cents % 100 === 0 ? String(cents / 100) : (cents / 100).toFixed(2);
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE }).format(
    new Date(iso),
  );
}

/** "2026-11-01" -> "November 2026" (a calendar month, so no time zone shift). */
export function formatMonth(monthStart: string): string {
  const [y, m] = monthStart.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" }).format(
    new Date(Date.UTC(y, m - 1, 1)),
  );
}

/** <input type="datetime-local"> value, read as Colombo time -> ISO 8601 with offset. */
export function colomboLocalToIso(value: string): string {
  return `${value.length === 16 ? `${value}:00` : value}${COLOMBO_OFFSET}`;
}

/** ISO timestamp -> "YYYY-MM-DDTHH:mm" in Colombo time, for a datetime-local input. */
export function isoToColomboLocal(iso: string): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: TIME_ZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(new Date(iso))
      .map((p) => [p.type, p.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}
