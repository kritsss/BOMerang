export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = opts;
  const init: RequestInit = { ...rest };
  if (json !== undefined) {
    init.body = JSON.stringify(json);
    init.headers = { "Content-Type": "application/json", ...(rest.headers || {}) };
    init.method = init.method || "POST";
  }
  const r = await fetch(`/api${path}`, init);
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(r.status, msg);
  }
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("application/json")) return r.json();
  return (await r.blob()) as unknown as T;
}

export async function download(path: string, body: unknown, fallbackName: string) {
  const r = await fetch(`/api${path}`, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new ApiError(r.status, (await r.text()) || r.statusText);
  const blob = await r.blob();
  const cd = r.headers.get("content-disposition") || "";
  const m = cd.match(/filename="?([^"]+)"?/);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = m ? m[1] : fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export type Project = { id: number; name: string; display_currency: string; fx_overrides: Record<string, number>; has_run: boolean; last_run_id: number | null; active_spend_upload_id: number | null };
export type Run = { id: number; kind: string; status: string; progress: number; message: string; error: string; rule_version: number; summary: Summary };
export type LedgerClass = { key: string; label: string; group: string; cents: number };
export type Summary = {
  ladder: Record<string, number>;
  ledger: { classes: LedgerClass[]; total_cents: number; ledger_cents: number; difference_cents: number; groups: Record<string, number>; allocated_cents: number; explained_share: number };
  items: number; auto: number; review: number; refused: number; human: number; waiting_cents: number; has_volumes: boolean; ai_used: boolean;
  display_currency: string; headline: string; subline: string; timing_on: boolean; rule_version?: number;
};
export type Receipt = { kind: string; key?: string; product?: string; supplier?: string; title?: string };
