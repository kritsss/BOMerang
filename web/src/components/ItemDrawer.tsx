import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { money, num } from "../lib/format";
import { Drawer } from "./Drawer";
import { AINote, AttributeChips, EvidencePanel } from "./Evidence";
import { StatusChip } from "./ui";

export function ItemDrawer({ pid, itemId, onClose }: { pid: number; itemId: string | null; onClose: () => void }) {
  const q = useQuery({ queryKey: ["item", pid, itemId], enabled: !!itemId, queryFn: () => api(`/projects/${pid}/items/${itemId}`) });
  const d = q.data;
  const it = d?.item;
  const cand = it?.evidence?.candidates?.find((c: any) => c.part_id === (it.part_id || it.suggestion_part_id));
  return (
    <Drawer open={!!itemId} onClose={onClose} title={it ? it.description : "Item"} width="max-w-[1000px]">
      {!d ? (
        <div className="text-muted">Loading…</div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-3">
            <StatusChip status={it.status} />
            <span className="text-sm text-muted">{it.supplier_name}{it.supplier_pn ? ` · ${it.supplier_pn}` : ""} · {num(it.n_lines)} line(s) · {money(it.spend_cents, d.currency)}</span>
          </div>
          <div className="rounded-xl bg-soft px-4 py-3 text-sm"><strong>Why: </strong>{it.reason}</div>
          {d.main_part && (
            <div className="text-sm"><span className="label">Part</span> <strong>{d.main_part.part_id}</strong> · {d.main_part.description}</div>
          )}
          {cand && <AttributeChips attrs={cand.attrs} />}
          <AINote ai={it.evidence?.ai} />
          <EvidencePanel item={it} currency={d.currency} />
          {it.evidence?.refused?.length > 0 && (
            <div className="rounded-xl border border-cost-line bg-cost-bg p-4 text-sm">
              <div className="mb-2 font-semibold text-cost">Refused for this item</div>
              {it.evidence.refused.map((r: any) => {
                const diff = r.attrs.filter((a: any) => a.hard && a.result === "differ");
                return <div key={r.part_id}><strong>{r.part_id}</strong>: {diff.map((a: any) => `${a.attr} ${a.why}`).join("; ")}</div>;
              })}
            </div>
          )}
          <details className="rounded-xl border border-line p-4">
            <summary className="cursor-pointer text-sm font-semibold">Lines behind this item ({d.lines.length})</summary>
            <table className="mt-3 w-full text-sm">
              <tbody>
                {d.lines.map((l: any) => (
                  <tr key={l.line_id} className="border-t border-line">
                    <td className="py-1.5 pr-3">{l.line_id}</td>
                    <td className="py-1.5 pr-3">{l.description}</td>
                    <td className="py-1.5 pr-3 text-right tabnum">{num(l.qty, 2)} {l.purchase_uom}</td>
                    <td className="py-1.5 pr-3">{l.month}</td>
                    <td className="py-1.5 pr-3">{l.is_service ? "service" : ""}</td>
                    <td className="py-1.5 text-right tabnum">{money(l.cents, d.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </div>
      )}
    </Drawer>
  );
}
