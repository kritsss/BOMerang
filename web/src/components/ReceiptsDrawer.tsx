import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";
import { api } from "../lib/api";
import { amount, money, num } from "../lib/format";
import { useProject } from "../lib/hooks";
import { useUI } from "../lib/store";
import { Drawer } from "./Drawer";
import { ErrorNote } from "./ui";

export function ReceiptsDrawer() {
  const r = useUI((s) => s.receipt);
  const close = useUI((s) => s.closeReceipt);
  const { pid } = useProject();
  const q = useQuery({
    queryKey: ["receipt", pid, r],
    enabled: !!pid && !!r && r.kind !== "formula",
    queryFn: () => {
      const p = new URLSearchParams({ kind: r!.kind, key: r!.key ?? "" });
      if (r!.product) p.set("product", r!.product);
      if (r!.supplier) p.set("supplier", r!.supplier);
      return api(`/projects/${pid}/receipts?${p}`);
    },
  });
  const d = q.data;
  return (
    <Drawer open={!!r} onClose={close} title={r?.title ?? d?.title ?? "Receipts"} width="max-w-[980px]">
      {r?.kind === "formula" ? (
        <FormulaOnly r={r as any} />
      ) : q.isLoading ? (
        <div className="text-muted">Loading the lines…</div>
      ) : q.error ? (
        <ErrorNote error={q.error} />
      ) : d ? (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-baseline gap-6">
            <div>
              <div className="label">Total</div>
              <div className="font-display text-3xl font-bold tabnum">{money(d.total_cents, d.currency)}</div>
            </div>
            <div>
              <div className="label">Lines</div>
              <div className="font-display text-3xl font-bold tabnum">{num(d.count)}</div>
            </div>
          </div>
          <div className="rounded-xl bg-soft px-4 py-3 text-sm leading-relaxed">
            <span className="font-semibold">How it is counted: </span>
            {d.formula}
          </div>
          <LineTable lines={d.lines} currency={d.currency} />
          {d.truncated && <div className="text-sm text-muted">Showing the {d.lines.length} largest lines. The full list is in the Excel export.</div>}
        </div>
      ) : null}
    </Drawer>
  );
}

function FormulaOnly({ r }: { r: { formula: string; inputs?: [string, string][] } }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-xl bg-soft px-4 py-3 font-mono text-sm">{r.formula}</div>
      {r.inputs && (
        <table className="text-sm">
          <tbody>
            {r.inputs.map(([k, v]) => (
              <tr key={k} className="border-b border-line">
                <td className="py-2 pr-6 text-muted">{k}</td>
                <td className="py-2 tabnum">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const COLS: [string, string, string][] = [
  ["line_id", "Line", "w-[90px]"],
  ["supplier_name", "Supplier", "w-[150px]"],
  ["description", "Description", "flex-1 min-w-[180px]"],
  ["qty", "Qty", "w-[80px] text-right"],
  ["purchase_uom", "Unit", "w-[56px]"],
  ["unit_price", "Price", "w-[90px] text-right"],
  ["counted_cents", "Counted", "w-[110px] text-right"],
];

export function LineTable({ lines, currency }: { lines: any[]; currency: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const v = useVirtualizer({ count: lines.length, getScrollElement: () => ref.current, estimateSize: () => 52, overscan: 10 });
  return (
    <div className="rounded-xl border border-line">
      <div className="flex gap-3 border-b border-line bg-soft px-3 py-2 text-xs font-semibold text-muted" role="row">
        {COLS.map(([k, l, c]) => (
          <div key={k} className={c} role="columnheader">
            {l}
          </div>
        ))}
      </div>
      <div ref={ref} className="max-h-[60vh] overflow-auto" role="table" aria-label="Lines behind this number">
        <div style={{ height: v.getTotalSize(), position: "relative" }}>
          {v.getVirtualItems().map((vi) => {
            const l = lines[vi.index];
            return (
              <div key={vi.key} role="row" className="absolute left-0 right-0 flex gap-3 border-b border-line px-3 py-2 text-sm" style={{ transform: `translateY(${vi.start}px)` }} title={l.reason || ""}>
                <div className={COLS[0][2]}>{l.line_id}</div>
                <div className={`${COLS[1][2]} truncate`}>{l.supplier_name}</div>
                <div className={`${COLS[2][2]} truncate`}>
                  {l.description}
                  {l.reason && <div className="truncate text-xs text-muted">{l.reason}</div>}
                </div>
                <div className={`${COLS[3][2]} tabnum`}>{num(l.qty, 2)}</div>
                <div className={COLS[4][2]}>{l.purchase_uom}</div>
                <div className={`${COLS[5][2]} tabnum`}>
                {l.unit_price != null && l.fx_rate != null ? amount(l.unit_price * l.fx_rate, currency) : "–"}
                {l.currency && l.currency !== currency && l.unit_price != null && (
                  <div className="text-xs text-muted">{num(l.unit_price, 4)} {l.currency}</div>
                )}
              </div>
                <div className={`${COLS[6][2]} tabnum font-semibold`}>{money(l.counted_cents, currency)}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
