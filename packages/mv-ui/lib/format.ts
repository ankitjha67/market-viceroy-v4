/** Display formatting only. Money arrives as Decimal strings from the API; we
 * parse to a number for *display* (never for accounting) and format per currency. */

export function formatMoney(value: string, currency = "USD"): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return new Intl.NumberFormat("en-US", {
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

export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().replace("T", " ").replace("Z", " UTC").slice(0, 23);
}
