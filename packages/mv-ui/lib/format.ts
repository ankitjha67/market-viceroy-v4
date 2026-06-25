/** Display formatting only. Money arrives as Decimal strings from the API; we
 * parse to a number for *display* (never for accounting) and format per currency. */

export function formatMoney(value: string, currency = "INR"): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  const locale = currency === "INR" ? "en-IN" : "en-US";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(n);
}

export function formatPct(value: string | number, digits = 2): string {
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return String(value);
  return `${(n * 100).toFixed(digits)}%`;
}

export function formatNum(value: string | number, digits = 4): string {
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return String(value);
  return n.toFixed(digits);
}

/** "pos" / "neg" / "" for sign-aware colouring of a numeric string. */
export function signClass(value: string | number): "pos" | "neg" | "" {
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n) || n === 0) return "";
  return n > 0 ? "pos" : "neg";
}

/** Format a UTC ISO timestamp in the viewer's *local* timezone (e.g. IST), not
 * UTC. The backend stores UTC (correct); only the display localizes. The short
 * zone name is appended so a single timestamp is self-describing. */
export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
    timeZoneName: "short",
  }).formatToParts(d);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const zone = get("timeZoneName");
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")}:${get("second")}${zone ? ` ${zone}` : ""}`;
}
