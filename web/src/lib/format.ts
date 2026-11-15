export function money(cents: number | null | undefined, currency = "USD", opts: { decimals?: number; sign?: boolean } = {}): string {
  if (cents === null || cents === undefined || Number.isNaN(cents)) return "–";
  const v = cents / 100;
  return amount(v, currency, { decimals: opts.decimals ?? (Math.abs(v) >= 1000 ? 0 : 2), sign: opts.sign });
}

export function amount(v: number | null | undefined, currency = "USD", opts: { decimals?: number; sign?: boolean } = {}): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const decimals = opts.decimals ?? (v === 0 || Math.abs(v) >= 10 ? (Math.abs(v) >= 1000 ? 0 : 2) : Math.abs(v) >= 0.1 ? 2 : 4);
  let s: string;
  try {
    s = new Intl.NumberFormat(undefined, { style: "currency", currency, minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(Math.abs(v));
  } catch {
    s = `${currency} ${Math.abs(v).toFixed(decimals)}`;
  }
  const neg = v < 0 ? "−" : opts.sign && v > 0 ? "+" : "";
  return neg + s;
}

export function num(v: number | null | undefined, decimals = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: decimals, minimumFractionDigits: 0 }).format(v);
}

export function pct(v: number | null | undefined, decimals = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${(v * 100).toFixed(decimals)}%`;
}

export function plural(n: number, one: string, many?: string) {
  return `${num(n)} ${n === 1 ? one : many ?? one + "s"}`;
}
