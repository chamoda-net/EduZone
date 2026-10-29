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
