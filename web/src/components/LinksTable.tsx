import { useQuery } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type SortingState } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { money, pct } from "../lib/format";
import { useUI } from "../lib/store";
import { ItemDrawer } from "./ItemDrawer";
import { StatusChip } from "./ui";

const col = createColumnHelper<any>();
const FILTERS = [["", "All"], ["auto,evidence,human", "Linked"], ["review", "Needs review"], ["refused", "Refused"], ["nomatch,notbom", "No match"]];

export function LinksTable({ pid, currency }: { pid: number; currency: string }) {
  const [status, setStatus] = useState("");
  const search = useUI((s) => s.linkSearch);
  const setSearch = useUI((s) => s.setLinkSearch);
  const [sorting, setSorting] = useState<SortingState>([{ id: "spend_cents", desc: true }]);
  const [open, setOpen] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["links", pid, status], queryFn: () => api<any[]>(`/projects/${pid}/links${status ? `?status=${status}` : ""}`) });
  const data = useMemo(() => {
    const s = search.toLowerCase();
    return (q.data ?? []).filter((r) => !s || `${r.supplier_name} ${r.description} ${r.supplier_pn ?? ""} ${r.part_id ?? ""} ${r.suggestion_part_id ?? ""}`.toLowerCase().includes(s));
  }, [q.data, search]);
  const columns = useMemo(() => [
    col.accessor("supplier_name", { header: "Supplier", size: 150 }),
    col.accessor("description", { header: "Purchase description", size: 300, cell: (c) => <span title={c.row.original.supplier_pn ?? ""}>{c.getValue()}</span> }),
    col.accessor("spend_cents", { header: `Spend`, size: 110, cell: (c) => <span className="tabnum">{money(c.getValue(), currency)}</span> }),
    col.accessor("status", { header: "Status", size: 200, cell: (c) => <StatusChip status={c.getValue()} /> }),
    col.accessor((r) => r.part_id ?? r.suggestion_part_id, { id: "part", header: "Part", size: 220, cell: (c) => <span>{c.getValue() ? <><strong>{c.getValue()}</strong> <span className="text-muted">{c.row.original.part_description}</span>{!c.row.original.part_id && <span className="text-muted"> (suggested)</span>}</> : "–"}</span> }),
    col.accessor("rung_label", { header: "Step", size: 140 }),
    col.accessor("confidence", { header: "Conf.", size: 70, cell: (c) => <span className="tabnum">{c.getValue() ? pct(c.getValue(), 0) : "–"}</span> }),
  ], [currency]);
  const table = useReactTable({ data, columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  const rows = table.getRowModel().rows;
  const ref = useRef<HTMLDivElement>(null);
  const v = useVirtualizer({ count: rows.length, getScrollElement: () => ref.current, estimateSize: () => 48, overscan: 12 });
  const tmpl = columns.map((c) => `${c.size}px`).join(" ");
  return (
    <section className="card flex flex-col gap-4 p-6" aria-label="All links">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-base font-semibold">All spend items and their links</h2>
        <div className="flex flex-wrap items-center gap-2">
          <input className="input w-56" placeholder="Search supplier, text, part…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search links" />
          <div role="tablist" className="flex gap-1">
            {FILTERS.map(([k, l]) => (
              <button key={l} role="tab" aria-selected={status === k} type="button" onClick={() => setStatus(k)} className={status === k ? "btn-primary px-3 py-1.5" : "btn-ghost px-3 py-1.5"}>{l}</button>
            ))}
          </div>
        </div>
      </div>
      <div className="overflow-x-auto rounded-xl border border-line">
        <div style={{ minWidth: columns.reduce((a, c) => a + (c.size ?? 100), 0) }}>
          <div className="grid gap-0 border-b border-line bg-soft text-xs font-semibold text-muted" style={{ gridTemplateColumns: tmpl }} role="row">
            {table.getHeaderGroups()[0].headers.map((h) => (
              <button key={h.id} type="button" className="px-3 py-2 text-left" onClick={h.column.getToggleSortingHandler()}>
                {flexRender(h.column.columnDef.header, h.getContext())}{{ asc: " ↑", desc: " ↓" }[h.column.getIsSorted() as string] ?? ""}
              </button>
            ))}
          </div>
          <div ref={ref} className="max-h-[520px] overflow-auto">
            <div style={{ height: v.getTotalSize(), position: "relative" }}>
              {v.getVirtualItems().map((vi) => {
                const r = rows[vi.index];
                return (
                  <button type="button" key={r.id} onClick={() => setOpen(r.original.item_id)} className="absolute left-0 right-0 grid items-center border-b border-line text-left text-sm hover:bg-soft" style={{ gridTemplateColumns: tmpl, transform: `translateY(${vi.start}px)`, height: 48 }}>
                    {r.getVisibleCells().map((c) => <div key={c.id} className="truncate px-3">{flexRender(c.column.columnDef.cell, c.getContext())}</div>)}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
      <div className="text-xs text-muted">{data.length} items. Click a row for its evidence and lines.</div>
      <ItemDrawer pid={pid} itemId={open} onClose={() => setOpen(null)} />
    </section>
  );
}
